"""
Product-shaped CLI wrapper.

`app.py` remains the backwards-compatible entrypoint. This wrapper exposes a
clear `fix` command that maps to the same platform workflow.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import click

from analyzers.test_suggester import GoTestSuggester
from app import CodeRepairPlatform
from core.logger import get_logger
from core.tool_calling import ToolLedger
from validators.config_checker import ConfigChecker


logger = get_logger(__name__)


@click.group()
def cli() -> None:
    """CodeRepair command group."""


@cli.command()
@click.option("--repo", "-r", "workspace", required=True, help="Target repository path")
@click.option("--task", "-t", "query", required=True, help="Natural-language task")
@click.option("--apply-file", default=None, help="Workspace-relative file to write back")
@click.option("--validate", "validate_cmd", default=None, help="Custom validation command")
@click.option(
    "--mode",
    type=click.Choice(["single", "multi"], case_sensitive=False),
    default="single",
    help="Agent mode",
)
@click.option(
    "--validation-mode",
    type=click.Choice(["auto", "local", "docker"], case_sensitive=False),
    default="auto",
    help="Validation execution mode",
)
@click.option("--provider", default=None, help="Override LLM provider")
@click.option("--model", default=None, help="Override LLM model")
@click.option("--temperature", type=float, default=None, help="Override temperature")
@click.option("--no-validate", is_flag=True, default=False, help="Skip validation")
@click.option(
    "--rollback-on-failure/--no-rollback-on-failure",
    default=True,
    help="Rollback when write-back validation fails",
)
def fix(
    workspace: str,
    query: str,
    apply_file: Optional[str],
    validate_cmd: Optional[str],
    mode: str,
    validation_mode: str,
    provider: Optional[str],
    model: Optional[str],
    temperature: Optional[float],
    no_validate: bool,
    rollback_on_failure: bool,
) -> None:
    """Run an AI code repair task and emit delivery artifacts."""
    try:
        platform = CodeRepairPlatform(
            provider=provider,
            model=model,
            temperature=temperature,
        )
        platform.run(
            user_input=query,
            workspace_root=workspace,
            validate=not no_validate,
            apply_file=apply_file,
            mode=mode.lower(),
            validation_mode=validation_mode.lower(),
            validate_cmd=validate_cmd,
            rollback_on_failure=rollback_on_failure,
        )
    except Exception as exc:
        logger.error("CLI fix failed: %s", exc, exc_info=True)
        sys.exit(1)


@cli.command("check-config")
@click.option("--repo", "-r", "workspace", required=True, help="Target repository path")
@click.option("--file", "config_file", required=True, help="Workspace-relative config file")
@click.option(
    "--required",
    default="",
    help="Comma-separated required fields, for example id,name,type",
)
@click.option("--id-field", default="id", help="Unique id field name")
@click.option(
    "--check-references/--no-check-references",
    default=True,
    help="Check *_id and *_ids references against known ids",
)
def check_config(
    workspace: str,
    config_file: str,
    required: str,
    id_field: str,
    check_references: bool,
) -> None:
    """Check JSON/YAML/CSV config before delivery."""
    try:
        ledger = ToolLedger(Path(workspace))
        relative_file = ledger.normalize_workspace_path(config_file)
        required_fields = [field.strip() for field in required.split(",") if field.strip()]
        result = ConfigChecker(
            required_fields=required_fields,
            id_field=id_field,
            check_references=check_references,
        ).check_file(Path(workspace) / relative_file)
        ledger.record(
            "config_check",
            {
                "file": relative_file,
                "required_fields": required_fields,
                "id_field": id_field,
                "check_references": check_references,
            },
            {
                "passed": result["passed"],
                "error_count": result["error_count"],
                "warning_count": result["warning_count"],
                "record_count": result["record_count"],
            },
            status="success" if result["passed"] else "failed",
        )
        click.echo(json.dumps({"result": result, "tool_calls": ledger.to_dict()}, indent=2, ensure_ascii=False))
    except Exception as exc:
        logger.error("config check failed: %s", exc, exc_info=True)
        sys.exit(1)


@cli.command("suggest-tests")
@click.option("--repo", "-r", "workspace", required=True, help="Target Go repository path")
def suggest_tests(workspace: str) -> None:
    """Suggest missing Go unit tests and edge cases."""
    try:
        ledger = ToolLedger(Path(workspace))
        result = GoTestSuggester(workspace).suggest()
        ledger.record(
            "test_suggest",
            {"workspace_root": str(Path(workspace).resolve())},
            {
                "function_count": result["function_count"],
                "missing_test_count": result["missing_test_count"],
                "test_files": result["test_files"],
            },
        )
        click.echo(json.dumps({"result": result, "tool_calls": ledger.to_dict()}, indent=2, ensure_ascii=False))
    except Exception as exc:
        logger.error("test suggestion failed: %s", exc, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
