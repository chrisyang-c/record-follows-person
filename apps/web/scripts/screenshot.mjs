// 390×844 screenshots of the caregiver chat for docs/ACCEPTANCE.md.
//   pnpm screenshot   (API on :8000 and web on :3000 must be running)
import { chromium } from "playwright";

const base = process.env.WEB_URL ?? "http://localhost:3000";
const out = process.env.OUT_DIR ?? "../../docs/img";
const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true, locale: "zh-TW" });
const page = await ctx.newPage();
const click = async (text) => {
  await page.getByRole("button", { name: text, exact: true }).click();
  await page.waitForTimeout(400);
};
const waitIdle = async () => {
  await page.waitForFunction(() => !document.body.innerText.includes("傳送中…"), null, { timeout: 60000 });
};

await page.goto(`${base}/caregiver?patient=P001`, { waitUntil: "networkidle" });
await page.waitForSelector("text=王伯今天怎麼樣");
await page.screenshot({ path: `${out}/caregiver-390-1-start.png` });

await page.fill("#say", "王伯今天只吃一半");
await page.press("#say", "Enter");
await waitIdle();
await page.screenshot({ path: `${out}/caregiver-390-2-question.png` });

await click("晚上起來三次以上");
await waitIdle();
await click("精神跟平常一樣");
await waitIdle();
await click("走路跟平常一樣");
await waitIdle();
await click("沒有痛");
await waitIdle();
await page.waitForSelector("text=我聽到的是");
await page.screenshot({ path: `${out}/caregiver-390-3-summary.png` });

// red flag: 李阿公 (no anticoagulant) → 跌倒 → 有撞到頭嗎 → 撞到頭 → RF05
await page.goto(`${base}/caregiver?patient=P003`, { waitUntil: "networkidle" });
await page.waitForSelector("text=李阿公今天怎麼樣");
await click("跌倒");
await waitIdle();
await click("撞到頭");
await waitIdle();
await page.waitForSelector("text=已通知護理師", { timeout: 60000 });
await page.screenshot({ path: `${out}/caregiver-390-4-red.png` });

await browser.close();
console.log("screenshots written to", out);
