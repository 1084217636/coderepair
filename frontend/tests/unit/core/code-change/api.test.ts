import { beforeEach, describe, expect, it, rs } from "@rstest/core";

rs.mock("@/core/api/fetcher", () => ({
  fetch: rs.fn(),
}));

rs.mock("@/core/config", () => ({
  getBackendBaseURL: () => "/backend",
}));

import { fetch as fetcher } from "@/core/api/fetcher";
import {
  createCodeChangeTask,
  listCodeChangeTasks,
  retryCodeChangeTask,
} from "@/core/code-change/api";

const mockedFetch = rs.mocked(fetcher);

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

beforeEach(() => {
  mockedFetch.mockReset();
});

describe("code-change api", () => {
  it("lists owner-scoped project tasks", async () => {
    mockedFetch.mockResolvedValueOnce(
      jsonResponse({ tasks: [{ task_id: "task-1" }] }),
    );

    await expect(listCodeChangeTasks("demo project")).resolves.toEqual([
      { task_id: "task-1" },
    ]);
    expect(mockedFetch).toHaveBeenCalledWith(
      "/backend/api/code-change/projects/demo%20project/tasks",
    );
  });

  it("submits explicit Agent mode without the removed run_now field", async () => {
    mockedFetch.mockResolvedValueOnce(jsonResponse({ task_id: "task-1" }));

    await createCodeChangeTask("demo", {
      requirement: "fix health",
      patch_mode: "agent",
      agent_model_name: "default-model",
    });

    const request = mockedFetch.mock.calls[0]![1]!;
    expect(JSON.parse(request.body as string)).toEqual({
      requirement: "fix health",
      patch_mode: "agent",
      agent_model_name: "default-model",
    });
    expect(request.body).not.toContain("run_now");
  });

  it("uses the dedicated retry endpoint without a browser test command", async () => {
    mockedFetch.mockResolvedValueOnce(
      jsonResponse({ task_id: "task-1", status: "QUEUED" }),
    );

    await retryCodeChangeTask("demo", "task-1");

    expect(mockedFetch).toHaveBeenCalledWith(
      "/backend/api/code-change/projects/demo/tasks/task-1/retry",
      { method: "POST" },
    );
  });
});
