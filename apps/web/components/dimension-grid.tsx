import { DIMENSIONS, DIMENSION_LABELS, type DimensionValue, type Lang } from "@schema";
import { DIRECTION_LABEL } from "@/lib/labels";
import { cn } from "@/lib/utils";

const ARROW: Record<string, string> = { up: "↑", down: "↓", same: "＝", unknown: "" };

export function DimensionGrid({
  domains,
  lang = "zh-TW",
  compact = false,
}: {
  domains: Record<string, DimensionValue>;
  lang?: Lang;
  compact?: boolean;
}) {
  return (
    <ul className={cn("grid gap-2", compact ? "grid-cols-4" : "grid-cols-2 sm:grid-cols-4")} aria-label="八維度">
      {DIMENSIONS.map((d) => {
        const v = domains[d];
        const lit = !!v;
        const dir = v?.direction ?? "unknown";
        return (
          <li
            key={d}
            className={cn(
              "min-w-0 rounded-[10px] border px-3 py-2",
              lit ? "border-primary bg-ai-fill text-ink" : "border-line bg-surface text-ink-2",
              compact && "px-2 py-1",
            )}
          >
            <div className={cn("flex items-center gap-1 text-sm font-medium", compact && "text-xs")}>
              <span className="truncate">{DIMENSION_LABELS[d][lang] ?? DIMENSION_LABELS[d]["zh-TW"]}</span>
              {lit && (
                <span className="ml-auto font-latin">
                  <span aria-hidden="true">{ARROW[dir]}</span>
                  <span className="sr-only">{DIRECTION_LABEL[dir]}</span>
                </span>
              )}
            </div>
            {lit && !compact && (
              <p className="mt-1 line-clamp-2 text-xs text-ink-2" lang={v.lang}>
                “{v.raw_quote}”
              </p>
            )}
          </li>
        );
      })}
    </ul>
  );
}
