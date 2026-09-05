import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";
import { cn } from "@/lib/utils";

// design.md §5：只動 opacity / transform，不做顏色 transition。
const button = cva(
  "inline-flex items-center justify-center gap-2 rounded-[10px] font-medium select-none disabled:opacity-50 disabled:pointer-events-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 cursor-pointer",
  {
    variants: {
      variant: {
        // docs/UIUX_OMNI_TWIN.md §5：主＝--accent 底、--bg 字；次＝透明底 1px --line；危險＝只有外框（退回／撤銷）
        primary: "bg-primary text-on-primary hover:bg-primary-hover",
        secondary: "bg-transparent text-ink border border-line hover:bg-surface",
        ghost: "bg-transparent text-ink-2 hover:bg-surface hover:text-ink",
        ok: "bg-ok-fill text-ink border border-ok hover:bg-ok-fill-hover",
        danger: "bg-transparent text-danger-ink border border-danger hover:bg-danger-fill",
        outline: "bg-transparent text-ink border border-line hover:border-ink-2",
      },
      size: {
        md: "min-h-12 px-4 text-base",
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
