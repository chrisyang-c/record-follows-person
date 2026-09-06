"""Isolated HTTP + PostgreSQL restart check; only a disposable rfp_smoke* DB is allowed.

Example: uv run python ../../scripts/smoke_runtime.py --web
Set RFP_SMOKE_DATABASE_URL to a dedicated localhost PostgreSQL database first.
The web option requires a built apps/web and free localhost ports 8000 and 3000.
All records are synthetic and temporary; model and notification calls are disabled.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import quote, urlparse

import httpx

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "apps/api"


def wait_http(url, process, seconds=60):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Service exited before {url} became ready")
        try:
            response = httpx.get(url, timeout=2)
            if response.status_code == 200:
                return response
        except httpx.TransportError:
            pass
        time.sleep(0.25)
    raise TimeoutError(f"Service did not become ready: {url}")


def stop(process):
    if process is not None and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--web", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    database = os.environ.get("RFP_SMOKE_DATABASE_URL", "")
    parsed = urlparse(database)
    if parsed.hostname not in {"localhost", "127.0.0.1"} or not parsed.path.startswith(
        "/rfp_smoke"
    ):
        raise ValueError("Set RFP_SMOKE_DATABASE_URL to a disposable localhost rfp_smoke* DB")
    for port in [8000, 3000] if args.web else [8000]:
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", port))
    api_process = web_process = None
    report = {"provider": "mock", "external_notifications": False, "postgres": False}
    with tempfile.TemporaryDirectory(prefix="rfp-runtime-") as temporary:
        scratch = Path(temporary)
        records = scratch / "records"
        env = {
            **os.environ,
            "MODEL_PROVIDER": "mock",
            "DATABASE_URL": database,
            "RECORDS_ROOT": str(records),
            "LINE_CHANNEL_TOKEN": "",
            "LINE_FAMILY_TO": "",
            "OPENAI_API_KEY": "",
            "ANTHROPIC_API_KEY": "",
            "NURSE_REVIEW_TIMEOUT_S": "3600",
            "WORKER_SCAN_INTERVAL_S": "3600",
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
        }
        # This process is itself a disposable verifier; never load the user's .env values.
        os.environ.update(env)
        sys.path[:0] = [str(API), str(ROOT / "data/seed")]
        import seed

        seed.seed(records, quiet=True, end_date=datetime.now(UTC).date() - timedelta(days=1))
        subprocess.run([sys.executable, "-m", "graphs.migrate"], cwd=API, env=env, check=True)
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        with (
            (scratch / "api.log").open("w", encoding="utf-8") as api_log,
            (scratch / "web.log").open("w", encoding="utf-8") as web_log,
        ):

            def start_api():
                process = subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "uvicorn",
                        "main:app",
                        "--host",
                        "127.0.0.1",
                        "--port",
                        "8000",
                    ],
                    cwd=API,
                    env=env,
                    stdout=api_log,
                    stderr=subprocess.STDOUT,
                    creationflags=creationflags,
                )
                try:
                    health = wait_http("http://127.0.0.1:8000/health", process).json()
                    if (
                        health["checkpointer"] != "postgres"
                        or health["effective_provider"] != "mock"
                    ):
                        raise AssertionError("Smoke requires actual PostgreSQL and mock provider")
                except Exception:
                    stop(process)
                    raise
                return process

            try:
                api_process = start_api()
                report["postgres"] = True
                with httpx.Client(base_url="http://127.0.0.1:8000", timeout=60) as client:
                    started = client.post(
                        "/shift/start",
                        json={
                            "patient_id": "P003",
                            "text": "吃一半，右膝痛，晚上起來兩次",
                            "language": "zh-TW",
                            "caregiver_id": "cg_xiaofang",
                            "shift": "day",
                        },
                    )
                    started.raise_for_status()
                    snap = started.json()
                    assert snap["interrupt"]["type"] == "nurse_10s_confirm"
                    thread = quote(snap["thread_id"], safe="")
                    stop(api_process)
                    api_process = start_api()
                    restored = client.get(f"/threads/{thread}/state")
                    restored.raise_for_status()
                    assert restored.json()["interrupt"]["type"] == "nurse_10s_confirm"
                    report["pending_interrupt_survives_restart"] = True
                    approved = client.post(
                        f"/threads/{thread}/resume",
                        json={
                            "action": "edit",
                            "nurse_id": "nurse_lin",
                            "edited_a": "進食減半、疼痛新出現",
                        },
                    )
                    approved.raise_for_status()
                    done = approved.json()
                    assert done["status"] == "done"
                    written = done["values"]["written_id"]
                    stop(api_process)
                    api_process = start_api()
                    restored = client.get(f"/threads/{thread}/state")
                    restored.raise_for_status()
                    assert restored.json()["status"] == "done"
                    record = client.get("/records/P003")
                    record.raise_for_status()
                    row = next(
                        entry for entry in record.json()["timeline"] if entry["id"] == written
                    )
                    assert row["status"] == "approved" and row["confirmed_by"] == "nurse_lin"
                    assert row["provenance"]
                    report["approved_record_survives_restart"] = True
                if args.web:
                    node = shutil.which("node")
                    if not node:
                        raise RuntimeError("Node is required for --web")
                    web_process = subprocess.Popen(
                        [
                            node,
                            str(ROOT / "apps/web/node_modules/next/dist/bin/next"),
                            "start",
                            "--hostname",
                            "127.0.0.1",
                            "--port",
                            "3000",
                        ],
                        cwd=ROOT / "apps/web",
                        env=env,
                        stdout=web_log,
                        stderr=subprocess.STDOUT,
                        creationflags=creationflags,
                    )
                    wait_http("http://127.0.0.1:3000/login", web_process)
                    subprocess.run(
                        [node, str(ROOT / "scripts/smoke_browser.mjs")], env=env, check=True
                    )
                    report["browser_reads_twin_from_api"] = True
            except Exception:
                api_log.flush()
                web_log.flush()
                for name in ("api.log", "web.log"):
                    print((scratch / name).read_text(encoding="utf-8")[-5000:], file=sys.stderr)
                raise
            finally:
                stop(web_process)
                stop(api_process)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
