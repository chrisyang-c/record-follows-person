"use client";

import type { Document, PersonRecord, StructuredObservation, TimelineEntry, RedFlagResult } from "@schema";
import { useCallback, useEffect, useState } from "react";

export const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function api<T>(path: string, init?: RequestInit & { json?: unknown }): Promise<T> {
  const { json, ...rest } = init ?? {};
  const res = await fetch(`${API}${path}`, {
    ...rest,
    headers: { "content-type": "application/json", ...(rest.headers ?? {}) },
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
export interface InboxItem {
  thread_id: string;
  graph: string;
  patient_id: string;
  interrupt_type: string | null;
  red_flag: boolean;
  red_flag_lines: string[];
  deadline: string | null;
  escalation_level: number;
  updated_at: string | null;
  summary: string;
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
