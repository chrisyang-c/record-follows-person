// Run only against the temporary mock API created by smoke_runtime.py.
import { createRequire } from "node:module";
const require = createRequire(new URL("../apps/web/package.json", import.meta.url));
const { chromium } = require("playwright");
const browser = await chromium.launch({ channel: process.env.RFP_BROWSER_CHANNEL || "msedge", headless: true });
try {
  const context = await browser.newContext();
  // Demo cookie tests existing app wiring; this is not an authentication security test.
  await context.addCookies([{ name: "me", value: "P003", url: "http://127.0.0.1:3000" }]);
  const page = await context.newPage();
  const responsePromise = page.waitForResponse(
    response => response.url().includes("/twin/P003") && response.status() === 200,
    { timeout: 45000 },
  );
  await page.goto("http://127.0.0.1:3000/twin?pid=P003", { waitUntil: "domcontentloaded" });
  const response = await responsePromise;
  const data = await response.json();
  if (data.profile?.health_id !== "P-0000003" || data.wearable?.length !== 14) {
    throw new Error("Browser did not receive the expected synthetic patient's twin");
  }
  console.log("Browser smoke: Next.js page received P003 twin and 14 simulated wearable days.");
} finally {
  await browser.close();
}
