// Run only against the temporary mock API created by smoke_runtime.py.
import { createRequire } from "node:module";
const require = createRequire(new URL("../apps/web/package.json", import.meta.url));
const { chromium } = require("playwright");
const browser = await chromium.launch({ channel: process.env.RFP_BROWSER_CHANNEL || "msedge", headless: true });
try {
  const context = await browser.newContext();
  // Forging the old display cookie must not establish a session or expose a record.
  await context.addCookies([{ name: "me", value: "P003", url: "http://127.0.0.1:3000" }]);
  const page = await context.newPage();
  page.on("pageerror", error => console.error("Browser page error:", error.message));
  page.on("response", response => {
    if (response.status() >= 300 && response.status() < 400) {
      console.log("Browser redirect:", response.url(), response.headers().location);
    }
  });
  await page.goto("http://127.0.0.1:3000/twin?pid=P003", { waitUntil: "domcontentloaded" });
  await page.waitForURL(/\/login/);
  const anonymous = await context.request.get("http://127.0.0.1:3000/api/twin/P003");
  if (anonymous.status() !== 401) throw new Error("Display cookie bypassed authentication");
  await page.getByLabel("個人帳號").selectOption("P003");
  await page.getByLabel("我的帳號密碼").fill("demo-P003-2026!");
  const responsePromise = page.waitForResponse(
    response => response.url().includes("/twin/P003") && response.status() === 200,
    { timeout: 45000 },
  );
  let response;
  try {
    [response] = await Promise.all([responsePromise, page.getByRole("button", { name: "登入帳號" }).click()]);
  } catch (error) {
    console.error("Browser stopped at:", page.url(), (await page.locator("body").innerText()).slice(0, 900));
    throw error;
  }
  const data = await response.json();
  if (data.profile?.health_id !== "P-0000003" || data.wearable?.length !== 14) {
    throw new Error("Browser did not receive the expected synthetic patient's twin");
  }
  const foreign = await context.request.get("http://127.0.0.1:3000/api/twin/P001");
  if (foreign.status() !== 403 || (await foreign.text()).includes("P-0000001")) {
    throw new Error("Patient session exposed another patient's twin");
  }
  await page.getByRole("button", { name: "登出", exact: true }).click();
  await page.waitForURL(/\/login/);
  await page.goto("http://127.0.0.1:3000/twin?pid=P003");
  await page.waitForURL(/\/login/);
  if ((await context.request.get("http://127.0.0.1:3000/api/twin/P003")).status() !== 401) {
    throw new Error("Logout did not revoke record access");
  }
  console.log("Browser smoke: real login, P003 twin, 14 wearable days, cross-patient denial, logout and forged-cookie denial passed.");
} finally {
  await browser.close();
}
