import { NextResponse, type NextRequest } from "next/server";

// Route guard. Reads only the `ws_session` marker cookie (no secret in it); the
// backend still checks the real tokens on every API call.
export function proxy(request: NextRequest) {
  const signedIn = request.cookies.has("ws_session");
  const { pathname } = request.nextUrl;

  if (pathname.startsWith("/app") && !signedIn) {
    const url = new URL("/login", request.url);
    url.searchParams.set("next", pathname);
    return NextResponse.redirect(url);
  }
  if ((pathname === "/login" || pathname === "/signup") && signedIn) {
    return NextResponse.redirect(new URL("/app", request.url));
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/app/:path*", "/login", "/signup"],
};
