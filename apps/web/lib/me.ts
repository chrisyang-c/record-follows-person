"use client";

import { useSyncExternalStore } from "react";
import { identityOf, readMe } from "@/lib/role";

/** 本人／家屬身份對應的住民 id（cookie me → identity.patient_id）；伺服器端為 null。 */
export function useMyPatientId(): string | null | undefined {
  const me = useSyncExternalStore(() => () => {}, () => readMe(), () => undefined);
  if (me === undefined) return undefined;
  return identityOf(me)?.patient_id ?? null;
}
