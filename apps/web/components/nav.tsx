"use client";

import Link from "next/link";
import { ROLE_HOME, ROLE_LABEL, type Role } from "@/lib/role";
import { usePatientTitle } from "@/lib/patient-title";

/** 頂欄只放：我是誰（角色 · 名字，點回自己的首頁）與目前住民。換身份回 `/`。 */
export function Nav({ role, name }: { role: Role | null; name: string | null }) {
  const patient = usePatientTitle();
  return (
    <nav aria-label="主要" className="mx-auto flex max-w-6xl items-center gap-3 px-4 py-2">
      {role ? (
        <Link href={ROLE_HOME[role]} className="inline-flex min-h-11 items-center gap-1 rounded-lg px-2 text-base font-medium text-ink hover:bg-surface">
          {ROLE_LABEL[role]}
          {name && <span className="font-normal text-ink-2">· {name}</span>}
        </Link>
      ) : (
        <Link href="/" className="inline-flex min-h-11 items-center rounded-lg px-2 text-base font-medium text-ink hover:bg-surface">
          選擇身份
        </Link>
      )}
      {patient && (
        <span className="min-w-0 truncate text-base text-ink-2">
          · {patient}
        </span>
      )}
    </nav>
  );
}
