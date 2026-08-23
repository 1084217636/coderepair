from __future__ import annotations

import fcntl
import json
import os
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from deerflow.code_change.models import Project, Task, TaskStatus, ensure_repo_path, project_safe_name


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


class StaleTaskClaim(RuntimeError):
    """Raised when a worker tries to mutate a task after losing its lease."""


class CodeChangeStore:
    def __init__(
        self,
        base_dir: str | Path | None = None,
        owner_id: str = "default",
        allowed_repo_roots: Iterable[str | Path] | None = None,
    ) -> None:
        if base_dir is None:
            base_dir = Path(os.getenv("DEER_FLOW_HOME", Path.cwd() / ".deer-flow")) / "code-change"
        self.base_dir = Path(base_dir).expanduser().resolve()
        self.owner_id = project_safe_name(owner_id)
        self.owner_dir = self.base_dir if self.owner_id == "default" else self.base_dir / "users" / self.owner_id
        self.projects_dir = self.owner_dir / "projects"
        self.projects_index = self.owner_dir / "projects.json"
        self.queue_log = self.owner_dir / "task_queue.jsonl"
        if allowed_repo_roots is None:
            configured = [item.strip() for item in os.getenv("CODE_CHANGE_ALLOWED_REPO_ROOTS", "").split(os.pathsep) if item.strip()]
            allowed_repo_roots = configured or [self.base_dir.parent]
        self.allowed_repo_roots = [Path(root).expanduser().resolve() for root in allowed_repo_roots]
        self.projects_dir.mkdir(parents=True, exist_ok=True)

    def create_project(
        self,
        name: str,
        repo_path: str,
        test_command: str,
        repo_url: str = "",
        default_branch: str = "main",
        test_profile: str = "",
    ) -> Project:
        safe = project_safe_name(name)
        repo = ensure_repo_path(repo_path, self.allowed_repo_roots)
        projects = self._load_index()
        if safe in projects:
            raise ValueError(f"project already exists: {safe}")
        project = Project(
            project_id=safe,
            name=name,
            repo_path=repo,
            repo_url=repo_url,
            default_branch=default_branch,
            test_command=test_command,
            test_profile=test_profile,
            owner_id=self.owner_id,
            created_at=now_iso(),
            updated_at=now_iso(),
        )
        self._write_project(project)
        projects[safe] = project.to_dict()
        self._write_json(self.projects_index, projects)
        self.append_timeline(safe, "PROJECT_CREATED", f"repo_path={repo}")
        return project

    def list_projects(self) -> list[Project]:
        return [Project.from_dict(item) for item in self._load_index().values()]

    def get_project(self, project_id: str) -> Project:
        safe = project_safe_name(project_id)
        path = self.project_dir(safe) / "project.json"
        if not path.exists():
            raise KeyError(f"project not found: {project_id}")
        project = Project.from_dict(self._read_json(path))
        self._ensure_owner(project.owner_id)
        return project

    def save_task(self, task: Task, *, expected_claim_id: str | None = None) -> None:
        self._ensure_owner(task.owner_id)
        task_path = Path(task.artifact_dir) / "task.json"
        with self._task_claim_lock(task):
            claim = self._read_claim(task)
            if expected_claim_id:
                self._validate_claim(claim, task.worker_id, expected_claim_id, require_unexpired=True)
            elif claim is not None:
                if self._claim_expiry(claim) > datetime.now(UTC):
                    raise StaleTaskClaim("task has an active worker claim")
                self._claim_path(task).unlink(missing_ok=True)
                task.worker_id = ""
                task.claim_id = ""
                task.heartbeat_at = ""
                task.lease_expires_at = ""
            self._write_json(task_path, task.to_dict())
        self.append_timeline(task.project_id, "TASK_UPDATED", f"{task.task_id} status={task.status}")

    def get_task(self, project_id: str, task_id: str) -> Task:
        safe_task_id = project_safe_name(task_id)
        if safe_task_id != task_id:
            raise KeyError(f"task not found: {task_id}")
        task_path = self.project_dir(project_id) / "tasks" / safe_task_id / "task.json"
        if not task_path.exists():
            raise KeyError(f"task not found: {task_id}")
        task = Task.from_dict(self._read_json(task_path))
        self._ensure_owner(task.owner_id)
        return task

    def list_tasks(self, project_id: str | None = None) -> list[Task]:
        if project_id:
            project_ids = [project_safe_name(project_id)]
        else:
            project_ids = list(self._load_index().keys())

        tasks: list[Task] = []
        for pid in project_ids:
            tasks_dir = self.project_dir(pid) / "tasks"
            if not tasks_dir.exists():
                continue
            for task_path in sorted(tasks_dir.glob("*/task.json")):
                tasks.append(Task.from_dict(self._read_json(task_path)))
        return tasks

    def task_metrics(self, project_id: str | None = None) -> dict:
        tasks = self.list_tasks(project_id)
        status_counts = {str(status): 0 for status in TaskStatus}
        for task in tasks:
            status_counts[str(task.status)] = status_counts.get(str(task.status), 0) + 1

        retryable_failed = [task for task in tasks if task.status is TaskStatus.FAILED and task.attempt_count < task.max_attempts]
        exhausted_failed = [task for task in tasks if task.status is TaskStatus.FAILED and task.attempt_count >= task.max_attempts]
        return {
            "project_id": project_safe_name(project_id) if project_id else "",
            "total_tasks": len(tasks),
            "status_counts": status_counts,
            "queue_depth": status_counts.get(str(TaskStatus.QUEUED), 0),
            "failed_count": status_counts.get(str(TaskStatus.FAILED), 0),
            "retryable_failed_count": len(retryable_failed),
            "exhausted_failed_count": len(exhausted_failed),
            "attempts_total": sum(task.attempt_count for task in tasks),
        }

    def new_task_dir(self, project_id: str) -> Path:
        task_id = "task_" + datetime.now(UTC).strftime("%Y%m%d_%H%M%S_") + uuid4().hex[:8]
        path = self.project_dir(project_id) / "tasks" / task_id
        path.mkdir(parents=True, exist_ok=False)
        return path

    def enqueue_task(self, task: Task) -> None:
        item = {"time": now_iso(), "project_id": task.project_id, "task_id": task.task_id}
        self.queue_log.parent.mkdir(parents=True, exist_ok=True)
        with self.queue_log.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(item, ensure_ascii=False) + "\n")
        self.append_timeline(task.project_id, "TASK_ENQUEUED", task.task_id)

    def queued_items(self) -> list[dict]:
        if not self.queue_log.exists():
            return []
        return [json.loads(line) for line in self.queue_log.read_text(encoding="utf-8").splitlines() if line.strip()]

    def claim_next_task(self, worker_id: str, lease_seconds: int = 300) -> Task | None:
        if not worker_id.strip():
            raise ValueError("worker_id is required")
        for item in self.queued_items():
            try:
                task = self.get_task(item["project_id"], item["task_id"])
            except KeyError:
                continue
            if task.status is not TaskStatus.QUEUED:
                continue
            claimed = self._claim_task_file(task, worker_id, lease_seconds)
            if claimed is not None:
                self.append_timeline(claimed.project_id, "TASK_CLAIMED", f"{claimed.task_id} worker={worker_id} claim={claimed.claim_id}")
                return claimed
        return None

    def renew_task_claim(
        self,
        project_id: str,
        task_id: str,
        worker_id: str,
        claim_id: str,
        *,
        lease_seconds: int = 300,
    ) -> Task:
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive when renewing a task claim")
        task = self.get_task(project_id, task_id)
        with self._task_claim_lock(task):
            claim = self._read_claim(task)
            self._validate_claim(claim, worker_id, claim_id, require_unexpired=True)
            heartbeat_at = now_iso()
            expires_at = (datetime.now(UTC) + timedelta(seconds=lease_seconds)).isoformat()
            claim = {"worker_id": worker_id, "claim_id": claim_id, "heartbeat_at": heartbeat_at, "expires_at": expires_at}
            self._write_json(self._claim_path(task), claim)
            persisted = self._read_task_file(task)
            persisted.worker_id = worker_id
            persisted.claim_id = claim_id
            persisted.heartbeat_at = heartbeat_at
            persisted.lease_expires_at = expires_at
            self._write_json(Path(persisted.artifact_dir) / "task.json", persisted.to_dict())
            return persisted

    def assert_task_claim(self, task: Task, worker_id: str, claim_id: str) -> None:
        with self._task_claim_lock(task):
            self._validate_claim(self._read_claim(task), worker_id, claim_id, require_unexpired=True)

    def release_task_claim(self, task: Task, worker_id: str, claim_id: str) -> bool:
        with self._task_claim_lock(task):
            claim = self._read_claim(task)
            try:
                self._validate_claim(claim, worker_id, claim_id, require_unexpired=False)
            except StaleTaskClaim:
                return False
            persisted = self._read_task_file(task)
            persisted.worker_id = ""
            persisted.claim_id = ""
            persisted.heartbeat_at = ""
            persisted.lease_expires_at = ""
            self._write_json(Path(persisted.artifact_dir) / "task.json", persisted.to_dict())
            self._claim_path(task).unlink(missing_ok=True)
            task.worker_id = ""
            task.claim_id = ""
            task.heartbeat_at = ""
            task.lease_expires_at = ""
        self.append_timeline(task.project_id, "TASK_RELEASED", f"{task.task_id} worker={worker_id} claim={claim_id}")
        return True

    def _claim_task_file(self, task: Task, worker_id: str, lease_seconds: int) -> Task | None:
        claim_path = self._claim_path(task)
        with self._task_claim_lock(task):
            task = self._read_task_file(task)
            if task.status is not TaskStatus.QUEUED:
                return None
            current = self._read_claim(task)
            if current is not None and self._claim_expiry(current) > datetime.now(UTC):
                return None
            claim_path.unlink(missing_ok=True)
            expires_at = datetime.now(UTC) + timedelta(seconds=lease_seconds)
            claim_id = uuid4().hex
            heartbeat_at = now_iso()
            payload = json.dumps({"worker_id": worker_id, "claim_id": claim_id, "heartbeat_at": heartbeat_at, "expires_at": expires_at.isoformat()}).encode()
            try:
                fd = os.open(claim_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                return None
            with os.fdopen(fd, "wb") as fh:
                fh.write(payload)
                fh.flush()
                os.fsync(fh.fileno())
            task.worker_id = worker_id
            task.claim_id = claim_id
            task.heartbeat_at = heartbeat_at
            task.lease_expires_at = expires_at.isoformat()
            self._write_json(Path(task.artifact_dir) / "task.json", task.to_dict())
            return task

    @contextmanager
    def _task_claim_lock(self, task: Task) -> Iterator[None]:
        lock_path = Path(task.artifact_dir) / ".claim.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    @staticmethod
    def _claim_path(task: Task) -> Path:
        return Path(task.artifact_dir) / ".claim.json"

    def _read_claim(self, task: Task) -> dict | None:
        path = self._claim_path(task)
        if not path.exists():
            return None
        try:
            return self._read_json(path)
        except (OSError, json.JSONDecodeError):
            return {}

    @staticmethod
    def _claim_expiry(claim: dict) -> datetime:
        try:
            expiry = datetime.fromisoformat(str(claim["expires_at"]))
        except (KeyError, TypeError, ValueError):
            return datetime.min.replace(tzinfo=UTC)
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=UTC)
        return expiry

    def _validate_claim(
        self,
        claim: dict | None,
        worker_id: str,
        claim_id: str,
        *,
        require_unexpired: bool,
    ) -> None:
        if claim is None:
            raise StaleTaskClaim("task claim no longer exists")
        if claim.get("worker_id") != worker_id or claim.get("claim_id") != claim_id:
            raise StaleTaskClaim("task claim belongs to another worker or attempt")
        if require_unexpired and self._claim_expiry(claim) <= datetime.now(UTC):
            raise StaleTaskClaim("task claim lease has expired")

    def _read_task_file(self, task: Task) -> Task:
        persisted = Task.from_dict(self._read_json(Path(task.artifact_dir) / "task.json"))
        self._ensure_owner(persisted.owner_id)
        return persisted

    def project_dir(self, project_id: str) -> Path:
        return self.projects_dir / project_safe_name(project_id)

    def append_timeline(self, project_id: str, event: str, detail: str) -> None:
        item = {"time": now_iso(), "event": event, "detail": detail}
        timeline = self.project_dir(project_id) / "timeline.jsonl"
        timeline.parent.mkdir(parents=True, exist_ok=True)
        with timeline.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(item, ensure_ascii=False) + "\n")

    def _write_project(self, project: Project) -> None:
        project_dir = self.project_dir(project.project_id)
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "tasks").mkdir(exist_ok=True)
        self._write_json(project_dir / "project.json", project.to_dict())

    def _load_index(self) -> dict:
        if not self.projects_index.exists():
            return {}
        return self._read_json(self.projects_index)

    @staticmethod
    def _read_json(path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _write_json(path: Path, data: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        staging = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        try:
            staging.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            os.replace(staging, path)
        finally:
            staging.unlink(missing_ok=True)

    def _ensure_owner(self, owner_id: str) -> None:
        if project_safe_name(owner_id) != self.owner_id:
            raise PermissionError("code-change object belongs to another owner")
