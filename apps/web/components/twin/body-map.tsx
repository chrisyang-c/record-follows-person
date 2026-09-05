"use client";

import type { Dimension } from "@schema";
import { cn } from "@/lib/utils";

/** 八維度 → 人體位置（viewBox 0 0 200 420）：頭＝認知、頭側＝睡眠、胸＝生命徵象、腹＝進食飲水、骨盆＝排泄、腿＝活動功能、背（肩後）＝皮膚、浮動＝疼痛。 */
export const HOTSPOTS: Record<Dimension, { x: number; y: number; short: string }> = {
  cognition: { x: 100, y: 52, short: "認知" },
  sleep: { x: 136, y: 46, short: "睡眠" },
  vitals: { x: 100, y: 150, short: "心肺" },
  intake: { x: 100, y: 205, short: "進食" },
  elimination: { x: 100, y: 250, short: "排泄" },
  function: { x: 78, y: 330, short: "活動" },
  skin: { x: 140, y: 120, short: "皮膚" },
  pain: { x: 46, y: 250, short: "疼痛" },
};

const COLOR = { same: "var(--accent)", changed: "var(--accent-2)", red: "var(--danger)", idle: "var(--ink-2)" } as const;

/**
 * 人體線稿（--ink-2 20%）＋ 8 個熱點。狀態：與基線一致（--accent 靜態）、有變化（--accent-2 呼吸 2s）、紅燈（--danger 不動畫）。
 * 熱點是全站兩個允許發光的元素之一。點熱點只切換右側面板，人體不重繪。
 */
export function BodyMap({ states, selected, onSelect, idle = false }: { states: Record<string, "same" | "changed" | "red">; selected: Dimension; onSelect: (d: Dimension) => void; idle?: boolean }) {
  return (
    <svg viewBox="0 0 200 420" role="group" aria-label="八維度人體圖" className="mx-auto h-auto w-full max-w-[360px]">
      <g fill="none" stroke="color-mix(in srgb, var(--ink-2) 20%, transparent)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="100" cy="48" r="26" />
        <path d="M100 74 v18 M72 96 q28 -10 56 0 l14 110 q-4 12 -14 12 M72 96 l-14 110 q4 12 14 12" />
        <path d="M86 92 q14 8 28 0 l10 118 h-48 z" />
        <path d="M58 206 l-12 60 M142 206 l12 60" />
        <path d="M76 210 l-6 120 l6 70 M124 210 l6 120 l-6 70 M100 214 v100" />
        <path d="M70 400 h-10 M130 400 h10" />
      </g>
      {(Object.keys(HOTSPOTS) as Dimension[]).map((d) => {
        const h = HOTSPOTS[d];
        const st = idle ? "idle" : (states[d] ?? "same");
        const color = COLOR[st];
        const isSel = d === selected;
        return (
          <g key={d} transform={`translate(${h.x} ${h.y})`} style={{ color }} className={cn(st === "changed" && !idle && "breathe")}>
            <circle r={isSel ? 13 : 10} fill="var(--surface)" stroke={color} strokeWidth={isSel ? 2.5 : 1.5} style={{ filter: st !== "idle" ? `drop-shadow(0 0 8px ${color})` : undefined }} />
            <circle r="3.5" fill={color} />
            <foreignObject x="-24" y="-24" width="48" height="48">
              <button type="button" aria-label={`${h.short}${isSel ? "（已選）" : ""}`} aria-pressed={isSel} onClick={() => onSelect(d)} className="size-full rounded-full bg-transparent" />
            </foreignObject>
          </g>
        );
      })}
    </svg>
  );
}
