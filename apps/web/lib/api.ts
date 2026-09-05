"use client";

import type { Baseline, Document, PersonRecord, Profile, StructuredObservation, TimelineEntry, RedFlagResult, TrendLine, TrendReport } from "@schema";
import { useCallback, useEffect, useState } from "react";
import { readRole } from "@/lib/role";

export const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

/** 病人頁的權限過濾靠這個 header（照護者只看自己記的）；角色來自 cookie。 */
function roleHeader(): Record<string, string> {
  const r = readRole();
  return r ? { "X-Role": r } : {};
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
    abnormal?: TrendLine[];
    series?: TrendReport["series"];
    round_page?: { first: string; generated_at: string; status: string; confirmed_by: string | null } | null;
  };
}
export interface HomeData {
  role: "caregiver" | "nurse" | "doctor";
  generated_at: string;
  residents: HomeResident[];
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
  role: "caregiver" | "nurse" | "doctor";
  profile: Profile;
  baseline: Baseline;
  timeline: TimelineEntry[];
  documents: Document[];
  conversation: ConvMessage[];
  session: SessionState | null;
  pending: PendingThread[];
  changed_dimensions: string[];
  trend_lines: TrendLine[];
  recorded_today: boolean;
  notes_count: number;
}
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
