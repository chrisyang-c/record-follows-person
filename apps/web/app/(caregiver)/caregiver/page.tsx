"use client";

import { Mic, SendHorizontal, Square } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState, useSyncExternalStore } from "react";
import type { RedFlagResult, StructuredObservation } from "@schema";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/field";
import { api, startPathA, startShift, useApi, type Resident, type Snapshot } from "@/lib/api";
import { SPEECH_LANG, T } from "@/lib/i18n";
import { cn } from "@/lib/utils";

type Turn = { text: string; dimension: string | null; quick: boolean };
type Kind = "start" | "question" | "summary" | "red" | "final" | "plain";
type Msg = { id: number; role: "sys" | "me"; text: string; kind?: Kind; quick?: string[]; qkey?: string; lines?: string[] };
interface DialogResult {
  observation: StructuredObservation;
  red_flags: RedFlagResult;
  red_flag_lines: string[];
  next_question: { key: string; text: string; quick_replies: string[] } | null;
  asked_dimensions: string[];
  turn_count: number;
  done: boolean;
  red: boolean;
  summary: string;
  transcript: string;
}
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

const EVENTS = [
  { key: "seems_different", label: "跟平常不一樣", text: "跟平常不一樣" },
  { key: "fall", label: "跌倒", text: "跌倒" },
  { key: "medication_issue", label: "拒藥／吐藥", text: "不肯吃藥" },
  { key: "choking", label: "嗆咳", text: "嗆到" },
  { key: "behavior", label: "打人／遊走", text: "打人遊走" },
];
const t = T["zh-TW"];

function getRecognition(): (new () => SpeechRecognitionLike) | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as { SpeechRecognition?: new () => SpeechRecognitionLike; webkitSpeechRecognition?: new () => SpeechRecognitionLike };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

let nextId = 1;
const mk = (role: Msg["role"], text: string, extra: Partial<Msg> = {}): Msg => ({ id: nextId++, role, text, ...extra });

function Bubble({ m, children }: { m: Msg; children?: React.ReactNode }) {
  const me = m.role === "me";
  const cls = m.kind === "red" ? "red-flag" : me ? "bg-primary text-white" : "bg-surface text-ink";
  return (
    <div className={cn("flex flex-col", me ? "items-end" : "items-start")}>
      <div
        className={cn("max-w-[85%] whitespace-pre-wrap break-words rounded-2xl px-4 py-3 text-base leading-relaxed", cls, me ? "rounded-br-md" : "rounded-bl-md")}
        role={m.kind === "red" ? "alert" : undefined}
        aria-live={m.kind === "red" ? "assertive" : undefined}
      >
        {m.text}
        {m.lines && (
          <ul className="mt-2 space-y-1 text-sm">
            {m.lines.map((l, i) => (
              <li key={i}>{l}</li>
            ))}
          </ul>
        )}
      </div>
      {children}
    </div>
  );
}

function ChatInner() {
  const router = useRouter();
  const params = useSearchParams();
  const { data: residents } = useApi<Resident[]>("/residents");
  const patient = params.get("patient") ?? residents?.[0]?.patient_id ?? "P001";
  const resident = residents?.find((r) => r.patient_id === patient);
  const name = resident?.code_name ?? "他";

  const [messages, setMessages] = useState<Msg[]>([]);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [incidents, setIncidents] = useState<string[]>([]);
  const [seemsDifferent, setSeemsDifferent] = useState(false);
  const [pendingKey, setPendingKey] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [finished, setFinished] = useState(false);
  const [hint, setHint] = useState<string | null>(null);
  const [listening, setListening] = useState(false);
  const recRef = useRef<SpeechRecognitionLike | null>(null);
  const endRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const speechOk = useSyncExternalStore(() => () => {}, () => !!getRecognition(), () => true);

  const started = messages.length > 0;
  const opening = mk("sys", `${name}今天怎麼樣？講一句就好。`, { kind: "start" });
  const view = started ? messages : [opening];

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [messages.length, busy]);

  const push = (...ms: Msg[]) => setMessages((prev) => (prev.length ? [...prev, ...ms] : [opening, ...ms]));

  const reset = () => {
    setMessages([]);
    setTurns([]);
    setIncidents([]);
    setSeemsDifferent(false);
    setPendingKey(null);
    setFinished(false);
    setHint(null);
    setInput("");
  };

  const finish = async (mode: "shift" | "path_a", allTurns: Turn[], inc: string[], sd: boolean) => {
    const body = { patient_id: patient, turns: allTurns, incidents: inc, seems_different: sd, caregiver_id: resident?.caregiver_code_name, caregiver_confirmed_meaning: true };
    const snap: Snapshot = mode === "path_a" ? await startPathA(body) : await startShift(body);
    const red = mode === "path_a" || !!snap.handoff;
    push(mk("sys", red ? "已通知護理師，請留在他身邊。" : "已送出，護理師會在這一班確認。謝謝你。", { kind: "final" }));
    setFinished(true);
  };

  const submitTurn = async (text: string, dimension: string | null, quick: boolean, inc = incidents, sd = seemsDifferent) => {
    const clean = text.trim();
    if (!clean) {
      setHint("先講一句或打幾個字。");
      inputRef.current?.focus();
      return;
    }
    setHint(null);
    setBusy(true);
    const allTurns = [...turns, { text: clean, dimension, quick }];
    setTurns(allTurns);
    setPendingKey(null);
    push(mk("me", clean));
    setInput("");
    try {
      const r = await api<DialogResult>("/intake/turn", { method: "POST", json: { patient_id: patient, turns: allTurns, seems_different: sd, incidents: inc } });
      if (r.red) {
        push(mk("sys", "已通知護理師。", { kind: "red", lines: r.red_flag_lines }));
        await finish("path_a", allTurns, inc, sd);
      } else if (r.next_question) {
        setPendingKey(r.next_question.key);
        push(mk("sys", r.next_question.text, { kind: "question", quick: r.next_question.quick_replies, qkey: r.next_question.key }));
      } else {
        push(mk("sys", r.summary, { kind: "summary" }));
      }
    } catch (e) {
      push(mk("sys", `${t.errorRetry}（${(e as Error).message}）`, { kind: "plain" }));
    } finally {
      setBusy(false);
    }
  };

  const onEvent = (key: string, text: string) => {
    const inc = key === "seems_different" ? incidents : [...incidents, key];
    const sd = key === "seems_different" ? true : seemsDifferent;
    setIncidents(inc);
    setSeemsDifferent(sd);
    void submitTurn(text, null, true, inc, sd);
  };

  const confirm = async (mode: "shift" | "path_a") => {
    setBusy(true);
    try {
      await finish(mode, turns, incidents, seemsDifferent);
    } catch (e) {
      push(mk("sys", `${t.errorRetry}（${(e as Error).message}）`, { kind: "plain" }));
    } finally {
      setBusy(false);
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
    rec.lang = SPEECH_LANG["zh-TW"];
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

  const lastQuestion = [...view].reverse().find((m) => m.kind === "question");
  const lastSummary = view[view.length - 1]?.kind === "summary" ? view[view.length - 1] : null;

  return (
    <div className="-my-6 mx-auto flex min-h-[calc(100dvh-3.75rem)] w-full max-w-[390px] flex-col">
      <h1 className="sr-only">{t.title}</h1>
      <header className="flex items-center gap-2 border-b border-line px-3 py-2">
        <label htmlFor="patient" className="sr-only">{t.resident}</label>
        <Select
          id="patient"
          name="patient"
          value={patient}
          onChange={(e) => {
            reset();
            router.replace(`/caregiver?patient=${e.target.value}`);
          }}
          className="min-h-11 flex-1 text-base"
        >
          {(residents ?? []).map((r) => (
            <option key={r.patient_id} value={r.patient_id}>
              {r.code_name} · {r.room}
            </option>
          ))}
        </Select>
        <Link href={`/caregiver/notes?patient=${patient}`} className="inline-flex min-h-11 items-center rounded-[10px] px-3 text-sm text-primary hover:bg-surface">
          {t.notes}
        </Link>
      </header>

      <div className="flex-1 space-y-3 px-3 py-4" aria-live="polite">
        {view.map((m) => (
          <Bubble key={m.id} m={m}>
            {m.kind === "start" && !started && (
              <div className="mt-2 grid w-full max-w-[85%] grid-cols-2 gap-2">
                {EVENTS.map((ev) => (
                  <Button key={ev.key} variant={ev.key === "seems_different" ? "secondary" : "outline"} size="lg" className={cn("text-base", ev.key === "seems_different" && "col-span-2")} disabled={busy} onClick={() => onEvent(ev.key, ev.text)}>
                    {ev.label}
                  </Button>
                ))}
              </div>
            )}
            {m.kind === "question" && m === lastQuestion && m.qkey === pendingKey && (
              <div className="mt-2 grid w-full max-w-[85%] grid-cols-2 gap-2">
                {(m.quick ?? []).map((q) => (
                  <Button key={q} variant={q === t.dontKnow ? "secondary" : "outline"} size="lg" className="text-base" disabled={busy} onClick={() => submitTurn(q, m.qkey ?? null, true)}>
                    {q}
                  </Button>
                ))}
              </div>
            )}
            {m.kind === "summary" && m === lastSummary && !finished && (
              <div className="mt-2 grid w-full max-w-[85%] gap-2">
                <Button variant="ok" size="lg" className="text-base" disabled={busy} onClick={() => confirm("shift")}>
                  對，送給護理師
                </Button>
                <Button variant="danger" size="lg" className="text-base" disabled={busy} onClick={() => confirm("path_a")}>
                  對，需要護理師現在來看
                </Button>
                <Button variant="outline" size="lg" className="text-base" disabled={busy} onClick={reset}>
                  不對，我再說
                </Button>
              </div>
            )}
            {m.kind === "final" && (
              <div className="mt-2 flex gap-2">
                <Button variant="outline" size="lg" className="text-base" onClick={reset}>
                  再報一句
                </Button>
              </div>
            )}
          </Bubble>
        ))}
        {busy && <p className="px-2 text-sm text-ink-2">{t.sending}</p>}
        <div ref={endRef} />
      </div>

      <form
        className="sticky bottom-0 flex items-end gap-2 border-t border-line bg-bg px-3 pt-2 pb-[calc(0.5rem+env(safe-area-inset-bottom))]"
        onSubmit={(e) => {
          e.preventDefault();
          void submitTurn(input, pendingKey, false);
        }}
      >
        <Button type="button" variant={listening ? "danger" : "secondary"} size="lg" className="size-14 shrink-0 rounded-full p-0" onClick={toggleListen} disabled={!speechOk || finished} aria-pressed={listening} aria-label={listening ? "說完了" : "按一下說話"}>
          {listening ? <Square className="size-6" aria-hidden="true" /> : <Mic className="size-6" aria-hidden="true" />}
        </Button>
        <label htmlFor="say" className="sr-only">打字</label>
        <input
          id="say"
          ref={inputRef}
          name="say"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={listening ? "聽你說…" : pendingKey ? "或打字回答…" : `${name}今天…`}
          autoComplete="off"
          disabled={finished}
          className="min-h-14 min-w-0 flex-1 rounded-[10px] border border-line bg-bg px-4 text-base text-ink placeholder:text-ink-2/70 focus-visible:border-primary"
        />
        <Button type="submit" variant="primary" size="lg" className="size-14 shrink-0 p-0" disabled={busy || finished} aria-label="送出">
          <SendHorizontal className="size-6" aria-hidden="true" />
        </Button>
      </form>
      {hint && (
        <p role="alert" className="px-3 pb-2 text-sm text-danger-ink">
          {hint}
        </p>
      )}
    </div>
  );
}

export default function CaregiverPage() {
  return (
    <Suspense fallback={<p className="text-ink-2">Loading…</p>}>
      <ChatInner />
    </Suspense>
  );
}
