/** 角色存在 cookie（role=caregiver|nurse|doctor），由 /role?set= 寫入；proxy.ts 依角色限制路由。 */
export type Role = "caregiver" | "nurse" | "doctor";
export type Tab = "who" | "timeline" | "docs" | "talk";

export const ROLES: Role[] = ["caregiver", "nurse", "doctor"];
export const ROLE_LABEL: Record<Role, string> = { caregiver: "照護者", nurse: "護理師", doctor: "醫師" };
export const ROLE_HOME: Record<Role, string> = { caregiver: "/caregiver", nurse: "/nurse", doctor: "/doctor" };
export const TAB_LABEL: Record<Tab, string> = { who: "這是誰", timeline: "紀錄", docs: "文件", talk: "對話" };
/** 每個角色能開的 tab（醫師不進對話；照護者看得到自己記的紀錄與注意事項） */
export const ROLE_TABS: Record<Role, Tab[]> = {
  caregiver: ["talk", "who", "timeline", "docs"],
  nurse: ["docs", "timeline", "who", "talk"],
  doctor: ["docs", "who", "timeline"],
};

export const isRole = (v: unknown): v is Role => typeof v === "string" && (ROLES as string[]).includes(v);
export const isTab = (v: unknown): v is Tab => v === "who" || v === "timeline" || v === "docs" || v === "talk";

/** 瀏覽器端讀 cookie；伺服器端回 null。 */
export function readRole(): Role | null {
  if (typeof document === "undefined") return null;
  const m = document.cookie.match(/(?:^|;\s*)role=([a-z]+)/);
  return m && isRole(m[1]) ? m[1] : null;
}
