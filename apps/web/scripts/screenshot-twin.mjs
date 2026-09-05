// Screenshots for the Personal Health Twin blocks (docs/ACCEPTANCE.md「介面對齊 VISION §28」).
//   pnpm screenshot:twin   (API :8000 + web :3000 running; real model for the talk turn)
// 390×844: /me, /me/timeline, /caregiver (家屬), talk four buttons after POST /sim/fall
// 1280×800: /nurse Clinical Queue (event card with raw values), /doctor + docs 縱向摘要
import { chromium } from "playwright";

const base = process.env.WEB_URL ?? "http://localhost:3000";
const api = process.env.API_URL ?? "http://localhost:8000";
const out = process.env.OUT_DIR ?? "../../docs/img";
const browser = await chromium.launch();

const mobile = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true, locale: "zh-TW" });
const page = await mobile.newPage();
const settle = async (ms = 900) => page.waitForTimeout(ms);

// --- 本人 /me
await page.goto(`${base}/role?set=P001&next=/me`, { waitUntil: "networkidle" });
await page.waitForSelector("text=MY HEALTH TWIN");
await settle();
await page.screenshot({ path: `${out}/me-390-home.png`, fullPage: true });
await page.goto(`${base}/me/timeline`, { waitUntil: "networkidle" });
await page.waitForSelector("h1:has-text(\"我的時間軸\")");
await settle();
await page.screenshot({ path: `${out}/me-390-timeline.png`, fullPage: true });

// --- 問我的紀錄（真模型）
await page.goto(`${base}/me`, { waitUntil: "networkidle" });
await page.fill("#ask", "我住過幾次院？");
await page.press("#ask", "Enter");
await page.waitForSelector("text=來源 ·", { timeout: 90000 });
await settle();
const ask = page.locator("section", { hasText: "問我的紀錄" });
await ask.screenshot({ path: `${out}/me-390-ask.png` });

// --- 可能跌倒 → 家屬 /caregiver + talk 四鍵
await fetch(`${api}/sim/fall/P-0000001`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ location: "房間" }) });
await page.goto(`${base}/role?set=fam_P001&next=/caregiver`, { waitUntil: "networkidle" });
await page.waitForSelector("text=我的家人");
await settle(1500);
await page.screenshot({ path: `${out}/caregiver-390-family-home.png`, fullPage: true });
await page.goto(`${base}/p/P001?tab=talk`, { waitUntil: "networkidle" });
await page.waitForSelector("text=請確認王伯現在的狀況");
await settle();
await page.screenshot({ path: `${out}/talk-390-four-buttons.png` });
await page.fill("#say", "爸爸意識清楚，但說髖部痛");
await page.click("text=他可能受傷");
await page.waitForFunction(() => !document.querySelector('button[aria-label="送出"]')?.disabled, null, { timeout: 180000 });
await settle();
await page.screenshot({ path: `${out}/talk-390-after-verify.png` });
// --- 01 活體數位孿生（本人）
await page.goto(`${base}/role?set=P001&next=/twin`, { waitUntil: "networkidle" });
await page.waitForSelector("text=活體數位孿生體");
await settle(1200);
await page.screenshot({ path: `${out}/twin-390-body.png`, fullPage: true });

await mobile.close();

// --- desktop
const desktop = await browser.newContext({ viewport: { width: 1280, height: 800 }, deviceScaleFactor: 1, locale: "zh-TW" });
const d = await desktop.newPage();
await d.goto(`${base}/role?set=nurse_lin&next=/nurse`, { waitUntil: "networkidle" });
await d.waitForSelector("text=Clinical Queue");
await d.waitForTimeout(1500);
await d.screenshot({ path: `${out}/nurse-1280-clinical-queue.png`, fullPage: true });
await d.goto(`${base}/role?set=dr_wu&next=/p/P001?tab=docs`, { waitUntil: "networkidle" });
await d.waitForSelector("text=縱向摘要");
await d.waitForTimeout(800);
await d.screenshot({ path: `${out}/doctor-1280-longitudinal.png`, fullPage: true });
// 列印白底驗證：殼隱藏、tokens 切白（docs/UIUX_OMNI_TWIN.md §8）
await d.emulateMedia({ media: "print" });
await d.screenshot({ path: `${out}/print-1280-white.png`, fullPage: false });
await d.emulateMedia({ media: "screen" });
await d.goto(`${base}/role?set=P001&next=/twin`, { waitUntil: "networkidle" });
await d.waitForSelector("text=活體數位孿生體");
await d.click("button[aria-label^='睡眠']");
await d.waitForTimeout(1200);
await d.screenshot({ path: `${out}/twin-1280-body.png` });
await d.goto(`${base}/role?set=P001&next=/me`, { waitUntil: "networkidle" });
await d.waitForSelector("text=MY HEALTH TWIN");
await d.waitForTimeout(800);
await d.screenshot({ path: `${out}/me-1280-home.png` });
await desktop.close();
await browser.close();
console.log("twin screenshots written to", out);
