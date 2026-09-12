"use client";

import { useState } from "react";
import { api, ApiError } from "@/lib/api";

export function LogoutButton() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const logout = async () => {
    setBusy(true);
    setError(null);
    try {
      await api("/auth/logout", { method: "POST", json: {} });
    } catch (err) {
      if (!(err instanceof ApiError && err.status === 401)) {
        setError("登出未完成，請重新嘗試。");
        setBusy(false);
        return;
      }
    }
    document.cookie = "me=; Path=/; Max-Age=0; SameSite=Lax";
    document.cookie = "role=; Path=/; Max-Age=0; SameSite=Lax";
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination -- destroy the prior account's in-memory clinical data
    window.location.assign("/login");
  };
  return (
    <div className="relative">
      <button type="button" disabled={busy} aria-busy={busy} onClick={() => void logout()} className="inline-flex min-h-14 items-center rounded-lg px-2 text-sm text-ink-2 hover:bg-surface hover:text-ink focus-visible:ring-2 focus-visible:ring-accent disabled:opacity-50">
        {busy ? "登出中…" : "登出"}
      </button>
      {error && <p role="alert" className="absolute right-0 top-full w-52 rounded-lg border border-danger bg-surface p-2 text-sm text-danger-ink">{error}</p>}
    </div>
  );
}
