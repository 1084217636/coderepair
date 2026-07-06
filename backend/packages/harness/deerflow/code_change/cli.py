from __future__ import annotations

import argparse
from deerflow.code_change.models import Task
from deerflow.code_change.store import CodeChangeStore
from deerflow.code_change.worker import create_task, run_next_task, run_task_now


def main() -> None:
    parser = argparse.ArgumentParser(prog="deerflow-code-change")
    parser.add_argument("--home", default=None, help="Code-change state directory")
    sub = parser.add_subparsers(dest="resource", required=True)

    project = sub.add_parser("project")
    project_sub = project.add_subparsers(dest="action", required=True)
    create = project_sub.add_parser("create")
    create.add_argument("name")
    create.add_argument("--repo-path", required=True)
    create.add_argument("--test-command", required=True)
    create.add_argument("--repo-url", default="")
    create.add_argument("--default-branch", default="main")
    project_sub.add_parser("list")
    status = project_sub.add_parser("status")
    status.add_argument("name")

    task = sub.add_parser("task")
    task_sub = task.add_subparsers(dest="action", required=True)
    run = task_sub.add_parser("run")
    run.add_argument("project")
    run.add_argument("requirement")
    run.add_argument("--patch-file", default="", help="Unified diff to apply before running tests")
    enqueue = task_sub.add_parser("enqueue")
    enqueue.add_argument("project")
    enqueue.add_argument("requirement")
    enqueue.add_argument("--patch-file", default="", help="Unified diff to apply in worker")

    worker = sub.add_parser("worker")
    worker_sub = worker.add_subparsers(dest="action", required=True)
    worker_sub.add_parser("run-once")

    args = parser.parse_args()
    store = CodeChangeStore(args.home)

    if args.resource == "project" and args.action == "create":
        item = store.create_project(args.name, args.repo_path, args.test_command, args.repo_url, args.default_branch)
        print(f"created project {item.project_id}: {item.repo_path}")
        return
    if args.resource == "project" and args.action == "list":
        for item in store.list_projects():
            print(f"{item.project_id}\t{item.repo_path}\t{item.test_command}")
        return
    if args.resource == "project" and args.action == "status":
        item = store.get_project(args.name)
        timeline = store.project_dir(item.project_id) / "timeline.jsonl"
        print(f"project={item.project_id}")
        print(f"repo_path={item.repo_path}")
        print(f"test_command={item.test_command}")
        print(f"timeline={timeline}")
        return
    if args.resource == "task" and args.action == "run":
        run_task(store, args.project, args.requirement, patch_file=args.patch_file)
        return
    if args.resource == "task" and args.action == "enqueue":
        task = create_task(store, args.project, args.requirement, patch_file=args.patch_file, enqueue=True)
        print(f"task={task.task_id} status={task.status} artifacts={task.artifact_dir}")
        return
    if args.resource == "worker" and args.action == "run-once":
        task = run_next_task(store)
        if task is None:
            print("worker=noop")
        else:
            print(f"task={task.task_id} status={task.status} artifacts={task.artifact_dir}")
        return


def run_task(store: CodeChangeStore, project_name: str, requirement: str, patch_file: str = "", patch_text: str = "") -> Task:
    task = run_task_now(store, project_name, requirement, patch_file=patch_file, patch_text=patch_text)
    print(f"task={task.task_id} status={task.status} artifacts={task.artifact_dir}")
    return task


if __name__ == "__main__":
    main()
