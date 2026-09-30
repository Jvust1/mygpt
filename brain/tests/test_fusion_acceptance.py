import importlib.util
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

SPEC = importlib.util.spec_from_file_location("fusion_gate", Path(__file__).resolve().parents[1] / "scripts/verify_fusion_upstreams.py")
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)


def report_file(tmp_path, *, omit=None, result=None):
    suite = ET.Element("testsuite")
    for name in sorted(gate.REQUIRED_CASES - set(omit or [])):
        case = ET.SubElement(suite, "testcase", name=name)
        if result is not None:
            ET.SubElement(case, result)
    target = tmp_path / "tests.xml"
    ET.ElementTree(suite).write(target)
    return target


def test_fusion_gate_accepts_complete_required_component_story_set(tmp_path):
    report = gate.inspect_report(report_file(tmp_path))
    assert report["accepted"] and report["skipped"] == 0


@pytest.mark.parametrize("result", ["failure", "error", "skipped"])
def test_fusion_gate_rejects_unsuccessful_or_skipped_component_tests(tmp_path, result):
    assert not gate.inspect_report(report_file(tmp_path, result=result))["accepted"]


def test_fusion_gate_rejects_missing_story_even_when_others_pass(tmp_path):
    name = "test_voice_to_real_components_to_durable_native_replay"
    report = gate.inspect_report(report_file(tmp_path, omit=[name]))
    assert not report["accepted"] and report["missing_required_cases"] == [name]


def test_fusion_gate_rejects_empty_collection(tmp_path):
    assert not gate.inspect_report(report_file(tmp_path, omit=gate.REQUIRED_CASES))["accepted"]


def test_fusion_gate_checks_existing_exact_upstream_pins_without_new_dependency():
    assert gate.required_versions() == {"pipecat-ai": "1.12.0", "scikit-learn": "1.9.1"}


def test_java_runner_cannot_silently_downgrade_hosted_api_acceptance():
    import os
    import subprocess
    root = Path(__file__).resolve().parents[2]
    env = {**os.environ, "GITHUB_ACTIONS": "true", "MYGPT_JAVA_SOURCE_TARGET_ONLY": "1", "GSON_JAR": "must-not-be-opened"}
    result = subprocess.run(["bash", str(root / "android_spike/tools/run_boundary_smoke.sh")],
                            env=env, text=True, capture_output=True, timeout=5)
    assert result.returncode == 2
    assert "fallback is prohibited" in result.stderr
    assert "Gson artifact/license PASS" not in result.stdout


@pytest.mark.parametrize("name", [
    "test_tokenizer_and_scores_match_deterministic_randomized_corpus",
    "test_reverse_scan_matches_actual_airi_on_randomized_turn_reaction_groups",
])
def test_fusion_gate_rejects_missing_behavior_oracle_even_with_identity_check(tmp_path, name):
    report = gate.inspect_report(report_file(tmp_path, omit=[name]))
    assert not report["accepted"] and report["missing_required_cases"] == [name]
