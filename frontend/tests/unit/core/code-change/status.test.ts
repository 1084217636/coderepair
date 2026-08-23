import { describe, expect, it } from "@rstest/core";

import { statusTone } from "@/core/code-change/status";

describe("statusTone", () => {
  it("groups active worker states", () => {
    expect(statusTone("QUEUED")).toBe("running");
    expect(statusTone("PATCH_RECEIVED")).toBe("running");
    expect(statusTone("RUNNING_TESTS")).toBe("running");
  });

  it("separates review, success and failure states", () => {
    expect(statusTone("PATCH_REQUIRED")).toBe("warning");
    expect(statusTone("HANDOFF_READY")).toBe("success");
    expect(statusTone("FAILED")).toBe("error");
  });
});
