"""Fail-closed deployment checks for the local-account prototype.

Usage: ``python scripts/preflight_security.py --production``.  The normal mock development
workflow intentionally does not run this command; CI still runs the regular deterministic tests.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

API = Path(__file__).resolve().parents[1] / "apps" / "api"
if str(API) not in sys.path:
    sys.path.insert(0, str(API))

from core.settings import Settings, get_settings  # noqa: E402


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str


def checks(settings: Settings | None = None, *, production: bool = False) -> list[Check]:
    s = settings or get_settings()
    if not production:
        return [Check("mode", True, f"environment={s.ENVIRONMENT}; development preflight skipped")]
    origin_values = [value.strip() for value in s.AUTH_ALLOWED_ORIGINS.split(",") if value.strip()]
    return [
        Check("environment", s.ENVIRONMENT == "production", f"ENVIRONMENT={s.ENVIRONMENT}"),
        Check(
            "model",
            s.MODEL_PROVIDER != "mock" and bool(s.provider_key),
            "real provider key is configured",
        ),
        Check("database", bool(s.DATABASE_URL), "DATABASE_URL is configured"),
        Check(
            "checkpoint_fallback",
            not s.ALLOW_MEMORY_CHECKPOINT_FALLBACK,
            "memory fallback is disabled",
        ),
        Check("secure_cookie", s.AUTH_COOKIE_SECURE, "AUTH_COOKIE_SECURE=true"),
        Check(
            "origins",
            bool(origin_values)
            and "*" not in origin_values
            and all(v.startswith("https://") for v in origin_values),
            "allowed origins are explicit HTTPS origins",
        ),
        Check("simulation", not s.ENABLE_DEMO_SIMULATION, "demo simulation is disabled"),
    ]


def run(*, production: bool = False, as_json: bool = False) -> int:
    result = checks(production=production)
    if as_json:
        print(json.dumps([asdict(item) for item in result], ensure_ascii=False))
    else:
        for item in result:
            print(f"{'PASS' if item.ok else 'FAIL':4} {item.name}: {item.detail}")
    return 0 if all(item.ok for item in result) else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--production", action="store_true")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    return run(production=args.production, as_json=args.as_json)


if __name__ == "__main__":
    raise SystemExit(main())
