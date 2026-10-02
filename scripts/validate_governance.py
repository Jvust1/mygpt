"""Offline checkpoint consistency, never remote authenticity or current-head CI.

Works with Git checkouts and source-only recovery. No network, installs or writes.
A checked-in checkpoint is historical evidence, independent of a dirty/new HEAD.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "Jvust1/mygpt"
ENTRY_DOCS = ("README.md", "START_HERE.md", "docs/CURRENT_STATE.md", "docs/HANDOFF.md")
EVIDENCE = "governance/verified_checkpoint_evidence_20261002.json"


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def load(root, path):
    return json.loads((root / path).read_text(encoding="utf-8"))


def checkpoint_summary(cp):
    return (f"最后已验证源码 checkpoint：[Draft PR #{cp['pr']}]({cp['pr_url']})，分支 `{cp['branch']}`，\n"
            f"提交 `{cp['tested_commit']}`；[run {cp['run_id']}]({cp['run_url']}) {cp['successful_jobs']} 个 job 全部成功。\n"
            "这是已验证输入源码的记录；本次文档/校验器 checkout 的身份和新 CI 必须另外取得，不能继承这次绿灯。\n")


def historical_index_text(history):
    """Public immutable provenance only; do not embed historical file contents."""
    lines = ["# HISTORICAL governance provenance index — 2026-10-02", "",
             "This index does not contain the original files or private vault references.",
             "Original text remains in the immutable Git history and private original source archive.",
             "Old current/latest labels describe their historical commits, not current acceptance.",
             "The default offline validator checks index consistency only; it cannot verify absent original bytes.",
             "For current guidance use [CURRENT_STATE](CURRENT_STATE.md) and [HANDOFF](HANDOFF.md).", "",
             f"Historical source commit: `{history['source_commit']}`", "",
             "| Original public source | Original bytes | SHA-256 |", "| --- | ---: | --- |"]
    seen = set()
    for row in history["files"]:
        from source_bundle import safe_path
        name = row["path"]
        require(safe_path(name) and name not in seen, "historical_index_path")
        require(type(row["bytes"]) is int and row["bytes"] >= 0 and
                bool(re.fullmatch(r"[0-9a-f]{64}", row["sha256"])), "historical_index_digest")
        seen.add(name)
        url = f"https://github.com/{REPOSITORY}/blob/{history['source_commit']}/{name}"
        lines.append(f"| [{name}]({url}) | {row['bytes']} | `{row['sha256']}` |")
    require(len(seen) == 8, "historical_index_count")
    return "\n".join(lines) + "\n"


def verify_historical_archive(history, source, archive=None, expected_sha256=None):
    if archive is None and expected_sha256 is None:
        return {"status":"INDEX_CONSISTENCY_ONLY", "original_bytes_verified":False,
                "reason":"ORIGINAL_BYTES_NOT_ATTACHED"}
    require(archive is not None and expected_sha256 is not None,
            "historical_archive_and_external_hash_required")
    require(expected_sha256 == source["external_source_zip_sha256"],
            "historical_external_hash_mismatch")
    from source_bundle import verify
    result = verify(Path(archive), expected_sha256)
    require(result["source_commit"] == history["source_commit"] and
            result["files_verified"] == source["files_count"], "historical_archive_identity")
    with zipfile.ZipFile(archive) as bundle:
        require(digest(bundle.read("SOURCE_MANIFEST.json")) == source["original_manifest_sha256"],
                "historical_archive_manifest_hash")
        for row in history["files"]:
            data = bundle.read(row["path"])
            require(len(data) == row["bytes"] and digest(data) == row["sha256"],
                    "historical_original_bytes_changed")
    return {"status":"VERIFIED_AGAINST_CALLER_SUPPLIED_ARCHIVE_HASH",
            "original_bytes_verified":True, "original_files_verified":len(history["files"]),
            "source_commit":history["source_commit"],
            "authenticity":"DEPENDS_ON_CALLER_TRUST_IN_EXTERNAL_HASH_NOT_A_REMOTE_SIGNATURE"}


def checkout_identity(root):
    """Do not walk up to an unrelated parent Git checkout or invent a HEAD."""
    result = {"ci_acceptance": "NOT_ESTABLISHED_BY_OFFLINE_VALIDATOR"}
    if (root / ".git").exists():
        try:
            def git(*args):
                return subprocess.run(["git", "-C", str(root), *args], check=True,
                                      capture_output=True, text=True, timeout=10).stdout.strip()
            head = git("rev-parse", "--verify", "HEAD")
            require(bool(re.fullmatch(r"[0-9a-f]{40}", head)), "invalid_git_head")
            result.update(kind="GIT_CHECKOUT_OBSERVATION", head_commit=head,
                          branch=git("branch", "--show-current") or "DETACHED",
                          dirty=bool(git("status", "--porcelain", "--untracked-files=all")))
            return result
        except (OSError, subprocess.SubprocessError, ValueError):
            return {**result, "kind": "UNAVAILABLE", "reason": "git_identity_unreadable"}
    path = root / "SOURCE_MANIFEST.json"
    if not path.is_file():
        return {**result, "kind": "UNAVAILABLE", "reason": "no_git_or_source_manifest"}
    try:
        manifest = load(root, "SOURCE_MANIFEST.json")
        require(manifest["schema"] == "mygpt.source-bundle.v2", "invalid_manifest_schema")
        require(manifest["repository"] == REPOSITORY, "invalid_manifest_repository")
        commit = manifest["source_commit"]
        require(bool(re.fullmatch(r"[0-9a-f]{40}", commit)), "invalid_manifest_commit")
        # Reuse the existing recovery allowlist rather than inventing another one.
        from source_bundle import safe_path
        rows = manifest["files"]
        require(isinstance(rows, list) and bool(rows), "empty_manifest")
        names = set()
        for row in rows:
            name = row["path"]
            require(safe_path(name) and name not in names, "invalid_manifest_member")
            require(type(row["bytes"]) is int and row["bytes"] >= 0 and
                    bool(re.fullmatch(r"[0-9a-f]{64}", row["sha256"])), "invalid_manifest_hash")
            names.add(name)
        matches = all((root / r["path"]).is_file() and not (root / r["path"]).is_symlink()
                      and (root / r["path"]).stat().st_size == r["bytes"]
                      and digest((root / r["path"]).read_bytes()) == r["sha256"] for r in rows)
        ignored = {"__pycache__", ".pytest_cache"}
        actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()
                  and not ignored.intersection(p.relative_to(root).parts)}
        matches = matches and actual == names | {"SOURCE_MANIFEST.json"}
        return {**result, "kind": "SOURCE_BUNDLE_OBSERVATION",
                "archive_declared_source": commit, "archive_declared_files": len(rows),
                "worktree_state": "MATCHES_UNSIGNED_MANIFEST" if matches else "DIRTY_OR_UNVERIFIED",
                "authenticity": "REQUIRES_TRUSTED_EXTERNAL_ARCHIVE_HASH",
                "head_commit": None}
    except (OSError, KeyError, TypeError, ValueError):
        return {**result, "kind": "UNAVAILABLE", "reason": "source_manifest_invalid"}


def validate(root=ROOT, historical_source_zip=None, historical_source_sha256=None):
    root = Path(root).resolve()
    state = load(root, "governance/project_state.json")
    registry = load(root, "governance/artifact_manifest.json")
    desktop = load(root, "governance/desktop_delivery_current.json")
    pending = load(root, "governance/pending_sync.json")
    evidence = load(root, EVIDENCE)
    cp = state["last_verified_checkpoint"]
    require(set(state["drive"]) == {"purpose"} and
            set(registry["project"]) == {"repository", "artifact_storage"}, "private_vault_reference_not_allowed")
    require(state["schema_version"] == "mygpt_project_state_v1", "state_schema")
    require(registry["schema_version"] == "mygpt_artifact_manifest_v1", "artifact_schema")
    require(state["repository"] == cp["repository"] == registry["project"]["repository"] == REPOSITORY,
            "repository_owner_drift")
    require(cp["scope"] == registry["identity_scope"] == "LAST_VERIFIED_SOURCE_NOT_CURRENT_CHECKOUT",
            "checkpoint_scope_drift")
    require(state["current_checkout"]["ci_acceptance"] == "NOT_RECORDED_FOR_THIS_CHECKOUT",
            "checkout_cannot_inherit_ci")
    require(state["active_branch"] == cp["branch"] and cp["branch"] != state["default_branch"], "branch_drift")
    require(state["current_pr"]["number"] == cp["pr"] and state["current_pr"]["base_branch"] == cp["base_branch"], "pr_drift")
    require(state["current_pr"]["draft"] is True and state["current_pr"]["merged"] is False, "release_scope_drift")
    require(bool(re.fullmatch(r"[0-9a-f]{40}", cp["tested_commit"])), "invalid_tested_commit")
    require(type(cp["run_id"]) is int and cp["run_id"] > 0, "invalid_run_id")
    base = f"https://github.com/{REPOSITORY}"
    require(cp["run_url"] == f"{base}/actions/runs/{cp['run_id']}" and
            cp["pr_url"] == f"{base}/pull/{cp['pr']}", "checkpoint_url_drift")
    public_metadata = evidence["public_metadata"]
    run = public_metadata["run"]
    require(public_metadata["repository"]["full_name"] == REPOSITORY, "run_repository_drift")
    require(run["id"] == cp["run_id"] and run["head_sha"] == cp["tested_commit"] and
            run["head_branch"] == cp["branch"] and run["html_url"] == cp["run_url"], "run_identity_drift")
    require(run["status"] == "completed" and run["conclusion"] == cp["conclusion"] == "success", "run_not_success")
    require(cp["successful_jobs"] == evidence["successful_jobs"], "job_count_drift")
    require(evidence["validation"] == cp["validation"], "test_evidence_drift")
    require(cp["validation"]["failed"] == cp["validation"]["skipped"] == 0 and
            cp["validation"]["physical_device_acceptance"] is False, "acceptance_scope_drift")
    require(state["ui_candidate"]["historical_validation_only"] is True and
            state["ui_candidate"]["not_rerun_this_batch"] is True, "historical_ui_promoted")
    require(state["pending_sync"]["blocking_count"] == pending["blocking_count"] == len(pending["items"]), "pending_sync_drift")
    artifacts = registry["artifacts"]
    require(len(artifacts) == len(public_metadata["artifacts"]) == 2, "artifact_set_drift")
    require(len({a["workflow_artifact_id"] for a in artifacts}) == 2, "duplicate_artifact_identity")
    for kind, scope in (("source_bundle", "INNER_SOURCE_ZIP"), ("windows_evidence", "DOWNLOADED_EVIDENCE_ZIP")):
        target = cp[kind]
        item = next((a for a in artifacts if a["workflow_artifact_id"] == target["artifact_id"]), None)
        public = next((a for a in public_metadata["artifacts"] if a["id"] == target["artifact_id"]), None)
        require(item is not None and public is not None, "artifact_id_drift")
        require(item["repository"] == REPOSITORY and item["related_branch"] == cp["branch"] and
                item["related_commit"] == cp["tested_commit"], "artifact_source_identity_drift")
        require(item["workflow_run_id"] == cp["run_id"] and item["workflow_run"] == cp["run_url"], "artifact_run_drift")
        require(public["workflow_run"]["id"] == cp["run_id"] and public["workflow_run"]["head_sha"] == cp["tested_commit"] and
                public["workflow_run"]["head_branch"] == cp["branch"], "artifact_payload_run_drift")
        require(public["workflow_run"]["repository_id"] == public_metadata["repository"]["id"] and
                public["workflow_run"]["head_repository_id"] == public_metadata["repository"]["id"], "artifact_repository_id_drift")
        require(public["digest"] == target["github_artifact_digest"] and public["expires_at"] == target["expires_at"], "artifact_public_digest_or_expiry_drift")
        require(public["url"] == f"https://api.github.com/repos/{REPOSITORY}/actions/artifacts/{target['artifact_id']}", "artifact_api_owner_drift")
        if kind == "windows_evidence":
            require(public["digest"] == "sha256:" + target["download_zip_sha256"], "native_download_digest_drift")
        require(item["url"] == target["url"] == f"{cp['run_url']}/artifacts/{target['artifact_id']}", "artifact_url_drift")
        sha = target["inner_sha256"] if kind == "source_bundle" else target["download_zip_sha256"]
        require(bool(re.fullmatch(r"[0-9a-f]{64}", sha)) and item["sha256"] == sha == evidence[kind]["sha256"], "artifact_hash_drift")
        require(item["sha256_scope"] == scope == evidence[kind]["sha256_scope"], "artifact_hash_scope_drift")
        require(item["retention_days"] == target["retention_days"] == 3, "artifact_retention_drift")
        require(item["status"] == "LAST_VERIFIED_CHECKPOINT", "artifact_status_drift")
    source = evidence["source_bundle_manifest"]
    require(source["repository"] == REPOSITORY and source["source_commit"] == cp["tested_commit"], "checkpoint_manifest_identity_drift")
    require(source["files_count"] == cp["source_bundle"]["source_files"] and
            evidence["source_bundle"]["bytes"] == cp["source_bundle"]["inner_bytes"], "source_count_or_size_drift")
    require(evidence["windows_evidence"]["files"] == cp["windows_evidence"]["files"] and
            type(cp["windows_evidence"]["files"]) is int and cp["windows_evidence"]["files"] > 0 and
            cp["windows_evidence"]["content_scope"] == "SYNTHETIC_EVIDENCE_ONLY_NO_EXE_APK_DB", "windows_artifact_scope_drift")
    require(desktop["repository"] == REPOSITORY and desktop["branch"] == cp["branch"] and
            desktop["release_source_commit"] == cp["tested_commit"] and desktop["release_workflow_run"] == cp["run_id"], "desktop_identity_drift")
    review = desktop["current_review"]
    require(review["branch"] == cp["branch"] and review["source_commit"] == cp["tested_commit"] and
            review["run_id"] == cp["run_id"] and review["artifact_id"] == cp["windows_evidence"]["artifact_id"], "desktop_review_drift")
    require(desktop["actual_user_device_tested"] is False and desktop["exe_published"] is False, "desktop_scope_drift")
    desktop_keys = {"windows_tests", "windows_subtests", "native_executable_checks", "edge_browser_checks", "failed", "skipped"}
    require(set(desktop["verification_result"]) == desktop_keys and
            desktop["verification_result"] == {k:cp["validation"][k] for k in desktop_keys}, "desktop_test_drift")
    marker = {k:cp[k] for k in ("repository", "branch", "tested_commit", "pr", "run_id")}
    for name in ENTRY_DOCS:
        text = (root / name).read_text(encoding="utf-8")
        require(text.count(checkpoint_summary(cp)) == 1, "entry_document_summary_drift:" + name)
        found = re.findall(r"<!-- governance-checkpoint (.*?) -->", text)
        require(len(found) == 1 and json.loads(found[0]) == marker, "entry_document_identity_drift:" + name)
    history = state["historical_governance"]
    historical_source = evidence["historical_source_manifest"]
    require(historical_source["repository"] == REPOSITORY and
            historical_source["schema"] == "mygpt.source-bundle.v2" and
            history["source_commit"] == historical_source["source_commit"] and
            bool(re.fullmatch(r"[0-9a-f]{40}", history["source_commit"])), "historical_source_drift")
    require(history["evidence_scope"] == "PUBLIC_PROVENANCE_INDEX_ONLY_ORIGINAL_BYTES_NOT_ATTACHED",
            "historical_public_scope")
    require((root / history["ledger"]).read_text(encoding="utf-8") == historical_index_text(history),
            "historical_index_drift_or_unexpected_content")
    require(evidence["historical_originals"] == history["files"], "historical_manifest_drift")
    original_evidence = verify_historical_archive(history, historical_source,
                                                  historical_source_zip, historical_source_sha256)
    return {"status":"PASS", "scope":"OFFLINE_GOVERNANCE_CONSISTENCY_ONLY",
            "remote_authenticity_verified":False, "last_verified_source":cp["tested_commit"],
            "last_verified_run":cp["run_id"], "historical_originals":original_evidence,
            "checkout_identity":checkout_identity(root)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--historical-source-zip", type=Path)
    parser.add_argument("--historical-source-sha256", help="Caller-supplied trusted external archive hash")
    args = parser.parse_args()
    try:
        result = validate(args.root, args.historical_source_zip, args.historical_source_sha256)
    except (OSError, KeyError, TypeError, ValueError, StopIteration, zipfile.BadZipFile) as error:
        print(json.dumps({"status":"FAIL", "error":str(error)}, sort_keys=True))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
