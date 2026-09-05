"use client";

import Link from "next/link";
import { RedFlagBanner } from "@/components/red-flag-banner";
import { useApi, usePolling, type InboxItem } from "@/lib/api";

/** 護理師的每一頁都壓在紅燈橫幅之下：住民、規則事實、照護者目前回報、一鍵進病人頁。 */
export function RedBannerGlobal() {
  const { data, reload } = useApi<{ items: InboxItem[] }>("/nurse/inbox");
  usePolling(reload, 5000);
  const all = (data?.items ?? []).filter((i) => i.red_flag);
  // 同一位住民只顯示最新一件；其餘件數併在標題
  const latest = new Map<string, InboxItem>();
  for (const i of all) if (!latest.has(i.patient_id) || (i.updated_at ?? "") > (latest.get(i.patient_id)!.updated_at ?? "")) latest.set(i.patient_id, i);
  const red = [...latest.values()];
  if (!red.length) return null;
  return (
    <div className="no-print mx-auto w-full max-w-6xl px-4 pt-3">
      {red.map((i) => (
        <RedFlagBanner
          key={i.thread_id}
          title={`紅燈 · ${i.code_name ?? i.patient_id}${all.filter((x) => x.patient_id === i.patient_id).length > 1 ? `（另 ${all.filter((x) => x.patient_id === i.patient_id).length - 1} 件）` : ""}：觀察到的事實 → 建議立即聯絡護理師`}
          lines={[
            ...i.red_flag_lines,
            ...(i.caregiver_reports.length ? [`照護者目前回報（${i.turn_count}）：${i.caregiver_reports.slice(-2).map((r) => `${r.question} ${r.answer}`).join("；")}`] : []),
          ]}
          action={
            <Link href={`/p/${i.patient_id}?tab=docs`} className="inline-flex min-h-14 items-center justify-center rounded-[10px] bg-danger-ink px-4 text-base font-medium text-white hover:underline focus-visible:ring-2 focus-visible:ring-danger">
              到場評估 →
            </Link>
          }
        />
      ))}
    </div>
  );
}
