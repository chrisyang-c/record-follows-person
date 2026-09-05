"use client";

import { Printer } from "lucide-react";
import type { CaregiverNotes, IncidentFile, RoundPage } from "@schema";
import { IncidentFileView } from "@/components/incident-file-view";
import { LongitudinalSummary } from "@/components/patient/longitudinal-summary";
import { ReviewPanel } from "@/components/nurse/review-panel";
import { TenSecondConfirm } from "@/components/nurse/ten-second-confirm";
import { RoundPageView } from "@/components/round-page-view";
import { Chip, ProvenanceBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import type { PatientSummary } from "@/lib/api";
import { fmtDateTime } from "@/lib/format";
import type { Role } from "@/lib/role";

/**
 * 文件 tab（病人頁的單一入口）：
 * 護理師：紅燈／草稿先（Path A 審核、每班 10 秒確認）→ RoundPage（展開＋列印）→ 事件資訊包 → 注意事項
 * 醫師：RoundPage 展開＋列印 A4 → 事件資訊包（唯讀）
 * 照護者：本月注意事項
 */
export function DocsTab({ summary, role, onChanged }: { summary: PatientSummary; role: Role; onChanged: () => void }) {
  const name = summary.profile.code_name;
  const docs = [...summary.documents].sort((a, b) => (a.generated_at < b.generated_at ? 1 : -1));
  const round = docs.find((d) => d.doc_type === "round_page") as RoundPage | undefined;
  const incidents = docs.filter((d) => d.doc_type === "incident_file") as IncidentFile[];
  const notes = docs.find((d) => d.doc_type === "caregiver_notes") as CaregiverNotes | undefined;
  const pending = summary.pending;
  const pathA = pending.filter((p) => p.graph === "path_a");
  const shifts = pending.filter((p) => p.graph === "shift");
  return (
    <div className="space-y-6">
      {role === "nurse" && pending.length > 0 && (
        <section aria-labelledby="pend" className="no-print space-y-4">
          <h2 id="pend" className="text-lg font-medium">等我確認</h2>
          {pathA.map((p) => (
            <ReviewPanel key={p.thread_id} tid={p.thread_id} codeName={name} onChanged={onChanged} />
          ))}
          {shifts.map((p) => (
            <TenSecondConfirm key={p.thread_id} item={{ ...p, patient_id: summary.profile.patient_id, code_name: name }} onDone={onChanged} />
          ))}
        </section>
      )}

      {role === "doctor" && <LongitudinalSummary summary={summary} />}

      {role !== "caregiver" && (
        <section aria-labelledby="rp">
          <div className="no-print mb-2 flex flex-wrap items-center gap-2">
            <h2 id="rp" className="text-lg font-medium">RoundPage · 熟悉頁</h2>
            {round && <Chip tone={round.status === "approved" ? "ok" : "primary"}>{round.status === "approved" ? `護理長確認 · ${round.confirmed_by ?? ""}` : "AI 草稿，待護理長確認"}</Chip>}
            {round && (
              <Button variant="outline" className="ml-auto" onClick={() => window.print()} aria-label="列印 A4">
                <Printer className="size-4" aria-hidden="true" /> 列印 A4
              </Button>
            )}
          </div>
          {round ? <RoundPageView page={round} headingLevel={2} /> : <p className="text-sm text-ink-2">尚未發布 RoundPage：護理師在「巡診準備」發布後會出現在這裡。</p>}
        </section>
      )}

      {role !== "caregiver" && incidents.length > 0 && (
        <section aria-labelledby="inc" className="no-print space-y-4">
          <h2 id="inc" className="text-lg font-medium">事件資訊包（<span className="num">{incidents.length}</span>）</h2>
          {incidents.map((d) => (
            <IncidentFileView key={d.id} d={d} codeName={name} />
          ))}
        </section>
      )}

      <section aria-labelledby="notes" className="no-print">
        <h2 id="notes" className="mb-2 text-lg font-medium">本月注意事項（照護者三件事）</h2>
        {notes ? (
          <Card variant="confirmed" headingLevel={3} meta={fmtDateTime(notes.generated_at)} className="max-w-[390px] text-lg">
            <ol className="list-decimal space-y-3 pl-6">
              {notes.items.map((it, i) => (
                <li key={i} className="font-medium">{it}</li>
              ))}
            </ol>
            <div className="mt-4"><ProvenanceBadge source={notes.provenance.source} author={notes.provenance.author} /></div>
          </Card>
        ) : (
          <p className="text-sm text-ink-2">還沒有本月注意事項。護理師輸入醫囑後會出現在這裡。</p>
        )}
      </section>

      {role === "nurse" && pending.length === 0 && (
        <p className="no-print text-sm text-ink-2">目前沒有待確認的草稿。</p>
      )}
    </div>
  );
}
