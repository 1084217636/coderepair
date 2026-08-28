import { beforeEach, describe, expect, it, rs } from "@rstest/core";

rs.mock("@/core/api/fetcher", () => ({
  fetch: rs.fn(),
}));

rs.mock("@/core/config", () => ({
  getBackendBaseURL: () => "/backend",
}));

import {
  closeAnchoredBranch,
  createAnchoredBranch,
  getAnchoredBranchMessages,
} from "@/core/anchored-branch/api";
import { fetch as fetcher } from "@/core/api/fetcher";

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

describe("anchored branch api", () => {
  it("creates a branch with a message-local anchor", async () => {
    mockedFetch.mockResolvedValueOnce(jsonResponse({ branch_id: "branch-1" }));

    await createAnchoredBranch("main-1", {
      text: "selected fragment",
      message_id: "answer-1",
      start_offset: 10,
      end_offset: 27,
    });

    const request = mockedFetch.mock.calls[0]![1]!;
    expect(JSON.parse(request.body as string)).toEqual({
      main_thread_id: "main-1",
      anchor: {
        text: "selected fragment",
        message_id: "answer-1",
        start_offset: 10,
        end_offset: 27,
      },
    });
  });

  it("optionally links a registered code project for branch retrieval", async () => {
    mockedFetch.mockResolvedValueOnce(jsonResponse({ branch_id: "branch-2" }));

    await createAnchoredBranch(
      "main-1",
      { text: "validate token", message_id: "answer-1" },
      "auth-project",
    );

    const request = mockedFetch.mock.calls[0]![1]!;
    expect(JSON.parse(request.body as string)).toEqual({
      main_thread_id: "main-1",
      anchor: { text: "validate token", message_id: "answer-1" },
      code_change_project_id: "auth-project",
    });
  });

  it("loads child messages and closes without an apply payload", async () => {
    mockedFetch
      .mockResolvedValueOnce(
        jsonResponse([{ id: "m1", role: "human", text: "why?" }]),
      )
      .mockResolvedValueOnce(
        jsonResponse({ branch_id: "branch-1", status: "CLOSED" }),
      );

    await expect(getAnchoredBranchMessages("branch-1")).resolves.toHaveLength(
      1,
    );
    await closeAnchoredBranch("branch-1");

    expect(mockedFetch).toHaveBeenNthCalledWith(
      1,
      "/backend/api/anchored-branches/branch-1/messages",
    );
    expect(mockedFetch).toHaveBeenNthCalledWith(
      2,
      "/backend/api/anchored-branches/branch-1/close",
      {
        method: "POST",
      },
    );
  });
});
