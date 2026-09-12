import { describe, expect, it } from "vitest";
import { isAuthSession, sessionLanding } from "./auth";

describe("verified session navigation", () => {
  it.each(["//evil.invalid", "https://evil.invalid", "/\\evil.invalid", "/api/records", "/role?set=nurse_lin"])("rejects unsafe destination %s", (next) => {
    expect(sessionLanding({ role: "patient" }, next, "http://127.0.0.1:3000")).toBe("/twin");
  });
  it("preserves an in-app path without changing origin", () => {
    expect(sessionLanding({ role: "nurse" }, "/p/P001?tab=docs", "http://127.0.0.1:3000")).toBe("/p/P001?tab=docs");
  });
  it("rejects a display identity or expired session as authentication", () => {
    expect(isAuthSession({ who: "nurse_lin", role: "nurse" })).toBe(false);
    const session = { who: "P001", role: "patient", name: "Synthetic", patient_id: "P001", purpose: "self-care", csrf_token: "nonce", expires_at: "2099-01-01T00:00:00Z" };
    expect(isAuthSession(session)).toBe(true);
    expect(isAuthSession({ ...session, expires_at: "2000-01-01T00:00:00Z" })).toBe(false);
  });
});
