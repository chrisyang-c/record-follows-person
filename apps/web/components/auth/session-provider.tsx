"use client";

import { createContext, useContext, type ReactNode } from "react";
import type { AuthSession } from "@/lib/auth";

const SessionContext = createContext<AuthSession | null>(null);

/** The server obtains this snapshot from /auth/session, never from the display-only me cookie. */
export function AuthSessionProvider({ session, children }: { session: AuthSession | null; children: ReactNode }) {
  return <SessionContext.Provider value={session}>{children}</SessionContext.Provider>;
}

export const useAuthSession = () => useContext(SessionContext);
