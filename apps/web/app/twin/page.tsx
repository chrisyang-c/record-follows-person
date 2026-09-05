"use client";

import { ScanLine, UserRound } from "lucide-react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState, useSyncExternalStore } from "react";
import { DIMENSIONS, type Dimension } from "@schema";
import { AskBox } from "@/components/twin/ask-box";
import { BodyHologram, ORGANS } from "@/components/twin/body-hologram";
import { TrendLine } from "@/components/twin/trend-line";
import { WearableChart } from "@/components/twin/wearable-chart";
import { Chip } from "@/components/ui/badge";
import { useApi, type Mood, type TwinData } from "@/lib/api";
import { fmtDateTime } from "@/lib/format";
import { DIRECTION_LABEL } from "@/lib/labels";
import { useMyPatientId } from "@/lib/me";
import { identityOf, readMe } from "@/lib/role";
import { cn } from "@/lib/utils";

const AvatarView = dynamic(() => import("@/components/twin/avatar-view").then((m) => m.AvatarView), { ssr: false, loading: () => <div className="grid h-[420px] place-items-center rounded-[12px] border border-line bg-surface-2 text-sm text-ink-2 lg:h-[520px]">載入分身…</div> });

const STATE_LABEL = { same: "跟平常一樣", changed: "有變化", red: "護理師處理中" } as const;
const MOOD_LABEL: Record<Mood, string> = { same: "跟平常一樣", changed: "有變化", attention: "請留意" };

/** 沙盤的心情只是示意：睡眠與體重相對基準（不是預測、不是診斷）。 */
function sandboxMood(sleep: number, weight: number, base: number): Mood {
  const dw = Math.abs(weight - base);
  if (sleep < 5 || dw >= 8) return "attention";
  if (sleep < 6.5 || dw >= 4) return "changed";
  return "same";
}

/**
 * 01 活體數位孿生（docs/UIUX_OMNI_TWIN.md §4.1）：左「解剖全像｜我的分身」，右維度面板。
 * 分身、沙盤、穿戴數據卡、複合圖、唸給我聽的互動想法來自 health-ref（重寫）。wellness 語氣只在這裡與 /me。
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
  const [view, setView] = useState<"anatomy" | "avatar">("anatomy");
  const [sandbox, setSandbox] = useState(false);
  const [simSleep, setSimSleep] = useState(7.5);
  const [simWeight, setSimWeight] = useState<number | null>(null);
  const [speaking, setSpeaking] = useState(false);
  if (mine === undefined) return <p className="text-ink-2">Loading…</p>;
  if (pid === null) {
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
  const baseW = t.avatar.weight_kg ?? 60;
  const simW = simWeight ?? baseW;
  const last = t.wearable[t.wearable.length - 1];
  const bmi = t.profile.height_cm && t.profile.weight_kg ? (t.profile.weight_kg / Math.pow(t.profile.height_cm / 100, 2)).toFixed(1) : null;
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

      <div role="group" aria-label="視圖" className="flex gap-2">
        {([["anatomy", "解剖全像", ScanLine], ["avatar", "我的分身", UserRound]] as const).map(([k, label, Icon]) => (
          <button key={k} type="button" aria-pressed={view === k} onClick={() => setView(k)} className={cn("inline-flex min-h-11 items-center gap-2 rounded-full border px-4 text-sm focus-visible:ring-2 focus-visible:ring-accent", view === k ? "border-accent bg-surface text-ink" : "border-line text-ink-2 hover:text-ink")}>
            <Icon className="size-4" aria-hidden="true" />{label}
          </button>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-[55fr_45fr]">
        <section className="rounded-[12px] border border-line bg-surface p-4" aria-label={view === "anatomy" ? "人體圖" : "我的分身"}>
          {view === "anatomy" ? (
            <>
              <BodyHologram states={states} selected={sel} onSelect={setSel} idle={idle} />
              <p className="mt-2 text-center text-xs text-ink-2">{idle ? "熱點全部靜態：今天還沒有人記錄" : "亮紫＝有變化（呼吸）· 青＝跟平常一樣 · 紅＝護理師處理中"} · 解剖圖：EMBL-EBI anatomogram</p>
            </>
          ) : (
            <>
              <AvatarView
                now={{ sleepHours: t.avatar.sleep_hours, weightKg: t.avatar.weight_kg, mood: t.avatar.mood }}
                sandbox={sandbox ? { sleepHours: simSleep, weightKg: simW, mood: sandboxMood(simSleep, simW, baseW) } : null}
                baseWeightKg={baseW}
                speaking={speaking}
              />
              <div className="mt-3 rounded-[10px] border border-line bg-surface-2 p-3 text-sm">
                <div className="flex flex-wrap items-center gap-3">
                  <label className="inline-flex min-h-11 cursor-pointer items-center gap-2 font-medium text-accent-2">
                    <input type="checkbox" checked={sandbox} onChange={(e) => setSandbox(e.target.checked)} className="size-4 accent-[var(--accent-2)]" />
                    沙盤模擬
                  </label>
                  <span className="text-xs text-ink-2">「如果睡多一點、體重不同，我看起來會怎樣」——示意，不是預測或診斷。</span>
                  {sandbox && <Chip className="ml-auto" tone={sandboxMood(simSleep, simW, baseW) === "same" ? "ok" : sandboxMood(simSleep, simW, baseW) === "changed" ? "warn" : "danger"}>沙盤：{MOOD_LABEL[sandboxMood(simSleep, simW, baseW)]}</Chip>}
                </div>
                {sandbox && (
                  <div className="mt-3 grid gap-3 sm:grid-cols-2">
                    <label className="block">
                      <span className="flex justify-between text-xs"><span>每天睡</span><strong className="num text-accent">{simSleep} 小時</strong></span>
                      <input type="range" name="sim_sleep" min={3} max={10} step={0.5} value={simSleep} onChange={(e) => setSimSleep(Number(e.target.value))} className="mt-1 w-full accent-[var(--accent-2)]" />
                    </label>
                    <label className="block">
                      <span className="flex justify-between text-xs"><span>體重</span><strong className="num text-accent">{simW} kg</strong></span>
                      <input type="range" name="sim_weight" min={Math.round(baseW - 15)} max={Math.round(baseW + 15)} step={0.5} value={simW} onChange={(e) => setSimWeight(Number(e.target.value))} className="mt-1 w-full accent-[var(--accent-2)]" />
                    </label>
                  </div>
                )}
              </div>
              <p className="mt-2 text-center text-xs text-ink-2">分身表情與膚色只反映睡眠與八維度的變化；模型與規則想法來自團隊 health-ref（public/models/LICENSE.txt）。</p>
            </>
          )}
        </section>

        <section className="fade-in rounded-[12px] border border-line bg-surface p-5" key={sel} aria-live="polite">
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

      {/* 穿戴每日指標（通道 4，模擬）：只有事實數值，沒有品質分數 */}
      <section className="rounded-[12px] border border-line bg-surface p-5" aria-labelledby="wear">
        <div className="mb-3 flex flex-wrap items-baseline gap-2">
          <h2 id="wear" className="text-lg font-medium">今天的身體</h2>
          <span className="label-caps">Wearable · 模擬穿戴 · {last ? last.day : "—"}</span>
          {bmi && <span className="ml-auto text-sm text-ink-2">身高 <span className="num">{t.profile.height_cm}</span> cm · 體重 <span className="num">{t.profile.weight_kg}</span> kg · BMI <span className="num">{bmi}</span></span>}
        </div>
        {last ? (
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {[["睡眠", `${last.sleep_hours} h`, `深睡 ${last.deep_sleep_hours} h · REM ${last.rem_hours} h`], ["步數", `${last.steps.toLocaleString()}`, `運動 ${last.exercise_min} 分鐘`], ["靜息心率", `${last.resting_hr} bpm`, `HRV ${last.hrv_ms} ms`], ["血氧", `${last.spo2}%`, "SpO₂"]].map(([k, v, sub]) => (
              <div key={k} className="rounded-[10px] bg-surface-2 p-3">
                <p className="text-xs text-ink-2">{k}</p>
                <p className="big-num mt-1 text-[28px]">{v}</p>
                <p className="mt-1 text-xs text-ink-2">{sub}</p>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-ink-2">還沒有穿戴資料。</p>
        )}
        <div className="mt-4"><WearableChart rows={t.wearable} /></div>
      </section>

      <AskBox pid={pid} onSpeaking={setSpeaking} onFocus={(dim) => { if (dim) setSel(dim as Dimension); }} />
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
