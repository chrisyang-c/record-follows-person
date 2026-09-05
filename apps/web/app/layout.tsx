import type { Metadata, Viewport } from "next";
import { Inter, JetBrains_Mono, Noto_Sans_TC } from "next/font/google";
import { cookies } from "next/headers";
import { Nav } from "@/components/nav";
import { RedBannerGlobal } from "@/components/red-banner-global";
import { identityOf } from "@/lib/role";
import "./globals.css";

const noto = Noto_Sans_TC({ variable: "--font-noto", subsets: ["latin"], weight: ["400", "500", "700"], display: "swap" });
const inter = Inter({ variable: "--font-inter", subsets: ["latin"], display: "swap" });
const mono = JetBrains_Mono({ variable: "--font-jetbrains", subsets: ["latin"], display: "swap" });

export const metadata: Metadata = {
  title: { default: "一份能跟著人走的紀錄", template: "%s · 一份能跟著人走的紀錄" },
  description: "每個人有一份跟著他走的紀錄，和一個替這份紀錄說話的 agent。",
};

export const viewport: Viewport = { themeColor: "#0b0f14", width: "device-width", initialScale: 1 };

export default async function RootLayout({ children }: LayoutProps<"/">) {
  const me = (await cookies()).get("me")?.value ?? null;
  const identity = identityOf(me);
  const role = identity?.role ?? null;
  return (
    <html lang="zh-TW" className={`${noto.variable} ${inter.variable} ${mono.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col bg-bg text-ink">
        <a href="#main" className="skip-link">跳到主要內容</a>
        <header className="no-print border-b border-line bg-bg">
          <Nav role={role} name={identity?.name ?? null} />
        </header>
        {role === "nurse" && <RedBannerGlobal />}
        <main id="main" className="mx-auto w-full max-w-6xl flex-1 px-4 py-6">
          {children}
        </main>
      </body>
    </html>
  );
}
