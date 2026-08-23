import { fetch } from "@/core/api/fetcher";
import { getBackendBaseURL } from "@/core/config";

import {
  type CodeChangeProject,
  type CodeChangeTask,
  type CreateProjectInput,
  type CreateTaskInput,
  type ReviewTaskInput,
} from "./types";

const codeChangeBase = () => `${getBackendBaseURL()}/api/code-change`;

async function readJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) message = body.detail;
    } catch {
      // The gateway may return a plain-text proxy error. Keep the status-based
      // message so the page remains useful while the backend is unavailable.
    }
    throw new Error(message);
  }
  return (await response.json()) as T;
}

export async function listCodeChangeProjects(): Promise<CodeChangeProject[]> {
  const response = await fetch(`${codeChangeBase()}/projects`);
  const body = await readJson<{ projects: CodeChangeProject[] }>(response);
  return body.projects;
}

export async function createCodeChangeProject(
  input: CreateProjectInput,
): Promise<CodeChangeProject> {
  const response = await fetch(`${codeChangeBase()}/projects`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  return readJson<CodeChangeProject>(response);
}

export async function createCodeChangeTask(
  projectId: string,
  input: CreateTaskInput,
): Promise<CodeChangeTask> {
  const response = await fetch(
    `${codeChangeBase()}/projects/${encodeURIComponent(projectId)}/tasks`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    },
  );
  return readJson<CodeChangeTask>(response);
}

export async function listCodeChangeTasks(
  projectId: string,
): Promise<CodeChangeTask[]> {
  const response = await fetch(
    `${codeChangeBase()}/projects/${encodeURIComponent(projectId)}/tasks`,
  );
  const body = await readJson<{ tasks: CodeChangeTask[] }>(response);
  return body.tasks;
}

export async function getCodeChangeTask(
  projectId: string,
  taskId: string,
): Promise<CodeChangeTask> {
  const response = await fetch(
    `${codeChangeBase()}/projects/${encodeURIComponent(projectId)}/tasks/${encodeURIComponent(taskId)}`,
  );
  return readJson<CodeChangeTask>(response);
}

export async function reviewCodeChangeTask(
  projectId: string,
  taskId: string,
  input: ReviewTaskInput,
): Promise<CodeChangeTask> {
  const response = await fetch(
    `${codeChangeBase()}/projects/${encodeURIComponent(projectId)}/tasks/${encodeURIComponent(taskId)}/review`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    },
  );
  return readJson<CodeChangeTask>(response);
}

export async function resubmitCodeChangeTask(
  projectId: string,
  taskId: string,
  patchText: string,
): Promise<CodeChangeTask> {
  const response = await fetch(
    `${codeChangeBase()}/projects/${encodeURIComponent(projectId)}/tasks/${encodeURIComponent(taskId)}/resubmit`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ patch_text: patchText }),
    },
  );
  return readJson<CodeChangeTask>(response);
}

export async function retryCodeChangeTask(
  projectId: string,
  taskId: string,
): Promise<CodeChangeTask> {
  const response = await fetch(
    `${codeChangeBase()}/projects/${encodeURIComponent(projectId)}/tasks/${encodeURIComponent(taskId)}/retry`,
    { method: "POST" },
  );
  return readJson<CodeChangeTask>(response);
}

export async function getCodeChangeReport(
  projectId: string,
  taskId: string,
): Promise<string> {
  const response = await fetch(
    `${codeChangeBase()}/projects/${encodeURIComponent(projectId)}/tasks/${encodeURIComponent(taskId)}/report`,
  );
  if (!response.ok) throw new Error(`Report unavailable (${response.status})`);
  return response.text();
}
