"""Exercise the Windows entry point with real failing tool subprocesses."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PWSH = shutil.which("pwsh") or shutil.which("powershell")


@pytest.fixture
def harness(tmp_path):
    if os.name != "nt" or not PWSH:
        pytest.skip("Windows PowerShell entry-point regression")
    for folder in ("scripts", "apps/api", "apps/web"):
        (tmp_path / folder).mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / "scripts/dev.ps1", tmp_path / "scripts/dev.ps1")
    stub = tmp_path / "tool.py"
    stub.write_text(
        "import json, os, sys\n"
        "tool, args = sys.argv[1], sys.argv[2:]\n"
        "with open(os.environ['RFP_TOOL_LOG'], 'a', encoding='utf-8') as log:\n"
        " log.write(json.dumps([tool, *args]) + '\\n')\n"
        "fail = os.environ.get('RFP_TOOL_FAIL', '')\n"
        "key = tool + ':' + ' '.join(args)\n"
        "sys.exit(23 if fail and key.startswith(fail) else 0)\n",
        encoding="utf-8",
    )
    for tool in ("uv", "pnpm"):
        (tmp_path / f"{tool}.cmd").write_text(
            f'@"{sys.executable}" "{stub}" {tool} %*\r\n', encoding="utf-8"
        )
    log = tmp_path / "calls.jsonl"

    def run(command="check", *, fail="", missing=False, api_only=False):
        runner = tmp_path / "runner.ps1"
        # Dot-source only the help entry point, then replace tool discovery.
        runner.write_text(
            ". (Join-Path $PSScriptRoot 'scripts/dev.ps1') help\n"
            "function Get-Uv { Join-Path $PSScriptRoot 'uv.cmd' }\n"
            "function Get-Pnpm {\n"
            " if ($env:RFP_PNPM_MISSING -eq '1') { throw 'pnpm missing' }\n"
            " Join-Path $PSScriptRoot 'pnpm.cmd'\n}\n"
            f"$ApiOnly = ${str(api_only).lower()}\n"
            f"Cmd-{command.title()}\n",
            encoding="utf-8-sig",
        )
        env = {
            **os.environ,
            "RFP_TOOL_LOG": str(log),
            "RFP_TOOL_FAIL": fail,
            "RFP_PNPM_MISSING": "1" if missing else "0",
        }
        result = subprocess.run(
            [PWSH, "-NoProfile", "-NonInteractive", "-File", str(runner)],
            capture_output=True,
            env=env,
            timeout=45,
        )
        calls = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
        return result, calls

    return run


@pytest.mark.parametrize(
    ("command", "failure"),
    [
        ("setup", "pnpm:install"),
        ("check", "pnpm:lint"),
        ("check", "pnpm:test"),
        ("check", "pnpm:build"),
        ("check", "pnpm:typecheck"),
        ("check", "uv:run --frozen ruff format --check"),
        ("check", "uv:run --frozen pytest -q"),
    ],
)
def test_executed_failure_is_not_swallowed(harness, command, failure):
    result, calls = harness(command, fail=failure)
    assert result.returncode != 0, result.stdout
    assert calls


def test_full_check_requires_frontend_tool_before_work(harness):
    result, calls = harness(missing=True)
    assert result.returncode != 0
    assert calls == []


def test_api_only_is_explicit_and_does_not_run_web(harness):
    result, calls = harness(missing=True, api_only=True)
    assert result.returncode == 0, result.stderr
    assert b"API-only" in result.stdout
    assert all(call[0] != "pnpm" for call in calls)


def test_full_check_covers_format_build_types_and_readonly_codegen(harness):
    result, calls = harness()
    assert result.returncode == 0, result.stderr
    assert ["uv", "run", "--frozen", "ruff", "format", "--check", "."] in calls
    assert calls.index(["pnpm", "build"]) < calls.index(["pnpm", "typecheck"])
    assert any("codegen.py" in " ".join(c) and "--check" in c for c in calls)
    assert any("check_eval.py" in " ".join(c) for c in calls)


def test_setup_uses_lockfiles(harness):
    result, calls = harness("setup")
    assert result.returncode == 0, result.stderr
    assert ["uv", "sync", "--frozen"] in calls
    assert ["pnpm", "install", "--frozen-lockfile"] in calls


def test_codegen_check_preserves_uncommitted_content(tmp_path):
    generator = ROOT / "packages/schema/codegen.py"
    target = tmp_path / "index.ts"
    args = [sys.executable, str(generator), "--output", str(target)]
    subprocess.run(args, check=True, capture_output=True)
    generated = target.read_bytes()
    # No Git repository or clean index is required for an up-to-date file.
    good = subprocess.run([*args, "--check"], capture_output=True)
    assert good.returncode == 0
    assert target.read_bytes() == generated
    dirty = generated + b"\n// unfinished user change\n"
    target.write_bytes(dirty)
    bad = subprocess.run([*args, "--check"], capture_output=True)
    assert bad.returncode == 1
    assert target.read_bytes() == dirty
