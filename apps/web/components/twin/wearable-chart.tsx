"use client";

import type { WearableDay } from "@/lib/api";

/**
 * 複合圖（想法參考 health-ref：長條＋折線）：步數（長條，--accent）＋睡眠時數（折線，--accent-2）。
 * wellness 區可放數字；沒有品質分數。
 */
export function WearableChart({ rows, height = 150 }: { rows: WearableDay[]; height?: number }) {
  if (rows.length < 2) return <p className="text-sm text-ink-2">還沒有足夠的穿戴資料。</p>;
  const w = 360;
  const padL = 30, padR = 30, padT = 10, padB = 18;
  const n = rows.length;
  const bw = (w - padL - padR) / n;
  const maxSteps = Math.max(...rows.map((r) => r.steps), 1);
  const maxSleep = 10;
  const x = (i: number) => padL + i * bw + bw / 2;
  const yS = (v: number) => height - padB - (v / maxSteps) * (height - padT - padB);
  const yH = (v: number) => height - padB - (v / maxSleep) * (height - padT - padB);
  const line = rows.map((r, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${yH(r.sleep_hours).toFixed(1)}`).join(" ");
  return (
    <figure className="min-w-0">
      <figcaption className="mb-1 flex items-center gap-3 text-xs text-ink-2">
        <span><span className="mr-1 inline-block size-2 rounded-sm bg-accent align-middle" aria-hidden="true" />步數</span>
        <span><span className="mr-1 inline-block h-0.5 w-3 bg-accent-2 align-middle" aria-hidden="true" />睡眠時數</span>
        <span className="ml-auto num">{rows[0].day.slice(5)} → {rows[n - 1].day.slice(5)}</span>
      </figcaption>
      <svg viewBox={`0 0 ${w} ${height}`} width="100%" height={height} role="img" aria-label={`近 ${n} 天步數與睡眠時數`} className="block">
        {rows.map((r, i) => (
          <rect key={r.day} x={x(i) - bw * 0.3} y={yS(r.steps)} width={bw * 0.6} height={height - padB - yS(r.steps)} rx="2" fill="color-mix(in srgb, var(--accent) 55%, transparent)" />
        ))}
        <path d={line} fill="none" stroke="var(--accent-2)" strokeWidth="1.5" strokeLinejoin="round" />
        {rows.map((r, i) => <circle key={r.day} cx={x(i)} cy={yH(r.sleep_hours)} r="2" fill="var(--accent-2)" />)}
        <text x={padL - 4} y={padT + 8} fontSize="9" fill="var(--ink-2)" textAnchor="end">{maxSteps}</text>
        <text x={w - padR + 4} y={padT + 8} fontSize="9" fill="var(--ink-2)">10h</text>
        <text x={w - padR + 4} y={height - padB} fontSize="9" fill="var(--ink-2)">0h</text>
      </svg>
    </figure>
  );
}
