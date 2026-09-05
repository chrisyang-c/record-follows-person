"use client";

import { useEffect, useState } from "react";
import { Chip } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Textarea } from "@/components/ui/field";
import { resumeThread, threadState, type InboxItem, type Snapshot } from "@/lib/api";
import { fmtDateTime } from "@/lib/format";
import { typeLabel } from "@/lib/labels";

const NURSE = "nurse_lin";

/**
 * 每班 10 秒確認（◇nurse_10s_confirm）：住民、S 一行、A 一行，三鍵「確認／改一句／退回」。
 * 改一句與退回都就地展開輸入，不鎖其他鍵（docs/UIUX_OMNI_TWIN.md §4.4；KNOWN_ISSUES #21）。
 * 超時升級：卡片 --warn 邊，標「已升級至護理長」。
 */
export function TenSecondConfirm({ item, onDone, title }: { item: Pick<InboxItem, "thread_id" | "interrupt_type" | "red_flag_lines" | "updated_at" | "patient_id" | "code_name"> & { escalation_level?: number }; onDone: () => void; title?: React.ReactNode }) {
  const [snap, setSnap] = useState<Snapshot | null>(null);
  const [editing, setEditing] = useState(false);
  const [returning, setReturning] = useState(false);
  const [a, setA] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState<"accept" | "return" | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    threadState(item.thread_id).then(setSnap).catch((e: Error) => setErr(e.message));
  }, [item.thread_id]);
  const ms = (snap?.interrupt?.minimal_sbar ?? null) as { s: string; a_change_vs_baseline: string } | null;
  const escalated = (item.escalation_level ?? 0) > 0;
  const act = async (kind: "accept" | "return", payload: Record<string, unknown>) => {
    setBusy(kind);
    setErr(null);
    try {
      await resumeThread(item.thread_id, { nurse_id: NURSE, ...payload });
      onDone();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(null);
    }
  };
  const confirm = () => act("accept", editing && a.trim() ? { action: "edit", edited_a: a.trim() } : { action: "accept" });
  return (
    <Card variant="ai" className={escalated ? "border-warn" : undefined} title={title ?? <>{item.code_name ?? item.patient_id} · {typeLabel(item.interrupt_type)}</>} meta={<>{escalated && <Chip tone="warn" className="mr-2">已升級至護理長</Chip>}{fmtDateTime(item.updated_at)}</>}>
      {!ms && !err && <p className="text-sm text-ink-2">Loading…</p>}
      {ms && (
        <div className="space-y-1 text-sm">
          <p className="truncate" title={ms.s}><span className="label-caps mr-2">S</span>{ms.s}</p>
          <p className="truncate" title={ms.a_change_vs_baseline}><span className="label-caps mr-2">A</span>{ms.a_change_vs_baseline}</p>
          {item.red_flag_lines.length > 0 && <p className="text-warn-ink">{item.red_flag_lines.join("；")}</p>}
        </div>
      )}
      {editing && (
        <div className="fade-in mt-2">
          <label htmlFor={`a-${item.thread_id}`} className="label-caps">改一句 A（與基線比的變化）</label>
          <Textarea id={`a-${item.thread_id}`} name="edited_a" value={a} onChange={(e) => setA(e.target.value)} placeholder="例如：進食量較平常少一半，已持續三天…" className="mt-1 min-h-14 text-sm" autoComplete="off" autoFocus />
        </div>
      )}
      {returning && (
        <div className="fade-in mt-2">
          <label htmlFor={`r-${item.thread_id}`} className="label-caps">退回原因（照護者會看到）</label>
          <Textarea id={`r-${item.thread_id}`} name="return_reason" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="例如：請補充喝水量…" className="mt-1 min-h-14 text-sm" autoComplete="off" autoFocus />
        </div>
      )}
      <div className="mt-3 flex flex-wrap gap-2">
        <Button variant="ok" size="lg" className="min-w-40 flex-1" onClick={confirm} disabled={!ms || busy !== null || (editing && !a.trim())}>
          {busy === "accept" ? "確認中…" : editing ? "修改並確認" : "確認"}
        </Button>
        <Button variant="secondary" size="lg" aria-pressed={editing} onClick={() => setEditing((v) => !v)} disabled={!ms}>改一句</Button>
        <Button
          variant="danger"
          size="lg"
          aria-pressed={returning}
          onClick={() => (returning && reason.trim() ? act("return", { action: "return", return_reason: reason.trim(), caregiver_addendum: reason.trim() }) : setReturning((v) => !v))}
          disabled={!ms || busy !== null}
        >
          {busy === "return" ? "退回中…" : returning ? (reason.trim() ? "退回照護者" : "退回（先填原因）") : "退回"}
        </Button>
      </div>
      {err && <p role="alert" className="mt-2 text-sm text-danger-ink">{err}</p>}
    </Card>
  );
}
