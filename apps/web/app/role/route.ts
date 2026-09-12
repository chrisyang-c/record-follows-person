import { NextResponse, type NextRequest } from "next/server";
import { sessionLanding } from "@/lib/auth";
import { verifiedSession } from "@/lib/server-session";

// Next's internal request URL may use localhost even when the browser uses 127.0.0.1.
// A relative Location preserves the browser's origin (and its host-only session cookie).
function redirectWithinOrigin(path: string) {
  return new NextResponse(null, { status: 303, headers: { Location: path, "Cache-Control": "no-store" } });
}

/** Legacy ?set= is ignored: only the API's authenticated session can identify this browser. */
export async function GET(req: NextRequest) {
  let session;
  try {
    session = await verifiedSession(req.cookies.get("rfp_session")?.value);
  } catch {
    const login = new URL("/login", req.url);
    login.searchParams.set("error", "unavailable");
    return redirectWithinOrigin(login.pathname + login.search);
  }
  if (!session) {
    const login = new URL("/login", req.url);
    const next = req.nextUrl.searchParams.get("next");
    if (next) login.searchParams.set("next", next);
    const res = redirectWithinOrigin(login.pathname + login.search);
    res.cookies.delete("me");
    res.cookies.delete("role");
    return res;
  }
  const target = sessionLanding(session, req.nextUrl.searchParams.get("next"), req.url);
  const res = redirectWithinOrigin(target);
  res.headers.set("Cache-Control", "no-store");
  res.cookies.set("me", session.who, {
    path: "/", sameSite: "lax", expires: new Date(session.expires_at),
    secure: req.nextUrl.protocol === "https:",
  });
  res.cookies.delete("role");
  return res;
}
