"""Create, verify, or restore a manifest-verified records backup.

Examples (PowerShell):
  uv run python scripts/backup_records.py create --root records --output backup.zip
  uv run python scripts/backup_records.py verify --archive backup.zip
  uv run python scripts/backup_records.py restore --archive backup.zip --target records-copy --force
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

API = Path(__file__).resolve().parents[1] / "apps" / "api"
sys.path.insert(0, str(API))

from record.backup import create_backup, restore_backup, verify_backup  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create")
    create.add_argument("--root", type=Path, required=True)
    create.add_argument("--output", type=Path, required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("--archive", type=Path, required=True)
    restore = sub.add_parser("restore")
    restore.add_argument("--archive", type=Path, required=True)
    restore.add_argument("--target", type=Path, required=True)
    restore.add_argument(
        "--force", action="store_true", help="allow restoring into a non-empty target"
    )
    args = parser.parse_args(argv)
    if args.command == "create":
        print(create_backup(args.root, args.output))
    elif args.command == "verify":
        print(verify_backup(args.archive))
    else:
        print(restore_backup(args.archive, args.target, overwrite=args.force))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
