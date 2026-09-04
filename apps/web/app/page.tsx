import Link from "next/link";
import { ROLE_LABEL, ROLES } from "@/lib/role";

const HINT: Record<string, string> = {
  caregiver: "講一句今天怎麼樣",
  nurse: "紅燈、等我確認、今日總覽",
  doctor: "巡診名單，一人一頁",
};

/** 角色入口：三顆大按鈕（≥88px），選完寫 cookie 進角色首頁。 */
export default async function Entry({ searchParams }: PageProps<"/">) {
  const sp = await searchParams;
  const next = typeof sp.next === "string" ? sp.next : "";
  return (
    <div className="mx-auto flex max-w-[390px] flex-col gap-6 py-6">
      <header>
        <h1 className="text-2xl font-medium leading-tight">你是誰？</h1>
        <p className="mt-1 text-ink-2">每個人有一份跟著他走的紀錄。選角色進去。</p>
      </header>
      <ul className="grid gap-3">
        {ROLES.map((r) => (
          <li key={r}>
            <Link
              href={`/role?set=${r}${next ? `&next=${encodeURIComponent(next)}` : ""}`}
              className="flex min-h-[88px] flex-col justify-center rounded-[12px] border border-line bg-bg px-5 shadow-[var(--shadow-card)] hover:border-primary hover:bg-surface"
            >
              <span className="text-xl font-medium">{ROLE_LABEL[r]}</span>
              <span className="text-sm text-ink-2">{HINT[r]}</span>
            </Link>
          </li>
        ))}
      </ul>
      <p className="text-center text-sm">
        <Link href="/about" className="inline-flex min-h-11 items-center text-primary hover:underline">關於這份紀錄 →</Link>
      </p>
    </div>
  );
}
