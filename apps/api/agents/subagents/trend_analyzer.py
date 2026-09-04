"""trend_analyzer subagent — structured output only, no prose (ARCHITECTURE §4.8).

Windows: 7 days, 30 days, since last round. Flags cross-dimension simultaneous change."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from record_schema import (
    DIMENSION_LABELS,
    DIMENSIONS,
    Observation,
    TrendLine,
    TrendPoint,
    TrendReport,
    TrendSeries,
)

_DIR_SCORE = {"down": -1.0, "up": 1.0, "same": 0.0, "unknown": 0.0}
# For symptom-type dimensions, "up" means *more* symptoms = worse.
_WORSE_DIRECTION = {
    "intake": "down",
    "elimination": "up",
    "function": "down",
    "cognition": "up",
    "sleep": "up",
    "skin": "up",
    "pain": "up",
    "vitals": "up",
}


def analyze(
    patient_id: str,
    observations: list[Observation],
    incidents: list[str],
    since: date,
    until: date,
    window_days: int = 7,
) -> TrendReport:
    win_start = until - timedelta(days=window_days - 1)
    lines: list[TrendLine] = []
    series: list[TrendSeries] = []
    per_dim_points: dict[str, list[TrendPoint]] = defaultdict(list)
    for o in sorted(observations, key=lambda x: x.ts):
        d = o.ts.date()
        if d < since:
            continue
        for dim, dv in o.observation.domains.items():
            val = float(dv.value) if isinstance(dv.value, int | float) else _DIR_SCORE[dv.direction]
            per_dim_points[dim].append(TrendPoint(date=d, value=val, label=dv.raw_quote[:24]))
    for dim in DIMENSIONS:
        pts = per_dim_points.get(dim, [])
        if not pts:
            continue
        window = [p for p in pts if p.date >= win_start]
        obs_in_window = [
            o for o in observations if o.ts.date() >= win_start and dim in o.observation.domains
        ]
        worse = _WORSE_DIRECTION[dim]
        worse_days = len(
            {o.ts.date() for o in obs_in_window if o.observation.domains[dim].direction == worse}
        )
        direction = (
            worse
            if worse_days >= max(2, len({p.date for p in window}) // 2 + 1)
            else ("same" if window else "unknown")
        )
        numeric = [p.value for p in pts if p.value is not None and dim in ("intake", "sleep")]
        magnitude = None
        if len(numeric) >= 2 and numeric[0]:
            first = sum(numeric[:2]) / 2
            last = sum(numeric[-2:]) / 2
            magnitude = round(abs(last - first) / abs(first), 2) if first else None
        is_abnormal = worse_days >= 3 or (
            magnitude is not None and magnitude >= 0.25 and direction == worse
        )
        label = DIMENSION_LABELS[dim]["zh-TW"]
        if direction == worse:
            verb = "減少" if worse == "down" else "出現或增加"
            summary = f"{label}：近 {window_days} 天有 {worse_days} 天{verb}"
            if magnitude is not None:
                summary += f"，幅度約 {magnitude:.0%}"
        elif direction == "same":
            summary = f"{label}：與平常相同"
        else:
            summary = f"{label}：資料不足"
        lines.append(
            TrendLine(
                dimension=dim,  # type: ignore[arg-type]
                direction=direction,  # type: ignore[arg-type]
                summary=summary,
                window_days=window_days,
                magnitude=magnitude,
                evidence_refs=[o.id for o in obs_in_window][:8],
                is_abnormal=is_abnormal,
            )
        )
        series.append(TrendSeries(dimension=dim, points=pts))  # type: ignore[arg-type]
    abnormal = [line for line in lines if line.is_abnormal]
    cross = None
    if len(abnormal) >= 2:
        names = "＋".join(DIMENSION_LABELS[line.dimension]["zh-TW"] for line in abnormal)
        cross = f"跨維度同時變化：{names} 在同一個 {window_days} 天窗口內一起變差"
    lines.sort(key=lambda line: (not line.is_abnormal, -(line.magnitude or 0)))
    return TrendReport(
        patient_id=patient_id,
        since=since,
        until=until,
        lines=lines,
        cross_dimension_signal=cross,
        series=series,
        incident_ids=incidents,
    )


def top_two_series(report: TrendReport) -> list[TrendSeries]:
    """ARCHITECTURE §11: one chart, the two dimensions that changed the most."""
    ranked = sorted(
        report.lines,
        key=lambda line: (not line.is_abnormal, -(line.magnitude or 0), -len(line.evidence_refs)),
    )
    chosen = [line.dimension for line in ranked[:2]]
    return [s for s in report.series if s.dimension in chosen]
