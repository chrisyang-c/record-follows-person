"use client";

import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";
import type { Observation, PersonRecord, TimelineEntry } from "@schema";
import { DIMENSION_LABELS } from "@schema";
import { ConfirmedChip } from "@/components/confirmed-chip";
import { DimensionGrid } from "@/components/dimension-grid";
import { Chip, ProvenanceBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useApi } from "@/lib/api";
import { fmtDateTime, fmtDay } from "@/lib/format";
import { DOC_TYPE_LABEL, INCIDENT_LABEL, SHIFT_LABEL } from "@/lib/labels";

const PAGE = 20;
const LINK = "inline-flex min-h-11 items-center text-primary hover:underline";

const KIND: Record<TimelineEntry["kind"], { label: string; tone: "neutral" | "primary" | "danger" | "ok" | "warn" }> = {
  observation: { label: "觀察", tone: "primary" },
  incident: { label: "事故", tone: "danger" },
  encounter: { label: "巡診", tone: "ok" },
  order: { label: "醫囑", tone: "warn" },
};

function Entry({ e }: { e: TimelineEntry }) {
  const k = KIND[e.kind];
  return (
    <li id={e.id} className="scroll-mt-20 rounded-[12px] border border-line bg-bg p-4 shadow-[var(--shadow-card)]">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <Chip tone={k.tone}>{k.label}</Chip>
        <span className="text-ink-2">{fmtDateTime(e.ts)}</span>
        {e.kind === "observation" && <span className="text-ink-2">{SHIFT_LABEL[(e as Observation).shift]}</span>}
        {e.kind === "incident" && <Chip tone="danger">{INCIDENT_LABEL[e.incident_kind] ?? e.incident_kind}</Chip>}
        <span className="ml-auto" />
        <ProvenanceBadge source={e.provenance.source} author={e.provenance.author} />
        {e.confirmed_by && <ConfirmedChip by={e.confirmed_by} at={e.provenance.ts} />}
        <code className="text-xs text-ink-2" translate="no">{e.id}</code>
      </div>
      {e.kind === "observation" && (
        <div className="mt-3 space-y-2">
          <p lang={e.observation.language}>“{e.observation.raw_text}”</p>
          <DimensionGrid domains={e.observation.domains} compact />
          {e.minimal_sbar && (
            <div className="confirmed p-2 text-sm">
              <p className="mb-1">
                {/* 護理師改寫 vs 接受 AI 草稿：兩者都已確認，但來源不同 */}
                <Chip tone={e.minimal_sbar.author === "nurse" ? "ok" : "neutral"}>{e.minimal_sbar.author === "nurse" ? "護理師改寫" : "護理師接受 AI 草稿"}</Chip>
              </p>
              <p><span className="text-ink-2">S</span> {e.minimal_sbar.s}</p>
              <p><span className="text-ink-2">A</span> {e.minimal_sbar.a_change_vs_baseline}</p>
            </div>
          )}
          {e.red_flags?.hits?.length ? (
            <ul className="text-sm text-warn-ink">
              {e.red_flags.hits.map((h) => (
                <li key={h.rule_id}>{h.action === "observe" ? "記錄觀察" : "紅燈"}：{h.facts.join("；")}</li>
              ))}
            </ul>
          ) : null}
        </div>
      )}
      {e.kind === "incident" && (
        <p className="mt-2 flex flex-wrap items-center gap-2">
          <span>{e.summary}</span>
          {e.incident_file_id && (
            <Link href={`/nurse/incident/${e.patient_id}/${e.incident_file_id}`} className={LINK}>
              事故檔 →
            </Link>
          )}
        </p>
      )}
      {e.kind === "encounter" && <p className="mt-2">{e.summary}（<span translate="no">{e.doctor}</span>）</p>}
      {e.kind === "order" && (
        <div className="mt-2">
          <p>{e.raw_text}</p>
          {e.follow_up && (
            <p className="text-sm text-ink-2">
              執行：{e.follow_up.done == null ? "未知" : e.follow_up.done ? "已做" : "未做"} · 有效：{e.follow_up.effective == null ? "未知" : e.follow_up.effective ? "有" : "無"} · {e.follow_up.note}
            </p>
          )}
        </div>
      )}
    </li>
  );
}

function RecordInner() {
  const { patientId } = useParams<{ patientId: string }>();
  const params = useSearchParams();
  const idsKey = params.get("ids") ?? "";
  const onlyIds = useMemo(() => idsKey.split(",").filter(Boolean), [idsKey]);
  const { data, error, loading } = useApi<PersonRecord>(`/records/${patientId}`);
  // 進頁時的 #hash（RoundPage 的 evidence 連結）；伺服器端為空字串，不影響首次 markup
  const [hash] = useState(() => (typeof window === "undefined" ? "" : window.location.hash.replace(/^#/, "")));
  const [extraPages, setExtraPages] = useState(0);
  const timeline = useMemo(() => {
    const all = data ? [...data.timeline].sort((a, b) => (a.ts < b.ts ? 1 : -1)) : [];
    return onlyIds.length ? all.filter((e) => onlyIds.includes(e.id)) : all;
  }, [data, onlyIds]);
  const hashIdx = hash ? timeline.findIndex((e) => e.id === hash) : -1;
  // 顯示到 hash 目標所在的那一頁為止（至少一頁）
  const shown = Math.max(PAGE * (1 + extraPages), hashIdx >= 0 ? Math.ceil((hashIdx + 1) / PAGE) * PAGE : 0);
  useEffect(() => {
    if (hashIdx < 0) return;
    document.getElementById(hash)?.scrollIntoView();
  }, [hash, hashIdx]);

  if (loading) return <p className="text-ink-2">Loading…</p>;
  if (error || !data) return <p role="alert" className="text-danger-ink">{error ?? "無資料"}</p>;
  const p = data.profile;
  const visible = timeline.slice(0, shown);
  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-medium">
          {p.code_name} <span className="text-base text-ink-2">· {p.room} · {p.sex === "M" ? "男" : "女"} · {new Date().getFullYear() - p.birth_year} 歲</span>
        </h1>
        <p className="text-ink-2">{p.one_liner}</p>
      </header>
      <div className="grid gap-4 md:grid-cols-3">
        <Card title="Profile" headingLevel={2}>
          <dl className="space-y-1 text-sm">
            <dt className="text-ink-2">慢性病</dt><dd>{p.conditions.map((c) => c.display).join("、") || "—"}</dd>
            <dt className="text-ink-2">過敏</dt><dd>{p.allergies.map((a) => a.substance).join("、") || "無"}</dd>
            <dt className="text-ink-2">用藥</dt><dd>{p.medications.map((m) => `${m.name} ${m.dose} ${m.schedule}${m.is_anticoagulant ? "（抗凝血）" : ""}`).join("；")}</dd>
            <dt className="text-ink-2">DNR</dt><dd>{p.dnr ? "是" : "否"}</dd>
            <dt className="text-ink-2">緊急聯絡</dt><dd>{p.emergency_contacts.map((c) => `${c.relation} ${c.name}`).join("、")}</dd>
            <dt className="text-ink-2">照護者</dt><dd translate="no">{p.caregiver_code_name}</dd>
          </dl>
        </Card>
        <Card title="Baseline（平常）" headingLevel={2} className="md:col-span-2">
          <table className="w-full text-sm">
            <tbody>
              {data.baseline.entries.filter((e) => !e.valid_to).map((e) => (
                <tr key={e.dimension} className="border-t border-line">
                  <th scope="row" className="py-1 pr-3 text-left font-medium">{DIMENSION_LABELS[e.dimension]["zh-TW"]}</th>
                  <td className="py-1">{e.description}</td>
                  <td className="py-1 pl-2 text-right text-ink-2"><span translate="no">{e.confirmed_by ?? e.set_by}</span> · {fmtDay(e.valid_from)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      </div>
      <section aria-labelledby="tl">
        <h2 id="tl" className="mb-2 text-lg font-medium">Timeline（只增不改，<span className="num">{timeline.length}</span> 筆）</h2>
        {onlyIds.length > 0 && (
          <p className="mb-2 rounded-[8px] bg-ai-fill px-3 py-2 text-sm">
            只顯示 RoundPage 引用的 <span className="num">{timeline.length}</span> 筆紀錄。{" "}
            <Link href={`/record/${patientId}`} className="text-primary hover:underline">顯示全部</Link>
          </p>
        )}
        <ul className="space-y-3">
          {visible.map((e) => (
            <Entry key={e.id} e={e} />
          ))}
        </ul>
        {shown < timeline.length && (
          <div className="mt-3 flex items-center gap-3">
            <Button variant="outline" onClick={() => setExtraPages(Math.ceil(shown / PAGE))}>再顯示 {PAGE} 筆</Button>
            <span className="text-sm text-ink-2">
              已顯示 <span className="num">{visible.length}</span> / <span className="num">{timeline.length}</span>
            </span>
          </div>
        )}
      </section>
      <section aria-labelledby="docs">
        <h2 id="docs" className="mb-2 text-lg font-medium">Documents</h2>
        <ul className="grid gap-2 sm:grid-cols-2">
          {data.documents.map((d) => (
            <li key={d.id} className="rounded-[10px] border border-line p-3 text-sm">
              <Chip tone="neutral">{DOC_TYPE_LABEL[d.doc_type] ?? d.doc_type}</Chip> <span className="text-ink-2">{fmtDateTime(d.generated_at)}</span> · {d.audience}
              <div className="mt-1 flex flex-wrap gap-3">
                {d.doc_type === "round_page" && <Link className={LINK} href={`/doctor/round/${patientId}`}>RoundPage →</Link>}
                {d.doc_type === "incident_file" && <Link className={LINK} href={`/nurse/incident/${patientId}/${d.id}`}>事故檔 →</Link>}
                {d.doc_type === "caregiver_notes" && <Link className={LINK} href={`/caregiver/notes?patient=${patientId}`}>注意事項 →</Link>}
              </div>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

export default function RecordPage() {
  return (
    <Suspense fallback={<p className="text-ink-2">Loading…</p>}>
      <RecordInner />
    </Suspense>
  );
}
