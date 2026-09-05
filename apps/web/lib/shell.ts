import type { Identity, Role } from "@/lib/role";
import { ROLE_HOME } from "@/lib/role";

/** 五大生命維度（docs/UIUX_OMNI_TWIN.md §2）。02–04 第二階段：導覽存在、頁面空。 */
export interface Dimension5 {
  id: "01" | "02" | "03" | "04" | "05";
  name: string;
  en: string;
  href: string;
  soon?: boolean;
}
export const DIMENSIONS5: Dimension5[] = [
  { id: "01", name: "活體數位孿生", en: "BIO-TWIN & SANDBOX", href: "/twin" },
  { id: "02", name: "風格美學與形態", en: "AESTHETICS & MORPHOLOGY", href: "/twin/aesthetics", soon: true },
  { id: "03", name: "心理情緒與飲食", en: "EMOTION & NUTRITION", href: "/twin/emotion", soon: true },
  { id: "04", name: "全資產與生命週期", en: "WEALTH & LIFECYCLE", href: "/twin/wealth", soon: true },
  { id: "05", name: "照護與醫療艙", en: "CAREGIVER & CLINICAL", href: "/me" },
];

export const CABIN_LABEL: Record<Role, string> = { patient: "本人艙", family: "家屬艙", caregiver: "家屬艙", nurse: "護理站", doctor: "醫師艙" };

/** 依路徑決定 rail 選中的維度與麵包屑。 */
export function whichDimension(pathname: string): Dimension5["id"] {
  if (pathname === "/twin") return "01";
  if (pathname.startsWith("/twin/aesthetics")) return "02";
  if (pathname.startsWith("/twin/emotion")) return "03";
  if (pathname.startsWith("/twin/wealth")) return "04";
  return "05";
}

export function breadcrumb(pathname: string, identity: Identity | null, patientName: string): string[] {
  const d = DIMENSIONS5.find((x) => x.id === whichDimension(pathname))!;
  const parts = ["OMNI-TWIN", `${d.id} ${d.name}`];
  if (d.id === "05") {
    if (identity) parts.push(CABIN_LABEL[identity.role]);
    if (pathname.startsWith("/p/") && patientName) parts.push(patientName);
    else if (pathname.startsWith("/me/timeline")) parts.push("我的時間軸");
    else if (pathname.startsWith("/me/events")) parts.push("事件");
    else if (pathname.startsWith("/me/circle")) parts.push("Care Circle");
    else if (pathname.startsWith("/nurse/round")) parts.push("巡診準備");
    else if (pathname.startsWith("/nurse")) parts.push("Clinical Queue");
    else if (pathname.startsWith("/doctor")) parts.push("巡診名單");
    else if (pathname.startsWith("/trace")) parts.push("Agent 呼叫紀錄");
  }
  return parts;
}

/** 手機底部 5 格：01 孿生｜05 對話｜05 事件｜05 紀錄｜我（依身份決定連到哪）。 */
export function bottomTabs(identity: Identity | null): { key: string; label: string; href: string }[] {
  const pid = identity?.patient_id;
  const role = identity?.role;
  const home = role ? ROLE_HOME[role] : "/";
  const talk = pid ? `/p/${pid}?tab=talk` : role === "caregiver" ? "/caregiver" : role === "nurse" ? "/nurse" : home;
  const events = role === "patient" ? "/me/events" : role === "nurse" ? "/nurse" : pid ? `/p/${pid}?tab=docs` : home;
  const records = role === "patient" ? "/me/timeline" : pid ? `/p/${pid}?tab=timeline` : role === "doctor" ? "/doctor" : home;
  return [
    { key: "twin", label: "孿生", href: "/twin" },
    { key: "talk", label: "對話", href: talk },
    { key: "events", label: "事件", href: events },
    { key: "records", label: "紀錄", href: records },
    { key: "me", label: "我", href: home },
  ];
}
