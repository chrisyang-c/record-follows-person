"""Small, review-gated FHIR R4 Bundle adapter.

This is intentionally a synthetic interoperability slice, not a FHIR server.  It accepts
Patient + Observation resources, resolves the Patient against the local Health ID, normalizes
known vital codes, and stores the raw bundle plus normalized observations for nurse review.
Nothing is promoted to the clinical timeline automatically.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from core.ids import new_id
from record.store import get_store

_CODE_MAP: dict[str, tuple[str, str]] = {
    "8310-5": ("temp_c", "Cel"),
    "8480-6": ("sbp", "mmHg"),
    "8462-4": ("dbp", "mmHg"),
    "8867-4": ("hr", "/min"),
    "2708-6": ("spo2", "%"),
    "9279-1": ("rr", "/min"),
}


class NormalizedObservation(BaseModel):
    resource_id: str
    code: str
    display: str | None = None
    dimension: str | None = None
    value: float | None = None
    unit: str | None = None
    effective_at: datetime | None = None
    status: str = "unknown"
    subject_reference: str | None = None


class FHIRImportResult(BaseModel):
    import_id: str
    bundle_id: str
    patient_id: str
    status: str
    resource_count: int
    normalized_observations: list[NormalizedObservation] = Field(default_factory=list)
    unresolved_resources: list[str] = Field(default_factory=list)
    received_at: datetime
    source: str = "synthetic"


def _imports_path(patient_id: str) -> Path:
    return get_store().dir(patient_id) / "external" / "fhir_imports.json"


def _read_imports(patient_id: str) -> list[dict[str, Any]]:
    path = _imports_path(patient_id)
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _write_atomic(path: Path, data: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        with tmp.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def _date_time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=parsed.tzinfo or UTC)


def _code(resource: dict[str, Any]) -> tuple[str, str | None]:
    coding = (resource.get("code") or {}).get("coding") or []
    first = coding[0] if coding and isinstance(coding[0], dict) else {}
    return str(first.get("code") or "unknown"), first.get("display") or (
        resource.get("code") or {}
    ).get("text")


def _subject(resource: dict[str, Any]) -> str | None:
    ref = (resource.get("subject") or {}).get("reference")
    return str(ref) if ref else None


def _normalize(resource: dict[str, Any]) -> NormalizedObservation:
    code, display = _code(resource)
    quantity = resource.get("valueQuantity") or {}
    dimension, canonical_unit = _CODE_MAP.get(code, (None, quantity.get("unit")))
    value = quantity.get("value")
    try:
        numeric = float(value) if value is not None else None
    except (TypeError, ValueError):
        numeric = None
    return NormalizedObservation(
        resource_id=str(resource.get("id") or "unknown"),
        code=code,
        display=display,
        dimension=dimension,
        value=numeric,
        unit=canonical_unit,
        effective_at=_date_time(resource.get("effectiveDateTime")),
        status=str(resource.get("status") or "unknown"),
        subject_reference=_subject(resource),
    )


def _bundle_id(bundle: dict[str, Any]) -> str:
    value = bundle.get("id")
    if value:
        return str(value)
    canonical = json.dumps(bundle, ensure_ascii=False, sort_keys=True).encode()
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


def import_bundle(
    patient_id: str, bundle: dict[str, Any], *, source: str = "synthetic"
) -> FHIRImportResult:
    """Validate and persist a review-gated import.  Replaying a bundle is idempotent."""
    if bundle.get("resourceType") != "Bundle":
        raise ValueError("FHIR payload must be a Bundle")
    if bundle.get("type") not in {"collection", "batch", "transaction"}:
        raise ValueError("only collection, batch, or transaction Bundles are accepted")
    entries = [
        e
        for e in bundle.get("entry", [])
        if isinstance(e, dict) and isinstance(e.get("resource"), dict)
    ]
    resources = [e["resource"] for e in entries]
    patient_resources = [r for r in resources if r.get("resourceType") == "Patient"]
    local = get_store().load_profile(patient_id)
    bundle_id = _bundle_id(bundle)
    existing = next(
        (
            row
            for row in _read_imports(patient_id)
            if row.get("result", {}).get("bundle_id") == bundle_id
            and row.get("result", {}).get("source") == source
        ),
        None,
    )
    if existing:
        return FHIRImportResult.model_validate(existing["result"])

    identifiers = {
        str(item.get("value"))
        for resource in patient_resources
        for item in (resource.get("identifier") or [])
        if isinstance(item, dict) and item.get("value")
    }
    patient_ids = {patient_id, local.health_id}
    identity_ok = bool(identifiers & patient_ids) or any(
        str(resource.get("id")) in patient_ids for resource in patient_resources
    )
    observations = [
        _normalize(resource)
        for resource in resources
        if resource.get("resourceType") == "Observation"
    ]
    unresolved = [
        item.resource_id
        for item in observations
        if not item.subject_reference or item.subject_reference.split("/")[-1] not in patient_ids
    ]
    if not identity_ok:
        status = "identity_unresolved"
        unresolved = [*unresolved, "Patient"]
    elif unresolved:
        status = "partial_identity_review"
    else:
        status = "pending_review"
    result = FHIRImportResult(
        import_id=new_id("fhir"),
        bundle_id=bundle_id,
        patient_id=patient_id,
        status=status,
        resource_count=len(resources),
        normalized_observations=observations,
        unresolved_resources=sorted(set(unresolved)),
        received_at=datetime.now(UTC),
        source=source,
    )
    rows = _read_imports(patient_id)
    rows.append({"result": result.model_dump(mode="json"), "raw_bundle": bundle})
    _write_atomic(_imports_path(patient_id), rows)
    return result


def list_imports(patient_id: str) -> list[FHIRImportResult]:
    return [FHIRImportResult.model_validate(row["result"]) for row in _read_imports(patient_id)]


def export_bundle(patient_id: str, import_id: str | None = None) -> dict[str, Any]:
    """Export normalized observations as a valid synthetic FHIR collection Bundle."""
    rows = _read_imports(patient_id)
    row = next(
        (item for item in rows if not import_id or item["result"]["import_id"] == import_id), None
    )
    if row is None:
        raise KeyError(import_id or patient_id)
    profile = get_store().load_profile(patient_id)
    resources: list[dict[str, Any]] = [
        {
            "resourceType": "Patient",
            "id": profile.health_id,
            "identifier": [{"system": "urn:health-id", "value": profile.health_id}],
        }
    ]
    for item in row["result"].get("normalized_observations", []):
        resources.append(
            {
                "resourceType": "Observation",
                "id": item["resource_id"],
                "status": item["status"],
                "subject": {"reference": f"Patient/{profile.health_id}"},
                "code": {"coding": [{"code": item["code"], "display": item.get("display")}]},
                "valueQuantity": {"value": item["value"], "unit": item["unit"]},
                "effectiveDateTime": item["effective_at"],
            }
        )
    return {
        "resourceType": "Bundle",
        "id": f"export-{row['result']['import_id']}",
        "type": "collection",
        "entry": [{"resource": resource} for resource in resources],
    }
