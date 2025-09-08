'use client';

import React from 'react';
import { UserProvider } from '@auth0/nextjs-auth0/client';

export default function Providers({ children }) {
  return <UserProvider>{children}</UserProvider>;
}
