/**
 * 身份與角色。cookie 只存「我是誰」（me=cg_xiaofang | nurse_lin | dr_wu | P001 | fam_P001…），
 * 由 /role?set= 寫入；角色由身份推得（demo 身份表與 data/seed/residents.json 的 identities 一致）。
 * 能看哪些 tab 由 API 依 Care Circle 決定（summary.allowed_tabs），這裡的 ROLE_TABS 只是預設順序。
 */
export type Role = "patient" | "family" | "caregiver" | "nurse" | "doctor";
export type Tab = "who" | "timeline" | "docs" | "talk";

export interface Identity {
  role: Role;
  name: string;
  /** 本人／家屬：這個身份對應的住民 */
  patient_id?: string;
}

/** Demo 身份（與 seed 一致；新身份由本人在 Care Circle 授權後也能用） */
export const IDENTITIES: Record<string, Identity> = {
  P001: { role: "patient", name: "王伯", patient_id: "P001" },
  P002: { role: "patient", name: "陳奶奶", patient_id: "P002" },
  P003: { role: "patient", name: "李阿公", patient_id: "P003" },
  fam_P001: { role: "family", name: "王小姐（女兒）", patient_id: "P001" },
  fam_P002: { role: "family", name: "陳先生（兒子）", patient_id: "P002" },
  fam_P003: { role: "family", name: "李太太（配偶）", patient_id: "P003" },
  cg_xiaofang: { role: "caregiver", name: "小芳（照服員）" },
  cg_ahua: { role: "caregiver", name: "阿華（照服員）" },
  cg_amei: { role: "caregiver", name: "阿美（照服員）" },
  nurse_lin: { role: "nurse", name: "林護理師" },
  nurse_huang: { role: "nurse", name: "黃護理師" },
  head_nurse_chen: { role: "nurse", name: "陳護理長" },
  dr_wu: { role: "doctor", name: "吳醫師" },
};
/** 角色入口的四扇門各自的預設身份 */
export const DOOR_DEFAULT: Record<Role, string> = { patient: "P001", family: "fam_P001", caregiver: "cg_xiaofang", nurse: "nurse_lin", doctor: "dr_wu" };

export const ROLES: Role[] = ["patient", "caregiver", "nurse", "doctor"];
export const ROLE_LABEL: Record<Role, string> = { patient: "本人", family: "家屬", caregiver: "照護者", nurse: "護理師", doctor: "醫師" };
export const ROLE_HOME: Record<Role, string> = { patient: "/me", family: "/caregiver", caregiver: "/caregiver", nurse: "/nurse", doctor: "/doctor" };
export const TAB_LABEL: Record<Tab, string> = { who: "這是誰", timeline: "紀錄", docs: "文件", talk: "對話" };
/** 每個角色 tab 的預設順序（實際可見以 API 的 allowed_tabs 為準） */
export const ROLE_TABS: Record<Role, Tab[]> = {
  patient: ["who", "timeline", "docs", "talk"],
  family: ["talk", "who", "timeline", "docs"],
  caregiver: ["talk", "who", "timeline", "docs"],
  nurse: ["docs", "timeline", "who", "talk"],
  doctor: ["docs", "who", "timeline"],
};

export const isRole = (v: unknown): v is Role => typeof v === "string" && (["patient", "family", "caregiver", "nurse", "doctor"] as string[]).includes(v);
export const isTab = (v: unknown): v is Tab => v === "who" || v === "timeline" || v === "docs" || v === "talk";
export const identityOf = (me: string | null | undefined): Identity | null => (me && IDENTITIES[me]) || null;
export const roleOfMe = (me: string | null | undefined): Role | null => identityOf(me)?.role ?? null;

/** 瀏覽器端讀 cookie me；伺服器端回 null。 */
export function readMe(): string | null {
  if (typeof document === "undefined") return null;
  const m = document.cookie.match(/(?:^|;\s*)me=([A-Za-z0-9_]+)/);
  return m ? m[1] : null;
}
export function readRole(): Role | null {
  return roleOfMe(readMe());
}
