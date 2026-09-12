import { NextResponse, type NextRequest } from "next/server";

/** Optimistic navigation only. The API validates sessions and authorizes every data access. */
export function proxy(req: NextRequest) {
  if (!req.cookies.has("rfp_session")) {
    const url = new URL("/login", req.url);
    url.searchParams.set("next", req.nextUrl.pathname + req.nextUrl.search);
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
}

export const config = { matcher: ["/me/:path*", "/caregiver/:path*", "/nurse/:path*", "/doctor/:path*", "/p/:path*", "/twin/:path*"] };
