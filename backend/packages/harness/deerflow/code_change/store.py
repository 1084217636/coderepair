from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from deerflow.code_change.models import Project, Task, ensure_repo_path, project_safe_name


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


class CodeChangeStore:
    def __init__(self, base_dir: str | Path | None = None) -> None:
        if base_dir is None:
            base_dir = Path(os.getenv("DEER_FLOW_HOME", Path.cwd() / ".deer-flow")) / "code-change"
        self.base_dir = Path(base_dir)
        self.projects_dir = self.base_dir / "projects"
        self.projects_index = self.base_dir / "projects.json"
        self.queue_log = self.base_dir / "task_queue.jsonl"
        self.projects_dir.mkdir(parents=True, exist_ok=True)

    def create_project(self, name: str, repo_path: str, test_command: str, repo_url: str = "", default_branch: str = "main") -> Project:
        safe = project_safe_name(name)
        repo = ensure_repo_path(repo_path)
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
        return Project.from_dict(self._read_json(path))

    def save_task(self, task: Task) -> None:
        task_path = Path(task.artifact_dir) / "task.json"
        self._write_json(task_path, task.to_dict())
        self.append_timeline(task.project_id, "TASK_UPDATED", f"{task.task_id} status={task.status}")

    def get_task(self, project_id: str, task_id: str) -> Task:
        task_path = self.project_dir(project_id) / "tasks" / task_id / "task.json"
        if not task_path.exists():
            raise KeyError(f"task not found: {task_id}")
        return Task.from_dict(self._read_json(task_path))

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
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
