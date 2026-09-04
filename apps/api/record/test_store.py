from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError
from record_schema import (
    Baseline,
    BaselineEntry,
    BaselineProposal,
    DimensionValue,
    Facility,
    Observation,
    Profile,
    Provenance,
    StructuredObservation,
)

from record.store import (
    ImmutableTimelineError,
    MissingProvenanceError,
    RecordStore,
    UnapprovedWriteError,
)

TS = datetime(2026, 9, 1, 8, 0, tzinfo=UTC)


def prov(source="caregiver_said", author="cg_xiaofang", confirmed_by=None) -> Provenance:
    return Provenance(source=source, author=author, confirmed_by=confirmed_by, ts=TS)


def profile() -> Profile:
    return Profile(
        patient_id="P001",
        code_name="王伯",
        sex="M",
        birth_year=1940,
        room="201-A",
        contract_facility=Facility(name="特約醫院", phone="02-0000-0000"),
        caregiver_code_name="cg_xiaofang",
        caregiver_language="zh-TW",
        primary_nurse="nurse_lin",
    )


def baseline() -> Baseline:
    return Baseline(
        entries=[
            BaselineEntry(
                dimension="intake",
                value=1.0,
                description="三餐吃完",
                valid_from=date(2026, 8, 1),
                set_by="nurse_confirmed",
                confirmed_by="nurse_lin",
                provenance=prov("nurse_confirmed", "nurse_lin", "nurse_lin"),
            )
        ]
    )


def observation(status="approved", confirmed_by="nurse_lin", oid="obs_1") -> Observation:
    return Observation(
        id=oid,
        patient_id="P001",
        ts=TS,
        status=status,
        confirmed_by=confirmed_by,
        provenance=prov("nurse_confirmed", "nurse_lin", confirmed_by),
        shift="day",
        observation=StructuredObservation(
            raw_text="吃一半",
            language="zh-TW",
            domains={
                "intake": DimensionValue(
                    value=0.5,
                    raw_quote="吃一半",
                    provenance=prov("ai_extracted", "intake_agent"),
                    confidence=0.8,
                    lang="zh-TW",
                    direction="down",
                )
            },
        ),
    )


@pytest.fixture
def store(tmp_path) -> RecordStore:
    s = RecordStore(tmp_path)
    s.init_record(profile(), baseline())
    return s


def test_write_timeline_rejects_draft(store):
    with pytest.raises(UnapprovedWriteError):
        store.write_timeline("P001", observation(status="draft", confirmed_by=None))
    assert store.load_timeline("P001") == []


def test_write_timeline_rejects_missing_confirmed_by(store):
    with pytest.raises(UnapprovedWriteError):
        store.write_timeline("P001", observation(status="approved", confirmed_by=None))


def test_write_timeline_rejects_draft_dict(store):
    payload = observation().model_dump(mode="json")
    payload["status"] = "draft"
    with pytest.raises(UnapprovedWriteError):
        store.write_timeline("P001", payload)


def test_write_timeline_requires_provenance_on_every_line(store):
    payload = observation().model_dump(mode="json")
    payload["observation"]["domains"]["intake"].pop("provenance")
    with pytest.raises(MissingProvenanceError):
        store.write_timeline("P001", payload)
    payload = observation().model_dump(mode="json")
    payload.pop("provenance")
    with pytest.raises(MissingProvenanceError):
        store.write_timeline("P001", payload)


def test_schema_refuses_dimension_without_provenance():
    with pytest.raises(ValidationError):
        DimensionValue(value=1, raw_quote="x", confidence=0.5, lang="zh-TW")  # type: ignore[call-arg]


def test_write_timeline_appends_and_is_immutable(store):
    oid = store.write_timeline("P001", observation())
    assert oid == "obs_1"
    with pytest.raises(ImmutableTimelineError):
        store.write_timeline("P001", observation())
    tl = store.load_timeline("P001")
    assert len(tl) == 1 and tl[0].kind == "observation"
    ledger = store.read_provenance("P001")
    refs = {(line.ref, line.field) for line in ledger}
    assert ("obs_1", "") in refs and ("obs_1", "intake") in refs
    assert ("baseline", "intake") in refs


def test_provenance_is_frozen():
    p = prov()
    with pytest.raises(ValidationError):
        p.source = "nurse_confirmed"  # type: ignore[misc]


def test_baseline_write_requires_approved_proposal(store):
    entry = BaselineEntry(
        dimension="intake",
        value=0.5,
        description="半碗",
        valid_from=date(2026, 9, 2),
        set_by="doctor_ordered",
        provenance=prov("doctor_ordered", "dr_chen"),
    )
    draft = BaselineProposal(patient_id="P001", proposals=[entry], reason="醫囑")
    with pytest.raises(UnapprovedWriteError):
        store.write_baseline("P001", draft)
    ok = draft.model_copy(update={"status": "approved", "confirmed_by": "nurse_lin"})
    b = store.write_baseline("P001", ok)
    cur = b.current("intake", on=date(2026, 9, 3))
    assert cur is not None and cur.value == 0.5 and cur.confirmed_by == "nurse_lin"
    old = b.current("intake", on=date(2026, 8, 15))
    assert old is not None and old.value == 1.0 and old.valid_to == date(2026, 9, 2)


def test_document_write_rejects_draft(store):
    from record_schema import CaregiverNotes

    doc = CaregiverNotes(
        id="notes_1",
        patient_id="P001",
        generated_at=TS,
        status="draft",
        author="order_ingest",
        provenance=prov("ai_extracted", "order_ingest"),
        audience="caregiver",
        lang="zh-TW",
        items=["a", "b", "c"],
        source_order_id="ord_1",
    )
    with pytest.raises(UnapprovedWriteError):
        store.write_document("P001", doc)
    ok = doc.model_copy(update={"status": "approved", "confirmed_by": "nurse_lin"})
    assert store.write_document("P001", ok) == "notes_1"
    assert store.load_documents("P001", "caregiver_notes")[0].id == "notes_1"
