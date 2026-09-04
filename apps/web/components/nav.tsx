"use client";

import Link from "next/link";
import { ROLE_HOME, ROLE_LABEL, type Role } from "@/lib/role";
import { usePatientTitle } from "@/lib/patient-title";

/** 頂欄只放兩樣：角色（點回角色首頁）與目前住民姓名。切角色回 `/`。 */
export function Nav({ role }: { role: Role | null }) {
  const patient = usePatientTitle();
  return (
    <nav aria-label="主要" className="mx-auto flex max-w-6xl items-center gap-3 px-4 py-2">
      {role ? (
        <Link href={ROLE_HOME[role]} className="inline-flex min-h-11 items-center rounded-lg px-2 text-base font-medium text-ink hover:bg-surface">
          {ROLE_LABEL[role]}
        </Link>
      ) : (
        <Link href="/" className="inline-flex min-h-11 items-center rounded-lg px-2 text-base font-medium text-ink hover:bg-surface">
          選擇角色
        </Link>
      )}
      {patient && (
        <span className="min-w-0 truncate text-base text-ink-2" aria-current="page">
          · {patient}
        </span>
      )}
      <Link href="/" className="ml-auto inline-flex min-h-11 items-center rounded-lg px-2 text-sm text-ink-2 hover:bg-surface hover:text-ink">
        {role ? "切換角色" : "關於"}
      </Link>
    </nav>
  );
}
