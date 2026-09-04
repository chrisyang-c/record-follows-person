"use client";

import { ChevronDown } from "lucide-react";
import { useState } from "react";
import type { ActivityEvent } from "@/lib/api";
import type { Role } from "@/lib/role";
import { cn } from "@/lib/utils";

const NODE_ZH: Record<string, string> = {
  load_person_record: "讀紀錄",
  record_caregiver_message: "記下原話",
  intake_agent: "intake_agent",
  baseline_comparator: "與基線比",
  red_flag_rules: "紅燈規則",
  notify_nurse_urgent: "通知護理師",
  caregiver_report: "回報護理師",
  decide_next_question: "決定下一題",
  extract_observation: "llm.extract",
  next_question: "llm.next_question",
  roster_agent: "roster_agent",
  trend_analyzer: "trend_analyzer",
  familiarization_writer: "familiarization_writer",
  handoff_packager: "handoff_packager",
  publish_round_pages: "發布 RoundPage",
};

const fmtMs = (ms: number) => (ms >= 1000 ? `${(ms / 1000).toFixed(1)} 秒` : `${ms} 毫秒`);

/**
 * Agent 活動列。收合：「花了 2.3 秒，4 步」；展開：每步的名稱、摘要、輸入／輸出（= /debug/trace 內容）。
 * 照護者看 plain（白話），護理師／醫師看 summary（正式）。紅燈那一步用紅色。
 * live=true 時是正在進行中的那一輪（會一直長）。
 */
export function ActivityBar({ events, role, live = false, defaultOpen = false, className }: { events: ActivityEvent[]; role: Role; live?: boolean; defaultOpen?: boolean; className?: string }) {
  const [open, setOpen] = useState(defaultOpen);
  if (!events.length) return null;
  const plain = role === "caregiver";
  const steps = events.filter((e) => e.type !== "node_start");
  const ms = events.filter((e) => e.type === "node_end" || e.type === "red").reduce((a, e) => a + (e.ms ?? 0), 0);
  const running = live ? events.filter((e) => e.type === "node_start").find((s) => !events.some((e) => e.name === s.name && (e.type === "node_end" || e.type === "red"))) : undefined;
  const hasRed = events.some((e) => e.type === "red");
  const label = live && running ? (plain ? running.plain : running.summary) : plain ? `花了 ${fmtMs(ms)}，${steps.length} 步` : `${fmtMs(ms)} · ${steps.length} 步`;
  return (
    <div className={cn("max-w-[85%] text-xs", className)}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className={cn(
          "inline-flex min-h-11 items-center gap-1 rounded-full border border-dashed px-3 py-0.5 text-left",
          hasRed ? "border-danger text-danger-ink" : "border-primary text-ink-2 hover:text-ink",
        )}
      >
        {live && running && <span className="size-2 animate-pulse rounded-full bg-primary" aria-hidden="true" />}
        <span>{label}</span>
        <ChevronDown className={cn("size-3 transition-transform", open && "rotate-180")} aria-hidden="true" />
      </button>
      {open && (
        <ol className="mt-1 space-y-1 rounded-[10px] border border-dashed border-primary bg-ai-fill p-2" aria-live={live ? "polite" : undefined}>
          {steps.map((e, i) => (
            <li key={i} className={cn("grid grid-cols-[auto_1fr_auto] gap-x-2", e.type === "red" && "text-danger-ink")}>
              <span className={cn("font-mono", e.type === "llm_call" && "text-primary", e.type === "tool_call" && "text-warn-ink")} translate="no">
                {e.type === "llm_call" ? "LLM" : e.type === "tool_call" ? "tool" : e.type === "red" ? "紅燈" : "節點"}
              </span>
              <span className="min-w-0 break-words">
                <span className="font-medium" translate="no">{plain ? (NODE_ZH[e.name] ?? e.name) : e.name}</span>
                {" · "}
                {plain ? e.plain : e.summary}
                {!plain && e.output && e.type !== "llm_call" && <span className="block text-ink-2">→ {e.output}</span>}
                {!plain && e.input && <span className="block text-ink-2">← {e.input}</span>}
              </span>
              <span className="num text-ink-2">{e.ms != null ? fmtMs(e.ms) : ""}</span>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
