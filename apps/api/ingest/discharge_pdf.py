"""Channel 3 — discharge summary (PDF/photo). MOCK: returns a fixed, synthetic summary.

Real parsing is out of demo scope (ARCHITECTURE §8)."""

from __future__ import annotations

from datetime import UTC, date, datetime

from pydantic import BaseModel
from record_schema import BaselineEntry, BaselineProposal, Provenance


class DischargeSummary(BaseModel):
    hospital: str
    admitted: date
    discharged: date
    diagnosis_text: str
    medications: list[str]
    follow_up: str
    source_ref: str


def ingest(patient_id: str, file_ref: str = "mock://discharge.pdf") -> DischargeSummary:
    return DischargeSummary(
        hospital="合作醫院（示意）",
        admitted=date(2026, 7, 20),
        discharged=date(2026, 7, 26),
        diagnosis_text="（出院摘要文字為 mock，非真實資料）",
        medications=["（依出院帶藥單）"],
        follow_up="兩週後門診回診",
        source_ref=file_ref,
    )


def to_baseline_proposal(patient_id: str, summary: DischargeSummary) -> BaselineProposal:
    """Discharge summaries become *proposals*; a nurse must confirm before baseline changes."""
    ts = datetime.now(UTC)
    prov = Provenance(source="system_derived", author="discharge_pdf_ingest", ts=ts)
    return BaselineProposal(
        patient_id=patient_id,
        proposals=[
            BaselineEntry(
                dimension="function",
                value=None,
                description="出院後：短距離行走需一人扶持（出院摘要建議，待護理師確認）",
                valid_from=summary.discharged,
                set_by="system_derived",
                provenance=prov,
            )
        ],
        reason=f"出院摘要 {summary.source_ref}（mock）",
    )
