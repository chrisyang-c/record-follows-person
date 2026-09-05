"use client";

import { Mic, SendHorizontal, Square } from "lucide-react";
import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { ActivityBar } from "@/components/patient/activity-bar";
import { Button } from "@/components/ui/button";
import { streamSSE, type ActivityEvent, type ConvMessage, type PatientSummary, type TalkDone } from "@/lib/api";
import { fmtDay } from "@/lib/format";
import type { Role } from "@/lib/role";
import { cn } from "@/lib/utils";

type SpeechRecognitionLike = {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  start(): void;
  stop(): void;
  onresult: ((e: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null;
  onend: (() => void) | null;
  onerror: (() => void) | null;
};
function getRecognition(): (new () => SpeechRecognitionLike) | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as { SpeechRecognition?: new () => SpeechRecognitionLike; webkitSpeechRecognition?: new () => SpeechRecognitionLike };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

let localId = 0;
const dayOf = (ts: string) => ts.slice(0, 10);

function Bubble({ m, role }: { m: ConvMessage; role: Role }) {
  if (m.role === "system") {
    return (
      <p className={cn("px-4 text-center text-xs text-ink-2", m.kind === "error" && "text-danger-ink")} role={m.kind === "error" ? "alert" : undefined}>
        {m.text}
      </p>
    );
  }
  const me = m.role === "caregiver";
  const red = !!m.meta.red || m.meta.phase === "red";
  return (
    <div className={cn("flex flex-col gap-1", me ? "items-end" : "items-start")}>
      <div className={cn("max-w-[85%] whitespace-pre-wrap break-words rounded-2xl px-4 py-3 text-base leading-relaxed", me ? "rounded-br-md bg-primary text-white" : "rounded-bl-md bg-surface text-ink", !me && red && "border border-danger")}>
        {m.text}
      </div>
      {!me && m.meta.activity && <ActivityBar events={m.meta.activity} role={role} />}
    </div>
  );
}

/**
 * 對話 tab：每位住民一條持續的對話（日期分隔線），系統事件置中灰字；
 * 送出 → SSE：活動事件（活動列）→ 逐字回覆 → done。紅燈不打斷對話。
 */
export function TalkTab({ summary, role, onChanged }: { summary: PatientSummary; role: Role; onChanged: () => void }) {
  const pid = summary.profile.patient_id;
  const name = summary.profile.code_name;
  const [messages, setMessages] = useState<ConvMessage[]>(summary.conversation);
  const [live, setLive] = useState<{ events: ActivityEvent[]; text: string; system: string[] } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [listening, setListening] = useState(false);
  const recRef = useRef<SpeechRecognitionLike | null>(null);
  const endRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const speechOk = useSyncExternalStore(() => () => {}, () => !!getRecognition(), () => true);
  const busy = live !== null;

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [messages.length, live?.text, live?.events.length]);

  const send = async (raw: string) => {
    const text = raw.trim();
    if (!text || busy) {
      inputRef.current?.focus();
      return;
    }
    setError(null);
    setInput("");
    const mine: ConvMessage = { id: `local_${++localId}`, patient_id: pid, session_id: "", role: "caregiver", kind: "message", text, ts: new Date().toISOString(), meta: {} };
    setMessages((ms) => [...ms, mine]);
    const state = { events: [] as ActivityEvent[], text: "", system: [] as string[] };
    setLive({ ...state });
    try {
      await streamSSE(`/patients/${pid}/talk`, { text, role_view: role }, (name, data) => {
        if (name === "event") state.events = [...state.events, data as unknown as ActivityEvent];
        else if (name === "token") state.text += String(data.text ?? "");
        else if (name === "system") state.system = [...state.system, String(data.text ?? "")];
        else if (name === "error") throw new Error(String(data.text ?? "系統暫時無法回覆，請直接告訴護理師。"), { cause: String(data.detail ?? "") });
        else if (name === "done") {
          const d = data as unknown as TalkDone;
          const sys: ConvMessage[] = state.system.map((t, i) => ({ id: `sys_${localId}_${i}`, patient_id: pid, session_id: "", role: "system", kind: "event", text: t, ts: new Date().toISOString(), meta: { red: d.red } }));
          const agent: ConvMessage | null = d.reply
            ? { id: String(d.meta?.message_id ?? `agent_${localId}`), patient_id: pid, session_id: "", role: "agent", kind: d.kind, text: d.reply, ts: new Date().toISOString(), meta: { ...(d.meta ?? {}), activity: state.events, red: d.red } }
            : null;
          setMessages((ms) => [...ms, ...sys, ...(agent ? [agent] : [])]);
          onChanged();
        }
        setLive({ ...state });
      });
    } catch (e) {
      // 沒有模型／模型失敗：畫面上顯示錯誤並停止，不退回規則版
      const err = e as Error;
      const msg = err.message || "系統暫時無法回覆，請直接告訴護理師。";
      const detail = typeof err.cause === "string" ? err.cause : "";
      setError(role === "caregiver" || !detail ? msg : `${msg}（${detail}）`);
      setMessages((ms) => [...ms, { id: `err_${localId}`, patient_id: pid, session_id: "", role: "system", kind: "error", text: msg, ts: new Date().toISOString(), meta: { detail } }]);
    } finally {
      setLive(null);
    }
  };

  const toggleListen = () => {
    const R = getRecognition();
    if (!R) return;
    if (listening) {
      recRef.current?.stop();
      return;
    }
    const rec = new R();
    rec.lang = "zh-TW";
    rec.interimResults = false;
    rec.continuous = false;
    rec.onresult = (e) => {
      const transcript = Array.from({ length: e.results.length }, (_, i) => e.results[i][0].transcript).join("");
      setInput((prev) => (prev ? `${prev}，${transcript}` : transcript));
      inputRef.current?.focus();
    };
    rec.onend = () => setListening(false);
    rec.onerror = () => setListening(false);
    recRef.current = rec;
    setListening(true);
    rec.start();
  };

  // 日期分隔線
  const rows: (ConvMessage | { day: string })[] = [];
  let lastDay = "";
  for (const m of messages) {
    const d = dayOf(m.ts);
    if (d !== lastDay) {
      rows.push({ day: d });
      lastDay = d;
    }
    rows.push(m);
  }
  const phase = summary.session?.phase;
  const placeholder = listening ? "聽你說…" : busy ? "…" : phase === "confirm" ? "對／不對，或再補一句…" : phase === "red" ? "還有什麼要跟護理師說的…" : `${name}今天…`;

  return (
    <div className="mx-auto flex min-h-[calc(100dvh-9rem)] w-full max-w-[390px] flex-col">
      <div className="flex-1 space-y-3 px-1 py-3">
        {messages.length === 0 && !live && <p className="rounded-2xl rounded-bl-md bg-surface px-4 py-3 text-base">{name}今天怎麼樣？講一句就好。</p>}
        {rows.map((r) =>
          "day" in r ? (
            <p key={`d_${r.day}`} className="text-center text-xs text-ink-2">
              <span className="rounded-full bg-surface px-2 py-0.5">{fmtDay(r.day)}</span>
            </p>
          ) : (
            <Bubble key={r.id} m={r} role={role} />
          ),
        )}
        {live && (
          <div className="flex flex-col items-start gap-1" aria-live="polite">
            <ActivityBar events={live.events} role={role} live defaultOpen={role !== "caregiver"} />
            {live.system.map((s, i) => (
              <p key={i} className="w-full text-center text-xs text-ink-2">{s}</p>
            ))}
            {live.text && <div className="max-w-[85%] whitespace-pre-wrap break-words rounded-2xl rounded-bl-md bg-surface px-4 py-3 text-base leading-relaxed">{live.text}<span className="ml-0.5 inline-block w-[2px] animate-pulse bg-ink align-text-bottom" style={{ height: "1em" }} aria-hidden="true" /></div>}
          </div>
        )}
        <div ref={endRef} />
      </div>

      <form
        className="sticky bottom-0 flex items-end gap-2 border-t border-line bg-bg px-1 pt-2 pb-[calc(0.5rem+env(safe-area-inset-bottom))]"
        onSubmit={(e) => {
          e.preventDefault();
          void send(input);
        }}
      >
        <Button type="button" variant={listening ? "danger" : "secondary"} size="lg" className="size-[72px] shrink-0 rounded-full p-0" onClick={toggleListen} disabled={!speechOk || busy} aria-pressed={listening} aria-label={listening ? "說完了" : "按一下說話"}>
          {listening ? <Square className="size-7" aria-hidden="true" /> : <Mic className="size-8" aria-hidden="true" />}
        </Button>
        <label htmlFor="say" className="sr-only">打字</label>
        <input
          id="say"
          ref={inputRef}
          name="say"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={placeholder}
          autoComplete="off"
          inputMode="text"
          enterKeyHint="send"
          className="min-h-14 min-w-0 flex-1 rounded-[10px] border border-line bg-bg px-4 text-base text-ink placeholder:text-ink-2 focus-visible:border-primary"
        />
        <Button type="submit" variant="primary" size="lg" className="size-14 shrink-0 p-0" disabled={busy} aria-label="送出">
          <SendHorizontal className="size-6" aria-hidden="true" />
        </Button>
      </form>
      {error && (
        <p role="alert" className="px-1 pb-2 text-sm text-danger-ink">
          {error}
        </p>
      )}
    </div>
  );
}
