from __future__ import annotations

import argparse
from pathlib import Path

from deerflow.code_change.context_retriever import retrieve_context
from deerflow.code_change.models import Task, TaskStatus
from deerflow.code_change.patcher import apply_patch_file, write_pr_body
from deerflow.code_change.repo_scanner import scan_repo
from deerflow.code_change.report_writer import write_reports
from deerflow.code_change.state_machine import transition
from deerflow.code_change.store import CodeChangeStore, now_iso
from deerflow.code_change.test_runner import run_tests


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


def run_task(store: CodeChangeStore, project_name: str, requirement: str, patch_file: str = "") -> Task:
    project = store.get_project(project_name)
    task_dir = store.new_task_dir(project.project_id)
    task = Task(
        task_id=Path(task_dir).name,
        project_id=project.project_id,
        requirement=requirement,
        artifact_dir=str(task_dir),
        created_at=now_iso(),
        updated_at=now_iso(),
    )
    try:
        transition(task, TaskStatus.PLANNING, "Created a simple execution plan from the requirement.")
        files = scan_repo(project.repo_path)
        transition(task, TaskStatus.RETRIEVING_CONTEXT, f"Scanned {len(files)} source files.")
        task.contexts = retrieve_context(project.repo_path, requirement, files)
        if patch_file:
            transition(task, TaskStatus.GENERATING_PATCH, f"Retrieved {len(task.contexts)} context items; using patch artifact.")
            transition(task, TaskStatus.APPLYING_PATCH, f"Applying patch from {patch_file}.")
            task.patch_result = apply_patch_file(project.repo_path, patch_file, task_dir)
            if not task.patch_result.applied:
                transition(task, TaskStatus.FAILED, "Patch failed to apply.", error=task.patch_result.error)
                write_reports(task)
                store.save_task(task)
                print(f"task={task.task_id} status={task.status} artifacts={task.artifact_dir}")
                return task
        transition(task, TaskStatus.RUNNING_TESTS, f"Retrieved {len(task.contexts)} context items.")
        task.test_result = run_tests(project.repo_path, project.test_command, task_dir)
        if task.test_result.passed:
            transition(task, TaskStatus.REVIEWING, "Tests passed; report is ready for human review.")
            if task.patch_result:
                pr_body = write_pr_body(task.task_id, task.requirement, task.patch_result, True, task_dir)
                task.pr_body_path = str(pr_body)
                transition(task, TaskStatus.PR_CREATED, "Generated PR draft with diff explanation and test result.")
        else:
            transition(task, TaskStatus.FAILED, "Tests failed; inspect test.log.", error="test command returned non-zero exit code")
    except Exception as exc:
        if task.status is not TaskStatus.FAILED:
            transition(task, TaskStatus.FAILED, "Task failed.", error=str(exc))
    write_reports(task)
    store.save_task(task)
    print(f"task={task.task_id} status={task.status} artifacts={task.artifact_dir}")
    return task


if __name__ == "__main__":
    main()
