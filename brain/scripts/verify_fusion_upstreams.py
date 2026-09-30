"""Fail-closed gate for integrated stories and the actual pinned upstream oracles."""
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
REQUIRED_CASES = {
    "test_voice_to_real_components_to_durable_native_replay",
    "test_book_native_story_keeps_context_ephemeral_and_rejects_expiry",
    "test_oracle_is_exact_pinned_upstream_release",
    "test_tokenizer_and_scores_match_deterministic_randomized_corpus",
    "test_pinned_source_and_license_identity",
    "test_reverse_scan_matches_actual_airi_on_randomized_turn_reaction_groups",
    "test_actual_markdown_filter_matches_pinned_source_blob",
    "test_production_factory_real_queue_flushes_clean_act_speech",
}


def required_versions():
    extras = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["optional-dependencies"]
    result = {}
    for extra in ("realtime", "lexical-test"):
        for requirement in extras[extra]:
            name, separator, version = requirement.partition("==")
            if not separator or not name or not version:
                raise ValueError("fusion oracle dependencies must be exact pins")
            result[name] = version
    return result


def inspect_report(path):
    cases = ET.parse(path).getroot().findall(".//testcase")
    failures = sum(case.find("failure") is not None for case in cases)
    errors = sum(case.find("error") is not None for case in cases)
    skipped = sum(case.find("skipped") is not None for case in cases)
    missing = sorted(REQUIRED_CASES - {case.get("name") for case in cases})
    return {"tests": len(cases), "failed": failures, "errors": errors, "skipped": skipped,
            "missing_required_cases": missing,
            "accepted": bool(cases) and not (failures or errors or skipped or missing)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New evidence directory, never overwritten")
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    expected = required_versions()
    installed = {}
    for name in expected:
        try:
            installed[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            installed[name] = None
    report = {"evidence_kind": "SIMULATED_FUSION_COMPONENT_ACCEPTANCE", "accepted": False,
              "expected_versions": expected, "installed_versions": installed,
              "limits": ["synthetic model inference", "synthetic audio generation", "no device or APK acceptance"]}
    if installed != expected:
        report["status"] = "BLOCKED_DEPENDENCIES"
    else:
        env = os.environ.copy()
        env.update(PYTEST_DISABLE_PLUGIN_AUTOLOAD="1", OTEL_SDK_DISABLED="true", PYTHONPATH=str(ROOT))
        command = [sys.executable, "-m", "pytest", "-p", "pytest_asyncio.plugin", "-q", "--strict-markers",
                   f"--junitxml={out / 'tests.xml'}", "realtime_tests", "lexical_tests", "history_tests"]
        try:
            result = subprocess.run(command, cwd=ROOT, env=env, text=True, capture_output=True, timeout=120)
            (out / "pytest.log").write_text(result.stdout + result.stderr)
            print(result.stdout, end="")
            report["exit_code"] = result.returncode
            report.update(inspect_report(out / "tests.xml"))
            report["accepted"] = report["accepted"] and result.returncode == 0
            report["status"] = "PASS" if report["accepted"] else "FAIL"
        except (subprocess.TimeoutExpired, OSError, ET.ParseError):
            report["status"] = "FAIL_INCOMPLETE_RUN"
    (out / "acceptance.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if report["accepted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
