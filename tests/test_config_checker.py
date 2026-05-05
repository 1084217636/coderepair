import json

from validators.config_checker import ConfigChecker


def test_config_checker_finds_delivery_issues(tmp_path):
    config = tmp_path / "heroes.json"
    config.write_text(
        json.dumps(
            {
                "items": [
                    {"id": 1, "name": "Warrior", "hp": 100, "skill_id": 10},
                    {"id": 1, "hp": "120", "skill_id": 999},
                ]
            }
        ),
        encoding="utf-8",
    )

    result = ConfigChecker(required_fields=["id", "name", "hp"]).check_file(config)
    issue_codes = {issue["code"] for issue in result["issues"]}

    assert result["passed"] is False
    assert result["record_count"] == 2
    assert "missing_required_field" in issue_codes
    assert "duplicate_id" in issue_codes
    assert "mixed_field_type" in issue_codes
    assert "broken_reference" in issue_codes


def test_config_checker_accepts_valid_yaml(tmp_path):
    config = tmp_path / "skills.yaml"
    config.write_text(
        """
items:
  - id: 10
    name: Slash
    cooldown: 3
  - id: 11
    name: Fireball
    cooldown: 5
""",
        encoding="utf-8",
    )

    result = ConfigChecker(required_fields=["id", "name"]).check_file(config)

    assert result["passed"] is True
    assert result["error_count"] == 0
    assert result["record_count"] == 2
