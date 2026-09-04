import { Check } from "lucide-react";
import { fmtDateTime } from "@/lib/format";
import { cn } from "@/lib/utils";

/** design.md §3：人確認 = 綠勾 + 「已確認 · 姓名 · 時間」。文字用 --ok-ink（填色上 ≥4.5:1）。 */
export function ConfirmedChip({ by, at, className }: { by?: string | null; at?: string | null; className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-full bg-ok-fill px-2 py-0.5 text-xs text-ok-ink", className)}>
      <Check className="size-3 shrink-0" aria-hidden="true" />
      <span>
        已確認
        {by && (
          <>
            {" · "}
            <span translate="no">{by}</span>
          </>
        )}
        {at && ` · ${fmtDateTime(at)}`}
      </span>
    </span>
  );
}
