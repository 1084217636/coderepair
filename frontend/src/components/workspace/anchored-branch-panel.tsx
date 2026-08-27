"use client";

import { GitBranchIcon, SendIcon, XIcon } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  closeAnchoredBranch,
  createAnchoredBranch,
  getAnchoredBranchMessages,
  listAnchoredBranches,
  streamAnchoredBranchRun,
  type AnchorSelection,
  type BranchMessage,
  type BranchRecord,
} from "@/core/anchored-branch";
import { cn } from "@/lib/utils";

interface AnchoredBranchPanelProps {
  mainThreadId: string;
  disabled?: boolean;
}

interface PendingSelection {
  anchor: AnchorSelection;
  x: number;
  y: number;
}

function captureSelection(): PendingSelection | null {
  const selection = window.getSelection();
  const text = selection?.toString().trim() ?? "";
  if (!selection || selection.rangeCount === 0 || !text) return null;
  const range = selection.getRangeAt(0);
  const node = range.commonAncestorContainer;
  const element = node instanceof Element ? node : node.parentElement;
  const answer = element?.closest<HTMLElement>(
    "[data-branch-message-role='assistant']",
  );
  const messageId = answer?.dataset.branchMessageId;
  if (
    !answer ||
    !messageId ||
    !answer.contains(range.startContainer) ||
    !answer.contains(range.endContainer)
  ) {
    return null;
  }

  const prefix = range.cloneRange();
  prefix.selectNodeContents(answer);
  prefix.setEnd(range.startContainer, range.startOffset);
  const startOffset = prefix.toString().length;
  const rect = range.getBoundingClientRect();
  return {
    anchor: {
      text,
      message_id: messageId,
      start_offset: startOffset,
      end_offset: startOffset + range.toString().length,
    },
    x: Math.min(rect.right, window.innerWidth - 150),
    y: Math.max(8, rect.top - 42),
  };
}

export function AnchoredBranchPanel({
  mainThreadId,
  disabled = false,
}: AnchoredBranchPanelProps) {
  const [branches, setBranches] = useState<BranchRecord[]>([]);
  const [branch, setBranch] = useState<BranchRecord | null>(null);
  const [messages, setMessages] = useState<BranchMessage[]>([]);
  const [selection, setSelection] = useState<PendingSelection | null>(null);
  const [question, setQuestion] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const branchesByMessage = useMemo(() => {
    const grouped = new Map<string, BranchRecord[]>();
    for (const item of branches) {
      const id = item.anchor.message_id;
      if (id) grouped.set(id, [...(grouped.get(id) ?? []), item]);
    }
    return grouped;
  }, [branches]);

  useEffect(() => {
    if (disabled) return;
    const handleMouseUp = () =>
      window.setTimeout(() => setSelection(captureSelection()), 0);
    document.addEventListener("mouseup", handleMouseUp);
    return () => document.removeEventListener("mouseup", handleMouseUp);
  }, [disabled]);

  useEffect(() => {
    if (!mainThreadId || disabled) return;
    void listAnchoredBranches(mainThreadId)
      .then((items) => {
        setBranches(items);
        setBranch(
          (current) =>
            current ??
            items.find((item) => item.status === "ACTIVE") ??
            items[0] ??
            null,
        );
      })
      .catch(() => setError("Branch 列表加载失败"));
  }, [disabled, mainThreadId]);

  useEffect(() => {
    if (!branch) {
      setMessages([]);
      return;
    }
    void getAnchoredBranchMessages(branch.branch_id)
      .then(setMessages)
      .catch(() => setError("Branch 历史加载失败"));
  }, [branch]);

  useEffect(() => {
    document
      .querySelectorAll("[data-anchored-branch-marker]")
      .forEach((marker) => marker.remove());
    for (const [messageId, items] of branchesByMessage) {
      const answer = [
        ...document.querySelectorAll<HTMLElement>("[data-branch-message-id]"),
      ].find((item) => item.dataset.branchMessageId === messageId);
      if (!answer) continue;
      const marker = document.createElement("button");
      marker.type = "button";
      marker.dataset.anchoredBranchMarker = "true";
      marker.textContent = `⑂ ${items.length}`;
      marker.className =
        "absolute right-1 top-1 z-20 rounded-full border bg-background px-2 py-0.5 text-xs text-muted-foreground shadow-sm";
      marker.title = `${items.length} 个局部分支`;
      marker.onclick = () => setBranch(items[0] ?? null);
      answer.appendChild(marker);
    }
    return () =>
      document
        .querySelectorAll("[data-anchored-branch-marker]")
        .forEach((marker) => marker.remove());
  }, [branchesByMessage]);

  async function handleCreate() {
    if (!selection) return;
    setBusy(true);
    setError("");
    try {
      const created = await createAnchoredBranch(
        mainThreadId,
        selection.anchor,
      );
      setBranches((items) => [created, ...items]);
      setBranch(created);
      setMessages([]);
      setSelection(null);
      window.getSelection()?.removeAllRanges();
    } catch (nextError) {
      setError(
        nextError instanceof Error ? nextError.message : "Branch 创建失败",
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleAsk() {
    const current = branch;
    const text = question.trim();
    if (current?.status !== "ACTIVE" || !text) return;
    setBusy(true);
    setError("");
    const responseId = `stream-${Date.now()}`;
    setMessages((items) => [
      ...items,
      { id: `local-${Date.now()}`, role: "human", text },
      { id: responseId, role: "ai", text: "" },
    ]);
    setQuestion("");
    try {
      await streamAnchoredBranchRun(current.branch_id, text, (chunk) =>
        setMessages((items) =>
          items.map((item) =>
            item.id === responseId
              ? { ...item, text: item.text + chunk }
              : item,
          ),
        ),
      );
    } catch (nextError) {
      setError(
        nextError instanceof Error ? nextError.message : "Branch 对话失败",
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleClose() {
    if (!branch || branch.status === "CLOSED") return;
    setBusy(true);
    try {
      const closed = await closeAnchoredBranch(branch.branch_id);
      setBranches((items) =>
        items.map((item) =>
          item.branch_id === closed.branch_id ? closed : item,
        ),
      );
      setBranch(null);
    } catch (nextError) {
      setError(
        nextError instanceof Error ? nextError.message : "Branch 关闭失败",
      );
    } finally {
      setBusy(false);
    }
  }

  if (disabled || !mainThreadId) return null;

  return (
    <>
      {selection && (
        <Button
          className="fixed z-50 shadow-lg"
          size="sm"
          style={{ left: selection.x, top: selection.y }}
          disabled={busy}
          onMouseDown={(event) => event.preventDefault()}
          onClick={() => void handleCreate()}
        >
          <GitBranchIcon className="size-4" /> Ask in Branch
        </Button>
      )}
      <aside
        className={cn(
          "bg-background flex min-h-0 w-[26rem] shrink-0 flex-col border-l pt-12 max-lg:fixed max-lg:top-0 max-lg:right-0 max-lg:bottom-0 max-lg:z-40 max-lg:w-[min(26rem,92vw)]",
          !branch && "max-lg:hidden",
        )}
      >
        <header className="flex items-center justify-between border-b px-4 py-3">
          <div className="flex items-center gap-2 text-sm font-medium">
            <GitBranchIcon className="size-4" /> Branch Panel
          </div>
          {branch && (
            <Button
              size="icon-sm"
              variant="ghost"
              disabled={busy || branch.status === "CLOSED"}
              onClick={() => void handleClose()}
              title="关闭 Branch；不会改动主线"
            >
              <XIcon className="size-4" />
            </Button>
          )}
        </header>

        <div className="border-b p-3">
          <select
            className="border-input bg-background w-full rounded-md border px-2 py-2 text-sm"
            value={branch?.branch_id ?? ""}
            onChange={(event) =>
              setBranch(
                branches.find(
                  (item) => item.branch_id === event.target.value,
                ) ?? null,
              )
            }
          >
            <option value="">选择回答文字后创建 Branch</option>
            {branches.map((item) => (
              <option key={item.branch_id} value={item.branch_id}>
                {item.status === "CLOSED" ? "已关闭" : "讨论中"} ·{" "}
                {item.anchor.text.slice(0, 36)}
              </option>
            ))}
          </select>
          {branch && (
            <div className="bg-muted mt-3 rounded-md p-3 text-xs">
              <div className="text-muted-foreground mb-1">
                Anchor · {branch.anchor.message_id}
              </div>
              <div className="max-h-28 overflow-y-auto whitespace-pre-wrap">
                {branch.anchor.text}
              </div>
            </div>
          )}
        </div>

        <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-3">
          {messages.map((message) => (
            <div
              key={message.id}
              className={cn(
                "rounded-lg px-3 py-2 text-sm whitespace-pre-wrap",
                message.role === "human" || message.role === "user"
                  ? "bg-primary text-primary-foreground ml-8"
                  : "bg-muted mr-4",
              )}
            >
              {message.text || (busy ? "正在回答…" : "")}
            </div>
          ))}
          {!branch && (
            <p className="text-muted-foreground p-3 text-sm">
              在左侧 AI 回答中选中一句、一段或代码片段，然后点击 Ask in Branch。
            </p>
          )}
        </div>

        {branch?.status === "ACTIVE" && (
          <div className="space-y-2 border-t p-3">
            <Textarea
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="只在当前 Branch 中继续追问"
            />
            <Button
              className="w-full"
              size="sm"
              disabled={busy || !question.trim()}
              onClick={() => void handleAsk()}
            >
              <SendIcon className="size-4" /> 发送到 Branch
            </Button>
          </div>
        )}
        {branch?.status === "CLOSED" && (
          <p className="text-muted-foreground border-t p-3 text-xs">
            该 Branch 已关闭。主线内容和位置没有变化。
          </p>
        )}
        {error && (
          <p className="text-destructive border-t p-3 text-xs">{error}</p>
        )}
      </aside>
    </>
  );
}
