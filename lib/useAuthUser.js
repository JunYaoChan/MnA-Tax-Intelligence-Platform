'use client';

import { useEffect, useState } from 'react';

/**
 * Lightweight client hook that determines the authenticated user
 * by calling the Auth0 App Router endpoint at /auth/me.
 * Works without needing UserProvider from @auth0/nextjs-auth0/client.
 */
export default function useAuthUser() {
  const [user, setUser] = useState(null);
  const [isLoading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function fetchUser() {
      try {
        const res = await fetch('/auth/me', { credentials: 'include' });
        if (cancelled) return;

        if (res.ok) {
          const data = await res.json();
          // Some versions return the profile directly, others under { user }
          setUser(data?.user ?? data ?? null);
        } else {
          setUser(null);
        }
      } catch (_) {
        if (!cancelled) setUser(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fetchUser();
    return () => {
      cancelled = true;
    };
  }, []);

  return { user, isLoading };
}
