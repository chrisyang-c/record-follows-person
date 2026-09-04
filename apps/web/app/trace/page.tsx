"use client";

import { useEffect } from "react";
import { Chip } from "@/components/ui/badge";
import { useApi } from "@/lib/api";
import { fmtDateTime } from "@/lib/format";

type Entry = Record<string, unknown> & { ts: string; kind: string };

const TONE: Record<string, "primary" | "ok" | "warn" | "danger" | "neutral"> = {
  "llm.": "primary",
  "deep_agent.": "ok",
  "subagent.": "ok",
  "intake.fallback": "warn",
};
const tone = (k: string) => (Object.entries(TONE).find(([p]) => k.startsWith(p))?.[1] ?? "neutral");
const brief = (v: unknown) => (typeof v === "string" ? v : JSON.stringify(v, null, 0));

export default function TracePage() {
  const { data, reload, error } = useApi<Entry[]>("/trace?limit=80");
  useEffect(() => {
    const id = setInterval(reload, 5000);
    return () => clearInterval(id);
  }, [reload]);
  const rows = [...(data ?? [])].reverse();
  return (
    <div className="space-y-3">
      <h1 className="text-2xl font-medium">Agent 呼叫紀錄</h1>
      <p className="text-sm text-ink-2">每一次模型呼叫（抽取、追問決定、ISBAR 草稿）、每一次 deep agent 派工與 subagent 工具呼叫。同步寫在 records/_trace/*.jsonl。每 5 秒更新。</p>
      {error && <p role="alert" className="text-danger-ink">{error}</p>}
      {rows.length === 0 && <p className="text-ink-2">還沒有紀錄。去照護者頁講一句話，或跑一次巡診。</p>}
      <ul className="space-y-2">
        {rows.map((e, i) => (
          <li key={i} className="rounded-[12px] border border-line bg-bg p-3 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <Chip tone={tone(e.kind)}>{e.kind}</Chip>
              <span className="text-xs text-ink-2">{fmtDateTime(e.ts)}</span>
              {typeof e.provider === "string" && <span className="text-xs text-ink-2" translate="no">{e.provider}</span>}
              {typeof e.duration_ms === "number" && <span className="num text-xs text-ink-2">{e.duration_ms} ms</span>}
              {typeof e.run_id === "string" && <span className="text-xs text-ink-2" translate="no">{e.run_id}</span>}
              {e.scripted === true && <Chip tone="warn">scripted (mock)</Chip>}
              {Array.isArray(e.subagents_called) && e.subagents_called.length > 0 && (
                <Chip tone="ok">subagents: {(e.subagents_called as string[]).join(", ")}</Chip>
              )}
              {typeof e.subagent === "string" && <Chip tone="ok">{e.subagent} → {String(e.tool)}</Chip>}
            </div>
            <dl className="mt-2 grid gap-1 sm:grid-cols-[6rem_1fr]">
              {(["input", "prompt", "args", "output", "reason", "next", "tool_counts", "subagents_called", "error", "final"] as const)
                .filter((k) => e[k] !== undefined && e[k] !== null)
                .map((k) => (
                  <div key={k} className="contents">
                    <dt className="text-ink-2">{k}</dt>
                    <dd className="min-w-0 whitespace-pre-wrap break-words font-latin text-xs">{brief(e[k])}</dd>
                  </div>
                ))}
            </dl>
          </li>
        ))}
      </ul>
    </div>
  );
}
