import { NextResponse, type NextRequest } from "next/server";
import { isRole, ROLE_HOME } from "@/lib/role";

/** GET /role?set=nurse&next=/p/P001 → 寫入 role cookie 後轉址（角色入口的三顆按鈕就是這種連結）。 */
export function GET(req: NextRequest) {
  const role = req.nextUrl.searchParams.get("set");
  const next = req.nextUrl.searchParams.get("next");
  if (!isRole(role)) return NextResponse.redirect(new URL("/", req.url));
  const target = next && next.startsWith("/") && !next.startsWith("//") ? next : ROLE_HOME[role];
  const res = NextResponse.redirect(new URL(target, req.url));
  res.cookies.set("role", role, { path: "/", sameSite: "lax", maxAge: 60 * 60 * 24 * 30 });
  return res;
}
