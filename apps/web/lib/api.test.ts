import { afterEach, expect, it, vi } from "vitest";
import { api } from "./api";

afterEach(() => {
  vi.unstubAllGlobals();
  document.cookie = "rfp_csrf=; Max-Age=0; Path=/";
});

it("uses a session cookie and CSRF instead of identity headers", async () => {
  document.cookie = "rfp_csrf=session-csrf; Path=/";
  const fetch = vi.fn().mockResolvedValue(new Response("{}", { headers: { "content-type": "application/json" } }));
  vi.stubGlobal("fetch", fetch);
  await api("/patients/P001/talk", { method: "POST", json: { text: "合成測試" }, headers: { "X-Who": "nurse_lin", "X-Role": "nurse" } });
  const init = fetch.mock.calls[0][1] as RequestInit;
  const headers = new Headers(init.headers);
  expect(init.credentials).toBe("include");
  expect(init.cache).toBe("no-store");
  expect(headers.get("X-CSRF-Token")).toBe("session-csrf");
  expect(headers.has("X-Who")).toBe(false);
  expect(headers.has("X-Role")).toBe(false);
});
