import { isRole, ROLE_HOME, type Role } from "@/lib/role";
import type { Purpose } from "@schema";

export type AccessPurpose = Purpose;

export interface AuthSession {
  who: string;
  role: Role;
  name: string;
  patient_id: string | null;
  purpose: AccessPurpose;
  csrf_token: string;
  expires_at: string;
}

export const PURPOSE_LABEL: Record<AccessPurpose, string> = {
  "self-care": "查看自己的健康紀錄",
  caregiving: "日常照顧與聯絡",
  treatment: "診療與護理評估",
  "care-management": "照護安排與交接",
};

export const ROLE_PURPOSES: Record<Role, AccessPurpose[]> = {
  patient: ["self-care"],
  family: ["caregiving"],
  caregiver: ["caregiving"],
  nurse: ["treatment", "care-management"],
  doctor: ["treatment", "care-management"],
};

export function isAuthSession(value: unknown): value is AuthSession {
  if (!value || typeof value !== "object") return false;
  const s = value as Partial<AuthSession>;
  return typeof s.who === "string" && /^[A-Za-z0-9_]+$/.test(s.who)
    && isRole(s.role) && typeof s.name === "string"
    && (s.patient_id === null || typeof s.patient_id === "string")
    && typeof s.purpose === "string" && Object.hasOwn(PURPOSE_LABEL, s.purpose)
    && typeof s.csrf_token === "string" && s.csrf_token.length > 0
    && typeof s.expires_at === "string" && Date.parse(s.expires_at) > Date.now();
}

/** Only allow an in-app page; never follow a protocol-relative or backslash redirect. */
export function sessionLanding(session: Pick<AuthSession, "role">, next: string | null, origin: string): string {
  const fallback = session.role === "patient" ? "/twin" : ROLE_HOME[session.role];
  if (!next?.startsWith("/") || next.startsWith("//") || /[\\\u0000-\u001f]/.test(next)) return fallback;
  const target = new URL(next, origin);
  if (target.origin !== new URL(origin).origin || /^\/(login|role|api|_next)(\/|$)/.test(target.pathname)) return fallback;
  return `${target.pathname}${target.search}${target.hash}`;
}
