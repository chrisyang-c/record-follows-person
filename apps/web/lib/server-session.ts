import { isAuthSession, type AuthSession } from "@/lib/auth";

/** Server-only callers pass the opaque session cookie; display cookies are never forwarded. */
export async function verifiedSession(token: string | undefined): Promise<AuthSession | null> {
  if (!token || !/^[A-Za-z0-9_-]+$/.test(token)) return null;
  const base = (process.env.API_INTERNAL_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
  const res = await fetch(`${base}/auth/session`, {
    headers: { cookie: `rfp_session=${token}` },
    cache: "no-store",
    signal: AbortSignal.timeout(5000),
  });
  if (res.status === 401 || res.status === 403) return null;
  if (!res.ok) throw new Error("登入服務暫時無法連線，請稍後重試。");
  const session: unknown = await res.json();
  return isAuthSession(session) ? session : null;
}
