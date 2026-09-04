"""baseline_comparator — rules, not LLM (ARCHITECTURE §4.2).

Given today's StructuredObservation and the person's Baseline + recent observations,
produce one BaselineDelta per dimension mentioned: direction / magnitude / consecutive days.
"""

from __future__ import annotations

from datetime import date

from record_schema import Baseline, BaselineDelta, Observation, StructuredObservation


def _consecutive_days(
    dim: str, direction: str, recent: list[Observation], today: date
) -> tuple[int, list[str]]:
    """Count consecutive prior days (ending yesterday) moving the same way for this dimension."""
    by_day: dict[date, list[Observation]] = {}
    for o in recent:
        by_day.setdefault(o.ts.date(), []).append(o)
    days = 0
    refs: list[str] = []
    d = today
    while True:
        d = date.fromordinal(d.toordinal() - 1)
        todays = by_day.get(d)
        if not todays:
            break
        hit = [
            o
            for o in todays
            if dim in o.observation.domains and o.observation.domains[dim].direction == direction
        ]
        if not hit:
            break
        days += 1
        refs.extend(o.id for o in hit)
        if days >= 30:
            break
    return days, refs


def compare(
    obs: StructuredObservation,
    baseline: Baseline,
    recent: list[Observation],
    today: date,
) -> list[BaselineDelta]:
    deltas: list[BaselineDelta] = []
    for dim, dv in obs.domains.items():
        base = baseline.current(dim, on=today)
        direction = dv.direction
        magnitude: float | None = None
        if (
            isinstance(dv.value, int | float)
            and base is not None
            and isinstance(base.value, int | float)
        ):
            if base.value:
                magnitude = round(abs(float(dv.value) - float(base.value)) / float(base.value), 2)
            if direction == "unknown":
                direction = (
                    "down" if dv.value < base.value else "up" if dv.value > base.value else "same"
                )
        prior_days, refs = _consecutive_days(dim, direction, recent, today)
        note = f"平常：{base.description}" if base else "尚無基線"
        deltas.append(
            BaselineDelta(
                domain=dim,  # type: ignore[arg-type]
                direction=direction,  # type: ignore[arg-type]
                magnitude=magnitude,
                days=prior_days + 1,
                note=note,
                evidence_refs=refs,
            )
        )
    return deltas
