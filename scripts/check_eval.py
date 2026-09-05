"""Run the existing extraction gate with mock inputs and entirely temporary outputs.

    cd apps/api && uv run python ../../scripts/check_eval.py

The regular ``dev.ps1 eval`` command still produces the persistent evaluation report.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

API = Path(__file__).resolve().parents[1] / "apps" / "api"


def main() -> int:
    # Windows consoles may default to cp950; this report contains Unicode math symbols.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    with TemporaryDirectory(prefix="rfp-check-eval-") as directory:
        scratch = Path(directory)
        os.environ.update(
            MODEL_PROVIDER="mock",
            DATABASE_URL="",
            LINE_CHANNEL_TOKEN="",
            RECORDS_ROOT=str(scratch / "records"),
        )
        sys.path.insert(0, str(API))
        # Configure isolation before importing settings, traces, or the evaluation module.
        from eval import run

        shutil.copyfile(API / "eval" / "sentences.json", scratch / "sentences.json")
        run.HERE = scratch
        print("Extraction gate: mock provider; temporary records and reports.")
        return run.main()


if __name__ == "__main__":
    raise SystemExit(main())
