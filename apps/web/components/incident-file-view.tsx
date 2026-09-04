"use client";

import type { IncidentFile } from "@schema";
import { ConfirmedChip } from "@/components/confirmed-chip";
import { DimensionGrid } from "@/components/dimension-grid";
import { IsbarView } from "@/components/isbar-editor";
import { Chip, ProvenanceBadge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { fmtDateTime } from "@/lib/format";
import { INCIDENT_LABEL, ROUTE_LABEL } from "@/lib/labels";

/** 事故檔（照護者區塊原話 + 護理師現場評估與 ISBAR + 通知追蹤），嵌在病人頁「文件」tab。 */
export function IncidentFileView({ d, codeName }: { d: IncidentFile; codeName: string }) {
  const cs = d.caregiver_section;
  const ns = d.nurse_section;
  const oa = ns.onsite_assessment;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-xl font-medium">事故檔 · {codeName}</h2>
        <ConfirmedChip by={d.confirmed_by} at={ns.confirmed_at} />
        <span className="text-sm text-ink-2">{fmtDateTime(d.generated_at)} · 路徑：{d.route_decision ? ROUTE_LABEL[d.route_decision] : "—"}</span>
      </div>
      {d.red_flags?.hits?.length ? (
        <div className="red-flag p-3 text-sm">
          {d.red_flags.hits.map((h) => (
            <p key={h.rule_id}>
              <span className="text-ink-2" translate="no">{h.rule_id}</span> {h.description}：{h.facts.join("；")}
            </p>
          ))}
          <p className="text-ink-2">{d.red_flags.disclaimer}</p>
        </div>
      ) : null}
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="照護者區塊（原話，不改口吻）" headingLevel={2} meta={<ProvenanceBadge source={cs.provenance.source} author={cs.provenance.author} />}>
          <p lang={cs.language}>“{cs.raw_text}”</p>
          <div className="mt-3"><DimensionGrid domains={cs.domains} compact /></div>
          <div className="mt-2 flex flex-wrap gap-1">
            {cs.incident_flags.map((i) => <Chip key={i} tone="danger">{INCIDENT_LABEL[i] ?? i}</Chip>)}
            {cs.seems_different && <Chip tone="warn">跟平常不一樣</Chip>}
            {cs.unknown.length > 0 && <Chip tone="neutral">未知：{cs.unknown.length} 格</Chip>}
          </div>
          {cs.followups.length > 0 && (
            <ul className="mt-2 text-sm text-ink-2">
              {cs.followups.map((f, i) => <li key={i}>Q：{f.question} → {f.answered_unknown ? "不知道" : f.answer ?? "（未答）"}</li>)}
            </ul>
          )}
        </Card>
        <Card title="護理師區塊（現場評估＋ISBAR）" headingLevel={2} meta={<ConfirmedChip by={ns.confirmed_by} at={ns.confirmed_at} />}>
          {oa && (
            <dl className="mb-3 grid grid-cols-3 gap-1 text-sm sm:grid-cols-6">
              <div><dt className="text-ink-2">體溫</dt><dd className="num">{oa.vitals.temp_c ?? "—"}</dd></div>
              <div><dt className="text-ink-2">血壓</dt><dd className="num">{oa.vitals.sbp ?? "—"}/{oa.vitals.dbp ?? "—"}</dd></div>
              <div><dt className="text-ink-2">心率</dt><dd className="num">{oa.vitals.hr ?? "—"}</dd></div>
              <div><dt className="text-ink-2">呼吸</dt><dd className="num">{oa.vitals.rr ?? "—"}</dd></div>
              <div><dt className="text-ink-2">SpO₂</dt><dd className="num">{oa.vitals.spo2 ?? "—"}</dd></div>
              <div><dt className="text-ink-2">意識</dt><dd>{oa.consciousness}</dd></div>
              {oa.wound && <div className="col-span-3"><dt className="text-ink-2">傷口</dt><dd>{oa.wound}</dd></div>}
              {oa.notes && <div className="col-span-3"><dt className="text-ink-2">備註</dt><dd>{oa.notes}</dd></div>}
            </dl>
          )}
          {/* 巢狀在 h2 Card 內：ISBAR 各段用 h3 */}
          <IsbarView isbar={ns.isbar} headingLevel={3} />
        </Card>
      </div>
      <Card title="通知與追蹤" headingLevel={2}>
        <ul className="space-y-1 text-sm">
          {d.notifications.map((n, i) => (
            <li key={i}><Chip tone="neutral"><span translate="no">{n.to} · {n.channel} · {n.status}</span></Chip> <span className="text-ink-2">{fmtDateTime(n.sent_at)}</span><p className="mt-1 whitespace-pre-wrap">{n.content}</p></li>
          ))}
          {d.follow_up && (
            <li className="pt-2"><Chip tone="primary">追蹤 {fmtDateTime(d.follow_up.due_at)}</Chip> {d.follow_up.question} → {d.follow_up.answer ?? "（尚未回答）"}</li>
          )}
        </ul>
      </Card>
    </div>
  );
}
