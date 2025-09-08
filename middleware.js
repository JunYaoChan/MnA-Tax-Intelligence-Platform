import { NextResponse } from 'next/server';

// Pass-through middleware. Auth is handled by the Auth0 route handlers under /auth/*
// and client-side gating (UserProvider/useUser). The previous middleware implementation
// used a custom client and interfered with /auth/me, preventing the user from being
// detected as logged in on the home page.
export function middleware() {
  return NextResponse.next();
}

export const config = {
  // Disable matching so this middleware does not run on every request.
  matcher: [],
};
