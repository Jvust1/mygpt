"""Publish only closed-schema numeric/hash recovery evidence, never source or logs.

Run after all recovery gates succeed. Reads local evidence and source archives;
no network, extraction or private-content projection. Failures print fixed codes.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET
import zipfile

from source_bundle import verify

STRICT_KEYS = {"evidence_kind", "python", "expected_versions", "installed_versions", "accepted",
               "status", "exit_code", "tests", "failed", "errors", "skipped", "missing_required_cases"}
REQUIRED_CASES = {"test_pydantic_ai_test_model_only", "test_mcp_in_memory_read_only",
                  "test_default_local_engine_runs_real_testmodel_without_provider",
                  "test_default_testmodel_handles_imported_context"}
JAVA_SMOKES = {"SpinePackageLayoutSmoke", "SkinCapabilityCatalogSmoke", "VoicePcmSmoke",
               "LocalLlmEngineSmoke", "FloatDragPolicySmoke", "OnDeviceCompanionBrainSmoke",
               "AiriActGoldenSmoke", "GgufModelProbeSmoke", "GgufModelInstallerSmoke",
               "BookContextMailboxSmoke", "StudySupervisorRuntimeSmoke", "CompanionPromptBudgetSmoke",
               "LlmBenchmarkCandidateCatalogSmoke", "BookClientSdkSmoke", "ModelFingerprintManifestSmoke",
               "SherpaModelIdentitySmoke", "AudioFloatResamplerSmoke", "LexicalMemoryScorerSmoke",
               "AiriHistoryBudgetSmoke", "BookUnicodeBudgetSmoke", "VoiceOutputCompletionSmoke"}
LAUNCHER_CHECKS = {prefix + ":" + check for prefix in ("intake_off", "intake_on")
                   for check in ("printed_loopback_ready","selection_page_loads","explicit_intake_flag_preserved",
                                 "no_implicit_inference_or_book","ctrl_c_exits","listener_closed")}
SELECTION_CHECKS = {"default_off","selection_page_and_httponly_cookie","frame_embedding_denied",
                    "connection_closed_after_response","token_not_in_html","missing_cookie","missing_client",
                    "missing_origin","cross_site","duplicate_Content-Length","duplicate_Host","duplicate_Cookie",
                    "duplicate_Origin","duplicate_Content-Type","static_host_pinned","missing_length",
                    "reject_duplicate_json","reject_nonfinite","reject_surrogate","reject_utf8","reject_depth",
                    "reject_metadata","size_limit","original_api_limit_unchanged","one_record_received",
                    "import_does_not_explain","actual_brain_path","import_request_deduplication",
                    "no_paid_model_or_live_book","reply_does_not_claim_real_inference","revoke_clears_imports","revoke_blocks_input"}
OUTPUT_KEYS = {"schema", "status", "scope", "source_commit", "inner_archive_sha256", "inner_archive_bytes",
               "source_files", "deterministic", "recovered_source_verified", "strict_accepted",
               "strict_tests", "root_python_tests", "javascript_tests", "java_entrypoints",
               "launcher_checks", "selection_http_checks", "failed", "errors", "skipped",
               "live_model_calls", "external_requests", "contains_source_archive", "contains_raw_logs"}


def require(condition, code):
    if not condition:
        raise ValueError(code)


def read_json(path):
    value = json.loads(path.read_text(encoding="utf-8"))
    require(type(value) is dict, "invalid_evidence_object")
    return value


def positive(value):
    return type(value) is int and 0 < value < 1000000


def zero(value):
    return type(value) is int and value == 0


def validate_public_summary(summary):
    require(type(summary) is dict and set(summary) == OUTPUT_KEYS, "public_field_set")
    constants = {"schema":"mygpt.public-source-recovery.v1", "status":"PASS",
                 "scope":"HASH_AND_TEST_METADATA_ONLY_NOT_SOURCE_DELIVERY",
                 "deterministic":True, "recovered_source_verified":True, "strict_accepted":True,
                 "contains_source_archive":False, "contains_raw_logs":False}
    require(all(type(summary[k]) is type(v) and summary[k] == v for k, v in constants.items()), "public_scope")
    for key, length in (("source_commit",40), ("inner_archive_sha256",64)):
        require(type(summary[key]) is str and bool(re.fullmatch(r"[0-9a-f]{"+str(length)+r"}",summary[key])), "public_identity")
    require(type(summary["inner_archive_bytes"]) is int and 0 < summary["inner_archive_bytes"] <= 34*1024*1024,
            "public_archive_size")
    for key in ("source_files", "strict_tests", "root_python_tests", "javascript_tests", "java_entrypoints",
                "launcher_checks", "selection_http_checks"):
        require(positive(summary[key]), "public_count")
    for key in ("failed", "errors", "skipped", "live_model_calls", "external_requests"):
        require(zero(summary[key]), "public_not_clean")
    return summary


def build_summary(evidence, repeat_archive, recovered, source_commit):
    evidence, recovered, repeat_archive = Path(evidence), Path(recovered), Path(repeat_archive)
    require(type(source_commit) is str and bool(re.fullmatch(r"[0-9a-f]{40}",source_commit)), "source_commit_format")
    require((evidence / "source-commit.txt").read_text().strip() == source_commit, "source_commit_mismatch")
    archive = evidence / "mygpt-source.zip"
    build, repeat = read_json(evidence/"build.json"), read_json(evidence/"repeat.json")
    for report, path in ((build, archive), (repeat, repeat_archive)):
        require(type(report.get("sha256")) is str and bool(re.fullmatch(r"[0-9a-f]{64}",report["sha256"])), "archive_hash_format")
        checked = verify(path, report["sha256"])
        expected = {**checked, "sha256":report["sha256"], "archive_bytes":path.stat().st_size}
        require(report == expected, "build_report_identity_or_extra_fields")
        require(checked["source_commit"] == source_commit, "archive_source_mismatch")
    require(build == repeat and archive.read_bytes() == repeat_archive.read_bytes(), "nondeterministic_source")
    with zipfile.ZipFile(archive) as bundle:
        manifest_bytes = bundle.read("SOURCE_MANIFEST.json")
        require((recovered/"SOURCE_MANIFEST.json").read_bytes() == manifest_bytes, "recovery_manifest_mismatch")
        manifest = json.loads(manifest_bytes)
        for row in manifest["files"]:
            path = recovered / row["path"]
            require(not path.is_symlink() and path.is_file() and path.stat().st_size == row["bytes"] and
                    hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"], "recovered_source_mismatch")
    doctor = read_json(evidence/"doctor.json")
    require(set(doctor) == {"schema","status","python","missing_files","dependencies","issue","opens_listener",
                            "installs_packages","live_model_enabled","note","instructions"}, "doctor_fields")
    require(doctor["schema"] == "mygpt.launcher-doctor.v1" and doctor["status"] == "READY" and
            doctor["missing_files"] == [] and doctor["issue"] is None and
            all(doctor[k] is False for k in ("opens_listener","installs_packages","live_model_enabled")), "doctor_not_ready")
    require(type(doctor["dependencies"]) is list and len(doctor["dependencies"]) > 0 and
            all(type(d) is dict and set(d) == {"package","expected","installed","matches"} and
                d["matches"] is True and d["installed"] == d["expected"] for d in doctor["dependencies"]), "doctor_dependencies")
    strict = read_json(evidence/"recovered-brain/acceptance.json")
    require(set(strict) == STRICT_KEYS, "strict_fields")
    require(strict["status"] == "PASS" and strict["accepted"] is True and
            strict["evidence_kind"] == "SIMULATED_SDK_ACCEPTANCE" and positive(strict["tests"]) and
            all(zero(strict[k]) for k in ("exit_code","failed","errors","skipped")) and
            strict["missing_required_cases"] == [] and strict["installed_versions"] == strict["expected_versions"], "strict_not_accepted")
    require(set(strict["expected_versions"]) == {"pydantic","httpx","pydantic-ai-slim","mcp","pytest","pytest-asyncio"} and
            all(type(v) is str and re.fullmatch(r"[0-9]+(?:\.[0-9]+){1,3}",v) for v in strict["expected_versions"].values()),
            "strict_package_versions")
    cases = ET.parse(evidence/"recovered-brain/tests.xml").getroot().findall(".//testcase")
    require(len(cases) == strict["tests"] and REQUIRED_CASES <= {c.get("name") for c in cases} and
            all(c.find(k) is None for c in cases for k in ("failure","error","skipped")), "strict_junit_mismatch")
    root_log = (evidence/"recovered-root.txt").read_text()
    root_counts = re.findall(r"(?m)^Ran ([1-9][0-9]*) tests? in [0-9.]+s$", root_log)
    require(len(root_counts) == 1 and re.search(r"\nOK\s*\Z",root_log) is not None, "root_tests_not_clean")
    node_log = (evidence/"recovered-node.txt").read_text()
    def node_count(label):
        values = re.findall(r"(?m)^[#ℹ] "+label+r" ([0-9]+)\s*$", node_log)
        require(len(values) == 1, "javascript_summary_missing")
        return int(values[0])
    js_tests = node_count("tests")
    require(js_tests > 0 and node_count("pass") == js_tests and
            all(node_count(k) == 0 for k in ("fail","cancelled","skipped","todo")), "javascript_not_clean")
    java_log = (evidence/"recovered-java.txt").read_text()
    smokes = re.findall(r"(?m)^([A-Za-z0-9]+Smoke) PASS(?:[:\n]|$)",java_log)
    require(len(smokes) == len(JAVA_SMOKES) and set(smokes) == JAVA_SMOKES and
            java_log.splitlines().count("PASS: Android companion boundary smoke") == 1, "java_smokes_missing")
    launcher = read_json(evidence/"launcher-http.json")
    selection = read_json(evidence/"recovered-http.json")
    require(set(launcher) == {"status","scope","checks","checks_passed","paid_model_calls","source_text_received",
                              "windows_device_acceptance"}, "launcher_fields")
    require(set(selection) == {"result","scope","checks","checks_passed","paid_model_calls","external_requests"}, "selection_fields")
    require(launcher["status"] == selection["result"] == "PASS" and
            launcher["source_text_received"] is False and launcher["windows_device_acceptance"] is False and
            zero(launcher["paid_model_calls"]) and zero(selection["paid_model_calls"]) and zero(selection["external_requests"]), "http_not_clean")
    for report, expected_checks in ((launcher,LAUNCHER_CHECKS),(selection,SELECTION_CHECKS)):
        count = len(expected_checks)
        require(type(report["checks"]) is list and report["checks_passed"] == count and
                len(report["checks"]) == count and set(report["checks"]) == expected_checks, "http_checks_missing")
    summary = {"schema":"mygpt.public-source-recovery.v1", "status":"PASS",
               "scope":"HASH_AND_TEST_METADATA_ONLY_NOT_SOURCE_DELIVERY", "source_commit":source_commit,
               "inner_archive_sha256":build["sha256"], "inner_archive_bytes":build["archive_bytes"],
               "source_files":build["files_verified"], "deterministic":True, "recovered_source_verified":True,
               "strict_accepted":True, "strict_tests":strict["tests"], "root_python_tests":int(root_counts[0]),
               "javascript_tests":js_tests, "java_entrypoints":len(JAVA_SMOKES)+1,
               "launcher_checks":12, "selection_http_checks":32,
               "failed":0, "errors":0, "skipped":0, "live_model_calls":0, "external_requests":0,
               "contains_source_archive":False, "contains_raw_logs":False}
    return validate_public_summary(summary)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir", required=True, type=Path)
    parser.add_argument("--repeat-archive", required=True, type=Path)
    parser.add_argument("--recovered-root", required=True, type=Path)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        summary = build_summary(args.evidence_dir,args.repeat_archive,args.recovered_root,args.source_commit)
        with args.output.open("x",encoding="utf-8") as stream:
            stream.write(json.dumps(summary,sort_keys=True,indent=2)+"\n")
    except (OSError,ValueError,TypeError,KeyError,zipfile.BadZipFile,ET.ParseError):
        # Never echo raw JSON fields, paths, exception messages, logs or credentials.
        print('{"status":"FAIL","error":"PUBLIC_RECOVERY_EVIDENCE_REJECTED"}')
        return 1
    print('{"status":"PASS","scope":"PUBLIC_HASH_METADATA_ONLY"}')
    return 0


if __name__ == "__main__":
    sys.exit(main())
