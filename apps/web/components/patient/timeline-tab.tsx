"use client";

import { useEffect, useMemo, useState } from "react";
import type { Observation, TimelineEntry } from "@schema";
import { DIMENSIONS, DIMENSION_LABELS } from "@schema";
import { ConfirmedChip } from "@/components/confirmed-chip";
import { DimensionGrid } from "@/components/dimension-grid";
import { ActivityBar } from "@/components/patient/activity-bar";
import { Chip, ProvenanceBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { ConvMessage, PatientSummary } from "@/lib/api";
import { fmtDateTime } from "@/lib/format";
import { INCIDENT_LABEL, SHIFT_LABEL } from "@/lib/labels";
import type { Role } from "@/lib/role";
import { cn } from "@/lib/utils";

const PAGE = 20;
const KIND: Record<TimelineEntry["kind"], { label: string; tone: "neutral" | "primary" | "danger" | "ok" | "warn" }> = {
  observation: { label: "觀察", tone: "primary" },
  incident: { label: "事故", tone: "danger" },
  encounter: { label: "巡診", tone: "ok" },
  order: { label: "醫囑", tone: "warn" },
};

type Row = { ts: string; id: string; entry?: TimelineEntry; msg?: ConvMessage };

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
      </div>
      {e.kind === "observation" && (
        <div className="mt-3 space-y-2">
          <p lang={e.observation.language}>“{e.observation.raw_text}”</p>
          <DimensionGrid domains={e.observation.domains} compact />
          {e.minimal_sbar && (
            <div className="confirmed p-2 text-sm">
              <p className="mb-1"><Chip tone={e.minimal_sbar.author === "nurse" ? "ok" : "neutral"}>{e.minimal_sbar.author === "nurse" ? "護理師改寫" : "護理師接受 AI 草稿"}</Chip></p>
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
      {e.kind === "incident" && <p className="mt-2">{e.summary}</p>}
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

/** 對話的每一輪也在紀錄 tab 出現：照服員原話 caregiver_said、AI 抽取 ai_extracted、系統事件 system_derived（可展開活動）。 */
function MsgRow({ m, role }: { m: ConvMessage; role: Role }) {
  const src = m.role === "caregiver" ? "caregiver_said" : m.role === "agent" ? "ai_extracted" : "system_derived";
  return (
    <li className={cn("rounded-[12px] border p-3 text-sm", m.role === "agent" ? "ai-draft" : "border-line bg-bg")}>
      <div className="flex flex-wrap items-center gap-2">
        <Chip tone={m.role === "system" ? "neutral" : m.role === "caregiver" ? "primary" : "primary"}>{m.role === "caregiver" ? "對話" : m.role === "agent" ? "agent" : "系統"}</Chip>
        <span className="text-ink-2">{fmtDateTime(m.ts)}</span>
        <span className="ml-auto" />
        <ProvenanceBadge source={src} author={m.role === "caregiver" ? undefined : m.role === "agent" ? "intake_agent" : undefined} />
      </div>
      <p className={cn("mt-2 whitespace-pre-wrap", m.role === "system" && "text-ink-2")}>{m.text}</p>
      {m.role === "agent" && m.meta.reason && <p className="mt-1 text-xs text-ink-2">為什麼問：{m.meta.reason}</p>}
      {m.meta.activity && <ActivityBar events={m.meta.activity} role={role} className="mt-2" />}
    </li>
  );
}

export function TimelineTab({ summary, role, onlyIds }: { summary: PatientSummary; role: Role; onlyIds: string[] }) {
  const [dim, setDim] = useState<string | null>(null);
  const [showConv, setShowConv] = useState(true);
  const [pages, setPages] = useState(1);
  const rows = useMemo(() => {
    const out: Row[] = summary.timeline.map((e) => ({ ts: e.ts, id: e.id, entry: e }));
    if (showConv && !onlyIds.length) for (const m of summary.conversation) out.push({ ts: m.ts, id: m.id, msg: m });
    out.sort((a, b) => (a.ts < b.ts ? 1 : -1));
    return out.filter((r) => {
      if (onlyIds.length && !(r.entry && onlyIds.includes(r.entry.id))) return false;
      if (dim && !(r.entry?.kind === "observation" && r.entry.observation.domains[dim])) return false;
      return true;
    });
  }, [summary, showConv, onlyIds, dim]);
  useEffect(() => {
    const hash = window.location.hash.replace(/^#/, "");
    if (hash) document.getElementById(hash)?.scrollIntoView();
  }, [rows.length]);
  const shown = rows.slice(0, PAGE * pages);
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2" role="group" aria-label="維度篩選">
        <button type="button" onClick={() => setDim(null)} aria-pressed={dim === null} className={cn("min-h-11 rounded-full border px-3 text-sm", dim === null ? "border-primary bg-ai-fill" : "border-line")}>全部</button>
        {DIMENSIONS.map((d) => (
          <button key={d} type="button" onClick={() => setDim(d)} className={cn("min-h-11 rounded-full border px-3 text-sm", dim === d ? "border-primary bg-ai-fill" : "border-line", summary.changed_dimensions.includes(d) && "text-warn-ink")} aria-pressed={dim === d}>
            {DIMENSION_LABELS[d]["zh-TW"]}
          </button>
        ))}
        <label className="ml-auto flex min-h-11 items-center gap-2 text-sm">
          <input type="checkbox" checked={showConv} onChange={(e) => setShowConv(e.target.checked)} className="size-4 accent-[var(--primary)]" /> 含對話
        </label>
      </div>
      {onlyIds.length > 0 && (
        <p className="rounded-[8px] bg-ai-fill px-3 py-2 text-sm">
          只顯示 RoundPage 引用的 <span className="num">{rows.length}</span> 筆紀錄。{" "}
          <a href={`/p/${summary.profile.patient_id}?tab=timeline`} className="text-primary hover:underline">顯示全部</a>
        </p>
      )}
      <p className="text-sm text-ink-2">只增不改，<span className="num">{rows.length}</span> 筆</p>
      <ul className="space-y-3">
        {shown.map((r) => (r.entry ? <Entry key={r.id} e={r.entry} /> : <MsgRow key={r.id} m={r.msg!} role={role} />))}
      </ul>
      {shown.length < rows.length && (
        <div className="flex items-center gap-3">
          <Button variant="outline" onClick={() => setPages((n) => n + 1)}>再顯示 {PAGE} 筆</Button>
          <span className="text-sm text-ink-2">已顯示 <span className="num">{shown.length}</span> / <span className="num">{rows.length}</span></span>
        </div>
      )}
    </div>
  );
}
