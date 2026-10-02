"""Execute fail-closed CI gates and inspect synthetic APKs without Android SDK."""
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
import warnings
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ANDROID = ROOT / ".github/workflows/android-spike.yml"
FUSION = ROOT / ".github/workflows/companion-fusion-acceptance.yml"


def job(path, name):
    text = path.read_text()
    match = re.search(r"^  " + re.escape(name) + r":\n(.*?)(?=^  [\w-]+:|\Z)",
                      text, re.MULTILINE | re.DOTALL)
    if match is None:
        raise AssertionError(f"missing required workflow job: {name}")
    return match.group(1)


class RequiredJobGateTests(unittest.TestCase):
    def run_gate(self, value, required=("java8-boundary", "android-debug-host")):
        env = dict(os.environ, REQUIRED_JOB_RESULTS=value)
        return subprocess.run([sys.executable, str(ROOT / "scripts/assert_required_jobs.py"),
                               *required], env=env, capture_output=True, text=True, timeout=5)

    def test_success_requires_all_jobs(self):
        report = {name: {"result": "success", "outputs": {}} for name in
                  ("java8-boundary", "android-debug-host")}
        self.assertEqual(self.run_gate(json.dumps(report)).returncode, 0)

    def test_each_unsuccessful_status_fails_for_each_job(self):
        for name in ("java8-boundary", "android-debug-host"):
            for status in ("skipped", "failure", "cancelled", "", None, True, "SUCCESS"):
                report = {key: {"result": "success"} for key in
                          ("java8-boundary", "android-debug-host")}
                report[name]["result"] = status
                with self.subTest(name=name, status=status):
                    self.assertEqual(self.run_gate(json.dumps(report)).returncode, 1)

    def test_missing_malformed_and_extra_results_fail_without_echoing_data(self):
        for report in ("", "not JSON", "null", "[]", "{}", '{"private":"SENTINEL"}',
                       '{"java8-boundary":{"result":"success"}}',
                       '{"java8-boundary":null,"android-debug-host":{"result":"success"}}'):
            with self.subTest(report=report):
                result = self.run_gate(report)
                self.assertEqual(result.returncode, 1)
                self.assertNotIn("SENTINEL", result.stdout + result.stderr)

    def test_empty_or_duplicate_expected_jobs_fail(self):
        for required in ((), ("same", "same")):
            self.assertEqual(self.run_gate("{}", required).returncode, 1)


class WorkflowWiringTests(unittest.TestCase):
    def test_android_jobs_target_actual_repository(self):
        for name in ("java8-boundary", "android-debug-host"):
            body = job(ANDROID, name)
            self.assertIn("if: github.repository == 'Jvust1/mygpt'", body)
            self.assertNotIn("continue-on-error", body)

    def test_android_gate_always_checks_both_required_jobs(self):
        body = job(ANDROID, "android-required-gate")
        self.assertIn("if: ${{ always() }}", body)
        self.assertIn("needs: [java8-boundary, android-debug-host]", body)
        self.assertIn("REQUIRED_JOB_RESULTS: ${{ toJSON(needs) }}", body)
        self.assertIn("run: python scripts/assert_required_jobs.py java8-boundary android-debug-host", body)
        self.assertNotIn("continue-on-error", body)

    def test_aggregate_always_requires_the_entire_reusable_workflow(self):
        body = job(FUSION, "fusion-required-gate")
        self.assertIn("if: ${{ always() }}", body)
        self.assertIn("needs: [production-components, android-java-boundaries, source-recovery, windows-desktop]", body)
        self.assertIn("REQUIRED_JOB_RESULTS: ${{ toJSON(needs) }}", body)
        self.assertIn("run: python scripts/assert_required_jobs.py production-components android-java-boundaries source-recovery windows-desktop", body)
        self.assertNotIn("continue-on-error", body)
        self.assertIn("uses: ./.github/workflows/android-spike.yml", job(FUSION, "android-java-boundaries"))

    def test_apk_is_built_and_verified_but_only_metadata_is_uploaded(self):
        body = job(ANDROID, "android-debug-host")
        self.assertIn("gradle -p android_spike :app:assembleDebug --no-daemon", body)
        self.assertIn("python android_spike/tools/verify_debug_apk.py", body)
        self.assertIn('--source-commit "$GITHUB_SHA"', body)
        self.assertIn("path: ${{ runner.temp }}/android-build-evidence/apk-evidence.json", body)
        self.assertNotRegex(body, r"path:.*\.apk")
        self.assertIn("if-no-files-found: error", body)
        self.assertIn("ref: ${{ github.sha }}", body)
        self.assertIn("persist-credentials: false", body)

    def test_changes_to_gate_and_candidate_trigger_validation(self):
        self.assertIn("fix/android-required-gate-dot-20261002", FUSION.read_text())
        self.assertIn("'scripts/assert_required_jobs.py'", FUSION.read_text())
        self.assertEqual(ANDROID.read_text().count("'scripts/assert_required_jobs.py'"), 2)


SPEC = importlib.util.spec_from_file_location("verify_debug_apk_test",
                                             ROOT / "android_spike/tools/verify_debug_apk.py")
apk_verifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(apk_verifier)


class ApkEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.apk = self.root / "synthetic.apk"
        self.license = self.root / "notice.txt"
        self.license.write_bytes(b"SYNTHETIC LICENSE NOTICE")
        self.members = {"classes.dex": b"dex\n035\0SYNTHETIC",
                        "lib/arm64-v8a/libgdx.so": b"\x7fELFSYNTHETIC",
                        "assets/SPINE_RUNTIME_LICENSE.txt": self.license.read_bytes()}

    def build(self, members=None):
        with zipfile.ZipFile(self.apk, "w") as archive:
            for name, data in (self.members if members is None else members).items():
                archive.writestr(name, data)

    def inspect(self, commit="a" * 40):
        return apk_verifier.inspect_apk(self.apk, commit, self.license)

    def test_valid_metadata_explicitly_excludes_distribution_and_device_acceptance(self):
        self.build()
        report = self.inspect()
        self.assertEqual(report["status"], "BUILD_PAYLOAD_VERIFIED")
        self.assertEqual(report["source_commit"], "a" * 40)
        self.assertEqual([x["path"] for x in report["required_entries"]], list(apk_verifier.REQUIRED))
        self.assertEqual(len(report["apk_sha256"]), 64)
        self.assertFalse(report["apk_published"])
        self.assertFalse(report["device_acceptance"])
        self.assertFalse(report["distribution_license_verified"])
        self.assertNotIn("SYNTHETIC", json.dumps(report))

    def test_each_missing_empty_or_duplicate_required_member_fails(self):
        for name in apk_verifier.REQUIRED:
            for mutation in ("missing", "empty", "duplicate"):
                with self.subTest(name=name, mutation=mutation):
                    members = self.members.copy()
                    if mutation == "missing":
                        del members[name]
                    elif mutation == "empty":
                        members[name] = b""
                    self.build(members)
                    if mutation == "duplicate":
                        with warnings.catch_warnings():
                            warnings.simplefilter("ignore", UserWarning)
                            with zipfile.ZipFile(self.apk, "a") as archive:
                                archive.writestr(name, members[name])
                    with self.assertRaises(ValueError):
                        self.inspect()

    def test_fake_dex_fake_library_and_changed_license_fail(self):
        for name in apk_verifier.REQUIRED:
            with self.subTest(name=name):
                members = self.members.copy()
                members[name] = b"wrong data"
                self.build(members)
                with self.assertRaises(ValueError):
                    self.inspect()

    def test_only_exact_source_commit_is_accepted(self):
        self.build()
        for commit in ("main", "a" * 39, "G" * 40, "a" * 40 + "\n"):
            with self.subTest(commit=commit), self.assertRaises(ValueError):
                self.inspect(commit)


if __name__ == "__main__":
    unittest.main()
