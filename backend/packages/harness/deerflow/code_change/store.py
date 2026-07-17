from __future__ import annotations

import json
import os
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from deerflow.code_change.models import Project, Task, TaskStatus, ensure_repo_path, project_safe_name


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


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

    def create_project(self, name: str, repo_path: str, test_command: str, repo_url: str = "", default_branch: str = "main") -> Project:
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

    def save_task(self, task: Task) -> None:
        self._ensure_owner(task.owner_id)
        task_path = Path(task.artifact_dir) / "task.json"
        self._write_json(task_path, task.to_dict())
        self.append_timeline(task.project_id, "TASK_UPDATED", f"{task.task_id} status={task.status}")

    def get_task(self, project_id: str, task_id: str) -> Task:
        task_path = self.project_dir(project_id) / "tasks" / task_id / "task.json"
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
            if self._claim_task_file(task, worker_id, lease_seconds):
                task.worker_id = worker_id
                task.lease_expires_at = (datetime.now(UTC) + timedelta(seconds=lease_seconds)).isoformat()
                self.save_task(task)
                self.append_timeline(task.project_id, "TASK_CLAIMED", f"{task.task_id} worker={worker_id}")
                return task
        return None

    def release_task_claim(self, task: Task, worker_id: str) -> None:
        claim_path = Path(task.artifact_dir) / ".claim.json"
        if claim_path.exists():
            try:
                claim = self._read_json(claim_path)
            except (OSError, json.JSONDecodeError):
                claim = {}
            if claim.get("worker_id") != worker_id:
                raise ValueError("task claim belongs to another worker")
            claim_path.unlink(missing_ok=True)
        task.worker_id = ""
        task.lease_expires_at = ""
        self.save_task(task)

    def _claim_task_file(self, task: Task, worker_id: str, lease_seconds: int) -> bool:
        claim_path = Path(task.artifact_dir) / ".claim.json"
        for _ in range(2):
            expires_at = datetime.now(UTC) + timedelta(seconds=lease_seconds)
            payload = json.dumps({"worker_id": worker_id, "expires_at": expires_at.isoformat()}).encode()
            try:
                fd = os.open(claim_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                try:
                    current = self._read_json(claim_path)
                    current_expiry = datetime.fromisoformat(current["expires_at"])
                except (OSError, KeyError, ValueError, json.JSONDecodeError):
                    current_expiry = datetime.min.replace(tzinfo=UTC)
                if current_expiry > datetime.now(UTC):
                    return False
                try:
                    claim_path.unlink()
                except FileNotFoundError:
                    pass
                continue
            with os.fdopen(fd, "wb") as fh:
                fh.write(payload)
                fh.flush()
                os.fsync(fh.fileno())
            return True
        return False

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
