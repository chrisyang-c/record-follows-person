import * as React from "react";
import { cn } from "@/lib/utils";

// React 19：ref 是一般 prop，ComponentProps<"…"> 已含 ref。

export function Label({ className, ...props }: React.ComponentProps<"label">) {
  return <label className={cn("mb-1 block text-sm font-medium text-ink", className)} {...props} />;
}

export function Input({ className, ...props }: React.ComponentProps<"input">) {
  return (
    <input
      className={cn(
        "min-h-11 w-full rounded-[10px] border border-line bg-bg px-3 text-base text-ink placeholder:text-ink-2/70 focus-visible:border-primary",
        className,
      )}
      {...props}
    />
  );
}

export function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return (
    <textarea
      className={cn(
        "min-h-24 w-full rounded-[10px] border border-line bg-bg px-3 py-2 text-base text-ink placeholder:text-ink-2/70 focus-visible:border-primary",
        className,
      )}
      {...props}
    />
  );
}

export function Select({ className, children, ...props }: React.ComponentProps<"select">) {
  return (
    <select
      className={cn("min-h-11 rounded-[10px] border border-line bg-bg px-3 text-base text-ink", className)}
      style={{ backgroundColor: "var(--bg)", color: "var(--ink)" }}
      {...props}
    >
      {children}
    </select>
  );
}
