"use client";

import Link from "next/link";
import { SensorEventCard } from "@/components/nurse/sensor-event-card";
import { TenSecondConfirm } from "@/components/nurse/ten-second-confirm";
import { DIMENSION_LABELS, DIMENSIONS, type Dimension } from "@schema";
import { Chip } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { useApi, usePolling, type HomeData, type HomeResident, type InboxItem, type SensorEvent } from "@/lib/api";
import { fmtDateTime } from "@/lib/format";
import { typeLabel } from "@/lib/labels";
import { cn } from "@/lib/utils";

/** 今日總覽一列：住民、八維度小點（有變化者亮 --accent-2、紅燈 --danger）、一句變化、待辦數。 */
function ResidentRow({ r, items }: { r: HomeResident; items: InboxItem[] }) {
  const abnormal = new Set((r.card.abnormal ?? []).map((l) => l.dimension));
  const mine = items.filter((i) => i.patient_id === r.patient_id);
  const red = mine.some((i) => i.red_flag);
  const first = r.card.abnormal?.[0]?.summary;
  return (
    <li className={cn("flex flex-wrap items-center gap-3 rounded-[12px] border bg-surface px-4 py-3", red ? "border-danger" : abnormal.size ? "border-warn/60" : "border-line")}>
      <Link href={`/p/${r.patient_id}`} className="min-w-[7rem] text-base font-medium hover:text-primary">{r.code_name} <span className="text-sm font-normal text-ink-2">{r.room}</span></Link>
      <ul className="flex items-center gap-1.5" aria-label="八維度">
        {DIMENSIONS.map((d) => (
          <li key={d} title={`${DIMENSION_LABELS[d as Dimension]["zh-TW"]}${abnormal.has(d) ? "：有變化" : ""}`} className={cn("size-2.5 rounded-full", red && abnormal.has(d) ? "bg-danger" : abnormal.has(d) ? "bg-accent-2" : "bg-line")} />
        ))}
      </ul>
      <span className="min-w-0 flex-1 truncate text-sm text-ink-2">{first ?? "近 7 天無異常趨勢"}</span>
      {mine.length > 0 && <Chip tone={red ? "danger" : "primary"}>{red ? "紅燈" : "待辦"} {mine.length}</Chip>}
      <span className="num text-xs text-ink-2">{fmtDateTime(r.last_entry_ts)}</span>
    </li>
  );
}

/** Clinical Queue（VISION §28.3）：紅燈橫幅（全站 layout）→ 新事件（含感測原始值）→ 待審核 → 今日總覽；右上「巡診準備」。 */
export default function NurseHome() {
  const { data: inbox, reload } = useApi<{ items: InboxItem[]; events: (SensorEvent & { code_name?: string | null })[] }>("/nurse/inbox");
  const { data: home } = useApi<HomeData>("/home/nurse");
  const residents = home?.residents;
  usePolling(reload, 5000);
  const items = inbox?.items ?? [];
  const pathA = items.filter((i) => i.graph === "path_a");
  const tens = items.filter((i) => i.interrupt_type === "nurse_10s_confirm");
  const round = items.filter((i) => i.graph === "round");
  const sensor = inbox?.events ?? [];
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-medium">Clinical Queue <span className="text-base font-normal text-ink-2">護理站</span></h1>
        <span className="text-sm text-ink-2" aria-live="polite">待辦 <span className="num">{items.length}</span> · 每 5 秒更新（分頁隱藏時暫停）</span>
        <Link href="/nurse/round" className="ml-auto inline-flex min-h-11 items-center rounded-[10px] border border-line px-4 hover:border-primary hover:text-primary">
          巡診準備{round.length > 0 ? `（${typeLabel(round[0].interrupt_type)}）` : ""} →
        </Link>
      </div>

      <section aria-labelledby="h-e">
        <h2 id="h-e" className="mb-2 text-lg font-medium">新事件</h2>
        {sensor.length === 0 && <p className="text-sm text-ink-2">沒有新的感測事件。（通道 4：<code>POST /sim/fall/{"{health_id}"}</code> 可模擬一筆「可能跌倒」）</p>}
        <ul className="grid gap-3 md:grid-cols-2">
          {sensor.map((e) => (
            <li key={e.id}><SensorEventCard e={e} /></li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="h-c">
        <h2 id="h-c" className="mb-2 text-lg font-medium">待審核</h2>
        {pathA.length === 0 && tens.length === 0 && <p className="text-sm text-ink-2">沒有待確認的草稿。照護者送出後會出現在這裡。</p>}
        <ul className="grid gap-3 md:grid-cols-2">
          {pathA.map((i) => (
            <li key={i.thread_id}>
              <Card variant={i.red_flag ? "red" : "ai"} title={<>{i.code_name ?? i.patient_id} · {typeLabel(i.interrupt_type)}</>} meta={fmtDateTime(i.updated_at)}>
                <p className="truncate text-sm" title={i.summary || i.red_flag_lines[0]}><span className="label-caps mr-2">S</span>{i.summary || i.red_flag_lines[0]}</p>
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
                <Link href={`/p/${i.patient_id}?tab=docs`} className="mt-3 inline-flex min-h-14 w-full items-center justify-center rounded-[10px] bg-primary px-4 text-on-primary hover:bg-primary-hover">
                  {i.red_flag ? "事件資訊包 / 護理評估" : "審核 ISBAR"}
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
        <ul className="space-y-2">
          {(residents ?? [])
            .slice()
            .sort((a, b) => Number(items.some((i) => i.patient_id === b.patient_id && i.red_flag)) - Number(items.some((i) => i.patient_id === a.patient_id && i.red_flag)) || (b.card.abnormal?.length ?? 0) - (a.card.abnormal?.length ?? 0))
            .map((r) => (
              <ResidentRow key={r.patient_id} r={r} items={items} />
            ))}
        </ul>
      </section>
      <p className="text-sm"><Link href="/" className="inline-flex min-h-11 items-center text-ink-2 hover:text-ink">切換角色</Link></p>
    </div>
  );
}
