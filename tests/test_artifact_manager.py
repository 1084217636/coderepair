from pathlib import Path

from outputs.artifact_manager import ArtifactManager


def _create_session_dir(root: Path, session_id: str) -> Path:
    session_dir = root / f"session_{session_id}"
    session_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / "marker.txt").write_text(session_id, encoding="utf-8")
    return session_dir


def test_prune_sessions_keeps_recent_sessions(tmp_path):
    manager = ArtifactManager(tmp_path)
    _create_session_dir(tmp_path, "20260408_100000_000001")
    _create_session_dir(tmp_path, "20260408_100001_000002")
    _create_session_dir(tmp_path, "20260408_100002_000003")
    _create_session_dir(tmp_path, "20260408_100003_000004")

    result = manager.prune_sessions(keep_last=2)

    remaining = sorted(path.name for path in tmp_path.glob("session_*"))
    assert result["deleted_count"] == 2
    assert remaining == [
        "session_20260408_100002_000003",
        "session_20260408_100003_000004",
    ]


def test_create_session_can_auto_cleanup_old_sessions(tmp_path):
    manager = ArtifactManager(tmp_path)
    _create_session_dir(tmp_path, "20260408_100000_000001")
    _create_session_dir(tmp_path, "20260408_100001_000002")

    manager.create_session("20260408_100002_000003", keep_last=2)

    remaining = sorted(path.name for path in tmp_path.glob("session_*"))
    assert remaining == [
        "session_20260408_100001_000002",
        "session_20260408_100002_000003",
    ]
