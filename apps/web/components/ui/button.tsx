import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";
import { cn } from "@/lib/utils";

// design.md §5：只動 opacity / transform，不做顏色 transition。
const button = cva(
  "inline-flex items-center justify-center gap-2 rounded-[10px] font-medium select-none disabled:opacity-50 disabled:pointer-events-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 cursor-pointer",
  {
    variants: {
      variant: {
        primary: "bg-primary text-on-primary hover:bg-primary-hover",
        secondary: "bg-surface text-ink border border-line hover:bg-surface-hover",
        ghost: "bg-transparent text-ink-2 hover:bg-surface hover:text-ink",
        // 文字用 --ink（§7 的 --ok / --danger 白字對比不足），原色只做邊框
        ok: "bg-ok-fill text-ink border border-ok hover:bg-ok-fill-hover",
        danger: "bg-danger-fill text-ink border border-danger hover:bg-danger-fill-hover",
        outline: "bg-bg text-ink border border-line hover:border-ink-2",
      },
      size: {
        md: "min-h-11 px-4 text-base",
        lg: "min-h-14 px-6 text-lg",
        xl: "min-h-[72px] min-w-[72px] px-8 text-xl",
      },
    },
    defaultVariants: { variant: "primary", size: "md" },
  },
);

export interface ButtonProps extends React.ComponentProps<"button">, VariantProps<typeof button> {}

export function Button({ className, variant, size, type = "button", ...props }: ButtonProps) {
  return <button type={type} className={cn(button({ variant, size }), className)} {...props} />;
}
