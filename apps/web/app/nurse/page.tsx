"use client";

import Link from "next/link";
import { useEffect } from "react";
import type { TrendReport } from "@schema";
import { TenSecondConfirm } from "@/components/nurse/ten-second-confirm";
import { Sparkline } from "@/components/sparkline";
import { Chip } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { useApi, type InboxItem, type Resident } from "@/lib/api";
import { fmtDateTime } from "@/lib/format";
import { typeLabel } from "@/lib/labels";

function ResidentRow({ r, items }: { r: Resident; items: InboxItem[] }) {
  const { data } = useApi<TrendReport>(`/trends/${r.patient_id}`);
  const abnormal = data?.lines.filter((l) => l.is_abnormal) ?? [];
  const series = data?.series.filter((s) => abnormal.slice(0, 2).some((a) => a.dimension === s.dimension)) ?? [];
  const mine = items.filter((i) => i.patient_id === r.patient_id);
  return (
    <Card title={<Link href={`/p/${r.patient_id}`} className="hover:text-primary">{r.code_name} · {r.room}</Link>} headingLevel={3} className={abnormal.length ? "border-warn" : ""}>
      <div className="mb-2 flex flex-wrap gap-1">
        {abnormal.length === 0 && <Chip tone="ok">近 7 天無異常趨勢</Chip>}
        {abnormal.map((l) => (
          <Chip key={l.dimension} tone="warn">{l.summary}</Chip>
        ))}
        {mine.map((i) => (
          <Chip key={i.thread_id} tone={i.red_flag ? "danger" : "primary"}>{typeLabel(i.interrupt_type)}</Chip>
        ))}
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {series.map((s) => (
          <Sparkline key={s.dimension} series={s} height={56} />
        ))}
      </div>
      <p className="mt-2 text-xs text-ink-2">最近 {fmtDateTime(r.last_entry_ts)} · 紀錄 <span className="num">{r.timeline_count}</span> 筆</p>
    </Card>
  );
}

/** 護理站：紅燈橫幅（全站 layout）→ 等我確認 → 今日總覽；右上「巡診準備」。 */
export default function NurseHome() {
  const { data: inbox, reload } = useApi<{ items: InboxItem[] }>("/nurse/inbox");
  const { data: residents } = useApi<Resident[]>("/residents");
  useEffect(() => {
    const id = setInterval(reload, 5000);
    return () => clearInterval(id);
  }, [reload]);
  const items = inbox?.items ?? [];
  const pathA = items.filter((i) => i.graph === "path_a");
  const tens = items.filter((i) => i.interrupt_type === "nurse_10s_confirm");
  const round = items.filter((i) => i.graph === "round");
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-medium">護理站</h1>
        <span className="text-sm text-ink-2" aria-live="polite">待辦 <span className="num">{items.length}</span> · 每 5 秒更新</span>
        <Link href="/nurse/round" className="ml-auto inline-flex min-h-11 items-center rounded-[10px] border border-line px-4 hover:border-primary hover:text-primary">
          巡診準備{round.length > 0 ? `（${typeLabel(round[0].interrupt_type)}）` : ""} →
        </Link>
      </div>

      <section aria-labelledby="h-c">
        <h2 id="h-c" className="mb-2 text-lg font-medium">等我確認</h2>
        {pathA.length === 0 && tens.length === 0 && <p className="text-sm text-ink-2">沒有待確認的草稿。照護者送出後會出現在這裡。</p>}
        <ul className="grid gap-3 md:grid-cols-2">
          {pathA.map((i) => (
            <li key={i.thread_id}>
              <Card variant={i.red_flag ? "red" : "ai"} title={<>{i.code_name ?? i.patient_id} · {typeLabel(i.interrupt_type)}</>} meta={fmtDateTime(i.updated_at)}>
                <p className="line-clamp-2 text-sm">{i.summary || i.red_flag_lines[0]}</p>
                {i.caregiver_reports.length > 0 && (
                  <div className="mt-2 rounded-[8px] bg-surface px-2 py-1 text-xs" aria-live="polite">
                    <p className="font-medium">照護者目前回報（{i.turn_count}）</p>
                    <ul>
                      {i.caregiver_reports.slice(-3).map((r, k) => (
                        <li key={k}>{r.question}：{r.answer}</li>
                      ))}
                    </ul>
                  </div>
                )}
                <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-ink-2">
                  {i.deadline && <span>期限 {fmtDateTime(i.deadline)}</span>}
                  {i.escalation_level > 0 && <Chip tone="warn">已升級 {i.escalation_level} 次</Chip>}
                </div>
                <Link href={`/p/${i.patient_id}?tab=docs`} className="mt-3 inline-flex min-h-14 w-full items-center justify-center rounded-[10px] bg-primary px-4 text-white hover:bg-primary-hover">
                  {i.red_flag ? "到場評估 / 審核" : "審核 ISBAR"}
                </Link>
              </Card>
            </li>
          ))}
          {tens.map((i) => (
            <li key={i.thread_id}>
              <TenSecondConfirm item={i} onDone={reload} />
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="h-t">
        <h2 id="h-t" className="mb-2 text-lg font-medium">今日總覽（異常優先）</h2>
        <ul className="grid gap-3 lg:grid-cols-3">
          {(residents ?? [])
            .slice()
            .sort((a, b) => Number(items.some((i) => i.patient_id === b.patient_id && i.red_flag)) - Number(items.some((i) => i.patient_id === a.patient_id && i.red_flag)))
            .map((r) => (
              <li key={r.patient_id}>
                <ResidentRow r={r} items={items} />
              </li>
            ))}
        </ul>
      </section>
    </div>
  );
}
