"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Textarea } from "@/components/ui/field";
import { resumeThread, threadState, type InboxItem, type Snapshot } from "@/lib/api";
import { fmtDateTime } from "@/lib/format";
import { typeLabel } from "@/lib/labels";

const NURSE = "nurse_lin";

/** 每班 10 秒確認：住民、S、A，接受／改一句／退回（CLAUDE.md §4 ◇nurse_10s_confirm）。 */
export function TenSecondConfirm({ item, onDone, title }: { item: Pick<InboxItem, "thread_id" | "interrupt_type" | "red_flag_lines" | "updated_at" | "patient_id" | "code_name">; onDone: () => void; title?: React.ReactNode }) {
  const [snap, setSnap] = useState<Snapshot | null>(null);
  const [mode, setMode] = useState<"idle" | "edit" | "return">("idle");
  const [a, setA] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    threadState(item.thread_id).then(setSnap).catch((e: Error) => setErr(e.message));
  }, [item.thread_id]);
  const ms = (snap?.interrupt?.minimal_sbar ?? null) as { s: string; a_change_vs_baseline: string } | null;
  const act = async (payload: Record<string, unknown>) => {
    setBusy(true);
    setErr(null);
    try {
      await resumeThread(item.thread_id, { nurse_id: NURSE, ...payload });
      onDone();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Card variant="ai" title={title ?? <>{item.code_name ?? item.patient_id} · {typeLabel(item.interrupt_type)}</>} meta={fmtDateTime(item.updated_at)}>
      {!ms && !err && <p className="text-sm text-ink-2">Loading…</p>}
      {ms && (
        <div className="space-y-1 text-sm">
          <p><span className="mr-1 rounded bg-bg px-1 text-xs text-ink-2">S</span>{ms.s}</p>
          <p><span className="mr-1 rounded bg-bg px-1 text-xs text-ink-2">A</span>{ms.a_change_vs_baseline}</p>
          {item.red_flag_lines.length > 0 && <p className="text-warn-ink">{item.red_flag_lines.join("；")}</p>}
        </div>
      )}
      {mode === "edit" && (
        <Textarea name="edited_a" aria-label="改一句 A（與基線比的變化）" value={a} onChange={(e) => setA(e.target.value)} placeholder="例如：進食量較平常少一半，已持續三天…" className="mt-2 min-h-14 text-sm" autoComplete="off" />
      )}
      {mode === "return" && (
        <Textarea name="return_reason" aria-label="退回原因" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="例如：請補充喝水量…" className="mt-2 min-h-14 text-sm" autoComplete="off" />
      )}
      <div className="mt-3 flex flex-wrap gap-2">
        {mode === "idle" && (
          <>
            <Button variant="ok" size="lg" className="min-w-40 flex-1" onClick={() => act({ action: "accept" })} disabled={busy || !ms}>
              {busy ? "確認中…" : "接受"}
            </Button>
            <Button variant="outline" size="lg" onClick={() => setMode("edit")} disabled={busy || !ms}>改一句</Button>
            <Button variant="ghost" size="lg" onClick={() => setMode("return")} disabled={busy || !ms}>退回</Button>
          </>
        )}
        {mode === "edit" && (
          <>
            <Button variant="ok" size="lg" className="flex-1" onClick={() => act({ action: "edit", edited_a: a })} disabled={busy || !a.trim()}>{busy ? "確認中…" : "修改並確認"}</Button>
            <Button variant="ghost" size="lg" onClick={() => setMode("idle")}>取消</Button>
          </>
        )}
        {mode === "return" && (
          <>
            <Button variant="danger" size="lg" className="flex-1" onClick={() => act({ action: "return", return_reason: reason, caregiver_addendum: reason })} disabled={busy || !reason.trim()}>{busy ? "退回中…" : "退回照護者"}</Button>
            <Button variant="ghost" size="lg" onClick={() => setMode("idle")}>取消</Button>
          </>
        )}
      </div>
      {err && <p role="alert" className="mt-2 text-sm text-danger-ink">{err}</p>}
    </Card>
  );
}
