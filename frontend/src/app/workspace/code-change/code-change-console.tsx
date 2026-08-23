"use client";

import { CheckCircle2Icon, Loader2Icon, RefreshCwIcon } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import {
  CODE_CHANGE_TEST_PROFILES,
  createCodeChangeProject,
  createCodeChangeTask,
  getCodeChangeReport,
  getCodeChangeTask,
  listCodeChangeProjects,
  listCodeChangeTasks,
  resubmitCodeChangeTask,
  retryCodeChangeTask,
  reviewCodeChangeTask,
  statusTone,
  type CodeChangeProject,
  type CodeChangeTask,
  type PatchMode,
  type TestProfile,
} from "@/core/code-change";
import { cn } from "@/lib/utils";

const toneClass = {
  neutral: "bg-muted text-muted-foreground",
  running: "bg-blue-500/15 text-blue-700 dark:text-blue-300",
  success: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300",
  warning: "bg-amber-500/15 text-amber-700 dark:text-amber-300",
  error: "bg-destructive/15 text-destructive",
};

const TERMINAL_TASK_STATUSES = new Set([
  "HANDOFF_READY",
  "APPROVED",
  "CHANGES_REQUESTED",
  "PR_CREATED",
  "FAILED",
  "ROLLED_BACK",
]);

export function CodeChangeConsole() {
  const [projects, setProjects] = useState<CodeChangeProject[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState("");
  const [tasks, setTasks] = useState<CodeChangeTask[]>([]);
  const [task, setTask] = useState<CodeChangeTask | null>(null);
  const [report, setReport] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const [name, setName] = useState("");
  const [repoPath, setRepoPath] = useState("");
  const [testProfile, setTestProfile] = useState<TestProfile>("python-pytest");
  const [requirement, setRequirement] = useState("");
  const [patchText, setPatchText] = useState("");
  const [patchMode, setPatchMode] = useState<PatchMode>("external");
  const [agentModelName, setAgentModelName] = useState("");
  const [reviewNote, setReviewNote] = useState("");

  const selectedProject = useMemo(
    () => projects.find((project) => project.project_id === selectedProjectId),
    [projects, selectedProjectId],
  );

  const refreshProjects = useCallback(async () => {
    setBusy(true);
    setError("");
    try {
      const next = await listCodeChangeProjects();
      setProjects(next);
      if (!next.length) {
        setTasks([]);
        setTask(null);
        setReport("");
      }
      setSelectedProjectId((current) =>
        next.some((project) => project.project_id === current)
          ? current
          : (next[0]?.project_id ?? ""),
      );
    } catch (nextError) {
      setError(
        nextError instanceof Error ? nextError.message : "项目列表加载失败",
      );
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    void refreshProjects();
  }, [refreshProjects]);

  useEffect(() => {
    if (!selectedProjectId) return;
    let cancelled = false;
    void listCodeChangeTasks(selectedProjectId)
      .then((next) => {
        if (cancelled) return;
        setTasks(next);
        setTask((current) => {
          if (current?.project_id === selectedProjectId) {
            return (
              next.find((item) => item.task_id === current.task_id) ??
              next[0] ??
              null
            );
          }
          return next[0] ?? null;
        });
      })
      .catch((nextError: unknown) => {
        if (!cancelled)
          setError(
            nextError instanceof Error ? nextError.message : "任务列表加载失败",
          );
      });
    return () => {
      cancelled = true;
    };
  }, [selectedProjectId]);

  const activeTaskProjectId = task?.project_id;
  const activeTaskId = task?.task_id;
  const activeTaskStatus = task?.status;

  useEffect(() => {
    if (
      !activeTaskProjectId ||
      !activeTaskId ||
      !activeTaskStatus ||
      TERMINAL_TASK_STATUSES.has(activeTaskStatus)
    )
      return;
    const projectId = activeTaskProjectId;
    const taskId = activeTaskId;
    let cancelled = false;

    const poll = async () => {
      try {
        const next = await getCodeChangeTask(projectId, taskId);
        if (cancelled) return;
        setTask(next);
        setTasks((current) =>
          current.map((item) => (item.task_id === next.task_id ? next : item)),
        );
        if (TERMINAL_TASK_STATUSES.has(next.status)) {
          try {
            const nextReport = await getCodeChangeReport(projectId, taskId);
            if (!cancelled) setReport(nextReport);
          } catch {
            // A terminal state can be persisted just before its report becomes
            // visible. Manual refresh remains available for that short window.
          }
        }
      } catch (nextError) {
        if (!cancelled) {
          setError(
            nextError instanceof Error ? nextError.message : "任务轮询失败",
          );
        }
      }
    };

    const timer = window.setInterval(() => void poll(), 2_000);
    void poll();
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [activeTaskId, activeTaskProjectId, activeTaskStatus]);

  async function handleCreateProject() {
    if (!name.trim() || !repoPath.trim()) return;
    setBusy(true);
    setError("");
    try {
      const created = await createCodeChangeProject({
        name: name.trim(),
        repo_path: repoPath.trim(),
        test_profile: testProfile,
      });
      setProjects((current) => [...current, created]);
      setTasks([]);
      setTask(null);
      setReport("");
      setSelectedProjectId(created.project_id);
      setName("");
      setRepoPath("");
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "项目创建失败");
    } finally {
      setBusy(false);
    }
  }

  async function handleRunTask() {
    if (!selectedProjectId || !requirement.trim()) return;
    setBusy(true);
    setError("");
    setReport("");
    try {
      const created = await createCodeChangeTask(selectedProjectId, {
        requirement: requirement.trim(),
        patch_text: patchMode === "external" ? patchText : "",
        patch_mode: patchMode,
        agent_model_name: patchMode === "agent" ? agentModelName.trim() : "",
      });
      setTask(created);
      setTasks((current) => [created, ...current]);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "任务执行失败");
    } finally {
      setBusy(false);
    }
  }

  async function handleResubmit() {
    if (!task || !patchText.trim()) return;
    setBusy(true);
    setError("");
    try {
      const next = await resubmitCodeChangeTask(
        task.project_id,
        task.task_id,
        patchText,
      );
      setTask(next);
      setTasks((current) =>
        current.map((item) => (item.task_id === next.task_id ? next : item)),
      );
      setReport("");
    } catch (nextError) {
      setError(
        nextError instanceof Error ? nextError.message : "补丁重新提交失败",
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleRefreshTask() {
    if (!task) return;
    setBusy(true);
    setError("");
    try {
      const next = await getCodeChangeTask(task.project_id, task.task_id);
      setTask(next);
      setTasks((current) =>
        current.map((item) => (item.task_id === next.task_id ? next : item)),
      );
      if (["HANDOFF_READY", "FAILED", "APPROVED"].includes(next.status)) {
        setReport(await getCodeChangeReport(next.project_id, next.task_id));
      }
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "任务刷新失败");
    } finally {
      setBusy(false);
    }
  }

  async function handleRetry() {
    if (!task) return;
    setBusy(true);
    setError("");
    try {
      const next = await retryCodeChangeTask(task.project_id, task.task_id);
      setTask(next);
      setTasks((current) =>
        current.map((item) => (item.task_id === next.task_id ? next : item)),
      );
      setReport("");
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "任务重试失败");
    } finally {
      setBusy(false);
    }
  }

  async function handleReview(decision: "approve" | "request_changes") {
    if (!task) return;
    setBusy(true);
    setError("");
    try {
      const next = await reviewCodeChangeTask(task.project_id, task.task_id, {
        decision,
        note: reviewNote,
      });
      setTask(next);
      setTasks((current) =>
        current.map((item) => (item.task_id === next.task_id ? next : item)),
      );
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "审批失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto flex h-full w-full max-w-7xl flex-col gap-6 overflow-y-auto p-6">
      <div>
        <h1 className="text-2xl font-semibold">Code Change 控制台</h1>
        <p className="text-muted-foreground mt-2 text-sm">
          选择受控仓库、提交变更任务、查看 Patch
          与测试报告，再由人确认是否交接。Worker 的内部令牌不会暴露到浏览器。
        </p>
      </div>

      {error ? (
        <div className="border-destructive/30 bg-destructive/10 text-destructive rounded-md border px-4 py-3 text-sm">
          {error}
        </div>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>1. 登记本地项目</CardTitle>
            <CardDescription>
              测试命令来自服务端固定模板，页面不能提交任意 shell 命令。
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <Input
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="项目名，例如 demo-api"
            />
            <Input
              value={repoPath}
              onChange={(event) => setRepoPath(event.target.value)}
              placeholder="允许根目录下的绝对路径"
            />
            <Select
              value={testProfile}
              onValueChange={(value) => setTestProfile(value as TestProfile)}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {CODE_CHANGE_TEST_PROFILES.map((profile) => (
                  <SelectItem key={profile.value} value={profile.value}>
                    {profile.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button
              disabled={busy || !name.trim() || !repoPath.trim()}
              onClick={() => void handleCreateProject()}
            >
              登记项目
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>2. 选择项目</CardTitle>
            <CardDescription>
              每个登录用户只能读取自己名下的项目与任务。
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex gap-2">
              <Select
                value={selectedProjectId}
                onValueChange={(projectId) => {
                  setSelectedProjectId(projectId);
                  setTasks([]);
                  setTask(null);
                  setReport("");
                }}
              >
                <SelectTrigger className="flex-1">
                  <SelectValue placeholder="还没有项目" />
                </SelectTrigger>
                <SelectContent>
                  {projects.map((project) => (
                    <SelectItem
                      key={project.project_id}
                      value={project.project_id}
                    >
                      {project.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Button
                variant="outline"
                size="icon"
                disabled={busy}
                onClick={() => void refreshProjects()}
                aria-label="刷新项目"
              >
                <RefreshCwIcon
                  className={cn("size-4", busy && "animate-spin")}
                />
              </Button>
            </div>
            {selectedProject ? (
              <div className="bg-muted rounded-md p-3 text-sm">
                <div className="font-medium">{selectedProject.repo_path}</div>
                <div className="text-muted-foreground mt-1">
                  测试模板：{selectedProject.test_profile}
                </div>
              </div>
            ) : null}
            {tasks.length ? (
              <Select
                value={task?.task_id ?? ""}
                onValueChange={(taskId) => {
                  setTask(
                    tasks.find((item) => item.task_id === taskId) ?? null,
                  );
                  setReport("");
                }}
              >
                <SelectTrigger>
                  <SelectValue placeholder="选择历史任务" />
                </SelectTrigger>
                <SelectContent>
                  {tasks.map((item) => (
                    <SelectItem key={item.task_id} value={item.task_id}>
                      {item.status} · {item.task_id}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            ) : null}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>3. 提交受控变更</CardTitle>
          <CardDescription>
            外部 Patch 与真实 Agent 生成是两条明确路径；两者都会进入同一个受控
            Worker，经过路径校验、测试与人工审批。
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <Textarea
            value={requirement}
            onChange={(event) => setRequirement(event.target.value)}
            placeholder="需求：修复登录接口在空用户名时返回 500 的问题"
          />
          <Select
            value={patchMode}
            onValueChange={(value) => setPatchMode(value as PatchMode)}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="external">外部 unified diff</SelectItem>
              <SelectItem value="agent">DeerFlow Agent 生成</SelectItem>
            </SelectContent>
          </Select>
          {patchMode === "agent" ? (
            <Input
              value={agentModelName}
              onChange={(event) => setAgentModelName(event.target.value)}
              placeholder="模型名（留空使用 config.yaml 默认模型）"
            />
          ) : (
            <Textarea
              className="min-h-48 font-mono text-xs"
              value={patchText}
              onChange={(event) => setPatchText(event.target.value)}
              placeholder="可选：粘贴 unified diff。留空时 Worker 会明确返回 PATCH_REQUIRED。"
            />
          )}
          <Button
            disabled={busy || !selectedProjectId || !requirement.trim()}
            onClick={() => void handleRunTask()}
          >
            {busy ? <Loader2Icon className="mr-2 size-4 animate-spin" /> : null}
            加入 Worker 队列
          </Button>
        </CardContent>
      </Card>

      {task ? (
        <Card>
          <CardHeader>
            <div className="flex flex-wrap items-center gap-3">
              <CardTitle>4. 任务结果</CardTitle>
              <Badge className={toneClass[statusTone(task.status)]}>
                {task.status}
              </Badge>
              <span className="text-muted-foreground font-mono text-xs">
                {task.task_id}
              </span>
            </div>
            <CardDescription>
              mode：{task.patch_mode}；source commit：
              {task.source_commit || "旧任务未记录"}；attempt：
              {task.attempt_count}/{task.max_attempts}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {task.error ? (
              <p className="text-destructive text-sm">{task.error}</p>
            ) : null}
            {task.patch_mode === "agent" ? (
              <div className="bg-muted rounded-md p-3 text-xs">
                <div>
                  Task 关联 thread_id（非 Gateway Thread）：
                  {task.agent_thread_id || "等待生成"}
                </div>
                <div>
                  Task 关联 run_id（非 Gateway Run）：
                  {task.agent_run_id || "等待生成"}
                </div>
                {task.agent_rationale ? (
                  <div className="mt-2">生成理由：{task.agent_rationale}</div>
                ) : null}
              </div>
            ) : null}
            <div className="flex flex-wrap gap-2">
              <Button
                variant="outline"
                disabled={busy}
                onClick={() => void handleRefreshTask()}
              >
                <RefreshCwIcon className="mr-2 size-4" />
                刷新状态
              </Button>
              <Button
                disabled={busy || task.status !== "HANDOFF_READY"}
                onClick={() => void handleReview("approve")}
              >
                <CheckCircle2Icon className="mr-2 size-4" />
                批准交接
              </Button>
              <Button
                variant="outline"
                disabled={busy || task.status !== "HANDOFF_READY"}
                onClick={() => void handleReview("request_changes")}
              >
                要求修改
              </Button>
              <Button
                variant="outline"
                disabled={
                  busy ||
                  task.status !== "FAILED" ||
                  task.error_code === "PATCH_REQUIRED" ||
                  task.attempt_count >= task.max_attempts
                }
                onClick={() => void handleRetry()}
              >
                重试原任务
              </Button>
              <Button
                variant="outline"
                disabled={
                  busy ||
                  !patchText.trim() ||
                  !(
                    task.status === "CHANGES_REQUESTED" ||
                    (task.status === "FAILED" &&
                      task.error_code === "PATCH_REQUIRED")
                  )
                }
                onClick={() => void handleResubmit()}
              >
                提交修订 Patch
              </Button>
            </div>
            <Input
              value={reviewNote}
              onChange={(event) => setReviewNote(event.target.value)}
              placeholder="审批说明（可选）"
            />
            {report ? (
              <pre className="bg-muted max-h-96 overflow-auto rounded-md p-4 text-xs whitespace-pre-wrap">
                {report}
              </pre>
            ) : null}
          </CardContent>
        </Card>
      ) : null}
    </main>
  );
}
