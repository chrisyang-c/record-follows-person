"use client";

import Link from "next/link";
import { useState } from "react";
import { Chip } from "@/components/ui/badge";
import { useApi, type MeTimeline } from "@/lib/api";
import { fmtDay } from "@/lib/format";
import { LIFE_EVENT_LABEL } from "@/lib/labels";
import { useMyPatientId } from "@/lib/me";

const MONTH = (m: number) => `${m} 月`;

/** 我的時間軸：年 → 月 → 事件。年層只列大事件（確診、住院、手術、跌倒）；月層點開才看每天的觀察筆數與巡診／醫囑。 */
export default function MeTimelinePage() {
  const pid = useMyPatientId();
  const { data, error } = useApi<MeTimeline>(pid ? `/me/${pid}/timeline` : null, [pid]);
  const [open, setOpen] = useState<Record<string, boolean>>({});
  if (pid === undefined || (!data && !error)) return <p className="text-ink-2">Loading…</p>;
  if (error) return <p role="alert" className="text-danger-ink">{error}</p>;
  return (
    <div>
      <h1 className="text-2xl font-medium">我的時間軸</h1>
      <p className="mb-4 text-sm text-ink-2">一份紀錄，從第一次確診到今天。</p>
      <ol className="relative border-l border-line pl-4">
        {data!.years.map((y) => (
          <li key={y.year} className="mb-6">
            <span className="absolute -left-[5px] mt-2 size-[9px] rounded-full bg-primary" aria-hidden="true" />
            <h2 className="num text-xl font-medium">{y.year}</h2>
            {y.major.length === 0 && <p className="text-sm text-ink-2">日常紀錄 {y.months.reduce((n, m) => n + m.count, 0)} 筆，沒有大事件</p>}
            <ul className="mt-1 space-y-1">
              {y.major.map((e) => (
                <li key={e.id} className="flex items-center gap-2">
                  <Chip tone={e.type === "fall" || e.type === "acute" ? "danger" : "neutral"}>{LIFE_EVENT_LABEL[e.type as keyof typeof LIFE_EVENT_LABEL] ?? "事件"}</Chip>
                  <Link href={`/p/${pid}?tab=timeline#${e.id}`} className="hover:text-primary">{e.title}</Link>
                  <span className="text-xs text-ink-2">{fmtDay(e.ts)}</span>
                </li>
              ))}
            </ul>
            <button type="button" onClick={() => setOpen((o) => ({ ...o, [y.year]: !o[y.year] }))} aria-expanded={!!open[y.year]} className="mt-2 inline-flex min-h-11 items-center rounded text-sm text-primary hover:underline focus-visible:ring-2 focus-visible:ring-primary">
              {open[y.year] ? "收起月份" : `展開 ${y.months.length} 個月`}
            </button>
            {open[y.year] && (
              <ul className="mt-1 space-y-2 border-l border-line pl-3">
                {y.months.map((m) => (
                  <li key={m.month}>
                    <p className="text-sm"><span className="font-medium">{MONTH(m.month)}</span> <span className="text-ink-2">· 紀錄 <span className="num">{m.count}</span> 筆</span></p>
                    <ul className="text-sm text-ink-2">
                      {m.events.map((e) => (
                        <li key={e.id}><Link href={`/p/${pid}?tab=timeline#${e.id}`} className="hover:text-primary">{e.title}</Link> <span className="text-xs">{fmtDay(e.ts)}</span></li>
                      ))}
                    </ul>
                  </li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ol>
    </div>
  );
}
