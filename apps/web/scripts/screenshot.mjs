// 390×844 screenshots of the caregiver chat for docs/ACCEPTANCE.md (real model: answers are typed).
//   pnpm screenshot   (API on :8000 and web on :3000 must be running)
import { chromium } from "playwright";

const base = process.env.WEB_URL ?? "http://localhost:3000";
const out = process.env.OUT_DIR ?? "../../docs/img";
const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true, locale: "zh-TW" });
const page = await ctx.newPage();
const say = async (text) => {
  await page.fill("#say", text);
  await page.press("#say", "Enter");
  await page.waitForFunction(() => !document.body.innerText.includes("傳送中…"), null, { timeout: 120000 });
  await page.waitForTimeout(300);
};
const click = async (text) => {
  await page.getByRole("button", { name: text, exact: true }).click();
  await page.waitForFunction(() => !document.body.innerText.includes("傳送中…"), null, { timeout: 120000 });
  await page.waitForTimeout(300);
};
const hasSummary = () => page.locator("text=我聽到的是").count().then((n) => n > 0);

await page.goto(`${base}/caregiver?patient=P001`, { waitUntil: "networkidle" });
await page.waitForSelector("text=王伯今天怎麼樣");
await page.screenshot({ path: `${out}/caregiver-390-1-start.png` });

await say("王伯這三天飯只吃一半");
await page.screenshot({ path: `${out}/caregiver-390-2-question.png` });
const answers = ["水喝很少，大概兩杯", "晚上起來三次", "精神跟平常一樣", "走路跟平常一樣", "沒有痛", "都沒有"];
for (const a of answers) {
  if (await hasSummary()) break;
  await say(a);
}
await page.waitForSelector("text=我聽到的是", { timeout: 120000 });
await page.screenshot({ path: `${out}/caregiver-390-3-summary.png` });

// red flag: 李阿公 (no anticoagulant) → 跌倒 → agent asks → 撞到頭 → RF05 → dialog continues (phase red)
await page.goto(`${base}/caregiver?patient=P003`, { waitUntil: "networkidle" });
await page.waitForSelector("text=李阿公今天怎麼樣");
await click("跌倒");
await say("在走廊滑倒，撞到頭");
await page.waitForSelector("text=已通知護理師", { timeout: 120000 });
await say("清醒，講話正常");
await page.screenshot({ path: `${out}/caregiver-390-4-red.png` });

await browser.close();
console.log("screenshots written to", out);
