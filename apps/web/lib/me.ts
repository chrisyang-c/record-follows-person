"use client";

import { useAuthSession } from "@/components/auth/session-provider";

/** Patient/family context comes from the API-verified session, never a writable display cookie. */
export function useMyPatientId(): string | null {
  const session = useAuthSession();
  return session && (session.role === "patient" || session.role === "family") ? session.patient_id : null;
}
