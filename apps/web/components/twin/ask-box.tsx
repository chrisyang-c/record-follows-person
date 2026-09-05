"use client";

import { Search, Volume2, VolumeX } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { askRecord, type AskAnswer } from "@/lib/api";
import { fmtDay } from "@/lib/format";

/** 瀏覽器語音（zh-TW）；「唸給我聽」的想法參考 health-ref（speechSynthesis 驅動嘴型），重寫。 */
function speak(text: string, onStart: () => void, onEnd: () => void) {
  if (typeof window === "undefined" || !("speechSynthesis" in window)) return false;
  window.speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  const zh = window.speechSynthesis.getVoices().find((v) => v.lang.startsWith("zh"));
  if (zh) u.voice = zh;
  u.lang = zh?.lang ?? "zh-TW";
  u.rate = 1.0;
  u.onstart = onStart;
  u.onend = onEnd;
  u.onerror = onEnd;
  window.speechSynthesis.speak(u);
  return true;
}

/**
 * 問我的紀錄：每句附可點的來源行；AI 產出＝虛線＋淡藍。可「唸給我聽」（語音，分身嘴型同步）。
 * 只回答紀錄裡有的事，不給建議、不解讀數值。
 */
export function AskBox({ pid, onSpeaking, onFocus }: { pid: string; onSpeaking?: (s: boolean) => void; onFocus?: (dimension: string | null) => void }) {
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [ans, setAns] = useState<AskAnswer | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [speaking, setSpeaking] = useState(false);
  useEffect(() => () => { if (typeof window !== "undefined" && "speechSynthesis" in window) window.speechSynthesis.cancel(); }, []);
  const setSpk = (s: boolean) => { setSpeaking(s); onSpeaking?.(s); };
  const ask = async (question: string) => {
    if (!question.trim() || busy) return;
    setBusy(true);
    setErr(null);
    try {
      const a = await askRecord(pid, question.trim());
      setAns(a);
      onFocus?.(a.found ? guessDimension(a) : null);
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const text = ans ? (ans.found ? ans.sentences.map((s) => s.text).join("。") : (ans.fallback ?? "紀錄裡沒有這件事。")) : "";
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
        <input id="ask" name="ask" value={q} onChange={(e) => setQ(e.target.value)} placeholder="我以前有做過心臟手術嗎…" autoComplete="off" enterKeyHint="search" inputMode="text" className="min-h-14 min-w-0 flex-1 rounded-[10px] border border-line bg-bg px-4 text-base text-ink placeholder:text-ink-2 focus-visible:border-primary focus-visible:ring-2 focus-visible:ring-primary" />
        <Button type="submit" size="lg" className="size-14 shrink-0 p-0" disabled={busy} aria-label="問">
          <Search className="size-6" aria-hidden="true" />
        </Button>
      </form>
      <div className="mt-2 flex flex-wrap gap-2">
        {["我住過幾次院？", "上次跌倒是什麼時候？", "我最近睡得怎樣？"].map((s) => (
          <button key={s} type="button" onClick={() => { setQ(s); void ask(s); }} className="min-h-11 rounded-full border border-line px-3 text-sm hover:border-primary focus-visible:ring-2 focus-visible:ring-primary">{s}</button>
        ))}
      </div>
      {busy && <p className="mt-3 text-sm text-ink-2" aria-live="polite">正在翻我的紀錄…</p>}
      {err && <p role="alert" className="mt-3 text-sm text-danger-ink">{err}</p>}
      {ans && !busy && (
        <div className="ai-draft mt-3 p-3" aria-live="polite">
          <div className="mb-2 flex items-center gap-2">
            <p className="text-xs text-accent-2">只回答紀錄裡有的事，不給建議、不解讀數值</p>
            <Button type="button" variant="secondary" className="ml-auto min-h-10 px-3 text-sm" onClick={() => (speaking ? (window.speechSynthesis.cancel(), setSpk(false)) : speak(text, () => setSpk(true), () => setSpk(false)))} aria-pressed={speaking}>
              {speaking ? <><VolumeX className="size-4" aria-hidden="true" />停止</> : <><Volume2 className="size-4" aria-hidden="true" />唸給我聽</>}
            </Button>
          </div>
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

/** 回答要高亮哪個維度（health-ref 的 focusWidget 想法）：依來源行與句子的關鍵字猜，猜不到就不動。 */
function guessDimension(a: AskAnswer): string | null {
  const text = a.sentences.map((s) => s.text + s.sources.map((x) => x.text).join(" ")).join(" ");
  const table: [string, RegExp][] = [
    ["sleep", /睡|夜|起來/], ["intake", /吃|喝|飯|食|水/], ["elimination", /尿|便|排泄/], ["function", /走|站|轉位|活動|跌/],
    ["cognition", /清醒|混亂|失智|認|情緒/], ["skin", /皮膚|傷|壓傷|紅/], ["pain", /痛/], ["vitals", /血壓|心跳|心率|喘|咳|發燒|SpO/],
  ];
  for (const [d, re] of table) if (re.test(text)) return d;
  return null;
}
