"use client";

import { ScanLine } from "lucide-react";
import Link from "next/link";
import { Suspense, useState, useSyncExternalStore } from "react";
import { useSearchParams } from "next/navigation";
import { identityOf, readMe } from "@/lib/role";
import { DIMENSIONS, type Dimension } from "@schema";
import { BodyHologram, ORGANS } from "@/components/twin/body-hologram";
import { TrendLine } from "@/components/twin/trend-line";
import { Chip } from "@/components/ui/badge";
import { useApi, type TwinData } from "@/lib/api";
import { fmtDateTime } from "@/lib/format";
import { DIRECTION_LABEL } from "@/lib/labels";
import { useMyPatientId } from "@/lib/me";
import { cn } from "@/lib/utils";

const STATE_LABEL = { same: "跟平常一樣", changed: "有變化", red: "護理師處理中" } as const;

/**
 * 01 活體數位孿生（docs/UIUX_OMNI_TWIN.md §4.1）：左 55% 人體圖（8 熱點），右 45% 維度面板
 * （維度名＋一句狀態、大數字、14 天趨勢、最近一筆照護者原話、一句一般建議）。底部八維度橫向 tab。
 * wellness 語氣只在這裡與 /me；沒有今天的紀錄時熱點全部靜態。
 */
function TwinInner() {
  const mine = useMyPatientId();
  const sp = useSearchParams();
  const me = useSyncExternalStore(() => () => {}, () => readMe(), () => null);
  const identity = identityOf(me);
  const pid = mine ?? sp.get("pid") ?? null;
  const { data, error } = useApi<TwinData>(pid ? `/twin/${pid}` : null, [pid]);
  const { data: residents } = useApi<{ patient_id: string; code_name: string; room: string }[]>(!pid ? "/residents" : null);
  const [sel, setSel] = useState<Dimension>("intake");
  if (mine === undefined) return <p className="text-ink-2">Loading…</p>;
  if (pid === null) {
    // 家屬／照護者／護理師／醫師：先選要看的人（01 是本人視角，工作人員代看）
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-medium">活體數位孿生體</h1>
        <p className="text-ink-2">{identity ? `${identity.name}，` : ""}01 是本人視角。你要看哪一位？（能看多少由 Care Circle 決定）</p>
        <ul className="grid gap-3 sm:grid-cols-3">
          {(residents ?? []).map((r) => (
            <li key={r.patient_id}>
              <Link href={`/twin?pid=${r.patient_id}`} className="flex min-h-16 items-center justify-between rounded-[12px] border border-line bg-surface px-4 hover:border-accent">
                <span className="text-lg font-medium">{r.code_name}</span><span className="text-sm text-ink-2">{r.room}</span>
              </Link>
            </li>
          ))}
        </ul>
      </div>
    );
  }
  if (!data && !error) return <p className="text-ink-2">Loading…</p>;
  if (error) return <p role="alert" className="text-danger-ink">{error}</p>;
  const t = data!;
  const idle = !t.today_ts;
  const states = Object.fromEntries(Object.entries(t.dimensions).map(([k, v]) => [k, v.state])) as Record<string, "same" | "changed" | "red">;
  const d = t.dimensions[sel];
  const age = new Date().getFullYear() - t.profile.birth_year;
  const changedN = Object.values(t.dimensions).filter((v) => v.state !== "same").length;
  const big = d.value != null && typeof d.value === "number" ? (sel === "intake" ? `${Math.round(d.value * 100)}%` : String(d.value)) : d.quote ? `「${d.quote}」` : "—";
  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-center gap-3">
        {!mine && <Link href="/twin" className="text-xs text-ink-2 hover:text-ink">← 換一位</Link>}
        <span className="inline-flex size-12 items-center justify-center rounded-full border border-accent/60 text-accent"><ScanLine className="size-6" aria-hidden="true" /></span>
        <div className="min-w-0">
          <h1 className="text-2xl font-medium">活體數位孿生體</h1>
          <p className="label-caps">Bio-Twin · Organ Drill-down · {t.profile.code_name} · {age} 歲</p>
        </div>
        <span className={cn("ml-auto inline-flex items-center gap-2 rounded-full border px-3 py-1 text-sm", changedN ? "border-accent-2/60 text-accent-2" : "border-accent/40 text-accent")}>
          <span className={cn("size-2 rounded-full", t.status_line.includes("護理師") ? "bg-danger" : changedN ? "bg-accent-2" : "bg-accent glow")} aria-hidden="true" />
          {idle ? "今天還沒有人記錄" : t.status_line}
        </span>
      </header>

      <div className="grid gap-4 lg:grid-cols-[55fr_45fr]">
        <section className="rounded-[12px] border border-line bg-surface p-4" aria-label="人體圖">
          <BodyHologram states={states} selected={sel} onSelect={setSel} idle={idle} />
          <p className="mt-2 text-center text-xs text-ink-2">{idle ? "熱點全部靜態：今天還沒有人記錄" : "亮紫＝有變化（呼吸）· 青＝跟平常一樣 · 紅＝護理師處理中"} · 解剖圖：EMBL-EBI anatomogram</p>
        </section>

        <section className="rounded-[12px] border border-line bg-surface p-5 fade-in" key={sel} aria-live="polite">
          <div className="flex flex-wrap items-center gap-2">
            <span className={cn("inline-flex size-10 items-center justify-center rounded-full border text-sm font-medium", d.state === "red" ? "border-danger text-danger-ink" : d.state === "changed" ? "border-accent-2/60 text-accent-2" : "border-accent/50 text-accent")}>{ORGANS[sel].short.slice(0, 1)}</span>
            <div className="min-w-0">
              <h2 className="text-lg font-medium">{d.label}</h2>
              <p className="text-sm text-ink-2">{d.note || (d.state === "same" ? "跟平常一樣" : STATE_LABEL[d.state])}{d.days > 1 ? `，第 ${d.days} 天` : ""}</p>
            </div>
            <Chip className="ml-auto" tone={d.state === "red" ? "danger" : d.state === "changed" ? "warn" : "ok"}>{STATE_LABEL[d.state]}</Chip>
          </div>
          <p className="mt-4"><span className="big-num">{big}</span>{d.direction !== "unknown" && d.direction !== "same" && <span className="ml-2 text-sm text-accent-2">{DIRECTION_LABEL[d.direction]}</span>}</p>
          <div className="mt-3"><TrendLine points={d.series} /></div>
          <dl className="mt-3 grid grid-cols-2 gap-2 text-sm">
            <div className="rounded-[10px] bg-surface-2 p-3"><dt className="label-caps">平常</dt><dd className="mt-1">{d.baseline || "—"}</dd></div>
            <div className="rounded-[10px] bg-surface-2 p-3"><dt className="label-caps">最近一筆</dt><dd className="mt-1 text-ink-2">{d.quote ? `「${d.quote}」` : "還沒有人記錄"}</dd></div>
          </dl>
          <p className="mt-3 rounded-[10px] border border-line p-3 text-sm"><span className="label-caps mr-2">一般建議</span>{d.tip}</p>
          <p className="mt-2 text-xs text-ink-2">最近更新 {fmtDateTime(t.today_ts)} · 照護鏈上的判斷仍由護理師與醫師做。</p>
        </section>
      </div>

      <nav aria-label="八維度" className="-mx-4 overflow-x-auto px-4">
        <ul className="flex gap-2">
          {DIMENSIONS.map((k) => {
            const v = t.dimensions[k];
            const on = k === sel;
            return (
              <li key={k}>
                <button type="button" aria-pressed={on} onClick={() => setSel(k as Dimension)} className={cn("inline-flex min-h-12 items-center gap-2 whitespace-nowrap rounded-full border px-4 text-sm focus-visible:ring-2 focus-visible:ring-accent", on ? "border-accent-2 bg-surface text-ink" : "border-line text-ink-2 hover:text-ink")}>
                  <span className={cn("size-2 rounded-full", v.state === "red" ? "bg-danger" : v.state === "changed" ? "bg-accent-2" : "bg-accent")} aria-hidden="true" />
                  {v.label}
                </button>
              </li>
            );
          })}
        </ul>
      </nav>
    </div>
  );
}

export default function TwinPage() {
  return (
    <Suspense fallback={<p className="text-ink-2">Loading…</p>}>
      <TwinInner />
    </Suspense>
  );
}
