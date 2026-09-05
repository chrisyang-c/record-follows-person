"use client";

import { ChevronRight, Search } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { DIMENSION_LABELS, DIMENSIONS, type Dimension } from "@schema";
import { Chip } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { askRecord, useApi, type AskAnswer, type MeHome } from "@/lib/api";
import { fmtDateTime, fmtDay } from "@/lib/format";
import { DIRECTION_LABEL, LIFE_EVENT_LABEL } from "@/lib/labels";
import { useMyPatientId } from "@/lib/me";

/** 「問我的紀錄」：每句附可點的來源行（timeline id）。AI 產出＝虛線＋淡藍。 */
function AskBox({ pid }: { pid: string }) {
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [ans, setAns] = useState<AskAnswer | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const ask = async (question: string) => {
    if (!question.trim() || busy) return;
    setBusy(true);
    setErr(null);
    try {
      setAns(await askRecord(pid, question.trim()));
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Card title="問我的紀錄" headingLevel={2}>
      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          void ask(q);
        }}
      >
        <label htmlFor="ask" className="sr-only">問題</label>
        <input id="ask" value={q} onChange={(e) => setQ(e.target.value)} placeholder="我以前有做過心臟手術嗎？" className="min-h-14 min-w-0 flex-1 rounded-[10px] border border-line bg-bg px-4 text-base placeholder:text-ink-2 focus-visible:border-primary" />
        <Button type="submit" size="lg" className="size-14 shrink-0 p-0" disabled={busy} aria-label="問">
          <Search className="size-6" aria-hidden="true" />
        </Button>
      </form>
      <div className="mt-2 flex flex-wrap gap-2">
        {["我住過幾次院？", "上次跌倒是什麼時候？", "我有哪些慢性病？"].map((s) => (
          <button key={s} type="button" onClick={() => { setQ(s); void ask(s); }} className="min-h-11 rounded-full border border-line px-3 text-sm hover:border-primary">{s}</button>
        ))}
      </div>
      {busy && <p className="mt-3 text-sm text-ink-2" aria-live="polite">正在翻我的紀錄…</p>}
      {err && <p role="alert" className="mt-3 text-sm text-danger-ink">{err}</p>}
      {ans && !busy && (
        <div className="ai-draft mt-3 p-3" aria-live="polite">
          <p className="mb-2 text-xs text-primary">只回答紀錄裡有的事，不給建議、不解讀數值</p>
          {ans.found ? (
            <ul className="space-y-2">
              {ans.sentences.map((s, i) => (
                <li key={i}>
                  <p className="text-base">{s.text}</p>
                  <p className="mt-0.5 flex flex-wrap gap-2 text-xs">
                    {s.sources.map((src) => (
                      <Link key={src.id} href={`/p/${pid}?tab=timeline#${src.id.split("#")[0]}`} className="rounded-full border border-line bg-bg px-2 py-0.5 text-ink-2 hover:border-primary hover:text-primary">
                        來源 · {fmtDay(src.date)} · {src.text.slice(0, 24)}{src.text.length > 24 ? "…" : ""}
                      </Link>
                    ))}
                  </p>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-base">{ans.fallback ?? "紀錄裡沒有這件事。"}</p>
          )}
          <p className="mt-2 text-[11px] text-ink-2">
            personal agent · retrieve {ans.meta.tool_counts?.retrieve ?? 0} 次{ans.meta.duration_s != null ? ` · ${ans.meta.duration_s} 秒` : ""}{ans.meta.scripted ? " · scripted" : ""}
          </p>
        </div>
      )}
    </Card>
  );
}

/** 本人首頁（VISION §28.1）：狀態一行 → 今天八維度 → 終身摘要 → 最近事件 → 問我的紀錄。 */
export default function MeHomePage() {
  const pid = useMyPatientId();
  const { data, error } = useApi<MeHome>(pid ? `/me/${pid}/home` : null, [pid]);
  if (pid === undefined) return <p className="text-ink-2">Loading…</p>;
  if (pid === null) return <p role="alert" className="text-danger-ink">這個身份沒有對應的紀錄。</p>;
  if (error) return <p role="alert" className="text-danger-ink">{error}</p>;
  if (!data) return <p className="text-ink-2">Loading…</p>;
  const p = data.profile;
  const age = new Date().getFullYear() - p.birth_year;
  const dims = data.today.dimensions;
  return (
    <div className="space-y-4">
      <header className="text-center">
        <p className="text-xs text-ink-2">MY HEALTH TWIN</p>
        <h1 className="text-2xl font-medium">{p.code_name}</h1>
        <p className="text-sm text-ink-2">{age} 歲 · <span className="num" translate="no">Health ID {p.health_id}</span></p>
        <p className="mt-2 inline-flex items-center gap-2 rounded-full bg-surface px-3 py-1 text-base">
          <span className={`size-2 rounded-full ${data.status_line.includes("護理師") ? "bg-danger" : data.status_line.includes("不一樣") ? "bg-warn" : "bg-ok"}`} aria-hidden="true" />
          {data.status_line}
        </p>
      </header>

      <Card title="今天" headingLevel={2} meta={data.today.ts ? fmtDateTime(data.today.ts) : "還沒有今天的紀錄"}>
        <ul className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
          {DIMENSIONS.map((d) => {
            const v = dims[d];
            return (
              <li key={d} className="flex items-baseline justify-between gap-2 border-b border-line py-1">
                <span className="text-ink-2">{DIMENSION_LABELS[d as Dimension]["zh-TW"]}</span>
                <span className="text-right">{v ? `「${v.raw_quote}」` : "跟平常一樣"}{v && v.direction !== "unknown" && v.direction !== "same" ? <Chip tone="warn" className="ml-1">{DIRECTION_LABEL[v.direction as "up" | "down"]}</Chip> : null}</span>
              </li>
            );
          })}
        </ul>
      </Card>

      <Card title="終身摘要" headingLevel={2} meta={`從 ${data.lifelong.since} 年起`}>
        <ul className="grid grid-cols-4 gap-2 text-center">
          {[["慢性病", data.lifelong.conditions], ["住院", data.lifelong.hospitalizations], ["手術", data.lifelong.surgeries], ["紀錄年數", data.lifelong.years_of_records]].map(([k, v]) => (
            <li key={String(k)} className="rounded-[10px] bg-surface py-2">
              <p className="num text-2xl font-medium">{v}</p>
              <p className="text-xs text-ink-2">{k}</p>
            </li>
          ))}
        </ul>
      </Card>

      <Card title="最近事件" headingLevel={2} meta={<Link href="/me/events" className="text-primary hover:underline">全部 →</Link>}>
        {data.recent_events.length === 0 && <p className="text-sm text-ink-2">沒有重大事件。</p>}
        <ul className="divide-y divide-line">
          {data.recent_events.slice(0, 3).map((e) => (
            <li key={e.id} className="flex items-center gap-2 py-2">
              <Chip tone={e.type === "fall" ? "danger" : "neutral"}>{LIFE_EVENT_LABEL[e.type as keyof typeof LIFE_EVENT_LABEL] ?? e.type}</Chip>
              <Link href={`/p/${pid}?tab=timeline#${e.id}`} className="min-w-0 flex-1 truncate hover:text-primary">{e.title}</Link>
              <span className="text-xs text-ink-2">{fmtDay(e.ts)}</span>
              <ChevronRight className="size-4 text-ink-2" aria-hidden="true" />
            </li>
          ))}
        </ul>
      </Card>

      <AskBox pid={pid} />
    </div>
  );
}
