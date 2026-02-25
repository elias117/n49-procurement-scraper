"use client";

import { SessionProvider } from "next-auth/react";

/**
 * Client-side SessionProvider wrapper for Auth.js v5.
 * Required for useSession() in client components within the dashboard.
 */
export function SessionWrapper({ children }: { children: React.ReactNode }) {
  return <SessionProvider>{children}</SessionProvider>;
}
