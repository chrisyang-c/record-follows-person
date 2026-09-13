from datetime import UTC, datetime

import pytest

from ingest.fhir_bundle import export_bundle, import_bundle, list_imports


def _bundle(patient_ref: str = "P001", bundle_id: str = "b-1"):
    return {
        "resourceType": "Bundle",
        "id": bundle_id,
        "type": "collection",
        "entry": [
            {
                "resource": {
                    "resourceType": "Patient",
                    "id": "P001",
                    "identifier": [{"system": "urn:health-id", "value": "P001-HID"}],
                }
            },
            {
                "resource": {
                    "resourceType": "Observation",
                    "id": "obs-bp",
                    "status": "final",
                    "subject": {"reference": f"Patient/{patient_ref}"},
                    "code": {"coding": [{"system": "http://loinc.org", "code": "8480-6"}]},
                    "valueQuantity": {"value": 150, "unit": "mmHg"},
                    "effectiveDateTime": datetime.now(UTC).isoformat(),
                }
            },
        ],
    }


def test_fhir_import_normalizes_without_promoting_to_timeline(records_root):
    result = import_bundle("P001", _bundle())
    assert result.status == "pending_review"
    assert result.normalized_observations[0].dimension == "sbp"
    assert result.normalized_observations[0].value == 150
    assert result.import_id == import_bundle("P001", _bundle()).import_id
    assert len(list_imports("P001")) == 1
    assert not [p for p in (records_root / "P001" / "timeline").glob("*obs-bp*")]


def test_fhir_identity_mismatch_is_visible_and_exportable(records_root):
    result = import_bundle("P002", _bundle(patient_ref="someone-else", bundle_id="b-2"))
    assert result.status == "identity_unresolved"
    assert "obs-bp" in result.unresolved_resources
    exported = export_bundle("P002", result.import_id)
    assert exported["resourceType"] == "Bundle"
    assert exported["type"] == "collection"


def test_fhir_rejects_non_bundle():
    with pytest.raises(ValueError, match="Bundle"):
        import_bundle("P001", {"resourceType": "Observation"})
