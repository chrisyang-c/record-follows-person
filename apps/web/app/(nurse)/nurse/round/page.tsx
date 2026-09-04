"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import type { BaselineProposal, RoundPage } from "@schema";
import { DIMENSION_LABELS } from "@schema";
import { RoundPageView } from "@/components/round-page-view";
import { Chip } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input, Label, Textarea } from "@/components/ui/field";
import { resumeThread, startRound, threadState, type Snapshot } from "@/lib/api";
import { typeLabel } from "@/lib/labels";

type Roster = { patient_id: string; code_name: string; room: string; abnormal_count: number; abnormal_dimensions: string[]; incident_count: number; reason: string }[];

/** 「填入示範醫囑」帶入的完整文字 */
const ORDER_FULL: Record<string, string> = {
  P001: "飲食：每餐記錄進食量，喝水每天 6 杯；新藥 Mirtazapine 7.5 mg，睡前。夜間醒來記錄時間與原因。",
  P002: "壓傷：維持每 2 小時翻身，尾椎敷料改為每兩日更換；飲食：糖尿病餐維持。",
  P003: "疼痛：右膝評估後止痛藥調整；活動：每天陪走廊走一趟；咳嗽：觀察痰量與顏色。",
};
/** placeholder 只給提示，以「…」收尾，不像已填好的內容 */
const ORDER_EXAMPLES: Record<string, string> = {
  P001: "飲食：每餐記錄進食量…",
  P002: "壓傷：維持每 2 小時翻身…",
  P003: "疼痛：右膝評估後止痛藥調整…",
};

const PILL = "inline-flex min-h-11 items-center rounded-full border border-line px-3 hover:border-primary hover:text-primary";

function RoundInner() {
  const params = useSearchParams();
  const router = useRouter();
  const tid = params.get("thread");
  const [snap, setSnap] = useState<Snapshot | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [head, setHead] = useState("head_nurse_chen");
  const [nurse, setNurse] = useState("nurse_lin");
  const [selected, setSelected] = useState<Record<string, boolean>>({});
  const [orders, setOrders] = useState<Record<string, string>>({});
  const [orderHint, setOrderHint] = useState<string | null>(null);
  const [doctor, setDoctor] = useState("dr_wu");
  const [accepted, setAccepted] = useState<Record<string, boolean>>({});
  const [open, setOpen] = useState<string | null>(null);

  useEffect(() => {
    if (!tid) return;
    let alive = true;
    threadState(tid).then((s) => alive && setSnap(s)).catch((e: Error) => alive && setErr(e.message));
    return () => {
      alive = false;
    };
  }, [tid]);

  const begin = async () => {
    setBusy(true);
    setErr(null);
    try {
      const s = await startRound();
      router.replace(`/nurse/round?thread=${encodeURIComponent(s.thread_id)}`);
      setSnap(s);
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const resume = async (payload: Record<string, unknown>) => {
    if (!tid) return;
    setBusy(true);
    setErr(null);
    try {
      setSnap(await resumeThread(tid, payload));
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const it = snap?.interrupt;
  const type = it?.type;
  const roster = ((it?.roster ?? snap?.values.roster ?? []) as Roster);
  const pages = ((it?.round_pages ?? snap?.values.round_pages ?? []) as RoundPage[]);
  const published = (snap?.values.published ?? []) as string[];
  const proposals = ((it?.proposals ?? []) as BaselineProposal[]);
  const isSel = (pid: string) => selected[pid] ?? true;
  const openPage = open ? pages.find((p) => p.patient_id === open) : undefined;

  // 送出鍵不鎖：沒有任何醫囑時就地提示，焦點放到第一個醫囑欄
  const submitOrders = () => {
    const list = Object.entries(orders).filter(([, t]) => t.trim());
    if (!list.length) {
      setOrderHint("請至少輸入一位住民的醫囑。");
      document.getElementById(`ord-${roster[0]?.patient_id}`)?.focus();
      return;
    }
    setOrderHint(null);
    resume({ nurse_id: nurse, orders: list.map(([patient_id, text]) => ({ patient_id, doctor, text })) });
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <h1 className="text-2xl font-medium">巡診前準備</h1>
        {snap && <Chip tone={snap.status === "done" ? "ok" : "primary"}>{snap.status === "done" ? "完成" : typeLabel(type)}</Chip>}
        {tid && <code className="text-xs text-ink-2" translate="no">{tid}</code>}
      </div>

      {!tid && !snap && (
        <Card title="開始" headingLevel={2}>
          <p className="text-sm text-ink-2">roster_agent 掃全院 → trend_analyzer ×N → familiarization_writer ×N → 護理長增刪名單。</p>
          <Button size="lg" className="mt-3" onClick={begin} disabled={busy}>{busy ? "產生中…" : "產生本月名單與 RoundPage"}</Button>
        </Card>
      )}
      {tid && !snap && !err && <p className="text-ink-2">Loading…</p>}

      {type === "head_nurse_edit_list" && (
        <>
          <Card title="這個月該看誰（異常優先）" headingLevel={2}>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[560px] text-sm">
                <thead className="text-left text-ink-2">
                  <tr><th className="py-1">看</th><th>住民</th><th>異常維度</th><th>事故</th><th>理由</th><th>頁</th></tr>
                </thead>
                <tbody>
                  {roster.map((r) => (
                    <tr key={r.patient_id} className="border-t border-line">
                      <td className="py-2">
                        <label className="flex min-h-11 cursor-pointer items-center gap-2">
                          <input type="checkbox" name={`sel-${r.patient_id}`} checked={isSel(r.patient_id)} onChange={(e) => setSelected((s) => ({ ...s, [r.patient_id]: e.target.checked }))} className="size-5 accent-[var(--primary)]" />
                          <span className="sr-only">納入 {r.code_name}</span>
                        </label>
                      </td>
                      <td>{r.code_name} · {r.room}</td>
                      <td><span className="num">{r.abnormal_count}</span> {r.abnormal_dimensions.join("、")}</td>
                      <td className="num">{r.incident_count}</td>
                      <td className="max-w-64 truncate">{r.reason}</td>
                      <td><Button variant="ghost" onClick={() => setOpen(open === r.patient_id ? null : r.patient_id)} aria-expanded={open === r.patient_id}>{open === r.patient_id ? "收起" : "掃一眼"}</Button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
          {openPage && <RoundPageView page={openPage} headingLevel={2} />}
          <div className="flex flex-wrap items-end gap-3">
            <div>
              <Label htmlFor="head">護理長</Label>
              <Input id="head" name="head_nurse" value={head} onChange={(e) => setHead(e.target.value)} className="w-44" autoComplete="off" />
            </div>
            <Button variant="ok" size="lg" className="min-w-48" disabled={busy} onClick={() => resume({ head_nurse: head, patient_ids: roster.filter((r) => isSel(r.patient_id)).map((r) => r.patient_id) })}>
              {busy ? "發布中…" : "確認名單，發布 RoundPage 給醫師"}
            </Button>
          </div>
        </>
      )}

      {type === "doctor_round" && (
        <>
          <Card variant="confirmed" headingLevel={2} title={`已發布 ${published.length} 頁（醫師端唯讀）`}>
            <ul className="flex flex-wrap gap-2 text-sm">
              {roster.map((r) => (
                <li key={r.patient_id}>
                  <Link href={`/doctor/round/${r.patient_id}`} className={PILL}>{r.code_name} RoundPage →</Link>
                </li>
              ))}
            </ul>
          </Card>
          <Card title="巡診當天：護理師輸入醫囑（醫師看頁、看人、開醫囑，系統不介入）" headingLevel={2}>
            <div className="mb-3 flex flex-wrap gap-3">
              <div><Label htmlFor="doctor">醫師</Label><Input id="doctor" name="doctor" value={doctor} onChange={(e) => setDoctor(e.target.value)} className="w-36" autoComplete="off" /></div>
              <div><Label htmlFor="nurse2">輸入護理師</Label><Input id="nurse2" name="nurse_id" value={nurse} onChange={(e) => setNurse(e.target.value)} className="w-36" autoComplete="off" /></div>
            </div>
            <div className="space-y-3">
              {roster.map((r) => (
                <div key={r.patient_id}>
                  <Label htmlFor={`ord-${r.patient_id}`}>{r.code_name} · {r.room}</Label>
                  <Textarea
                    id={`ord-${r.patient_id}`}
                    name={`order-${r.patient_id}`}
                    value={orders[r.patient_id] ?? ""}
                    onChange={(e) => {
                      setOrders((o) => ({ ...o, [r.patient_id]: e.target.value }));
                      if (orderHint) setOrderHint(null);
                    }}
                    placeholder={ORDER_EXAMPLES[r.patient_id] ?? "醫囑…"}
                    className="min-h-20 text-sm"
                    autoComplete="off"
                  />
                  <Button variant="ghost" className="mt-1" onClick={() => { setOrders((o) => ({ ...o, [r.patient_id]: ORDER_FULL[r.patient_id] ?? "" })); setOrderHint(null); }}>填入示範醫囑</Button>
                </div>
              ))}
            </div>
            {orderHint && <p role="alert" className="mt-3 text-sm text-danger-ink">{orderHint}</p>}
            <Button variant="ok" size="lg" className="mt-3 min-w-48" disabled={busy} onClick={submitOrders}>
              {busy ? "送出中…" : "送出醫囑 → 照護者注意事項 + 基線提案"}
            </Button>
          </Card>
        </>
      )}

      {type === "nurse_confirm_baseline" && (
        <>
          <Card variant="confirmed" headingLevel={2} title="照護者注意事項已產生（本月三件事）">
            <ul className="space-y-2 text-sm">
              {((snap?.values.caregiver_notes ?? []) as { patient_id: string; lang: string; items: string[] }[]).map((n) => (
                <li key={n.patient_id}>
                  <span className="font-medium" translate="no">{n.patient_id}</span> <Chip tone="neutral"><span translate="no">{n.lang}</span></Chip>
                  <ol className="list-decimal pl-5" lang={n.lang}>
                    {n.items.map((it, i) => (
                      <li key={i}>{it}</li>
                    ))}
                  </ol>
                </li>
              ))}
            </ul>
          </Card>
          <Card variant="ai" headingLevel={2} title="基線更新提案（只有確認後才寫入 baseline）">
            {proposals.map((p) => (
              <div key={p.patient_id} className="mb-3">
                <p className="font-medium"><span translate="no">{p.patient_id}</span> · {p.reason}</p>
                <ul className="space-y-1 text-sm">
                  {p.proposals.map((e) => {
                    const k = `${p.patient_id}:${e.dimension}`;
                    return (
                      <li key={k}>
                        <label className="flex min-h-11 cursor-pointer items-start gap-2">
                          <input type="checkbox" name={`acc-${k}`} checked={accepted[k] ?? true} onChange={(ev) => setAccepted((a) => ({ ...a, [k]: ev.target.checked }))} className="mt-1 size-5 accent-[var(--primary)]" />
                          <span><Chip tone="primary">{DIMENSION_LABELS[e.dimension]["zh-TW"]}</Chip> {e.description}</span>
                        </label>
                      </li>
                    );
                  })}
                </ul>
              </div>
            ))}
            <div className="flex flex-wrap gap-2">
              <Button variant="ok" size="lg" className="min-w-48" disabled={busy} onClick={() => {
                const acc: Record<string, string[]> = {};
                proposals.forEach((p) => { acc[p.patient_id] = p.proposals.filter((e) => accepted[`${p.patient_id}:${e.dimension}`] ?? true).map((e) => e.dimension); });
                resume({ action: "approve", nurse_id: nurse, accepted: acc });
              }}>{busy ? "確認中…" : "確認更新基線"}</Button>
              <Button variant="ghost" size="lg" disabled={busy} onClick={() => resume({ action: "reject", nurse_id: nurse })}>{busy ? "確認中…" : "不更新"}</Button>
            </div>
          </Card>
        </>
      )}

      {snap?.status === "done" && (
        <Card variant="confirmed" headingLevel={2} title="巡診流程完成：Encounter + Order 已寫入 timeline">
          <ul className="space-y-1 text-sm">
            <li>基線更新：{((snap.values.baseline_written ?? []) as string[]).join("、") || "無"}</li>
            <li>寫入：{((snap.values.written_ids ?? []) as string[]).length} 筆</li>
            <li className="flex flex-wrap gap-2 pt-1">
              {roster.map((r) => (
                <Link key={r.patient_id} href={`/caregiver/notes?patient=${r.patient_id}`} className={PILL}>{r.code_name} 注意事項（照護者語言）→</Link>
              ))}
            </li>
          </ul>
        </Card>
      )}
      {err && <p role="alert" className="rounded-[10px] bg-danger-fill p-3 text-sm text-danger-ink">{err}</p>}
    </div>
  );
}

export default function RoundPagePrep() {
  return (
    <Suspense fallback={<p className="text-ink-2">Loading…</p>}>
      <RoundInner />
    </Suspense>
  );
}
