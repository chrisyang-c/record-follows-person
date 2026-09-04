// Screenshots for docs/ACCEPTANCE.md (real model: the caregiver's answers are typed).
//   pnpm screenshot   (API on :8000 and web on :3000 must be running)
// Mobile 390×844: /caregiver, /p/P001?tab=talk (mid-stream + reply), /nurse (red banner)
// Desktop 1280×800: /doctor, /p/P001?tab=docs RoundPage + print preview (media: print)
import { chromium } from "playwright";

const base = process.env.WEB_URL ?? "http://localhost:3000";
const out = process.env.OUT_DIR ?? "../../docs/img";
const browser = await chromium.launch();

const mobile = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true, locale: "zh-TW" });
const page = await mobile.newPage();
const idle = async () => {
  await page.waitForTimeout(200);
  await page.waitForFunction(() => !document.querySelector('button[aria-label="送出"]')?.disabled, null, { timeout: 180000 });
  await page.waitForTimeout(300);
};
const say = async (text) => {
  await page.fill("#say", text);
  await page.press("#say", "Enter");
};

// --- caregiver home
await page.goto(`${base}/role?set=caregiver&next=/caregiver`, { waitUntil: "networkidle" });
await page.waitForSelector("text=今天照顧誰");
await page.waitForTimeout(800);
await page.screenshot({ path: `${out}/caregiver-390-home.png` });

// --- talk tab: 王伯（non-red sentence), capture mid-stream then the reply
await page.goto(`${base}/p/P001?tab=talk`, { waitUntil: "networkidle" });
await page.waitForSelector("#say");
await say("王伯這三天飯只吃一半");
await page.waitForSelector("text=/(在聽你說|把你說的|想下一句|在看跟平常)/", { timeout: 60000 });
await page.screenshot({ path: `${out}/talk-390-streaming.png` });
await idle();
await page.screenshot({ path: `${out}/talk-390-question.png` });
const answers = ["水喝很少，大概兩杯", "晚上起來三次", "精神跟平常一樣", "走路跟平常一樣", "沒有痛", "都沒有"];
for (const a of answers) {
  if ((await page.locator("text=我聽到的是").count()) > 0) break;
  await say(a);
  await idle();
}
await page.screenshot({ path: `${out}/talk-390-summary.png` });

// --- red flag as a separate example: 李阿公 fell and hit his head → dialog keeps asking
await page.goto(`${base}/p/P003?tab=talk`, { waitUntil: "networkidle" });
await page.waitForSelector("#say");
await say("李阿公在走廊滑倒，撞到頭");
await idle();
if ((await page.locator("text=已通知護理師").count()) === 0) {
  await say("站不起來，撞到頭");
  await idle();
}
await say("清醒，講話正常");
await idle();
await page.screenshot({ path: `${out}/talk-390-red.png` });

// --- nurse home with the red banner
await page.goto(`${base}/role?set=nurse&next=/nurse`, { waitUntil: "networkidle" });
await page.waitForSelector("text=護理站");
await page.waitForTimeout(1200);
await page.screenshot({ path: `${out}/nurse-390-red-banner.png` });
await mobile.close();

// --- desktop
const desktop = await browser.newContext({ viewport: { width: 1280, height: 800 }, deviceScaleFactor: 1, locale: "zh-TW" });
const d = await desktop.newPage();
await d.goto(`${base}/role?set=doctor&next=/doctor`, { waitUntil: "networkidle" });
await d.waitForSelector("text=今天巡診");
await d.waitForTimeout(1200);
await d.screenshot({ path: `${out}/doctor-1280-home.png` });
await d.goto(`${base}/p/P001?tab=docs`, { waitUntil: "networkidle" });
await d.waitForSelector("text=RoundPage");
await d.waitForTimeout(800);
await d.screenshot({ path: `${out}/roundpage-1280-docs.png`, fullPage: true });
await d.emulateMedia({ media: "print" });
await d.screenshot({ path: `${out}/roundpage-print-preview.png`, fullPage: true });
await d.pdf({ path: `${out}/roundpage-P001-A4.pdf`, format: "A4", printBackground: true });
await desktop.close();
await browser.close();
console.log("screenshots written to", out);
