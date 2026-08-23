"use client";

import { GitBranchIcon, SendIcon } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import {
  applyBranchDecision,
  createAnchoredBranch,
  createBranchDecision,
  listAnchoredBranches,
  streamAnchoredBranchRun,
  type BranchRecord,
} from "@/core/anchored-branch";

interface AnchoredBranchPanelProps {
  mainThreadId: string;
  disabled?: boolean;
}

export function AnchoredBranchPanel({
  mainThreadId,
  disabled = false,
}: AnchoredBranchPanelProps) {
  const [branches, setBranches] = useState<BranchRecord[]>([]);
  const [branch, setBranch] = useState<BranchRecord | null>(null);
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [decision, setDecision] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!mainThreadId || disabled) return;
    void listAnchoredBranches(mainThreadId)
      .then((items) => {
        setBranches(items);
        setBranch(items[0] ?? null);
      })
      .catch(() => setError("Branch 列表加载失败"));
  }, [disabled, mainThreadId]);

  async function handleCreate() {
    const text = window.getSelection()?.toString().trim() ?? "";
    if (!text) {
      setError("请先在回答中选择一段文字");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const created = await createAnchoredBranch(mainThreadId, { text });
      setBranches((items) => [created, ...items]);
      setBranch(created);
      setAnswer("");
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Branch 创建失败");
    } finally {
      setBusy(false);
    }
  }

  async function handleAsk() {
    if (!branch || !question.trim()) return;
    setBusy(true);
    setError("");
    setAnswer("");
    try {
      await streamAnchoredBranchRun(branch.branch_id, question.trim(), (text) =>
        setAnswer((current) => current + text),
      );
      setQuestion("");
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Branch 对话失败");
    } finally {
      setBusy(false);
    }
  }

  async function handleDecision() {
    if (!branch || !decision.trim()) return;
    setBusy(true);
    setError("");
    try {
      await createBranchDecision(branch.branch_id, {
        summary: decision.trim(),
        actions: [],
        constraints: [],
        rationale: answer,
      });
      const applied = await applyBranchDecision(branch.branch_id);
      setBranch(applied);
      setBranches((items) =>
        items.map((item) => (item.branch_id === applied.branch_id ? applied : item)),
      );
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Decision 合并失败");
    } finally {
      setBusy(false);
    }
  }

  if (disabled || !mainThreadId) return null;

  return (
    <Card className="bg-background/95 absolute top-14 right-4 z-30 w-[min(28rem,calc(100vw-2rem))] shadow-lg">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-sm">
          <GitBranchIcon className="size-4" />
          Anchored Branch
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <Button size="sm" variant="outline" disabled={busy} onClick={() => void handleCreate()}>
          从当前选择创建 Branch
        </Button>
        {branches.length > 0 && (
          <select
            className="border-input bg-background w-full rounded-md border px-2 py-2"
            value={branch?.branch_id ?? ""}
            onChange={(event) => setBranch(branches.find((item) => item.branch_id === event.target.value) ?? null)}
          >
            {branches.map((item) => (
              <option key={item.branch_id} value={item.branch_id}>
                {item.status} · {item.anchor.text.slice(0, 36)}
              </option>
            ))}
          </select>
        )}
        {branch && (
          <>
            <p className="text-muted-foreground rounded-md bg-muted p-2 text-xs">“{branch.anchor.text}”</p>
            <Textarea value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="针对这段回答继续追问" />
            <Button size="sm" disabled={busy || !question.trim()} onClick={() => void handleAsk()}>
              <SendIcon /> 发送到 Branch
            </Button>
            {answer && <div className="max-h-40 overflow-y-auto rounded-md border p-2 whitespace-pre-wrap">{answer}</div>}
            {answer && !branch.decision && (
              <>
                <Textarea value={decision} onChange={(event) => setDecision(event.target.value)} placeholder="Branch Decision：要合并回主任务的结论" />
                <Button size="sm" variant="secondary" disabled={busy || !decision.trim()} onClick={() => void handleDecision()}>
                  Apply to Main
                </Button>
              </>
            )}
          </>
        )}
        {error && <p className="text-destructive text-xs">{error}</p>}
      </CardContent>
    </Card>
  );
}
