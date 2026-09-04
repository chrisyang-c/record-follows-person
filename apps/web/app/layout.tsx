import type { Metadata, Viewport } from "next";
import { Inter, JetBrains_Mono, Noto_Sans_TC } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const noto = Noto_Sans_TC({ variable: "--font-noto", subsets: ["latin"], weight: ["400", "500", "700"], display: "swap" });
const inter = Inter({ variable: "--font-inter", subsets: ["latin"], display: "swap" });
const mono = JetBrains_Mono({ variable: "--font-jetbrains", subsets: ["latin"], display: "swap" });

export const metadata: Metadata = {
  title: { default: "一份能跟著人走的紀錄", template: "%s · 一份能跟著人走的紀錄" },
  description: "每個人有一份跟著他走的紀錄，和一個替這份紀錄說話的 agent。",
};

export const viewport: Viewport = { themeColor: "#ffffff", width: "device-width", initialScale: 1 };

const NAV = [
  { href: "/caregiver", label: "照護者" },
  { href: "/nurse", label: "護理師" },
  { href: "/doctor", label: "醫師" },
];

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="zh-TW" className={`${noto.variable} ${inter.variable} ${mono.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col bg-bg text-ink">
        <a href="#main" className="skip-link">跳到主要內容</a>
        <header className="no-print border-b border-line bg-bg">
          <nav aria-label="主要" className="mx-auto flex max-w-6xl items-center gap-2 px-4 py-2">
            <Link href="/" className="mr-auto font-medium text-ink hover:text-primary" translate="no">
              一份能跟著人走的紀錄
            </Link>
            {NAV.map((n) => (
              <Link
                key={n.href}
                href={n.href}
                className="inline-flex min-h-11 items-center rounded-lg px-3 text-sm text-ink-2 hover:bg-surface hover:text-ink"
              >
                {n.label}
              </Link>
            ))}
          </nav>
        </header>
        <main id="main" className="mx-auto w-full max-w-6xl flex-1 px-4 py-6">
          {children}
        </main>
      </body>
    </html>
  );
}
