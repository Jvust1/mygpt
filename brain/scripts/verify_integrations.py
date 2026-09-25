"""Strict acceptance runner. Missing SDKs, skipped cases and timeouts fail closed."""
from __future__ import annotations

import argparse
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import tomllib
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_CASES = {"test_pydantic_ai_test_model_only", "test_mcp_in_memory_read_only"}


def inspect_junit(path: Path) -> dict:
    cases = ET.parse(path).getroot().findall(".//testcase")
    failures = sum(case.find("failure") is not None for case in cases)
    errors = sum(case.find("error") is not None for case in cases)
    skipped = sum(case.find("skipped") is not None for case in cases)
    names = {case.get("name") for case in cases}
    missing = sorted(REQUIRED_CASES - names)
    return {"tests": len(cases), "failed": failures, "errors": errors, "skipped": skipped,
            "missing_required_cases": missing,
            "accepted": bool(cases) and not (failures or errors or skipped or missing)}


def required_versions() -> dict[str, str]:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    requirements = (project["dependencies"] + project["optional-dependencies"]["integrations"]
                    + project["optional-dependencies"]["test"])
    result = {}
    for requirement in requirements:
        name, sep, version = requirement.partition("==")
        if not sep or not name or not version:
            raise ValueError("acceptance requires exact top-level version pins")
        result[name] = version
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path,
                        help="New evidence directory; existing results are never overwritten")
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    wanted = required_versions()
    actual = {}
    for name in wanted:
        try:
            actual[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            actual[name] = None
    report = {"evidence_kind": "SIMULATED_SDK_ACCEPTANCE", "python": sys.version,
              "expected_versions": wanted, "installed_versions": actual,
              "accepted": False, "status": "BLOCKED_DEPENDENCIES"}
    mismatched = [name for name in wanted if actual[name] != wanted[name]]
    if mismatched:
        report["missing_or_mismatched"] = mismatched
        (out / "acceptance.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
        return 2
    env = os.environ.copy()
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    env["MYGPT_STRICT_SDK_TESTS"] = "1"
    env["OTEL_SDK_DISABLED"] = "true"
    env["PYTHONPATH"] = str(ROOT)
    command = [sys.executable, "-m", "pytest", "-p", "pytest_asyncio.plugin", "-q",
               "--strict-markers", f"--junitxml={out / 'tests.xml'}"]
    try:
        run = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True,
                             timeout=120, check=False)
        (out / "pytest.txt").write_text(run.stdout + run.stderr)
        print(run.stdout + run.stderr)
        report["exit_code"] = run.returncode
        if (out / "tests.xml").exists():
            report.update(inspect_junit(out / "tests.xml"))
        report["accepted"] = report["accepted"] and run.returncode == 0
        report["status"] = "PASS" if report["accepted"] else "FAIL"
    except subprocess.TimeoutExpired:
        report["status"] = "TIMEOUT"
    (out / "acceptance.json").write_text(json.dumps(report, indent=2) + "\n")
    return 0 if report["accepted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
