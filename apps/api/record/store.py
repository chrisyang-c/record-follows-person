"""Filesystem-backed PersonRecord store.

Layout (one directory per person, follows the person):

    records/{patient_id}/
      profile.json
      baseline.json
      timeline/{ts}_{kind}_{id}.json     append-only
      documents/{doc_type}_{id}.json     approved documents only
      provenance.jsonl                   append-only ledger, one line per written line

Gates enforced here (CLAUDE.md §1, §4, §11):
  * write_timeline: payload.status == "approved" and payload.confirmed_by, else UnapprovedWriteError
  * timeline is append-only: an existing id raises ImmutableTimelineError
  * provenance is required on every entry / document / dimension value (MissingProvenanceError)
  * baseline is written only through write_baseline with an approved BaselineProposal
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter, ValidationError
from record_schema import (
    Baseline,
    BaselineEntry,
    BaselineProposal,
    Document,
    Observation,
    PersonRecord,
    Profile,
    Provenance,
    ProvenanceLine,
    TimelineEntry,
)

from core.ids import new_id
from core.settings import get_settings

_TIMELINE = TypeAdapter(TimelineEntry)
_DOCUMENT = TypeAdapter(Document)


class UnapprovedWriteError(PermissionError):
    """Raised when something tries to write a non-approved payload into the record."""


class ImmutableTimelineError(PermissionError):
    """Raised when something tries to overwrite an existing timeline entry."""


class MissingProvenanceError(ValueError):
    """Raised when a payload lacks provenance on any line."""


def _dump(model: Any) -> str:
    return json.dumps(model.model_dump(mode="json"), ensure_ascii=False, indent=2)


class RecordStore:
    def __init__(self, root: Path):
        self.root = Path(root)

    # -- paths ---------------------------------------------------------------
    def dir(self, patient_id: str) -> Path:
        return self.root / patient_id

    def exists(self, patient_id: str) -> bool:
        return (self.dir(patient_id) / "profile.json").exists()

    def list_patients(self) -> list[str]:
        if not self.root.exists():
            return []
        return sorted(p.name for p in self.root.iterdir() if (p / "profile.json").exists())

    # -- init ------------------------------------------------------------------
    def init_record(self, profile: Profile, baseline: Baseline) -> None:
        d = self.dir(profile.patient_id)
        (d / "timeline").mkdir(parents=True, exist_ok=True)
        (d / "documents").mkdir(parents=True, exist_ok=True)
        (d / "profile.json").write_text(_dump(profile), encoding="utf-8")
        (d / "baseline.json").write_text(_dump(baseline), encoding="utf-8")
        (d / "provenance.jsonl").touch()
        for e in baseline.entries:
            self._append_provenance(
                profile.patient_id, ref="baseline", field=e.dimension, prov=e.provenance
            )

    # -- read ------------------------------------------------------------------
    def load_profile(self, patient_id: str) -> Profile:
        return Profile.model_validate_json((self.dir(patient_id) / "profile.json").read_text())

    def load_baseline(self, patient_id: str) -> Baseline:
        return Baseline.model_validate_json((self.dir(patient_id) / "baseline.json").read_text())

    def load_timeline(
        self,
        patient_id: str,
        since: datetime | date | None = None,
        kinds: set[str] | None = None,
    ) -> list[TimelineEntry]:
        tdir = self.dir(patient_id) / "timeline"
        if not tdir.exists():
            return []
        out: list[TimelineEntry] = []
        for f in sorted(tdir.glob("*.json")):
            e = _TIMELINE.validate_json(f.read_text())
            if kinds and e.kind not in kinds:
                continue
            if since is not None:
                s = since if isinstance(since, datetime) else datetime.combine(since, datetime.min.time(), UTC)
                if e.ts < s:
                    continue
            out.append(e)
        return sorted(out, key=lambda e: e.ts)

    def load_documents(self, patient_id: str, doc_type: str | None = None) -> list[Document]:
        ddir = self.dir(patient_id) / "documents"
        if not ddir.exists():
            return []
        docs = [_DOCUMENT.validate_json(f.read_text()) for f in sorted(ddir.glob("*.json"))]
        if doc_type:
            docs = [d for d in docs if d.doc_type == doc_type]
        return sorted(docs, key=lambda d: d.generated_at)

    def get_document(self, patient_id: str, doc_id: str) -> Document | None:
        for d in self.load_documents(patient_id):
            if d.id == doc_id:
                return d
        return None

    def read_provenance(self, patient_id: str) -> list[ProvenanceLine]:
        f = self.dir(patient_id) / "provenance.jsonl"
        if not f.exists():
            return []
        return [
            ProvenanceLine.model_validate_json(line)
            for line in f.read_text().splitlines()
            if line.strip()
        ]

    def load(self, patient_id: str) -> PersonRecord:
        return PersonRecord(
            profile=self.load_profile(patient_id),
            baseline=self.load_baseline(patient_id),
            timeline=self.load_timeline(patient_id),
            documents=self.load_documents(patient_id),
            provenance=self.read_provenance(patient_id),
        )

    # -- write (gated) ----------------------------------------------------------
    def write_timeline(self, patient_id: str, payload: Any) -> str:
        """The only write entry for the timeline. Rejects drafts, rewrites and missing provenance."""
        entry = self._coerce_timeline(payload)
        assert entry.status == "approved" and entry.confirmed_by, "timeline_write requires approval"
        if entry.patient_id != patient_id:
            raise ValueError("payload.patient_id does not match record")
        tdir = self.dir(patient_id) / "timeline"
        tdir.mkdir(parents=True, exist_ok=True)
        if any(f.name.endswith(f"_{entry.id}.json") for f in tdir.glob("*.json")):
            raise ImmutableTimelineError(f"timeline entry {entry.id} already exists (append-only)")
        fname = f"{entry.ts.strftime('%Y%m%dT%H%M%S')}_{entry.kind}_{entry.id}.json"
        (tdir / fname).write_text(_dump(entry), encoding="utf-8")
        self._append_provenance(patient_id, ref=entry.id, field="", prov=entry.provenance)
        if isinstance(entry, Observation):
            for dim, dv in entry.observation.domains.items():
                self._append_provenance(patient_id, ref=entry.id, field=dim, prov=dv.provenance)
        return entry.id

    def write_document(self, patient_id: str, payload: Any) -> str:
        doc = self._coerce_document(payload)
        if doc.status != "approved" or not doc.confirmed_by:
            raise UnapprovedWriteError(
                f"document {doc.id} is {doc.status}; only approved documents enter the record"
            )
        if doc.patient_id != patient_id:
            raise ValueError("payload.patient_id does not match record")
        ddir = self.dir(patient_id) / "documents"
        ddir.mkdir(parents=True, exist_ok=True)
        (ddir / f"{doc.doc_type}_{doc.id}.json").write_text(_dump(doc), encoding="utf-8")
        self._append_provenance(patient_id, ref=doc.id, field="", prov=doc.provenance)
        return doc.id

    def write_baseline(self, patient_id: str, proposal: BaselineProposal) -> Baseline:
        """Only entry for baseline changes; requires an approved proposal (◇nurse_confirm_baseline)."""
        if proposal.status != "approved" or not proposal.confirmed_by:
            raise UnapprovedWriteError("baseline proposal must be approved by a nurse")
        if proposal.patient_id != patient_id:
            raise ValueError("proposal.patient_id does not match record")
        baseline = self.load_baseline(patient_id)
        for new in proposal.proposals:
            if new.provenance is None:  # pragma: no cover - pydantic enforces
                raise MissingProvenanceError("baseline entry without provenance")
            for old in baseline.entries:
                if old.dimension == new.dimension and old.valid_to is None:
                    old.valid_to = new.valid_from
            entry = BaselineEntry(
                dimension=new.dimension,
                value=new.value,
                description=new.description,
                valid_from=new.valid_from,
                valid_to=None,
                set_by=new.set_by,
                confirmed_by=proposal.confirmed_by,
                provenance=new.provenance,
            )
            baseline.entries.append(entry)
            self._append_provenance(
                patient_id, ref="baseline", field=new.dimension, prov=new.provenance
            )
        (self.dir(patient_id) / "baseline.json").write_text(_dump(baseline), encoding="utf-8")
        return baseline

    # -- internals -------------------------------------------------------------
    def _coerce_timeline(self, payload: Any) -> TimelineEntry:
        if isinstance(payload, dict):
            self._require_provenance_in_dict(payload)
            try:
                return _TIMELINE.validate_python(payload)
            except ValidationError as e:
                raise MissingProvenanceError(str(e)) if "provenance" in str(e) else e
        if getattr(payload, "status", None) != "approved" or not getattr(payload, "confirmed_by", None):
            raise UnapprovedWriteError(
                f"timeline entry {getattr(payload, 'id', '?')} is not approved/confirmed"
            )
        return payload

    def _coerce_document(self, payload: Any) -> Document:
        if isinstance(payload, dict):
            self._require_provenance_in_dict(payload)
            return _DOCUMENT.validate_python(payload)
        return payload

    @staticmethod
    def _require_provenance_in_dict(payload: dict[str, Any]) -> None:
        if payload.get("status") != "approved" or not payload.get("confirmed_by"):
            raise UnapprovedWriteError("payload is not approved/confirmed")
        if not payload.get("provenance"):
            raise MissingProvenanceError("payload has no provenance")
        obs = payload.get("observation") or {}
        for dim, dv in (obs.get("domains") or {}).items():
            if not isinstance(dv, dict) or not dv.get("provenance"):
                raise MissingProvenanceError(f"dimension {dim} has no provenance")

    def _append_provenance(self, patient_id: str, *, ref: str, field: str, prov: Provenance) -> None:
        line = ProvenanceLine(
            line_id=new_id("prov"),
            ref=ref,
            field=field,
            source=prov.source,
            author=prov.author,
            confirmed_by=prov.confirmed_by,
            ts=prov.ts,
            language_original=prov.language_original,
        )
        with (self.dir(patient_id) / "provenance.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(line.model_dump(mode="json"), ensure_ascii=False) + "\n")


@lru_cache
def get_store() -> RecordStore:
    return RecordStore(get_settings().records_root)


def write_timeline(patient_id: str, payload: Any) -> str:
    """Module-level alias — the single sanctioned timeline write (used by graph `timeline_write`)."""
    return get_store().write_timeline(patient_id, payload)
