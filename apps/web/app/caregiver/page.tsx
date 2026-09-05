"use client";

import { AlertTriangle, Check, ChevronRight, Phone } from "lucide-react";
import Link from "next/link";
import { useSyncExternalStore } from "react";
import { DIMENSION_LABELS, type Dimension } from "@schema";
import { Chip } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { useApi, usePolling, type HomeData, type HomeResident } from "@/lib/api";
import { fmtDateTime, fmtDay } from "@/lib/format";
import { LIFE_EVENT_LABEL } from "@/lib/labels";
import { IDENTITIES, identityOf, readMe } from "@/lib/role";

/** 我照顧的人（一張卡）：今天狀態一行、有變的維度、警示、事件，點進去就是對話（四鍵在對話裡）。 */
function PersonCard({ r }: { r: HomeResident }) {
  const c = r.card;
  const status = c.status_line ?? (c.recorded_today ? "今天記了" : "今天還沒記");
  const alerts = (c.alerts ?? []).filter((a) => a !== status);
  const pendingFall = !!c.pending_event;
  return (
    <Card headingLevel={2} variant={pendingFall ? "red" : "default"} title={<Link href={`/p/${r.patient_id}?tab=talk`} className="text-xl hover:text-primary">{r.code_name} <span className="text-sm font-normal text-ink-2">{r.room}</span></Link>} meta={c.latest_ts ? `最近 ${fmtDateTime(c.latest_ts)}` : undefined}>
      <p className="flex items-center gap-2 text-base">
        <span className={`size-2 shrink-0 rounded-full ${(c.alerts ?? []).length ? "bg-danger" : c.changed_dimensions?.length ? "bg-warn" : "bg-ok"}`} aria-hidden="true" />
        {status}
      </p>
      {c.changed_dimensions && c.changed_dimensions.length > 0 && (
        <p className="mt-1 flex flex-wrap gap-1">
          {c.changed_dimensions.map((d) => (
            <Chip key={d} tone="warn">{DIMENSION_LABELS[d as Dimension]?.["zh-TW"] ?? d}</Chip>
          ))}
        </p>
      )}
      {alerts.length > 0 && (
        <ul className="mt-2 space-y-1" aria-label="警示">
          {alerts.map((a) => (
            <li key={a} className="flex items-center gap-2 text-sm text-danger-ink"><AlertTriangle className="size-4" aria-hidden="true" />{a}</li>
          ))}
        </ul>
      )}
      <p className="mt-2 flex flex-wrap items-center gap-2 text-sm text-ink-2">
        {c.recorded_today ? <span className="inline-flex items-center gap-1 text-ok-ink"><Check className="size-4" aria-hidden="true" />今天記了</span> : <span>今天還沒記</span>}
        {(c.notes_count ?? 0) > 0 && <span>注意事項 <span className="num">{c.notes_count}</span> 件</span>}
      </p>
      {c.recent_events && c.recent_events.length > 0 && (
        <ul className="mt-2 divide-y divide-line border-t border-line text-sm" aria-label="事件">
          {c.recent_events.slice(0, 2).map((e) => (
            <li key={e.id} className="flex items-center gap-2 py-1.5">
              <Chip tone={e.type === "fall" || e.type === "acute" ? "danger" : "neutral"}>{LIFE_EVENT_LABEL[e.type as keyof typeof LIFE_EVENT_LABEL] ?? "事件"}</Chip>
              <span className="min-w-0 flex-1 truncate">{e.title}</span>
              <span className="text-xs text-ink-2">{fmtDay(e.ts)}</span>
            </li>
          ))}
        </ul>
      )}
      <Link href={`/p/${r.patient_id}?tab=talk`} className={`mt-3 flex min-h-14 items-center justify-center gap-1 rounded-[10px] px-4 text-base font-medium ${pendingFall ? "bg-danger-ink text-on-primary" : "bg-primary text-on-primary hover:bg-primary-hover"}`}>
        {pendingFall ? "請確認他的狀況" : "講一句今天怎麼樣"} <ChevronRight className="size-5" aria-hidden="true" />
      </Link>
      {c.care_team && (
        <details className="mt-3 text-sm">
          <summary className="inline-flex min-h-11 cursor-pointer items-center gap-1 text-ink-2 hover:text-ink"><Phone className="size-4" aria-hidden="true" />聯絡照護團隊</summary>
          <ul className="mt-1 space-y-1 pl-5">
            <li>護理師：<span translate="no">{IDENTITIES[c.care_team.primary_nurse]?.name ?? c.care_team.primary_nurse}</span></li>
            <li>醫師：<span translate="no">{IDENTITIES[c.care_team.doctor]?.name ?? c.care_team.doctor}</span></li>
            <li>特約醫療機構：{c.care_team.facility.name} <a href={`tel:${c.care_team.facility.phone}`} className="num text-primary hover:underline">{c.care_team.facility.phone}</a></li>
            {c.care_team.emergency_contacts.map((e) => (
              <li key={e.phone}>{e.relation} {e.name} <a href={`tel:${e.phone}`} className="num text-primary hover:underline">{e.phone}</a></li>
            ))}
          </ul>
        </details>
      )}
    </Card>
  );
}

/**
 * 家屬／照護者首頁（VISION §28.2）：我照顧的人 → 今天狀態 → 警示 → 事件 → 聯絡照護團隊。
 * 家屬只看自己那一位；照服員看全部。每 5 秒更新（分頁隱藏時暫停），可能跌倒的四鍵在對話裡。
 */
export default function CaregiverHome() {
  const me = useSyncExternalStore(() => () => {}, () => readMe(), () => null);
  const identity = identityOf(me);
  const { data: home, error, reload } = useApi<HomeData>("/home/caregiver", [me]);
  usePolling(reload, 5000);
  const residents = (home?.residents ?? []).filter((r) => !identity?.patient_id || r.patient_id === identity.patient_id);
  return (
    <div className="mx-auto max-w-[390px] space-y-4">
      <h1 className="text-balance text-2xl font-medium">{identity?.role === "family" ? "我的家人" : "我照顧的人"}</h1>
      {error && <p role="alert" className="text-danger-ink">無法連線到 API，請確認 make api 已啟動。</p>}
      {home && residents.length === 0 && <p className="text-ink-2">還沒有住民資料，先跑 <code>make seed</code>。</p>}
      <ul className="grid gap-3">
        {residents.map((r) => (
          <li key={r.patient_id}><PersonCard r={r} /></li>
        ))}
      </ul>
      <p className="pt-4 text-center text-sm"><Link href="/" className="inline-flex min-h-11 items-center text-ink-2 hover:text-ink">切換身份</Link></p>
    </div>
  );
}
