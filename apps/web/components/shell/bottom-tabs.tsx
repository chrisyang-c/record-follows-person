"use client";

import { Activity, Bell, List, MessageCircle, UserRound } from "lucide-react";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { bottomTabs } from "@/lib/shell";
import type { Identity } from "@/lib/role";
import { cn } from "@/lib/utils";

const ICON = { twin: Activity, talk: MessageCircle, events: Bell, records: List, me: UserRound } as const;

function Tabs({ identity }: { identity: Identity | null }) {
  const pathname = usePathname();
  const sp = useSearchParams();
  const current = `${pathname}${sp.toString() ? `?${sp.toString()}` : ""}`;
  const tabs = bottomTabs(identity);
  return (
    <nav aria-label="主要（手機）" className="no-print fixed inset-x-0 bottom-0 z-30 border-t border-line bg-bg/95 pb-[env(safe-area-inset-bottom)] backdrop-blur lg:hidden">
      <ul className="grid grid-cols-5">
        {tabs.map((t) => {
          const Icon = ICON[t.key as keyof typeof ICON];
          const active = current === t.href || (t.key === "twin" && pathname === "/twin") || (t.key === "me" && pathname === t.href);
          return (
            <li key={t.key}>
              <Link href={t.href} aria-current={active ? "page" : undefined} className={cn("flex min-h-14 flex-col items-center justify-center gap-0.5 text-[11px]", active ? "text-accent" : "text-ink-2")}>
                <Icon className="size-5" aria-hidden="true" />
                {t.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

/** 手機底部 tab（≤ lg 顯示）：01 孿生｜05 對話｜05 事件｜05 紀錄｜我。 */
export function BottomTabs({ identity }: { identity: Identity | null }) {
  if (!identity) return null;
  return (
    <Suspense fallback={null}>
      <Tabs identity={identity} />
    </Suspense>
  );
}
