"use client";

import Link from "next/link";
import type { SensorEvent } from "@schema";
import { VERIFY_LABELS } from "@schema";
import { Chip } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { fmtDateTime } from "@/lib/format";

/**
 * 護理站「新事件」卡：通道 4 的「可能跌倒」。原始值（加速度尖峰、姿態改變、靜止秒數、心率前後、SpO₂）
 * 只在這裡出現；照護者與醫師端不顯示任何原始值、信心值或百分比（CLAUDE.md §1）。
 */
export function SensorEventCard({ e, codeName }: { e: SensorEvent & { code_name?: string | null }; codeName?: string | null }) {
  const name = codeName ?? e.code_name ?? e.patient_id;
  const v = e.verification;
  return (
    <Card variant={e.hard_flag ? "red" : "default"} title={<>{name} · 可能跌倒 <span className="text-sm font-normal text-ink-2">（感測器，{e.location}）</span></>} headingLevel={3} meta={fmtDateTime(e.ts)}>
      <div className="mb-2 flex flex-wrap gap-1">
        <Chip tone={e.status === "pending" ? "warn" : e.status === "verified" ? "ok" : "neutral"}>{e.status === "pending" ? "待照護者驗證" : e.status === "verified" ? "照護者已回覆" : "已結案"}</Chip>
        {e.hard_flag && <Chip tone="danger">硬條件命中 → 已通知護理師</Chip>}
        {e.thread_id && !e.hard_flag && <Chip tone="danger">已進紅燈流程</Chip>}
      </div>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm sm:grid-cols-3">
        <div><dt className="text-ink-2">加速度尖峰</dt><dd className="num">{e.accel_peak_g} g</dd></div>
        <div><dt className="text-ink-2">姿態改變</dt><dd className="num">{e.orientation_change_deg}°</dd></div>
        <div><dt className="text-ink-2">事件後靜止</dt><dd className="num">{e.still_seconds} 秒</dd></div>
        <div><dt className="text-ink-2">心率 前 → 後</dt><dd className="num">{e.hr_before} → {e.hr_after}</dd></div>
        <div><dt className="text-ink-2">SpO₂（後）</dt><dd className="num">{e.spo2_after ?? "—"}</dd></div>
        <div><dt className="text-ink-2">來源</dt><dd translate="no">{e.source}</dd></div>
      </dl>
      {e.hard_facts.length > 0 && (
        <ul className="mt-2 text-sm text-danger-ink">
          {e.hard_facts.map((f) => <li key={f}>觀察到：{f} → 建議立即聯絡護理師</li>)}
        </ul>
      )}
      <div className="mt-2 rounded-[8px] bg-surface px-3 py-2 text-sm" aria-live="polite">
        <p className="font-medium">照護者回覆</p>
        {v ? (
          <p>{VERIFY_LABELS[v.choice]}{v.text ? `：${v.text}` : ""} <span className="text-xs text-ink-2">· {v.by} · {fmtDateTime(v.ts)}</span></p>
        ) : (
          <p className="text-ink-2">還沒有回覆（照護者端四鍵：{Object.values(VERIFY_LABELS).join("／")}）</p>
        )}
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        <Link href={`/p/${e.patient_id}?tab=docs`} className="inline-flex min-h-14 flex-1 items-center justify-center rounded-[10px] bg-primary px-4 text-on-primary hover:bg-primary-hover">
          {e.thread_id ? "事件資訊包 / 護理評估" : "看這個人"}
        </Link>
        <Link href={`/p/${e.patient_id}?tab=talk`} className="inline-flex min-h-14 items-center justify-center rounded-[10px] border border-line px-4 hover:border-primary">對話</Link>
      </div>
    </Card>
  );
}
