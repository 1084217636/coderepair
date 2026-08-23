import json
import sys

from deerflow.code_change.cli import run_task
from deerflow.code_change.store import CodeChangeStore


def test_pr_handoff_contains_review_commands(tmp_path, committed_repo):
    repo = committed_repo({"app.py": "def health():\n    return 'bad'\n"})
    patch = tmp_path / "fix.patch"
    patch.write_text(
        """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1,2 +1,2 @@
 def health():
-    return 'bad'
+    return 'ok'
""",
        encoding="utf-8",
    )
    command = f"{sys.executable} -c \"import app; assert app.health() == 'ok'\""
    store = CodeChangeStore(tmp_path / "state")
    store.create_project("demo", str(repo), command, repo_url="git@github.com:example/demo.git", default_branch="main")

    task = run_task(store, "demo", "fix health function", patch_file=str(patch))

    handoff = json.loads((tmp_path / "state" / "projects" / "demo" / "tasks" / task.task_id / "pr_handoff.json").read_text(encoding="utf-8"))
    assert handoff["branch_name"].startswith("ai-code-change/")
    assert handoff["base_branch"] == "main"
    assert handoff["source_commit"] == task.source_commit
    assert handoff["commands"][0] == 'test -z "$(git status --porcelain)"'
    assert not any(command.startswith("git fetch") for command in handoff["commands"])
    assert "gh pr create --draft" in "\n".join(handoff["commands"])
    assert handoff["changed_files"] == ["app.py"]
