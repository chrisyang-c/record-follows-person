"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import type { TrendReport } from "@schema";
import { RedFlagBanner } from "@/components/red-flag-banner";
import { Sparkline } from "@/components/sparkline";
import { Chip } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Textarea } from "@/components/ui/field";
import { api, resumeThread, threadState, useApi, type InboxItem, type Resident, type Snapshot } from "@/lib/api";
import { fmtDateTime } from "@/lib/format";
import { typeLabel } from "@/lib/labels";

const NURSE = "nurse_lin";

function TenSecondConfirm({ item, onDone }: { item: InboxItem; onDone: () => void }) {
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
    <Card variant="ai" title={<><span translate="no">{item.patient_id}</span> · {typeLabel(item.interrupt_type)}</>} meta={fmtDateTime(item.updated_at)}>
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

function ResidentTrend({ r }: { r: Resident }) {
  const { data } = useApi<TrendReport>(`/trends/${r.patient_id}`);
  const abnormal = data?.lines.filter((l) => l.is_abnormal) ?? [];
  const top = data ? [...data.lines].sort((a, b) => Number(b.is_abnormal) - Number(a.is_abnormal) || (b.magnitude ?? 0) - (a.magnitude ?? 0)).slice(0, 2) : [];
  const series = data?.series.filter((s) => top.some((t) => t.dimension === s.dimension)) ?? [];
  return (
    <Card
      title={`${r.code_name} · ${r.room}`}
      meta={<Link href={`/record/${r.patient_id}`} className="inline-flex min-h-11 items-center text-primary hover:underline">紀錄 →</Link>}
      className={abnormal.length ? "border-warn" : ""}
    >
      <div className="mb-2 flex flex-wrap gap-1">
        {abnormal.length === 0 && <Chip tone="ok">近 7 天無異常趨勢</Chip>}
        {abnormal.map((l) => (
          <Chip key={l.dimension} tone="warn">{l.summary}</Chip>
        ))}
        {data?.cross_dimension_signal && <Chip tone="danger">{data.cross_dimension_signal}</Chip>}
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {series.map((s) => (
          <Sparkline key={s.dimension} series={s} height={56} />
        ))}
      </div>
    </Card>
  );
}

export default function NurseInbox() {
  const { data: inbox, reload } = useApi<{ items: InboxItem[] }>("/nurse/inbox");
  const { data: residents } = useApi<Resident[]>("/residents");
  const [scanMsg, setScanMsg] = useState<string | null>(null);
  const [scanErr, setScanErr] = useState<string | null>(null);
  const [scanning, setScanning] = useState(false);
  useEffect(() => {
    const id = setInterval(reload, 5000);
    return () => clearInterval(id);
  }, [reload]);
  const scan = async () => {
    setScanning(true);
    setScanErr(null);
    try {
      const r = await api<{ escalated: string[] }>("/worker/scan", { method: "POST" });
      setScanMsg(`逾時掃描：升級 ${r.escalated.length} 件`);
      reload();
    } catch (e) {
      setScanErr((e as Error).message);
    } finally {
      setScanning(false);
    }
  };
  const items = inbox?.items ?? [];
  const red = items.filter((i) => i.red_flag);
  const pathA = items.filter((i) => i.graph === "path_a");
  const tens = items.filter((i) => i.interrupt_type === "nurse_10s_confirm");
  const round = items.filter((i) => i.graph === "round");
  return (
    <div className="space-y-6">
      {red.length > 0 && <RedFlagBanner lines={[`${red[0].patient_id}：`, ...red[0].red_flag_lines]} />}
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-medium">護理站</h1>
        <span className="text-sm text-ink-2" aria-live="polite">待辦 <span className="num">{items.length}</span> · 每 5 秒更新</span>
        <span className="ml-auto flex gap-2">
          <Button variant="outline" onClick={scan} disabled={scanning}>
            {scanning ? "掃描中…" : "立即掃描逾時"}
          </Button>
          <Link href="/nurse/round" className="inline-flex min-h-11 items-center rounded-[10px] border border-line px-4 hover:border-primary hover:text-primary">巡診準備 →</Link>
        </span>
      </div>
      {scanMsg && <p className="text-sm text-ink-2" aria-live="polite">{scanMsg}</p>}
      {scanErr && (
        <p role="alert" className="text-sm text-danger-ink">
          逾時掃描失敗：<span translate="no">{scanErr}</span>
        </p>
      )}

      <section aria-labelledby="h-a">
        <h2 id="h-a" className="mb-2 text-lg font-medium">急症（Path A）</h2>
        {pathA.length === 0 && <p className="text-sm text-ink-2">沒有待處理的急症。</p>}
        <ul className="grid gap-3 md:grid-cols-2">
          {pathA.map((i) => (
            <li key={i.thread_id}>
              <Card variant={i.red_flag ? "red" : "ai"} title={<><span translate="no">{i.patient_id}</span> · {typeLabel(i.interrupt_type)}</>} meta={fmtDateTime(i.updated_at)}>
                <p className="line-clamp-2 text-sm">{i.summary || i.red_flag_lines.join("；")}</p>
                <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-ink-2">
                  {i.deadline && <span>期限 {fmtDateTime(i.deadline)}</span>}
                  {i.escalation_level > 0 && <Chip tone="warn">已升級 {i.escalation_level} 次</Chip>}
                </div>
                <Link href={`/nurse/review/${encodeURIComponent(i.thread_id)}`} className="mt-3 inline-flex min-h-14 w-full items-center justify-center rounded-[10px] bg-primary px-4 text-white hover:bg-primary-hover">
                  開啟審核
                </Link>
              </Card>
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="h-b">
        <h2 id="h-b" className="mb-2 text-lg font-medium">每班 10 秒確認（Path B）</h2>
        {tens.length === 0 && <p className="text-sm text-ink-2">沒有待確認的觀察。照護者送出後會出現在這裡。</p>}
        <ul className="grid gap-3 md:grid-cols-2">
          {tens.map((i) => (
            <li key={i.thread_id}>
              <TenSecondConfirm item={i} onDone={reload} />
            </li>
          ))}
        </ul>
      </section>

      {round.length > 0 && (
        <section aria-labelledby="h-r">
          <h2 id="h-r" className="mb-2 text-lg font-medium">巡診</h2>
          <ul className="space-y-2">
            {round.map((i) => (
              <li key={i.thread_id}>
                <Link href={`/nurse/round?thread=${encodeURIComponent(i.thread_id)}`} className="inline-flex min-h-11 items-center text-primary hover:underline">
                  {typeLabel(i.interrupt_type)} →
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section aria-labelledby="h-t">
        <h2 id="h-t" className="mb-2 text-lg font-medium">異常優先 · 近 7 天趨勢</h2>
        <ul className="grid gap-3 lg:grid-cols-3">
          {(residents ?? []).map((r) => (
            <li key={r.patient_id}>
              <ResidentTrend r={r} />
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
