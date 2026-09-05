"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState, type RefObject } from "react";
import type { BaselineDelta, ISBAR, RouteDecision, StructuredObservation } from "@schema";
import { DIMENSION_LABELS } from "@schema";
import { ConfirmedChip } from "@/components/confirmed-chip";
import { DimensionGrid } from "@/components/dimension-grid";
import { emptyOnsite, IsbarEditor, IsbarView, OnsiteFields, onsitePayload, type OnsiteForm } from "@/components/isbar-editor";
import { Chip } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input, Label, Textarea } from "@/components/ui/field";
import { api, resumeThread, threadState, usePolling, type Snapshot } from "@/lib/api";
import { fmtDateTime } from "@/lib/format";
import { DIRECTION_LABEL, ROUTE_LABEL, typeLabel } from "@/lib/labels";

const NURSE = "nurse_lin";
const ROUTES: { key: RouteDecision; hint: string }[] = [
  { key: "contact_contract_hospital", hint: "產通話版 ISBAR" },
  { key: "home_acute_mode_b", hint: "產通話版 ISBAR" },
  { key: "accompany_visit", hint: "產 VisitPage 陪診頁" },
  { key: "observe", hint: "進入每班流程" },
];

/** 急症審核（Path A 的 ◇nurse_review / 現場評估 / 路徑 / 家屬通知），嵌在病人頁「文件」tab。 */
export function ReviewPanel({ tid, codeName, onChanged }: { tid: string; codeName: string; onChanged?: () => void }) {
  const [snap, setSnap] = useState<Snapshot | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [onsite, setOnsite] = useState<OnsiteForm>(emptyOnsite);
  const [s, setS] = useState("");
  const [b, setB] = useState("");
  const [a, setA] = useState("");
  const [r, setR] = useState("");
  const [nurse, setNurse] = useState(NURSE);
  const [returnReason, setReturnReason] = useState("");
  const [famText, setFamText] = useState("");
  const [returning, setReturning] = useState(false);
  const [missing, setMissing] = useState<string[]>([]);
  const cRef = useRef<HTMLInputElement>(null);
  const aRef = useRef<HTMLTextAreaElement>(null);
  const rRef = useRef<HTMLTextAreaElement>(null);

  const load = () => threadState(tid).then((sn) => {
    setSnap(sn);
    const isbar = sn.values.sbar as ISBAR | undefined;
    if (isbar) {
      setS((v) => v || isbar.situation);
      setB((v) => v || isbar.background);
    }
    const fam = sn.values.family_notification as { content: string } | undefined;
    if (fam) setFamText((v) => v || fam.content);
    return sn;
  });

  const pollState = useCallback(() => {
    threadState(tid).then((sn) => setSnap((prev) => (prev && prev.status !== "interrupted" ? prev : sn))).catch(() => {});
  }, [tid]);
  usePolling(pollState, 5000, !!snap && snap.status === "interrupted");

  useEffect(() => {
    let alive = true;
    threadState(tid)
      .then(async (sn) => {
        if (!alive) return;
        setSnap(sn);
        const isbar = sn.values.sbar as ISBAR | undefined;
        if (isbar) {
          setS(isbar.situation);
          setB(isbar.background);
        }
        const fam = sn.values.family_notification as { content: string } | undefined;
        if (fam) setFamText(fam.content);
        const pid = sn.values.patient_id as string;
        const v = await api<{ temp_c: number; sbp: number; dbp: number; hr: number; rr: number; spo2: number }>(`/ingest/vitals/${pid}`);
        if (!alive) return;
        setOnsite((o) => (o.temp_c ? o : { ...o, temp_c: String(v.temp_c), sbp: String(v.sbp), dbp: String(v.dbp), hr: String(v.hr), rr: String(v.rr), spo2: String(v.spo2) }));
      })
      .catch((e: Error) => alive && setErr(e.message));
    return () => {
      alive = false;
    };
  }, [tid]);

  const submit = async (payload: Record<string, unknown>) => {
    setBusy(true);
    setErr(null);
    try {
      await resumeThread(tid, { nurse_id: nurse, ...payload });
      await load();
      onChanged?.();
      setReturning(false);
      setReturnReason("");
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  // 確認鍵不鎖：按下時檢查 意識 / A / R，就地列出缺什麼並把焦點放到第一個空欄
  const confirm = () => {
    const miss: { label: string; ref: RefObject<HTMLElement | null> }[] = [];
    if (!onsite.consciousness.trim()) miss.push({ label: "意識", ref: cRef });
    if (!a.trim()) miss.push({ label: "A · 護理師評估", ref: aRef });
    if (!r.trim()) miss.push({ label: "R · 護理師建議", ref: rRef });
    if (miss.length) {
      setMissing(miss.map((m) => m.label));
      miss[0].ref.current?.focus();
      return;
    }
    setMissing([]);
    submit({
      action: "accept",
      onsite_assessment: onsitePayload(onsite),
      nurse_assessment: a,
      nurse_recommendation: r,
      edits: { situation: s, background: b },
    });
  };

  if (!snap) return err ? <p role="alert" className="text-danger-ink">{err}</p> : <p className="text-ink-2">Loading…</p>;
  const it = snap.interrupt;
  const v = snap.values;
  const pid = v.patient_id as string;
  const obs = v.structured_observation as StructuredObservation | undefined;
  const deltas = (v.baseline_delta ?? []) as BaselineDelta[];
  const isbar = v.sbar as ISBAR | undefined;
  const docs = (v.documents ?? {}) as Record<string, string>;
  const type = it?.type;
  const done = snap.status === "done";
  const route = v.route_decision as RouteDecision | undefined;
  const reviewLog = (v.review_log ?? []) as { node: string; action: string; by: string; ts: string }[];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-xl font-medium">{codeName} · 急症審核</h2>
        {done ? <ConfirmedChip by={isbar?.confirmed_by ?? nurse} at={isbar?.confirmed_at} /> : <Chip tone="primary">{typeLabel(type)}</Chip>}
        {typeof v.escalation_level === "number" && (v.escalation_level as number) > 0 && <Chip tone="warn">已升級 {v.escalation_level as number} 次</Chip>}
        {!!v.deadline && <span className="text-sm text-ink-2">期限 {fmtDateTime(v.deadline as string)}</span>}
        <span className="ml-auto flex items-center gap-2 text-sm">
          <Label htmlFor="nurse" className="mb-0">護理師</Label>
          <Input id="nurse" name="nurse_id" value={nurse} onChange={(e) => setNurse(e.target.value)} className="w-36" autoComplete="off" />
        </span>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1fr_1.2fr]">
        <div className="space-y-3">
          {obs && (
            <Card title="照護者區塊（原話＋AI 結構化）" meta={<span translate="no">{obs.language}</span>}>
              <p lang={obs.language}>“{obs.raw_text}”</p>
              <div className="mt-3">
                <DimensionGrid domains={obs.domains} compact />
              </div>
              {((v.caregiver_reports ?? []) as { question: string; answer: string; ts: string }[]).length > 0 && (
                <div className="mt-3 rounded-[8px] bg-surface p-2 text-sm" aria-live="polite">
                  <p className="font-medium">照護者目前回報（每 5 秒更新）</p>
                  <ul className="mt-1 space-y-0.5">
                    {((v.caregiver_reports ?? []) as { question: string; answer: string; ts: string }[]).map((r, i) => (
                      <li key={i}>
                        <span className="text-ink-2">{fmtDateTime(r.ts)}</span> {r.question} → <span className="font-medium">{r.answer}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {obs.followups.length > 0 && (
                <ul className="mt-2 text-sm text-ink-2">
                  {obs.followups.map((f, i) => (
                    <li key={i}>Q：{f.question} → {f.answered_unknown ? "不知道" : f.answer ?? "（未答）"}</li>
                  ))}
                </ul>
              )}
            </Card>
          )}
          {deltas.length > 0 && (
            <Card title="與基線比（規則計算）">
              <ul className="space-y-1 text-sm">
                {deltas.map((d) => (
                  <li key={d.domain}>
                    <Chip tone={d.direction === "same" ? "ok" : "warn"}>{DIMENSION_LABELS[d.domain]["zh-TW"]} {DIRECTION_LABEL[d.direction]}</Chip> {d.note}
                    {d.days > 1 && <span className="text-ink-2">，持續 {d.days} 天</span>}
                  </li>
                ))}
              </ul>
            </Card>
          )}
          {reviewLog.length > 0 && (
            <Card title="審核紀錄">
              <ul className="text-sm text-ink-2">
                {reviewLog.map((l, i) => (
                  <li key={i}>
                    {fmtDateTime(l.ts)} · <span translate="no">{l.node}</span> · <span translate="no">{l.action}</span> · <span translate="no">{l.by}</span>
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </div>

        <div className="space-y-3">
          {(type === "nurse_review" || type === "nurse_onsite_assessment") && (
            <>
              <OnsiteFields value={onsite} onChange={setOnsite} consciousnessRef={cRef} />
              {type === "nurse_review" ? (
                <IsbarEditor isbar={isbar ?? null} s={s} b={b} a={a} r={r} onS={setS} onB={setB} onA={setA} onR={setR} aRef={aRef} rRef={rRef} />
              ) : (
                <IsbarEditor isbar={null} s={s || (obs ? `照護者回報：「${obs.raw_text}」` : "")} b={b} a={a} r={r} onS={setS} onB={setB} onA={setA} onR={setR} aRef={aRef} rRef={rRef} />
              )}
              {returning && (
                <Card title="退回照護者">
                  <Textarea name="return_reason" aria-label="退回原因" value={returnReason} onChange={(e) => setReturnReason(e.target.value)} placeholder="例如：請補充昨晚到今早喝了多少水…" className="min-h-14" autoComplete="off" />
                </Card>
              )}
              <div className="sticky bottom-0 flex flex-wrap gap-2 bg-bg pt-2 pb-[calc(0.5rem+env(safe-area-inset-bottom))]">
                {missing.length > 0 && (
                  <p role="alert" className="basis-full text-sm text-danger-ink">
                    請先填寫：{missing.join("、")}。
                  </p>
                )}
                {!returning ? (
                  <>
                    <Button variant="ok" size="lg" className="min-w-48 flex-1" disabled={busy} onClick={confirm}>
                      {busy ? "確認中…" : "現場評估完成，確認 ISBAR"}
                    </Button>
                    {type === "nurse_review" && (
                      <Button variant="ghost" size="lg" onClick={() => setReturning(true)} disabled={busy}>退回</Button>
                    )}
                  </>
                ) : (
                  <>
                    <Button variant="danger" size="lg" className="flex-1" disabled={busy || !returnReason.trim()} onClick={() => submit({ action: "return", return_reason: returnReason, caregiver_addendum: returnReason })}>
                      {busy ? "退回中…" : "退回照護者"}
                    </Button>
                    <Button variant="ghost" size="lg" onClick={() => setReturning(false)}>取消</Button>
                  </>
                )}
              </div>
              <p className="text-xs text-ink-2">A 與 R 由護理師撰寫；AI 的 A 只寫變化、R 只提問。確認後才會寫入紀錄。</p>
            </>
          )}

          {type === "nurse_route_choice" && isbar && (
            <>
              <IsbarView isbar={isbar} />
              <Card title="決定路徑">
                <div className="grid gap-2 sm:grid-cols-2">
                  {ROUTES.map((o) => (
                    <Button key={o.key} variant={o.key === "observe" ? "outline" : "primary"} size="lg" className="flex-col items-start gap-0 py-2" disabled={busy} onClick={() => submit({ route: o.key })}>
                      <span>{ROUTE_LABEL[o.key]}</span>
                      <span className="text-xs font-normal">{o.hint}</span>
                    </Button>
                  ))}
                </div>
              </Card>
            </>
          )}

          {type === "nurse_approve_notification" && (
            <>
              <Card variant="confirmed" title="事故檔已寫入紀錄" meta={<span translate="no">{docs.incident_file}</span>}>
                <p className="flex flex-wrap items-center gap-3 text-sm">
                  <span className="text-ink-2">事故檔會出現在下方「文件」清單</span>
                  {docs.handoff_page_id && <span className="text-ink-2">後送頁 <span translate="no">{docs.handoff_page_id}</span></span>}
                </p>
              </Card>
              <Card variant="ai" title="家屬通知（白話版，AI 草稿）">
                <Textarea name="family_content" aria-label="家屬通知內容" value={famText} onChange={(e) => setFamText(e.target.value)} className="min-h-32" autoComplete="off" />
                <div className="mt-3 flex flex-wrap gap-2">
                  <Button variant="ok" size="lg" className="flex-1" disabled={busy} onClick={() => submit({ action: "edit", content: famText })}>{busy ? "送出中…" : "核准並送出（LINE 未設定時只顯示）"}</Button>
                  <Button variant="ghost" size="lg" disabled={busy} onClick={() => submit({ action: "skip" })}>略過</Button>
                </div>
              </Card>
            </>
          )}

          {done && (
            <Card variant="confirmed" title="流程完成">
              <ul className="space-y-1 text-sm">
                <li>路徑：{route ? (ROUTE_LABEL[route] ?? route) : "—"}</li>
                <li>事故檔：<span translate="no">{docs.incident_file}</span>（見下方文件）</li>
                <li>家屬通知：{(v.family_notification as { status: string })?.status}</li>
                <li>追蹤：{fmtDateTime((v.follow_up as { due_at: string })?.due_at)} 再問照護者一次</li>
                <li>
                  <Link href={`/p/${pid}?tab=timeline`} className="inline-flex min-h-11 items-center text-primary hover:underline">看這個人的紀錄 →</Link>
                </li>
              </ul>
            </Card>
          )}
          {err && <p role="alert" className="rounded-[10px] bg-danger-fill p-3 text-sm text-danger-ink">{err}</p>}
        </div>
      </div>
    </div>
  );
}
