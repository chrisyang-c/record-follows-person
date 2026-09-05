import { redirect } from "next/navigation";

/** 入口即登入（以病人為核心）。 */
export default async function Entry({ searchParams }: PageProps<"/">) {
  const sp = await searchParams;
  const next = typeof sp.next === "string" ? sp.next : "";
  redirect(next ? `/login?next=${encodeURIComponent(next)}` : "/login");
}
