import type { TrendSeries } from "@schema";
import { DIMENSION_LABELS } from "@schema";
import { fmtDay, fmtNum } from "@/lib/format";

export function Sparkline({ series, height = 72 }: { series: TrendSeries; height?: number }) {
  const pts = series.points.filter((p) => p.value != null);
  const label = DIMENSION_LABELS[series.dimension]["zh-TW"];
  if (pts.length < 2) {
    return <p className="text-sm text-ink-2">{label}：資料不足</p>;
  }
  const w = 320;
  const pad = 6;
  const ys = pts.map((p) => p.value as number);
  const min = Math.min(...ys);
  const max = Math.max(...ys);
  const span = max - min || 1;
  const x = (i: number) => pad + (i / (pts.length - 1)) * (w - pad * 2);
  const y = (v: number) => height - pad - ((v - min) / span) * (height - pad * 2);
  const d = pts.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p.value as number).toFixed(1)}`).join(" ");
  const first = pts[0];
  const last = pts[pts.length - 1];
  return (
    <figure className="min-w-0">
      <figcaption className="mb-1 flex items-baseline justify-between text-sm">
        <span className="font-medium">{label}</span>
        <span className="num text-xs text-ink-2">
          {fmtDay(first.date)} → {fmtDay(last.date)}
        </span>
      </figcaption>
      <svg
        viewBox={`0 0 ${w} ${height}`}
        width="100%"
        height={height}
        role="img"
        aria-label={`${label}趨勢，${fmtNum(pts.length)} 個點，從 ${fmtNum(first.value)} 到 ${fmtNum(last.value)}`}
        className="block"
      >
        <line x1={pad} x2={w - pad} y1={height - pad} y2={height - pad} stroke="var(--line)" strokeWidth="1" />
        <path d={d} fill="none" stroke="var(--primary)" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
        {pts.map((p, i) => (
          <circle key={i} cx={x(i)} cy={y(p.value as number)} r="2.5" fill="var(--primary)" />
        ))}
      </svg>
    </figure>
  );
}
