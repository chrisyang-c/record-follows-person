"""De-identification before anything is sent to an LLM (CLAUDE.md §10).

Records only contain synthetic, code-named data, but the boundary is enforced anyway:
phone numbers, LINE ids, contact names and the patient id are replaced by stable tokens.
The original text stays local in provenance.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from record_schema import Profile

_PHONE = re.compile(r"(?<!\d)(?:\+?886[-\s]?|0)\d{1,2}[-\s]?\d{3,4}[-\s]?\d{3,4}(?!\d)")
_LINE_ID = re.compile(r"\bU[0-9a-f]{32}\b")


@dataclass
class Deidentified:
    text: str
    mapping: dict[str, str] = field(default_factory=dict)

    def reidentify(self, text: str) -> str:
        for token, original in self.mapping.items():
            text = text.replace(token, original)
        return text


def deidentify(text: str, profile: Profile | None = None) -> Deidentified:
    mapping: dict[str, str] = {}
    out = text
    if profile is not None:
        for i, c in enumerate(profile.emergency_contacts):
            token = f"[聯絡人{i + 1}]"
            if c.name and c.name in out:
                out = out.replace(c.name, token)
                mapping[token] = c.name
        if profile.patient_id in out:
            out = out.replace(profile.patient_id, "[住民]")
            mapping["[住民]"] = profile.patient_id
    for m in list(_PHONE.finditer(out)):
        token = f"[電話{len(mapping) + 1}]"
        out = out.replace(m.group(0), token)
        mapping[token] = m.group(0)
    for m in list(_LINE_ID.finditer(out)):
        token = f"[LINE{len(mapping) + 1}]"
        out = out.replace(m.group(0), token)
        mapping[token] = m.group(0)
    return Deidentified(text=out, mapping=mapping)
