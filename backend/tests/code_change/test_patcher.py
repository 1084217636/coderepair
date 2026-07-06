import subprocess

import pytest

from deerflow.code_change.patcher import PatchRejected, apply_patch_text


def test_patcher_applies_unified_diff(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.PIPE)
    (repo / "app.py").write_text("def health():\n    return 'bad'\n", encoding="utf-8")

    patch = """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1,2 +1,2 @@
 def health():
-    return 'bad'
+    return 'ok'
"""

    result = apply_patch_text(str(repo), patch, tmp_path / "artifacts")

    assert result.applied is True
    assert result.changed_files == ["app.py"]
    assert result.lines_added == 1
    assert result.lines_deleted == 1
    assert (repo / "app.py").read_text(encoding="utf-8") == "def health():\n    return 'ok'\n"
    assert (tmp_path / "artifacts" / "patch.diff").exists()


def test_patcher_rejects_paths_outside_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    patch = """diff --git a/../secret.txt b/../secret.txt
--- a/../secret.txt
+++ b/../secret.txt
@@ -1 +1 @@
-old
+new
"""

    with pytest.raises(PatchRejected):
        apply_patch_text(str(repo), patch, tmp_path / "artifacts")
