import { NextResponse, type NextRequest } from "next/server";
import { DOOR_DEFAULT, IDENTITIES, isRole, ROLE_HOME } from "@/lib/role";

/**
 * GET /role?set=nurse_lin&next=/p/P001 → 寫入 cookie me（只存「我是誰」）後轉址。
 * 也接受角色名（set=nurse → 該扇門的預設身份），舊連結不用改。
 */
export function GET(req: NextRequest) {
  const raw = req.nextUrl.searchParams.get("set") ?? "";
  const me = IDENTITIES[raw] ? raw : isRole(raw) ? DOOR_DEFAULT[raw] : null;
  const next = req.nextUrl.searchParams.get("next");
  if (!me) return NextResponse.redirect(new URL("/", req.url));
  const role = IDENTITIES[me].role;
  const target = next && next.startsWith("/") && !next.startsWith("//") ? next : ROLE_HOME[role];
  const res = NextResponse.redirect(new URL(target, req.url));
  res.cookies.set("me", me, { path: "/", sameSite: "lax", maxAge: 60 * 60 * 24 * 30 });
  res.cookies.delete("role");
  return res;
}
