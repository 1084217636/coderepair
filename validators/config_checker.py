"""
Configuration file checks for game/service delivery workflows.

The checker is intentionally lightweight: it catches common handoff issues in
JSON/YAML/CSV config files without requiring a full schema system.
"""
from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import yaml


@dataclass
class ConfigIssue:
    severity: str
    code: str
    message: str
    location: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ConfigChecker:
    """Check structured config files for delivery-time mistakes."""

    SUPPORTED_SUFFIXES = {".json", ".yaml", ".yml", ".csv"}

    def __init__(
        self,
        required_fields: Optional[Iterable[str]] = None,
        id_field: str = "id",
        check_references: bool = True,
    ):
        self.required_fields = [field for field in (required_fields or []) if field]
        self.id_field = id_field
        self.check_references = check_references

    def check_file(self, file_path: str | Path) -> Dict[str, Any]:
        path = Path(file_path)
        issues: List[ConfigIssue] = []

        if path.suffix.lower() not in self.SUPPORTED_SUFFIXES:
            return self._result(
                path=path,
                file_format="unsupported",
                records=[],
                issues=[
                    ConfigIssue(
                        severity="error",
                        code="unsupported_format",
                        message=f"unsupported config format: {path.suffix}",
                    )
                ],
            )

        try:
            payload = self._load(path)
        except Exception as exc:
            return self._result(
                path=path,
                file_format=path.suffix.lower().lstrip("."),
                records=[],
                issues=[
                    ConfigIssue(
                        severity="error",
                        code="parse_error",
                        message=str(exc),
                    )
                ],
            )

        records = self._normalize_records(payload)
        if not records:
            issues.append(
                ConfigIssue(
                    severity="warning",
                    code="empty_config",
                    message="no records found in config file",
                )
            )

        issues.extend(self._check_required_fields(records))
        issues.extend(self._check_duplicate_ids(records))
        issues.extend(self._check_type_consistency(records))
        if self.check_references:
            issues.extend(self._check_references(records))

        return self._result(
            path=path,
            file_format=path.suffix.lower().lstrip("."),
            records=records,
            issues=issues,
        )

    def _load(self, path: Path) -> Any:
        if path.suffix.lower() == ".json":
            return json.loads(path.read_text(encoding="utf-8"))
        if path.suffix.lower() in {".yaml", ".yml"}:
            return yaml.safe_load(path.read_text(encoding="utf-8"))
        with path.open("r", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))

    def _normalize_records(self, payload: Any) -> List[Dict[str, Any]]:
        if payload is None:
            return []
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            for key in ("items", "records", "data", "configs"):
                value = payload.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
            if all(isinstance(value, dict) for value in payload.values()):
                return [
                    {self.id_field: key, **value}
                    for key, value in payload.items()
                    if isinstance(value, dict)
                ]
            return [payload]
        return []

    def _check_required_fields(self, records: List[Dict[str, Any]]) -> List[ConfigIssue]:
        issues: List[ConfigIssue] = []
        for index, record in enumerate(records, 1):
            for field in self.required_fields:
                value = record.get(field)
                if value is None or value == "":
                    issues.append(
                        ConfigIssue(
                            severity="error",
                            code="missing_required_field",
                            message=f"required field '{field}' is missing",
                            location=f"record[{index}]",
                        )
                    )
        return issues

    def _check_duplicate_ids(self, records: List[Dict[str, Any]]) -> List[ConfigIssue]:
        seen: Dict[str, int] = {}
        issues: List[ConfigIssue] = []
        for index, record in enumerate(records, 1):
            value = record.get(self.id_field)
            if value is None or value == "":
                continue
            key = str(value)
            if key in seen:
                issues.append(
                    ConfigIssue(
                        severity="error",
                        code="duplicate_id",
                        message=f"duplicate {self.id_field} '{key}' also appears in record[{seen[key]}]",
                        location=f"record[{index}]",
                    )
                )
            else:
                seen[key] = index
        return issues

    def _check_type_consistency(self, records: List[Dict[str, Any]]) -> List[ConfigIssue]:
        field_types: Dict[str, set[str]] = {}
        for record in records:
            for field, value in record.items():
                if value is None or value == "":
                    continue
                field_types.setdefault(field, set()).add(type(value).__name__)

        return [
            ConfigIssue(
                severity="warning",
                code="mixed_field_type",
                message=f"field '{field}' has mixed types: {', '.join(sorted(types))}",
                location=field,
            )
            for field, types in sorted(field_types.items())
            if len(types) > 1
        ]

    def _check_references(self, records: List[Dict[str, Any]]) -> List[ConfigIssue]:
        known_ids = {
            str(record[self.id_field])
            for record in records
            if record.get(self.id_field) not in (None, "")
        }
        if not known_ids:
            return []

        issues: List[ConfigIssue] = []
        for index, record in enumerate(records, 1):
            for field, value in record.items():
                if field == self.id_field or not self._looks_like_reference_field(field):
                    continue
                if value in (None, ""):
                    continue
                values = value if isinstance(value, list) else [value]
                for item in values:
                    if str(item) not in known_ids:
                        issues.append(
                            ConfigIssue(
                                severity="error",
                                code="broken_reference",
                                message=f"field '{field}' references missing id '{item}'",
                                location=f"record[{index}]",
                            )
                        )
        return issues

    @staticmethod
    def _looks_like_reference_field(field: str) -> bool:
        lowered = field.lower()
        return lowered.endswith("_id") or lowered.endswith("idref") or lowered.endswith("_ids")

    def _result(
        self,
        *,
        path: Path,
        file_format: str,
        records: List[Dict[str, Any]],
        issues: List[ConfigIssue],
    ) -> Dict[str, Any]:
        errors = [issue for issue in issues if issue.severity == "error"]
        warnings = [issue for issue in issues if issue.severity == "warning"]
        return {
            "file": str(path),
            "format": file_format,
            "record_count": len(records),
            "passed": not errors,
            "error_count": len(errors),
            "warning_count": len(warnings),
            "required_fields": self.required_fields,
            "id_field": self.id_field,
            "issues": [issue.to_dict() for issue in issues],
        }
