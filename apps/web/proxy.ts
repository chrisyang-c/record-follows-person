import { NextResponse, type NextRequest } from "next/server";
import { isRole, isTab, ROLE_TABS, type Role } from "@/lib/role";

/**
 * 角色路由守門（Next 16 的 proxy = 以前的 middleware）：
 * - 沒選角色就進角色頁／病人頁 → 回 `/` 選角色，選完回原頁
 * - /p/{id} 沒帶 tab → 依角色預設（照護者 talk；護理師由頁面依紅燈／草稿決定，先給 docs；醫師 docs）
 * - tab 不在角色權限內 → 換成該角色的第一個 tab
 */
export function proxy(req: NextRequest) {
  const { pathname, searchParams } = req.nextUrl;
  const role = req.cookies.get("role")?.value;
  const guarded = /^\/(caregiver|nurse|doctor|p)(\/|$)/.test(pathname);
  if (!guarded) return NextResponse.next();
  if (!isRole(role)) {
    const url = req.nextUrl.clone();
    url.pathname = "/";
    url.search = `?next=${encodeURIComponent(pathname + req.nextUrl.search)}`;
    return NextResponse.redirect(url);
  }
  const home = pathname.match(/^\/(caregiver|nurse|doctor)(\/|$)/)?.[1] as Role | undefined;
  if (home && home !== role) {
    // 別的角色首頁：改走自己的（例如照護者點到 /nurse）
    const url = req.nextUrl.clone();
    url.pathname = `/${role}`;
    url.search = "";
    return NextResponse.redirect(url);
  }
  if (pathname.startsWith("/p/")) {
    const tab = searchParams.get("tab");
    const allowed = ROLE_TABS[role];
    if (!isTab(tab) || !allowed.includes(tab)) {
      const url = req.nextUrl.clone();
      url.searchParams.set("tab", allowed[0]);
      return NextResponse.redirect(url);
    }
  }
  return NextResponse.next();
}

export const config = { matcher: ["/caregiver/:path*", "/nurse/:path*", "/doctor/:path*", "/p/:path*"] };
