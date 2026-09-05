import { NextResponse, type NextRequest } from "next/server";
import { ROLE_HOME, roleOfMe, type Role } from "@/lib/role";

/**
 * 路由守門（Next 16 的 proxy = 以前的 middleware）。cookie 只存「我是誰」（me），角色由身份推得：
 * - 沒選身份就進角色頁／病人頁 → 回 `/` 選，選完回原頁
 * - 別的角色首頁 → 改走自己的
 * 病人頁的 tab 可見與否不在這裡決定：API 依 Care Circle 回 allowed_tabs，不在範圍的 tab 顯示「未獲授權」。
 */
export function proxy(req: NextRequest) {
  const { pathname } = req.nextUrl;
  const role = roleOfMe(req.cookies.get("me")?.value);
  const guarded = /^\/(me|caregiver|nurse|doctor|p)(\/|$)/.test(pathname);
  if (!guarded) return NextResponse.next();
  if (!role) {
    const url = req.nextUrl.clone();
    url.pathname = "/";
    url.search = `?next=${encodeURIComponent(pathname + req.nextUrl.search)}`;
    return NextResponse.redirect(url);
  }
  const home = pathname.match(/^\/(me|caregiver|nurse|doctor)(\/|$)/)?.[1];
  const mine = ROLE_HOME[role as Role].slice(1);
  if (home && home !== mine) {
    const url = req.nextUrl.clone();
    url.pathname = ROLE_HOME[role as Role];
    url.search = "";
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
}

export const config = { matcher: ["/me/:path*", "/caregiver/:path*", "/nurse/:path*", "/doctor/:path*", "/p/:path*"] };
