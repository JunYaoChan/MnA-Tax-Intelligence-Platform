/**
 * Auth0 route handlers for App Router mounted at /auth/*
 * Provides: /auth/login, /auth/logout, /auth/callback, /auth/profile, /auth/access-token
 * Using AuthClient in v4.
 */
import { auth0 } from '../../../lib/auth0';

export async function GET(request) {
  return auth0.middleware(request);
}

export async function POST(request) {
  return auth0.middleware(request);
}
