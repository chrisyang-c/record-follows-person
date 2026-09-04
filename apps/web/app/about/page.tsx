"use client";

import Link from "next/link";
import { Card } from "@/components/ui/card";
import { useApi, type Resident } from "@/lib/api";
import { fmtDateTime } from "@/lib/format";

const CHANNELS = [
  { n: 1, name: "照服員每班觀察 + 護理師 ISBAR", live: true },
  { n: 2, name: "醫師醫囑（巡診）", live: true },
  { n: 3, name: "出院摘要（mock）", live: false },
  { n: 4, name: "生命徵象（寫死）", live: false },
  { n: 5, name: "家屬觀察", live: false },
  { n: 6, name: "健保雲端藥歷", live: false },
  { n: 7, name: "感測器", live: false },
];

const PILL = "inline-flex min-h-11 items-center rounded-full border border-line px-3 hover:border-primary hover:text-primary";

export default function About() {
  const { data: residents, error, loading } = useApi<Resident[]>("/residents");
  return (
    <div className="space-y-8">
      <section className="max-w-3xl">
        <h1 className="text-3xl font-medium leading-tight">每個人有一份跟著他走的紀錄，和一個替這份紀錄說話的 agent。</h1>
        <p className="mt-3 text-ink-2">今天，它先學會聽照顧他的人說話。照服員講一句話（中文；多語為第二階段）→ 八維度 → 護理師按一下 → 醫師看一頁。</p>
      </section>

      <section aria-labelledby="residents">
        <h2 id="residents" className="mb-3 text-lg font-medium">三位住民（合成資料）</h2>
        {error && (
          <p role="alert" className="text-danger-ink">
            API 沒有回應：<span translate="no">{error}</span>。請先啟動 <code>make api</code>。
          </p>
        )}
        {loading && <p className="text-ink-2">Loading…</p>}
        {residents && residents.length === 0 && (
          <p className="text-ink-2">
            還沒有住民資料，先跑 <code>make seed</code>。
          </p>
        )}
        {residents && residents.length > 0 && (
          <ul className="grid gap-4 sm:grid-cols-3">
            {residents.map((r) => (
              <li key={r.patient_id}>
                <Card title={`${r.code_name} · ${r.room}`} meta={<span translate="no">{r.patient_id}</span>}>
                  <p className="text-sm text-ink-2">
                    紀錄 <span className="num">{r.timeline_count}</span> 筆 · 事故 <span className="num">{r.incident_count}</span> · 最近 {fmtDateTime(r.last_entry_ts)}
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2 text-sm">
                    <Link className={PILL} href={`/p/${r.patient_id}`}>這個人的頁 →</Link>
                  </div>
                </Card>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-labelledby="channels">
        <h2 id="channels" className="mb-3 text-lg font-medium">七條通道，同一份紀錄</h2>
        <ol className="grid gap-2 sm:grid-cols-4 lg:grid-cols-7">
          {CHANNELS.map((c) => (
            // --ai-fill 只代表「AI 草稿」；已接上的通道用 --primary 邊框 + --surface
            <li key={c.n} className={c.live ? "rounded-[10px] border border-primary bg-surface p-3 text-sm" : "rounded-[10px] border border-line bg-surface p-3 text-sm text-ink-2"}>
              <span className="num mr-1 text-xs">{c.n}</span>
              {c.name}
            </li>
          ))}
        </ol>
        <p className="mt-2 text-sm text-ink-2">今天接了通道 1 與 2，這份紀錄會一直長。</p>
        <p className="mt-4 text-sm"><Link href="/" className="inline-flex min-h-11 items-center text-primary hover:underline">← 選角色</Link></p>
      </section>
    </div>
  );
}
