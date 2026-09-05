"use client";

import { DIMENSION_LABELS, type Dimension } from "@schema";
import { Sparkline } from "@/components/sparkline";
import { Chip } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { useApi, type AccessLogEntry, type PatientSummary } from "@/lib/api";
import { fmtDateTime, fmtDay } from "@/lib/format";
import { IDENTITIES, ROLE_LABEL } from "@/lib/role";
import type { TrendReport } from "@schema";

/** 這是誰：profile、八維度基線（誰設、何時）、有變化的維度小圖。 */
export function WhoTab({ summary }: { summary: PatientSummary }) {
  const p = summary.profile;
  const changed = new Set(summary.changed_dimensions);
  const { data: trend } = useApi<TrendReport>(changed.size ? `/trends/${p.patient_id}` : null);
  const series = trend?.series.filter((s) => changed.has(s.dimension)) ?? [];
  const { data: log } = useApi<{ items: AccessLogEntry[] }>(`/patients/${p.patient_id}/access-log?limit=20`);
  return (
    <div className="space-y-4">
      <p className="text-ink-2">{p.one_liner}</p>
      <div className="grid gap-4 md:grid-cols-3">
        <Card title="基本" headingLevel={2}>
          <dl className="space-y-1 text-sm">
            <dt className="text-ink-2">房間</dt><dd>{p.room} · {p.sex === "M" ? "男" : "女"} · {new Date().getFullYear() - p.birth_year} 歲</dd>
            <dt className="text-ink-2">慢性病</dt><dd>{p.conditions.map((c) => c.display).join("、") || "—"}</dd>
            <dt className="text-ink-2">過敏</dt><dd>{p.allergies.map((a) => a.substance).join("、") || "無"}</dd>
            <dt className="text-ink-2">用藥</dt><dd>{p.medications.map((m) => `${m.name} ${m.dose} ${m.schedule}${m.is_anticoagulant ? "（抗凝血）" : ""}`).join("；")}</dd>
            <dt className="text-ink-2">DNR</dt><dd>{p.dnr ? "是" : "否"}</dd>
            <dt className="text-ink-2">緊急聯絡</dt><dd>{p.emergency_contacts.map((c) => `${c.relation} ${c.name}`).join("、")}</dd>
            <dt className="text-ink-2">特約醫療機構</dt><dd>{p.contract_facility?.name ?? "—"}</dd>
            <dt className="text-ink-2">照護者</dt><dd translate="no">{p.caregiver_code_name}</dd>
          </dl>
        </Card>
        <Card title="平常（基線，只在護理師確認時更新）" headingLevel={2} className="md:col-span-2">
          <table className="w-full text-sm">
            <tbody>
              {summary.baseline.entries.filter((e) => !e.valid_to).map((e) => (
                <tr key={e.dimension} className="border-t border-line">
                  <th scope="row" className="py-1 pr-3 text-left font-medium">
                    {DIMENSION_LABELS[e.dimension as Dimension]["zh-TW"]}
                    {changed.has(e.dimension) && <Chip tone="warn" className="ml-1">近期有變</Chip>}
                  </th>
                  <td className="py-1">{e.description}</td>
                  <td className="py-1 pl-2 text-right text-ink-2"><span translate="no">{e.confirmed_by ?? e.set_by}</span> · {fmtDay(e.valid_from)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      </div>
      <Card title="誰看過我的紀錄" headingLevel={2} meta={<span className="num" translate="no">Health ID {p.health_id}</span>}>
        {log && log.items.length === 0 && <p className="text-sm text-ink-2">還沒有人看過。</p>}
        <ul className="divide-y divide-line text-sm">
          {(log?.items ?? []).map((e, i) => (
            <li key={i} className="flex flex-wrap items-center gap-2 py-1.5">
              <span className="font-medium">{IDENTITIES[e.who]?.name ?? e.who}</span>
              <span className="text-ink-2">{e.role ? ROLE_LABEL[e.role] : ""}</span>
              <span className="text-ink-2">看了 {e.what.replace("summary:", "").replace("summary", "摘要").replace("who", "這是誰").replace("timeline", "紀錄").replace("docs", "文件").replace("talk", "對話")}</span>
              {e.purpose && <span className="text-xs text-ink-2">· 為了{e.purpose}</span>}
              <span className="ml-auto text-xs text-ink-2">{fmtDateTime(e.ts)}</span>
            </li>
          ))}
        </ul>
      </Card>
      {series.length > 0 && (
        <Card title="近 14 天有變化的維度" headingLevel={2}>
          <div className="grid gap-4 sm:grid-cols-2">
            {series.map((s) => (
              <Sparkline key={s.dimension} series={s} />
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
