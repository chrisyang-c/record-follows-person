"use client";

/** 14 天趨勢線（--accent-2 1.5px），基線區間淡帶（--line 30%）。wellness 語氣，只在 01／/me。 */
export function TrendLine({ points, height = 96 }: { points: { date: string; value: number | null }[]; height?: number }) {
  const pts = points.filter((p) => p.value != null) as { date: string; value: number }[];
  if (pts.length < 2) return <p className="text-sm text-ink-2">還沒有足夠的紀錄畫趨勢。</p>;
  const w = 320;
  const pad = 8;
  const ys = pts.map((p) => p.value);
  const min = Math.min(...ys);
  const max = Math.max(...ys);
  const span = max - min || 1;
  const x = (i: number) => pad + (i / (pts.length - 1)) * (w - pad * 2);
  const y = (v: number) => height - pad - ((v - min) / span) * (height - pad * 2);
  const d = pts.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p.value).toFixed(1)}`).join(" ");
  const mean = ys.reduce((a, b) => a + b, 0) / ys.length;
  const band = span * 0.15;
  return (
    <svg viewBox={`0 0 ${w} ${height}`} width="100%" height={height} role="img" aria-label={`近 ${pts.length} 天趨勢`} className="block">
      <rect x={pad} y={y(mean + band)} width={w - pad * 2} height={Math.max(2, y(mean - band) - y(mean + band))} fill="color-mix(in srgb, var(--line) 30%, transparent)" />
      <path d={d} fill="none" stroke="var(--accent-2)" strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={x(pts.length - 1)} cy={y(pts[pts.length - 1].value)} r="3" fill="var(--accent-2)" />
      <text x={pad} y={height - 1} fontSize="9" fill="var(--ink-2)">{pts[0].date.slice(5)}</text>
      <text x={w - pad} y={height - 1} fontSize="9" fill="var(--ink-2)" textAnchor="end">{pts[pts.length - 1].date.slice(5)}</text>
    </svg>
  );
}
