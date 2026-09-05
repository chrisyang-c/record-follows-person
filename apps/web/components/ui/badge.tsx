import type { ProvenanceSource } from "@schema";
import { cn } from "@/lib/utils";

const SOURCE_LABEL: Record<ProvenanceSource, string> = {
  caregiver_said: "照服員原話",
  ai_extracted: "AI 抽取",
  nurse_assessed: "護理師評估",
  nurse_confirmed: "護理師確認",
  doctor_ordered: "醫囑",
  system_derived: "系統推導",
};

export function ProvenanceBadge({ source, author, className }: { source: ProvenanceSource; author?: string; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border border-line bg-surface px-2 py-0.5 text-xs text-ink-2",
        className,
      )}
    >
      {SOURCE_LABEL[source]}
      {author && <span className="text-ink-2" translate="no">· {author}</span>}
    </span>
  );
}

// 填色上的文字一律用 *-ink（≥4.5:1）；§7 原色只做邊框。
export function Chip({ children, tone = "neutral", className }: { children: React.ReactNode; tone?: "neutral" | "primary" | "ok" | "warn" | "danger"; className?: string }) {
  const tones = {
    neutral: "bg-surface text-ink border-line",
    primary: "bg-ai-fill text-ink border-ai-line",
    ok: "bg-ok-fill text-ok-ink border-ok/30",
    warn: "bg-warn-fill text-warn-ink border-warn/30",
    danger: "bg-danger-fill text-danger-ink border-danger/30",
  };
  return <span className={cn("inline-flex items-center rounded-full border px-2 py-0.5 text-xs", tones[tone], className)}>{children}</span>;
}
