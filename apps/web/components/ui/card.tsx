import * as React from "react";
import { Check } from "lucide-react";
import { cn } from "@/lib/utils";

type Variant = "default" | "secondary" | "ai" | "confirmed" | "red";
type HeadingLevel = 2 | 3 | 4;

export function Card({
  className,
  variant = "default",
  title,
  meta,
  headingLevel = 3,
  children,
  ...props
}: Omit<React.HTMLAttributes<HTMLElement>, "title"> & { variant?: Variant; title?: React.ReactNode; meta?: React.ReactNode; headingLevel?: HeadingLevel }) {
  const Heading = `h${headingLevel}` as const;
  const base =
    variant === "ai"
      ? "ai-draft"
      : variant === "confirmed"
        ? "confirmed"
        : variant === "red"
          ? "red-flag"
          : variant === "secondary"
            ? "rounded-[12px] border border-line bg-surface-2"
            : "rounded-[12px] border border-line bg-surface";
  return (
    <section className={cn(base, "p-5", className)} {...props}>
      {(title || variant === "ai" || variant === "confirmed") && (
        <header className="mb-3 flex flex-wrap items-center gap-2">
          {variant === "ai" && (
            <span className="rounded-full border border-dashed border-ai-line bg-surface px-2 py-0.5 text-xs text-ink">
              AI 草稿，請確認
            </span>
          )}
          {variant === "confirmed" && (
            <span className="inline-flex items-center gap-1 rounded-full bg-ok-fill px-2 py-0.5 text-xs text-ok-ink">
              <Check className="size-3" aria-hidden="true" /> 已確認
            </span>
          )}
          {title && <Heading className="text-base font-medium text-ink">{title}</Heading>}
          {meta && <span className="ml-auto text-xs text-ink-2">{meta}</span>}
        </header>
      )}
      {children}
    </section>
  );
}
