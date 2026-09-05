import type { Metadata, Viewport } from "next";
import { Inter, JetBrains_Mono, Noto_Sans_TC } from "next/font/google";
import { cookies } from "next/headers";
import { BottomTabs } from "@/components/shell/bottom-tabs";
import { Breadcrumb } from "@/components/shell/breadcrumb";
import { Rail } from "@/components/shell/rail";
import { TopBar } from "@/components/shell/topbar";
import { RedBannerGlobal } from "@/components/red-banner-global";
import { identityOf } from "@/lib/role";
import "./globals.css";

const noto = Noto_Sans_TC({ variable: "--font-noto", subsets: ["latin"], weight: ["400", "500", "700"], display: "swap" });
const inter = Inter({ variable: "--font-inter", subsets: ["latin"], display: "swap" });
const mono = JetBrains_Mono({ variable: "--font-jetbrains", subsets: ["latin"], display: "swap" });

export const metadata: Metadata = {
  title: { default: "OMNI-TWIN · 一份能跟著人走的紀錄", template: "%s · OMNI-TWIN" },
  description: "外殼是一個人的生命作業系統，核心是一條經得起醫療審視的照護鏈。每個人有一份跟著他走的紀錄，和一個替這份紀錄說話的 agent。",
};

export const viewport: Viewport = { themeColor: "#0b0f14", width: "device-width", initialScale: 1 };

/**
 * OMNI-TWIN 殼（docs/UIUX_OMNI_TWIN.md §3）：頂欄 → 紅燈橫幅（護理師，不可關閉）→ 左 rail（桌機）＋內容區（麵包屑＋頁面）→ 底部 tab（手機）。
 * 列印時整個殼隱藏（.no-print），只印 RoundPage。
 */
export default async function RootLayout({ children }: LayoutProps<"/">) {
  const me = (await cookies()).get("me")?.value ?? null;
  const identity = identityOf(me);
  const role = identity?.role ?? null;
  return (
    <html lang="zh-TW" className={`${noto.variable} ${inter.variable} ${mono.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col bg-bg text-ink">
        <a href="#main" className="skip-link">跳到主要內容</a>
        <TopBar identity={identity} />
        {role === "nurse" && <RedBannerGlobal />}
        <div className="flex flex-1">
          <Rail identity={identity} />
          <main id="main" className="min-w-0 flex-1 px-4 py-6 pb-24 lg:px-8 lg:pb-8">
            <div className="mx-auto w-full max-w-6xl">
              <Breadcrumb identity={identity} />
              {children}
            </div>
          </main>
        </div>
        <BottomTabs identity={identity} />
      </body>
    </html>
  );
}
