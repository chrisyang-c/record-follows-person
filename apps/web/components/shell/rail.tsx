"use client";

import { Activity, Brain, Palette, Stethoscope, Wallet } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { DIMENSIONS5, whichDimension } from "@/lib/shell";
import { ROLE_HOME, type Identity } from "@/lib/role";
import { cn } from "@/lib/utils";

const ICON = { "01": Activity, "02": Palette, "03": Brain, "04": Wallet, "05": Stethoscope } as const;

/** 左 rail 240px：五大生命維度。選中項左側 3px --accent-2 指示條；02–04 灰階「第二階段」。底：資料完整度（不含健康分數）。 */
export function Rail({ identity }: { identity: Identity | null }) {
  const pathname = usePathname();
  const active = whichDimension(pathname);
  return (
    <aside className="no-print hidden w-60 shrink-0 flex-col border-r border-line bg-bg lg:flex" aria-label="五大生命維度">
      <p className="label-caps px-6 pt-6">The 5 Living Dimensions</p>
      <p className="px-6 pb-4 text-lg font-medium">五大生命維度</p>
      <nav className="flex-1">
        <ul className="space-y-1 px-3">
          {DIMENSIONS5.map((d) => {
            const Icon = ICON[d.id];
            const isActive = d.id === active;
            const href = d.id === "05" && identity ? ROLE_HOME[identity.role] : d.href;
            return (
              <li key={d.id} className="relative">
                {isActive && <span className="absolute top-3 bottom-3 left-0 w-[3px] rounded-full bg-accent-2" aria-hidden="true" />}
                <Link
                  href={href}
                  aria-current={isActive ? "page" : undefined}
                  aria-disabled={d.soon || undefined}
                  className={cn("flex min-h-16 items-center gap-3 rounded-[12px] px-3 py-2", isActive ? "bg-surface" : "hover:bg-surface", d.soon && "opacity-50")}
                >
                  <span className={cn("inline-flex size-10 shrink-0 items-center justify-center rounded-full border", isActive ? "border-accent-2/60 text-accent-2" : "border-line text-ink-2")}>
                    <Icon className="size-5" aria-hidden="true" />
                  </span>
                  <span className="min-w-0 leading-tight">
                    <span className="block truncate text-base font-medium">{d.name}</span>
                    <span className="label-caps block truncate">{d.id} · {d.en}{d.soon ? " · 第二階段" : ""}</span>
                  </span>
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
      <div className="m-3 rounded-[12px] border border-line bg-surface p-4">
        <p className="label-caps">Data Integrity</p>
        <p className="mt-1 text-sm">FHIR-lite <span className="num">9/9</span> 類資源 · 長照 3.0 · 來源 <span className="num">6</span> 種</p>
        <div className="mt-2 h-1 rounded-full bg-line"><div className="h-1 w-full rounded-full bg-accent" /></div>
        <p className="mt-1 text-[11px] text-ink-2">provenance 每行都有；不顯示健康分數。</p>
      </div>
    </aside>
  );
}
