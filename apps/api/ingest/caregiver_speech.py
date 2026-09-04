"""Channel 1 — caregiver speech (any language) → StructuredObservation.

Speech-to-text happens in the browser (Web Speech API); the API receives text. An audio
reference, if any, is kept out of state (only a reference string is stored)."""

from __future__ import annotations

from datetime import UTC, datetime

from record_schema import (
    Baseline,
    FollowupQA,
    Lang,
    Profile,
    StructuredObservation,
)

from core.llm import get_llm


def ingest(
    text: str,
    lang: Lang,
    profile: Profile | None = None,
    baseline: Baseline | None = None,
    followup_answers: list[FollowupQA] | None = None,
    media_refs: list[str] | None = None,
) -> StructuredObservation:
    obs = get_llm().extract_observation(text, lang, profile, baseline)
    if followup_answers:
        answered = {a.question: a for a in followup_answers}
        obs.followups = [answered.get(q.question, q) for q in obs.followups]
        for a in followup_answers:
            if a.question not in answered or a.answered_unknown or not a.answer:
                continue
            extra = get_llm().extract_observation(a.answer, lang, profile, baseline)
            for k, v in extra.domains.items():
                if k not in obs.domains or obs.domains[k].value is None:
                    obs.domains[k] = v
            for f, val in extra.flags.model_dump().items():
                if val:
                    setattr(obs.flags, f, True)
            if extra.vitals_reported:
                obs.vitals_reported = extra.vitals_reported
        obs.unknown = [d for d in obs.unknown if d not in obs.domains]
    if media_refs:
        obs.followups.append(
            FollowupQA(
                question="影像摘要（固定 mock）", answer="影像已附上，摘要由護理師確認", lang=lang
            )
        )
    _ = datetime.now(UTC)
    return obs
