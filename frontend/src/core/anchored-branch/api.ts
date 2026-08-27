import { fetch } from "@/core/api/fetcher";
import { getBackendBaseURL } from "@/core/config";

import type { AnchorSelection, BranchMessage, BranchRecord } from "./types";

const base = () => `${getBackendBaseURL()}/api/anchored-branches`;

async function json<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const body = (await response.json()) as { detail?: string };
      detail = body.detail ?? detail;
    } catch {
      // Keep the status-based error when the gateway returns plain text.
    }
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

export async function createAnchoredBranch(
  mainThreadId: string,
  anchor: AnchorSelection,
): Promise<BranchRecord> {
  return json(
    await fetch(base(), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ main_thread_id: mainThreadId, anchor }),
    }),
  );
}

export async function listAnchoredBranches(
  mainThreadId: string,
): Promise<BranchRecord[]> {
  return json(
    await fetch(`${base()}/main/${encodeURIComponent(mainThreadId)}`),
  );
}

export async function getAnchoredBranchMessages(
  branchId: string,
): Promise<BranchMessage[]> {
  return json(
    await fetch(`${base()}/${encodeURIComponent(branchId)}/messages`),
  );
}

export async function closeAnchoredBranch(
  branchId: string,
): Promise<BranchRecord> {
  return json(
    await fetch(`${base()}/${encodeURIComponent(branchId)}/close`, {
      method: "POST",
    }),
  );
}

function textFromEvent(event: unknown): string {
  const contentOf = (value: unknown): string => {
    if (typeof value === "string") return value;
    if (Array.isArray(value)) return value.map(contentOf).join("");
    if (typeof value !== "object" || value === null) return "";
    const item = value as {
      content?: unknown;
      text?: unknown;
      delta?: unknown;
    };
    return contentOf(item.content ?? item.text ?? item.delta);
  };
  if (Array.isArray(event)) return contentOf(event[0]);
  if (typeof event !== "object" || event === null) return "";
  const data = event as { data?: unknown; content?: unknown; text?: unknown };
  return contentOf(data.data ?? data.content ?? data.text);
}

export async function streamAnchoredBranchRun(
  branchId: string,
  question: string,
  onText: (text: string) => void,
): Promise<void> {
  const response = await fetch(
    `${base()}/${encodeURIComponent(branchId)}/runs/stream`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        input: { messages: [{ role: "human", content: question }] },
        stream_mode: ["messages-tuple", "values"],
        on_disconnect: "continue",
      }),
    },
  );
  if (!response.ok || !response.body) {
    throw new Error(`Branch stream failed (${response.status})`);
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const next = await reader.read();
    buffer += decoder.decode(next.value, { stream: !next.done });
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";
    for (const frame of frames) {
      const dataLine = frame
        .split("\n")
        .find((line) => line.startsWith("data: "));
      if (!dataLine) continue;
      try {
        const eventText = textFromEvent(JSON.parse(dataLine.slice(6)));
        if (eventText) onText(eventText);
      } catch {
        // Ignore keep-alives and non-JSON proxy frames.
      }
    }
    if (next.done) break;
  }
}
