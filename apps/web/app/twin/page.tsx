import Link from "next/link";
import { ScanLine } from "lucide-react";

/** 01 活體數位孿生（本人視角，wellness 語氣）——人體圖與維度面板在遷移第 6 步；此頁先站位。 */
export default function TwinPage() {
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <span className="inline-flex size-12 items-center justify-center rounded-full border border-accent/60 text-accent"><ScanLine className="size-6" aria-hidden="true" /></span>
        <div>
          <h1 className="text-2xl font-medium">活體數位孿生體</h1>
          <p className="label-caps">Bio-Twin · Organ Drill-down</p>
        </div>
      </div>
      <p className="text-ink-2">八維度人體圖與維度面板建置中（遷移第 6 步）。先到 <Link href="/me" className="text-accent hover:underline">05 本人艙</Link>。</p>
    </div>
  );
}
