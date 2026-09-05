"use client";

import { usePathname } from "next/navigation";
import { usePatientTitle } from "@/lib/patient-title";
import { breadcrumb } from "@/lib/shell";
import type { Identity } from "@/lib/role";

/** 麵包屑：OMNI-TWIN / 05 照護與醫療艙 / 護理站 / 王伯（label-caps 風格，最後一段亮色）。 */
export function Breadcrumb({ identity }: { identity: Identity | null }) {
  const pathname = usePathname();
  const patient = usePatientTitle();
  const parts = breadcrumb(pathname, identity, patient);
  return (
    <nav aria-label="位置" className="no-print mb-4 hidden lg:block">
      <ol className="label-caps flex flex-wrap items-center gap-2">
        {parts.map((p, i) => (
          <li key={i} className={i === parts.length - 1 ? "text-accent" : ""}>
            {i > 0 && <span className="mr-2 text-ink-2/60" aria-hidden="true">/</span>}
            {p}
          </li>
        ))}
      </ol>
    </nav>
  );
}
