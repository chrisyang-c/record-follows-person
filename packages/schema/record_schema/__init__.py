"""PersonRecord schema — the single source of truth for both Python and TypeScript.

FHIR-lite naming: Patient / Condition / AllergyIntolerance / Observation /
MedicationStatement / Encounter / ServiceRequest(Order) / Provenance / DocumentReference.
Run ``make codegen`` after any change here (regenerates packages/schema/ts/index.ts).
"""

from record_schema.models import *  # noqa: F401,F403
from record_schema.models import __all__  # noqa: F401
