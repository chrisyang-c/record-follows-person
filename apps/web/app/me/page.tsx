"use client";

import { ChevronRight, PenLine } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { AskBox } from "@/components/twin/ask-box";
import { DIMENSION_LABELS, DIMENSIONS, type Dimension } from "@schema";
import { Chip } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { streamSSE, useApi, type MeHome } from "@/lib/api";
import { fmtDateTime, fmtDay } from "@/lib/format";
import { DIRECTION_LABEL, LIFE_EVENT_LABEL } from "@/lib/labels";
import { useMyPatientId } from "@/lib/me";

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
    <div className="space-y-4 lg:grid lg:grid-cols-2 lg:gap-4 lg:space-y-0">
      <header className="text-center lg:col-span-2">
        <p className="text-xs text-ink-2">MY HEALTH TWIN</p>
        <h1 className="text-balance text-2xl font-medium">{p.code_name}</h1>
        <p className="text-sm text-ink-2">{age} 歲 · <span className="num" translate="no">Health ID {p.health_id}</span></p>
        <p className="mt-2 inline-flex items-center gap-2 rounded-full bg-surface px-3 py-1 text-base">
          <span className={`size-2 rounded-full ${data.status_line.includes("護理師") ? "bg-danger" : data.status_line.includes("不一樣") ? "bg-warn" : "bg-ok"}`} aria-hidden="true" />
          {data.status_line}
        </p>
      </header>

      <Card title="今天" headingLevel={2} meta={data.today.ts ? fmtDateTime(data.today.ts) : "還沒有今天的紀錄"}>
        {/* 8 個小卡：名稱＋一個詞（docs/UIUX_OMNI_TWIN.md §4.2） */}
        <ul className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {DIMENSIONS.map((d) => {
            const v = dims[d];
            const changed = !!v && v.direction !== "unknown" && v.direction !== "same";
            const word = !v ? "如常" : changed ? DIRECTION_LABEL[v.direction as "up" | "down"] : "如常";
            return (
              <li key={d} className={`rounded-[10px] border p-3 ${changed ? "border-accent-2/60 bg-surface-2" : "border-line bg-surface-2"}`} title={v ? `「${v.raw_quote}」` : undefined}>
                <p className="text-xs text-ink-2">{DIMENSION_LABELS[d as Dimension]["zh-TW"]}</p>
                <p className={`mt-1 text-lg font-medium ${changed ? "text-accent-2" : ""}`}>{word}</p>
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
              <Link href={e.id.startsWith("inc_") ? `/p/${pid}?tab=docs` : `/p/${pid}?tab=timeline#${e.id}`} className="min-w-0 flex-1 truncate hover:text-primary">{e.title}</Link>
              <span className="text-xs text-ink-2">{fmtDay(e.ts)}</span>
              <ChevronRight className="size-4 text-ink-2" aria-hidden="true" />
            </li>
          ))}
        </ul>
      </Card>

      <SelfNote pid={pid} name={p.code_name} />
      <div className="lg:col-span-2"><AskBox pid={pid} /></div>
    </div>
  );
}

/**
 * 本人自記（health-ref「手動填表」的想法改造）：寫進對話串（有 provenance、AI 只抽取），
 * 不直接寫 timeline——護理師確認後才是正式紀錄。
 */
function SelfNote({ pid, name }: { pid: string; name: string }) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [reply, setReply] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const send = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!text.trim() || busy) return;
    setBusy(true);
    setErr(null);
    setReply(null);
    let out = "";
    try {
      await streamSSE(`/patients/${pid}/talk`, { text: text.trim(), role_view: "caregiver" }, (n, d) => {
        if (n === "token") out += String(d.text ?? "");
        if (n === "error") throw new Error(String(d.text ?? d.detail ?? "error"));
      });
      setReply(out || "記下了。");
      setText("");
    } catch (e2) {
      setErr((e2 as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Card title="自己記一句" headingLevel={2} meta={<Link href={`/p/${pid}?tab=talk`} className="text-primary hover:underline">看整段對話 →</Link>}>
      <form onSubmit={send} className="flex gap-2">
        <label htmlFor="self-note" className="sr-only">今天怎麼樣</label>
        <input id="self-note" name="self_note" value={text} onChange={(e) => setText(e.target.value)} placeholder={`${name}今天…`} autoComplete="off" enterKeyHint="send" className="min-h-14 min-w-0 flex-1 rounded-[10px] border border-line bg-bg px-4 text-base text-ink placeholder:text-ink-2 focus-visible:border-primary focus-visible:ring-2 focus-visible:ring-primary" />
        <Button type="submit" size="lg" className="size-14 shrink-0 p-0" disabled={busy || !text.trim()} aria-label="記下">
          <PenLine className="size-6" aria-hidden="true" />
        </Button>
      </form>
      <p className="mt-2 text-xs text-ink-2">會進到你的對話串（AI 只抽取成八個面向），護理師確認後才成為正式紀錄。</p>
      {busy && <p className="mt-2 text-sm text-ink-2" aria-live="polite">記錄中…</p>}
      {reply && <p className="ai-draft mt-2 p-3 text-sm" aria-live="polite">{reply}</p>}
      {err && <p role="alert" className="mt-2 text-sm text-danger-ink">{err}</p>}
    </Card>
  );
}
