"use client";

import type { Baseline, Document, PersonRecord, Profile, StructuredObservation, TimelineEntry, RedFlagResult, SensorEvent, TrendLine, TrendReport, VerifyChoice } from "@schema";
import { useCallback, useEffect, useState } from "react";
import { readMe, readRole, type Tab } from "@/lib/role";

export const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

/** 每個請求帶「我是誰」（X-Who）；API 查 Care Circle 決定能看什麼並寫 access log。X-Role 只是舊相容。 */
function roleHeader(): Record<string, string> {
  const me = readMe();
  const r = readRole();
  return { ...(me ? { "X-Who": me } : {}), ...(r ? { "X-Role": r } : {}) };
}

export async function api<T>(path: string, init?: RequestInit & { json?: unknown }): Promise<T> {
  const { json, ...rest } = init ?? {};
  const res = await fetch(`${API}${path}`, {
    ...rest,
    headers: { "content-type": "application/json", ...roleHeader(), ...(rest.headers ?? {}) },
    body: json !== undefined ? JSON.stringify(json) : rest.body,
    cache: "no-store",
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body);
    } catch {
      /* keep statusText */
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

/**
 * 輪詢：分頁隱藏（document.hidden）時暫停，回到前景時立刻 reload 一次再繼續（KNOWN_ISSUES #20）。
 * `enabled=false` 時不輪詢（例如 thread 已不在 interrupted）。
 */
export function usePolling(reload: () => void, ms: number, enabled = true) {
  useEffect(() => {
    if (!enabled) return;
    let id: ReturnType<typeof setInterval> | null = null;
    const start = () => {
      if (id === null) id = setInterval(reload, ms);
    };
    const stop = () => {
      if (id !== null) clearInterval(id);
      id = null;
    };
    const onVisibility = () => {
      if (document.hidden) stop();
      else {
        reload();
        start();
      }
    };
    if (!document.hidden) start();
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      stop();
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [reload, ms, enabled]);
}

export function useApi<T>(path: string | null, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  /** HTTP status of the last failed request (null when it was not an ApiError, or on success). */
  const [status, setStatus] = useState<number | null>(null);
  const [tick, setTick] = useState(0);
  const depsKey = JSON.stringify(deps);
  useEffect(() => {
    if (!path) return;
    let alive = true;
    api<T>(path)
      .then((d) => {
        if (!alive) return;
        setData(d);
        setError(null);
        setStatus(null);
      })
      .catch((e: Error) => {
        if (!alive) return;
        setError(e.message);
        setStatus(e instanceof ApiError ? e.status : null);
      });
    return () => {
      alive = false;
    };
  }, [path, depsKey, tick]);
  const reload = useCallback(() => setTick((n) => n + 1), []);
  const loading = !!path && data === null && error === null;
  return { data, error, status, loading, reload };
}

// ---- shapes returned by the API (graph snapshots) ----
export interface Snapshot {
  thread_id: string;
  graph: "path_a" | "shift" | "round";
  status: "done" | "interrupted" | "running";
  next: string[];
  interrupt: (Record<string, unknown> & { type: string }) | null;
  values: Record<string, unknown>;
  handoff?: { thread_id: string; interrupt: Snapshot["interrupt"] };
}
export interface Resident {
  patient_id: string;
  code_name: string;
  room: string;
  caregiver_language: "zh-TW" | "id" | "vi" | "en";
  caregiver_code_name: string;
  primary_nurse: string;
  timeline_count: number;
  last_entry_ts: string | null;
  incident_count: number;
}
/** GET /home/{role}：角色首頁一次拿全部住民＋卡片資料（不再每人各打一次） */
export interface HomeResident extends Resident {
  card: {
    recorded_today?: boolean;
    notes_count?: number;
    session_phase?: "intake" | "confirm" | "red" | null;
    status_line?: string;
    changed_dimensions?: string[];
    latest_ts?: string | null;
    pending_event?: SensorEventPublic | null;
    alerts?: string[];
    recent_events?: MeEvent[];
    care_team?: { primary_nurse: string; doctor: string; facility: { name: string; phone: string }; emergency_contacts: { name: string; relation: string; phone: string; notify_first?: boolean }[] };
    abnormal?: TrendLine[];
    series?: TrendReport["series"];
    /** RF13：偏離他自己平常的量測範圍（observe，不是紅燈）；只有文字，沒有分數 */
    vitals_departures?: string[];
    vitals_band_texts?: string[];
    round_page?: { first: string; generated_at: string; status: string; confirmed_by: string | null } | null;
  };
}
export interface HomeData {
  role: "caregiver" | "nurse" | "doctor";
  generated_at: string;
  residents: HomeResident[];
}
/** 通道 4 感測事件（護理師視角含原始值；其他角色由 API 去掉原始值） */
export type { SensorEvent } from "@schema";
export interface SensorEventPublic {
  id: string;
  ts: string;
  kind: "possible_fall";
  location: string;
  status: "pending" | "verified" | "closed";
  verification: { choice: VerifyChoice; text: string; by: string; ts: string } | null;
  thread_id: string | null;
  nurse_notified: boolean;
}
export interface InboxItem {
  thread_id: string;
  graph: string;
  patient_id: string;
  code_name?: string | null;
  interrupt_type: string | null;
  red_flag: boolean;
  red_flag_lines: string[];
  deadline: string | null;
  escalation_level: number;
  updated_at: string | null;
  summary: string;
  caregiver_reports: { question: string; answer: string; key: string; ts: string }[];
  turn_count: number;
}
export interface Preview {
  observation: StructuredObservation;
  red_flags: RedFlagResult;
  red_flag_lines: string[];
}
export type { Document, PersonRecord, TimelineEntry };
export type { AccessLogEntry, CareCircleMember } from "@schema";

export const startShift = (body: Record<string, unknown>) => api<Snapshot>("/shift/start", { method: "POST", json: body });
export const startPathA = (body: Record<string, unknown>) => api<Snapshot>("/path-a/start", { method: "POST", json: body });
export const startRound = () => api<Snapshot>("/round/start", { method: "POST", json: {} });
export const resumeThread = (thread: string, payload: Record<string, unknown>) =>
  api<Snapshot>(`/threads/${encodeURIComponent(thread)}/resume`, { method: "POST", json: payload });
export const threadState = (thread: string) => api<Snapshot>(`/threads/${encodeURIComponent(thread)}/state`);
export const preview = (body: Record<string, unknown>) => api<Preview>("/intake/preview", { method: "POST", json: body });

// ---- patient page (/p/{id}) ----
export interface ConvMessage {
  id: string;
  patient_id: string;
  session_id: string;
  role: "caregiver" | "agent" | "system";
  kind: "message" | "question" | "summary" | "closing" | "event" | "error";
  text: string;
  ts: string;
  meta: Record<string, unknown> & { activity?: ActivityEvent[]; reason?: string; dimension?: string | null; thread_id?: string; red?: boolean };
}
export interface SessionState {
  session_id: string;
  dialog_id: string;
  phase: "intake" | "confirm" | "red" | "closed";
  thread_id: string | null;
  started: string;
  closed: string | null;
  closed_reason?: string | null;
  pending_event_id?: string | null;
}
/** LangGraph 串流事件（graphs/talk.py、runner.start_stream、agents/personal.run_task 發出） */
export interface ActivityEvent {
  type: "node_start" | "node_end" | "llm_call" | "tool_call" | "red";
  name: string;
  summary: string;
  plain: string;
  ms?: number;
  output?: string;
  input?: string;
  reason?: string;
  red?: boolean;
  patient_id?: string | null;
}
export interface PendingThread {
  thread_id: string;
  graph: "path_a" | "shift" | "round";
  interrupt_type: string | null;
  red_flag: boolean;
  red_flag_lines: string[];
  minimal_sbar: { s: string; a_change_vs_baseline: string } | null;
  sbar: Record<string, unknown> | null;
  caregiver_reports: { question: string; answer: string; key: string; ts: string }[];
  deadline: string | null;
  escalation_level: number;
  updated_at: string | null;
}
export interface PatientSummary {
  role: "patient" | "caregiver" | "nurse" | "doctor";
  who: string | null;
  /** Care Circle 允許這個身份看的 tab；不在裡面的 tab 顯示「未獲授權」 */
  allowed_tabs: Tab[];
  profile: Profile;
  baseline: Baseline;
  timeline: TimelineEntry[];
  documents: Document[];
  conversation: ConvMessage[];
  session: SessionState | null;
  pending: PendingThread[];
  /** 護理師：SensorEvent（含原始值）；其他角色：SensorEventPublic */
  sensor_events: (SensorEvent | SensorEventPublic)[];
  changed_dimensions: string[];
  trend_lines: TrendLine[];
  recorded_today: boolean;
  notes_count: number;
}
// ---- 01 活體數位孿生 /twin ----
export interface TwinDimension {
  label: string;
  state: "same" | "changed" | "red";
  quote: string | null;
  value: string | number | null;
  direction: "up" | "down" | "same" | "unknown";
  days: number;
  note: string;
  baseline: string;
  series: { date: string; value: number | null; label: string }[];
  tip: string;
}
export interface WearableDay { day: string; steps: number; exercise_min: number; resting_hr: number; hrv_ms: number; spo2: number; sleep_hours: number; deep_sleep_hours: number; rem_hours: number }
export type Mood = "same" | "changed" | "attention";
export interface TwinData {
  profile: { code_name: string; health_id: string; birth_year: number; height_cm: number | null; weight_kg: number | null };
  wearable: WearableDay[];
  vitals_bands: { established: boolean; bands: { metric: string; label: string; unit: string; text: string; low: number; high: number; n: number; days: number }[]; departures: string[] };
  avatar: { sleep_hours: number | null; weight_kg: number | null; height_cm: number | null; mood: Mood };
  today_ts: string | null;
  status_line: string;
  dimensions: Record<string, TwinDimension>;
}

// ---- 本人 App /me ----
export interface MeEvent { id: string; ts: string; type: string; title: string; summary: string; facility: string }
export interface MeHome {
  profile: Profile;
  status_line: string;
  today: { ts: string | null; dimensions: Record<string, { raw_quote: string; direction: string; value: string | number | null }>; vitals: Record<string, unknown> | null; changed_dimensions: string[] };
  lifelong: { conditions: number; hospitalizations: number; surgeries: number; falls: number; years_of_records: number; since: number };
  recent_events: MeEvent[];
  allowed_tabs: Tab[];
}
export interface MeTimeline { years: { year: number; major: MeEvent[]; months: { month: number; count: number; events: MeEvent[] }[] }[] }
export interface AskAnswer {
  question: string;
  found: boolean;
  sentences: { text: string; sources: { id: string; date: string; kind: string; text: string }[] }[];
  fallback: string | null;
  meta: { run_id: string; scripted: boolean; duration_s?: number; tool_counts?: Record<string, number>; model?: string };
}
export const askRecord = (pid: string, question: string) => api<AskAnswer>(`/me/${pid}/ask`, { method: "POST", json: { question } });
export interface TalkDone {
  reply: string;
  kind: ConvMessage["kind"];
  meta: ConvMessage["meta"];
  phase: SessionState["phase"];
  red: boolean;
  thread_id: string | null;
  sent: string | null;
  steps: number;
  ms: number;
  session: SessionState | null;
}

/**
 * 讀 SSE（POST）。每個 `event:` 行對應一次 onEvent(name, data)。
 * 串流結束或連線失敗時 resolve / reject；呼叫端在 "error" 事件顯示錯誤並停止（不退回規則版）。
 */
export async function streamSSE(path: string, body: unknown, onEvent: (name: string, data: Record<string, unknown>) => void, signal?: AbortSignal) {
  const res = await fetch(`${API}${path}`, {
    method: "POST",
    headers: { "content-type": "application/json", ...roleHeader() },
    body: JSON.stringify(body),
    signal,
    cache: "no-store",
  });
  if (!res.ok || !res.body) {
    let detail = res.statusText;
    try {
      const j = await res.json();
      detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail ?? j);
    } catch {
      /* keep */
    }
    throw new ApiError(res.status, detail);
  }
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let idx: number;
    while ((idx = buf.indexOf("\n\n")) >= 0) {
      const chunk = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      let name = "message";
      let data = "";
      for (const line of chunk.split("\n")) {
        if (line.startsWith("event:")) name = line.slice(6).trim();
        else if (line.startsWith("data:")) data += line.slice(5).trim();
      }
      if (!data) continue;
      try {
        onEvent(name, JSON.parse(data) as Record<string, unknown>);
      } catch {
        /* ignore malformed */
      }
    }
  }
}
