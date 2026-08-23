export type StatusTone =
  | "neutral"
  | "running"
  | "success"
  | "warning"
  | "error";

const RUNNING = new Set([
  "QUEUED",
  "PLANNING",
  "RETRIEVING_CONTEXT",
  "PATCH_RECEIVED",
  "GENERATING_PATCH",
  "VALIDATING_PATCH",
  "APPLYING_PATCH",
  "RUNNING_TESTS",
]);

export function statusTone(status: string): StatusTone {
  if (RUNNING.has(status)) return "running";
  if (["HANDOFF_READY", "APPROVED", "PR_CREATED"].includes(status)) {
    return "success";
  }
  if (["REVIEWING", "CHANGES_REQUESTED", "PATCH_REQUIRED"].includes(status)) {
    return "warning";
  }
  if (["FAILED", "ROLLED_BACK"].includes(status)) return "error";
  return "neutral";
}
