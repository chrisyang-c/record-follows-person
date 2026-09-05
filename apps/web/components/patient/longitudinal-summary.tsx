"use client";

import type { Incident, LifeEvent, TimelineEntry } from "@schema";
import { Chip } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import type { PatientSummary } from "@/lib/api";
import { fmtDay } from "@/lib/format";
import { INCIDENT_LABEL, LIFE_EVENT_LABEL } from "@/lib/labels";

const SOON = ["檢驗", "影像", "臨床紀錄", "AI 助理"];

/** 醫師的縱向摘要（VISION §28.4）：慢病、用藥、住院與手術年表、近期事件；其餘項目標第二階段。 */
export function LongitudinalSummary({ summary }: { summary: PatientSummary }) {
  const p = summary.profile;
  const tl = summary.timeline as TimelineEntry[];
  const life = tl.filter((e): e is LifeEvent => e.kind === "life_event").sort((a, b) => (a.ts < b.ts ? -1 : 1));
  const stays = life.filter((e) => e.event_type === "hospitalization" || e.event_type === "surgery");
  const recent = tl
    .filter((e): e is Incident | LifeEvent => e.kind === "incident" || (e.kind === "life_event" && e.event_type === "fall"))
    .sort((a, b) => (a.ts < b.ts ? 1 : -1))
    .slice(0, 4);
  const age = new Date().getFullYear() - p.birth_year;
  const since = life[0] ? new Date(life[0].ts).getFullYear() : null;
  return (
    <Card title="縱向摘要" headingLevel={2} meta={<span className="num" translate="no">Health ID {p.health_id}</span>}>
      <p className="text-sm text-ink-2">{p.code_name}，{age} 歲{since ? <> · 紀錄自 <span className="num">{since}</span> 年起</> : null}</p>
      <div className="mt-3 grid gap-4 md:grid-cols-2">
        <dl className="space-y-2 text-sm">
          <div><dt className="text-ink-2">慢性病</dt><dd>{p.conditions.map((c) => c.display).join("、") || "—"}</dd></div>
          <div><dt className="text-ink-2">用藥</dt><dd>{p.medications.map((m) => `${m.name} ${m.dose} ${m.schedule}${m.is_anticoagulant ? "（抗凝血）" : ""}`).join("；") || "—"}</dd></div>
          <div><dt className="text-ink-2">過敏 · DNR</dt><dd>{p.allergies.map((a) => a.substance).join("、") || "無"} · {p.dnr ? "DNR" : "非 DNR"}</dd></div>
        </dl>
        <div className="text-sm">
          <p className="text-ink-2">住院與手術年表</p>
          <ol className="mt-1 border-l border-line pl-3">
            {stays.length === 0 && <li className="text-ink-2">—</li>}
            {stays.map((e) => (
              <li key={e.id} className="mb-1">
                <span className="num text-ink-2">{new Date(e.ts).getFullYear()}</span> <Chip>{LIFE_EVENT_LABEL[e.event_type]}</Chip> {e.title}
                <span className="text-ink-2">（{e.facility}）</span>
              </li>
            ))}
          </ol>
          <p className="mt-3 text-ink-2">近期事件</p>
          <ul className="mt-1 space-y-1">
            {recent.length === 0 && <li className="text-ink-2">無</li>}
            {recent.map((e) => (
              <li key={e.id} className="flex items-center gap-2">
                <Chip tone="danger">{e.kind === "incident" ? (INCIDENT_LABEL[e.incident_kind] ?? e.incident_kind) : "跌倒"}</Chip>
                <span className="min-w-0 flex-1 truncate">{e.kind === "incident" ? e.summary : e.title}</span>
                <span className="text-xs text-ink-2">{fmtDay(e.ts)}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
      <p className="mt-3 flex flex-wrap gap-2 text-xs text-ink-2">
        {SOON.map((s) => (
          <span key={s} aria-disabled="true" className="rounded-full border border-line px-2 py-0.5 text-ink-2/70">{s} · 第二階段</span>
        ))}
      </p>
    </Card>
  );
}
