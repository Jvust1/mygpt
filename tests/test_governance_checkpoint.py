"""Offline current/checkpoint drift and honest Git/source-only identity tests."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import validate_governance as governance


class GovernanceCheckpointTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="mygpt-governance-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        paths = [*governance.ENTRY_DOCS, governance.EVIDENCE, "SOURCE_MANIFEST.json",
                 "governance/project_state.json", "governance/artifact_manifest.json",
                 "governance/desktop_delivery_current.json", "governance/pending_sync.json",
                 "docs/HISTORICAL_GOVERNANCE_LEDGER_20261002.md"]
        for name in paths:
            if (ROOT / name).exists():
                (self.root / name).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / name, self.root / name)

    def mutate(self, file, keys, value):
        path = self.root / file
        obj = json.loads(path.read_text())
        current = obj
        for key in keys[:-1]:
            current = current[key]
        current[keys[-1]] = value
        path.write_text(json.dumps(obj))

    def test_current_snapshot_passes_without_claiming_checkout_ci(self):
        result = governance.validate(self.root)
        self.assertEqual(result["status"], "PASS")
        self.assertFalse(result["remote_authenticity_verified"])
        self.assertEqual(result["checkout_identity"]["ci_acceptance"], "NOT_ESTABLISHED_BY_OFFLINE_VALIDATOR")

    def test_negative_identity_and_scope_drift(self):
        state = "governance/project_state.json"
        artifacts = "governance/artifact_manifest.json"
        desktop = "governance/desktop_delivery_current.json"
        cp = ["last_verified_checkpoint"]
        evidence = governance.EVIDENCE
        cases = [
            (state, ["repository"], "Jvust/mygpt"),
            (artifacts, ["project", "repository"], "Jvust2/mygpt"),
            (state, ["active_branch"], "old-branch"),
            (state, ["current_pr", "number"], 15),
            (state, ["current_pr", "merged"], True),
            (state, cp + ["tested_commit"], "0" * 40),
            (state, cp + ["tested_commit"], "765419f"),
            (state, cp + ["run_id"], 1),
            (state, cp + ["run_url"], "https://github.com/Jvust/mygpt/actions/runs/36970504484"),
            (state, cp + ["validation", "root_python"], 99),
            (state, cp + ["validation", "physical_device_acceptance"], True),
            (state, ["ui_candidate", "historical_validation_only"], False),
            (state, ["current_checkout", "ci_acceptance"], "PASS"),
            (state, cp + ["source_bundle", "source_files"], 470),
            (state, cp + ["source_bundle", "inner_bytes"], 1),
            (state, cp + ["source_bundle", "inner_sha256"], "0" * 64),
            (state, cp + ["windows_evidence", "files"], 12),
            (state, cp + ["windows_evidence", "content_scope"], "EXE_INCLUDED"),
            (artifacts, ["artifacts", 0, "workflow_artifact_id"], 11212461882),
            (artifacts, ["artifacts", 0, "related_branch"], "old-branch"),
            (artifacts, ["artifacts", 0, "related_commit"], "1" * 40),
            (artifacts, ["artifacts", 0, "workflow_run_id"], 1),
            (artifacts, ["artifacts", 0, "sha256_scope"], "DOWNLOADED_EVIDENCE_ZIP"),
            (artifacts, ["artifacts", 0, "retention_days"], 90),
            (artifacts, ["artifacts", 0, "url"], "https://github.com/Jvust/mygpt/actions/runs/36970504484/artifacts/11211481324"),
            (evidence, ["public_metadata", "run", "head_sha"], "2" * 40),
            (evidence, ["public_metadata", "run", "head_branch"], "other"),
            (evidence, ["public_metadata", "run", "conclusion"], "failure"),
            (evidence, ["public_metadata", "run", "status"], "in_progress"),
            (evidence, ["public_metadata", "repository", "full_name"], "Jvust/mygpt"),
            (evidence, ["public_metadata", "artifacts", 0, "workflow_run", "id"], 1),
            (evidence, ["public_metadata", "artifacts", 0, "workflow_run", "head_sha"], "3" * 40),
            (evidence, ["public_metadata", "artifacts", 0, "workflow_run", "repository_id"], 1),
            (evidence, ["public_metadata", "artifacts", 0, "digest"], "sha256:" + "0" * 64),
            (evidence, ["source_bundle_manifest", "source_commit"], "4" * 40),
            (desktop, ["release_source_commit"], "5" * 40),
            (desktop, ["current_review", "artifact_id"], 1),
            (desktop, ["actual_user_device_tested"], True),
            (desktop, ["exe_published"], True),
            (desktop, ["verification_result"], {}),
            (state, ["drive"], {"folder_id":"SYNTHETIC_ONLY"}),
            (state, ["historical_governance", "source_commit"], "68ea57e1aec5488b6ff24973f7ef2b781ca29bff"),
            (evidence, ["historical_source_manifest", "source_commit"], "68ea57e1aec5488b6ff24973f7ef2b781ca29bff"),
        ]
        for file, keys, value in cases:
            with self.subTest(file=file, keys=keys):
                path = self.root / file
                saved = path.read_bytes()
                self.mutate(file, keys, value)
                with self.assertRaises((ValueError, KeyError, TypeError)):
                    governance.validate(self.root)
                path.write_bytes(saved)

    def test_displayed_current_summary_cannot_drift_behind_valid_marker(self):
        path = self.root / "README.md"
        text = path.read_text()
        text = text.replace("分支 `fix/dependency-locks-dot-20261002`", "分支 `old-branch`")
        path.write_text(text)
        with self.assertRaisesRegex(ValueError, "entry_document_summary_drift"):
            governance.validate(self.root)

    def test_public_historical_index_is_not_original_byte_verification(self):
        state = governance.load(self.root, "governance/project_state.json")
        path = self.root / state["historical_governance"]["ledger"]
        text = path.read_text()
        self.assertNotIn("BEGIN ORIGINAL", text)
        self.assertLess(len(text), 5000)
        result = governance.validate(self.root)["historical_originals"]
        self.assertEqual(result["status"], "INDEX_CONSISTENCY_ONLY")
        self.assertFalse(result["original_bytes_verified"])
        sha = state["historical_governance"]["files"][0]["sha256"]
        path.write_text(text.replace(sha, "0"*64))
        with self.assertRaisesRegex(ValueError, "historical_index_drift"):
            governance.validate(self.root)

    def test_current_vault_identifiers_are_absent_and_other_authorities_stay_scoped(self):
        state = governance.load(self.root, "governance/project_state.json")
        registry = governance.load(self.root, "governance/artifact_manifest.json")
        self.assertEqual(set(state["drive"]), {"purpose"})
        self.assertEqual(set(registry["project"]), {"repository", "artifact_storage"})
        self.assertEqual(state["product"]["final_form"]["character_source"], "Jvust/Live")

    def test_optional_local_archive_requires_external_hash_and_verifies_originals(self):
        import source_bundle
        with tempfile.TemporaryDirectory(prefix="mygpt-history-source-") as temporary:
            path = Path(temporary) / "source.zip"
            original = b"Synthetic historical fixture, not user content.\n"
            row = {"path":"README.md", "bytes":len(original), "sha256":governance.digest(original)}
            entry = {**row, "mode":"100644", "git_blob":source_bundle.git_blob(original)}
            history = {"source_commit":"b"*40, "files":[row]}
            manifest = {"schema":"mygpt.source-bundle.v2", "repository":"Jvust1/mygpt",
                        "source_commit":history["source_commit"], "files":[entry],
                        "scope":"TRACKED_PROJECT_SOURCE_WITH_EXTERNAL_SUBMODULE_REFERENCES",
                        "includes_dependencies":False, "external_submodules":[], "build_bootstraps":[]}
            raw = json.dumps(manifest).encode()
            with zipfile.ZipFile(path, "w") as archive:
                source_bundle.write_entry(archive, "README.md", original, "100644")
                source_bundle.write_entry(archive, "SOURCE_MANIFEST.json", raw)
            sha = governance.digest(path.read_bytes())
            source = {"external_source_zip_sha256":sha, "files_count":1,
                      "original_manifest_sha256":governance.digest(raw)}
            with self.assertRaisesRegex(ValueError, "external_hash_required"):
                governance.verify_historical_archive(history, source, path)
            with self.assertRaisesRegex(ValueError, "external_hash_mismatch"):
                governance.verify_historical_archive(history, source, path, "0"*64)
            result = governance.verify_historical_archive(history, source, path, sha)
            self.assertTrue(result["original_bytes_verified"])
            self.assertEqual(result["original_files_verified"], 1)
            row["sha256"] = "0"*64
            with self.assertRaisesRegex(ValueError, "historical_original_bytes_changed"):
                governance.verify_historical_archive(history, source, path, sha)

    def test_latest_checkpoint_and_historical_original_source_are_independent(self):
        state = governance.load(self.root, "governance/project_state.json")
        self.assertNotEqual(state["historical_governance"]["source_commit"],
                            state["last_verified_checkpoint"]["tested_commit"])
        self.assertEqual(governance.validate(self.root)["status"], "PASS")

    def test_no_git_and_no_manifest_never_falls_back_to_checkpoint(self):
        (self.root / "SOURCE_MANIFEST.json").unlink(missing_ok=True)
        result = governance.validate(self.root)["checkout_identity"]
        self.assertEqual(result["kind"], "UNAVAILABLE")
        self.assertNotIn("head_commit", result)

    def test_modified_recovered_tree_is_not_checkpoint_head(self):
        result = governance.checkout_identity(self.root)
        if (self.root / "SOURCE_MANIFEST.json").exists():
            self.assertEqual(result["kind"], "SOURCE_BUNDLE_OBSERVATION")
            self.assertEqual(result["worktree_state"], "DIRTY_OR_UNVERIFIED")
            self.assertIsNone(result["head_commit"])
        else:
            self.assertEqual(result["kind"], "UNAVAILABLE")

    def test_manifest_identity_is_observation_not_acceptance_or_a_signature(self):
        with tempfile.TemporaryDirectory(prefix="mygpt-manifest-") as tmp:
            root = Path(tmp)
            raw = b"synthetic source\n"
            (root / "README.md").write_bytes(raw)
            manifest = {"schema":"mygpt.source-bundle.v2", "repository":"Jvust1/mygpt",
                        "source_commit":"a"*40, "files":[{"path":"README.md", "bytes":len(raw),
                        "sha256":hashlib.sha256(raw).hexdigest()}]}
            (root / "SOURCE_MANIFEST.json").write_text(json.dumps(manifest))
            result = governance.checkout_identity(root)
            self.assertEqual(result["worktree_state"], "MATCHES_UNSIGNED_MANIFEST")
            self.assertEqual(result["archive_declared_source"], "a"*40)
            self.assertIsNone(result["head_commit"])
            (root / "README.md").write_bytes(raw + b"edited")
            self.assertEqual(governance.checkout_identity(root)["worktree_state"], "DIRTY_OR_UNVERIFIED")
            (root / "README.md").write_bytes(raw)
            (root / "extra.txt").write_text("unlisted")
            self.assertEqual(governance.checkout_identity(root)["worktree_state"], "DIRTY_OR_UNVERIFIED")
            manifest["files"][0]["path"] = "../README.md"
            (root / "SOURCE_MANIFEST.json").write_text(json.dumps(manifest))
            self.assertEqual(governance.checkout_identity(root)["kind"], "UNAVAILABLE")

    @unittest.skipUnless(shutil.which("git"), "Git observation requires Git")
    def test_different_git_head_and_dirty_tree_do_not_inherit_checkpoint_ci(self):
        def git(*args):
            return subprocess.run(["git", "-C", str(self.root), *args], check=True,
                                  capture_output=True, text=True).stdout.strip()
        git("init", "-q")
        git("add", ".")
        git("-c", "user.name=Synthetic Test", "-c", "user.email=test@example.invalid",
            "commit", "-qm", "synthetic governance fixture")
        clean = governance.validate(self.root)["checkout_identity"]
        self.assertEqual(clean["kind"], "GIT_CHECKOUT_OBSERVATION")
        self.assertFalse(clean["dirty"])
        self.assertNotEqual(clean["head_commit"], governance.validate(self.root)["last_verified_source"])
        (self.root / "synthetic-untracked.txt").write_text("changed")
        dirty = governance.validate(self.root)["checkout_identity"]
        self.assertTrue(dirty["dirty"])
        self.assertEqual(dirty["ci_acceptance"], "NOT_ESTABLISHED_BY_OFFLINE_VALIDATOR")

    def test_cli_missing_or_malformed_metadata_fails_closed(self):
        (self.root / governance.EVIDENCE).write_text("{}")
        result = subprocess.run([sys.executable, str(ROOT / "scripts/validate_governance.py"),
                                 "--root", str(self.root)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["status"], "FAIL")


if __name__ == "__main__":
    unittest.main()
