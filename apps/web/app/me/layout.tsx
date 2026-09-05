import Link from "next/link";
import type { ReactNode } from "react";

const NAV: { href: string; label: string; soon?: boolean }[] = [
  { href: "/me", label: "首頁" },
  { href: "/me/timeline", label: "我的時間軸" },
  { href: "/me/events", label: "事件" },
  { href: "/me/circle", label: "Care Circle" },
  { href: "#", label: "用藥", soon: true },
  { href: "#", label: "影像", soon: true },
  { href: "#", label: "檢驗", soon: true },
];

/** 本人 App：手機優先（390px），子頁只做時間軸／事件／Care Circle；用藥、影像、檢驗為第二階段。 */
export default function MeLayout({ children }: { children: ReactNode }) {
  return (
    <div className="mx-auto w-full max-w-[390px] space-y-4 lg:max-w-4xl">
      <nav aria-label="本人" className="-mx-4 overflow-x-auto px-4">
        <ul className="flex gap-1 border-b border-line">
          {NAV.map((n) =>
            n.soon ? (
              <li key={n.label}>
                <span aria-disabled="true" title="第二階段" className="inline-flex min-h-11 items-center whitespace-nowrap px-3 text-sm text-ink-2/60">
                  {n.label}<span className="ml-1 rounded-full bg-surface px-1.5 text-[10px]">第二階段</span>
                </span>
              </li>
            ) : (
              <li key={n.href}>
                <Link href={n.href} className="inline-flex min-h-11 items-center whitespace-nowrap px-3 text-sm text-ink-2 hover:text-ink">{n.label}</Link>
              </li>
            ),
          )}
        </ul>
      </nav>
      {children}
    </div>
  );
}
