import Link from "next/link";
import { IDENTITIES, ROLE_LABEL, ROLES } from "@/lib/role";

const HINT: Record<string, string> = {
  patient: "01 活體數位孿生 → 05 本人艙：時間軸、問我的紀錄、Care Circle",
  caregiver: "05 家屬艙：講一句今天怎麼樣；家屬也從這裡進",
  nurse: "05 護理站：Clinical Queue（新事件、待審核、今日總覽）",
  doctor: "05 醫師艙：巡診名單，一人一頁",
};
const PATIENTS = ["P001", "P002", "P003"];

/** 身份入口：四扇門（本人／照護者／護理師／醫師）。cookie 只存「我是誰」。 */
export default async function Entry({ searchParams }: PageProps<"/">) {
  const sp = await searchParams;
  const next = typeof sp.next === "string" ? sp.next : "";
  const q = next ? `&next=${encodeURIComponent(next)}` : "";
  return (
    <div className="mx-auto flex max-w-[390px] flex-col gap-6 py-6">
      <header>
        <p className="label-caps">OMNI-TWIN · 進入</p>
        <h1 className="text-2xl font-medium leading-tight">你是誰？</h1>
        <p className="mt-1 text-ink-2">外殼是一個人的生命作業系統，核心是一條經得起醫療審視的照護鏈。本人進 01 活體數位孿生；家屬、護理師、醫師進 05 照護與醫療艙。</p>
      </header>
      <ul className="grid gap-3">
        {ROLES.map((r) =>
          r === "patient" ? (
            <li key={r} className="rounded-[12px] border border-line bg-bg px-5 py-4 shadow-[var(--shadow-card)]">
              <p className="text-xl font-medium">{ROLE_LABEL[r]}</p>
              <p className="text-sm text-ink-2">{HINT[r]}</p>
              <ul className="mt-3 grid grid-cols-3 gap-2">
                {PATIENTS.map((pid) => (
                  <li key={pid}>
                    <Link href={`/role?set=${pid}${q}`} className="flex min-h-14 items-center justify-center rounded-[10px] border border-line bg-surface px-2 text-base font-medium hover:border-primary">
                      {IDENTITIES[pid].name}
                    </Link>
                  </li>
                ))}
              </ul>
            </li>
          ) : (
            <li key={r}>
              <Link
                href={`/role?set=${r}${q}`}
                className="flex min-h-[88px] flex-col justify-center rounded-[12px] border border-line bg-bg px-5 shadow-[var(--shadow-card)] hover:border-primary hover:bg-surface"
              >
                <span className="text-xl font-medium">{ROLE_LABEL[r]}</span>
                <span className="text-sm text-ink-2">{HINT[r]}</span>
              </Link>
            </li>
          ),
        )}
      </ul>
      <p className="text-center text-sm">
        <Link href="/role?set=fam_P001" className="inline-flex min-h-11 items-center text-ink-2 hover:text-ink">以家屬身份（王小姐）進入 →</Link>
        <span className="mx-2 text-ink-2">·</span>
        <Link href="/about" className="inline-flex min-h-11 items-center text-primary hover:underline">關於這份紀錄 →</Link>
      </p>
    </div>
  );
}
