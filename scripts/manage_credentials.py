"""Provision an existing identity's individual password using an interactive hidden prompt.

From apps/api: uv run python ../../scripts/manage_credentials.py --who nurse_lin
Use --records-root PATH to explicitly target a separate record store. This command does not
create identities, change roles, or seed records. A reset revokes the account's sessions.
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys
import warnings
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--who", required=True, help="Existing identity ID; never a role name")
    parser.add_argument("--records-root", type=Path, help="Explicit record-store root")
    args = parser.parse_args()
    if args.records_root is not None:
        os.environ["RECORDS_ROOT"] = str(args.records_root.resolve())
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api"))
    from core import security
    from record import care_circle
    from record.store import get_store

    identity = care_circle.whoami(args.who)
    if identity is None:
        parser.error("The identity must already exist in this record store")
    if not sys.stdin.isatty():
        parser.error("Use an interactive terminal; password input from a pipe is not supported")
    print(f"Record store: {get_store().root.resolve()}")
    print(f"Set individual password: {args.who} ({identity['name']})")
    print("Existing sessions for this account will be revoked.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            password = getpass.getpass("New password (12–1024 characters): ")
            confirmation = getpass.getpass("Repeat password: ")
        if password != confirmation:
            print("Passwords did not match; no credential was changed.", file=sys.stderr)
            return 1
        security.set_password(args.who, password)
    except (getpass.GetPassWarning, EOFError, KeyboardInterrupt):
        print(
            "Hidden password entry was unavailable or cancelled; nothing changed.", file=sys.stderr
        )
        return 1
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print("Password saved and previous sessions revoked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
