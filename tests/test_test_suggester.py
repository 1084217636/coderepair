from analyzers.test_suggester import GoTestSuggester


def test_go_test_suggester_reports_missing_tests(tmp_path):
    (tmp_path / "go.mod").write_text("module github.com/acme/demo\n\ngo 1.21\n", encoding="utf-8")
    (tmp_path / "calc.go").write_text(
        """package main

func Calculate(a int, b int) int {
    return a + b
}

func ValidateName(name string) bool {
    return name != ""
}
""",
        encoding="utf-8",
    )
    (tmp_path / "calc_test.go").write_text(
        """package main

import "testing"

func TestCalculate(t *testing.T) {}
""",
        encoding="utf-8",
    )

    result = GoTestSuggester(tmp_path).suggest()
    suggestions = {item["name"]: item for item in result["suggestions"]}

    assert result["function_count"] == 2
    assert result["missing_test_count"] == 1
    assert suggestions["Calculate"]["has_existing_test"] is True
    assert suggestions["ValidateName"]["has_existing_test"] is False
    assert "missing required field" in suggestions["ValidateName"]["edge_cases"]
