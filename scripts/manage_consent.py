"""Local operator: explicitly reissue one patient's grant; never reset clinical records.

Run from apps/api using uv. Default is a read-only preview; --apply requires an interactive
confirmation. This is a trusted local operator tool, not a remotely accessible API.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records-root", type=Path)
    parser.add_argument("--patient", required=True)
    parser.add_argument("--member", required=True)
    parser.add_argument(
        "--scopes", nargs="+", required=True, choices=["who", "timeline", "docs", "talk"]
    )
    parser.add_argument(
        "--purposes",
        nargs="+",
        required=True,
        choices=["self-care", "caregiving", "treatment", "care-management"],
    )
    parser.add_argument("--reason", required=True)
    parser.add_argument("--days", type=int, help="Omit for no expiry; otherwise 1–3650")
    parser.add_argument("--can-manage", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", args.patient):
        parser.error("Invalid patient identifier")
    if not args.reason.strip() or (args.days is not None and not 1 <= args.days <= 3650):
        parser.error("A reason and valid expiry are required")
    if args.records_root:
        os.environ["RECORDS_ROOT"] = str(args.records_root.resolve())
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps/api"))
    from record_schema import CareCircleMember

    from core import security
    from record import care_circle as cc
    from record.store import get_store

    store = get_store()
    identity = cc.whoami(args.member)
    if not identity or not store.exists(args.patient):
        parser.error("Patient and member identity must already exist")
    now = datetime.now(UTC)
    grant = CareCircleMember(
        health_id=store.load_profile(args.patient).health_id,
        member_id=args.member,
        name=identity["name"],
        role=identity["role"],
        scopes=args.scopes,
        allowed_purposes=args.purposes,
        can_manage=args.can_manage,
        valid_from=now,
        valid_to=now + timedelta(days=args.days) if args.days else None,
        granted_by="local-operator",
        purpose=args.reason.strip(),
    )
    print(f"Record store: {store.root.resolve()}")
    print(grant.model_dump_json(indent=2))
    print("Existing grants for this member/patient will be superseded, not erased.")
    if not args.apply:
        print("Preview only. To apply, add --apply in an interactive terminal.")
        return 0
    if not sys.stdin.isatty():
        parser.error("--apply requires interactive confirmation")
    if input(f"Confirm consent for {args.patient}/{args.member}: type yes: ") != "yes":
        print("Cancelled; nothing changed.")
        return 1
    saved = cc.grant(args.patient, grant)
    security.audit(
        args.patient,
        "local-operator",
        "consent.reissued",
        outcome="allowed",
        purpose=args.reason.strip(),
        details={"grant_id": saved.grant_id},
    )
    print("Grant saved. Clinical records were not reset.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
