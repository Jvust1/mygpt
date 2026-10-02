"""Adversarial checks for the bounded target lock contract; no network required."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from scripts.lock_from_report import (DOCOPT_HASH, DOCOPT_URL, META_PREFIX, TARGETS,
                                      artifact_pins, build_lock)
from scripts import verify_dependency_lock as verify

ROOT = Path(__file__).resolve().parents[1]
LINUX = ROOT / "requirements-linux-py313-full.lock"
WINDOWS = ROOT / "requirements-windows-py313-build.lock"


def one_report(url="https://files.pythonhosted.org/packages/example-1.0-py3-none-any.whl"):
    return {"version": "1", "environment": {"implementation_name": "cpython",
            "python_full_version": "3.13.15", "sys_platform": "linux", "platform_machine": "x86_64"},
            "install": [{"metadata": {"name": "example", "version": "1.0"},
                         "download_info": {"url": url, "archive_info": {"hashes": {"sha256": "a" * 64}}}}]}


def docopt_report():
    data = one_report(DOCOPT_URL)
    data["install"][0]["metadata"] = {"name": "docopt", "version": "0.6.2"}
    data["install"][0]["download_info"]["archive_info"]["hashes"]["sha256"] = DOCOPT_HASH
    return data


def test_exact_docopt_exception_is_opt_in_and_hash_bound():
    with pytest.raises(ValueError):
        artifact_pins(docopt_report())
    assert artifact_pins(docopt_report(), allow_docopt=True) == {"docopt": ("0.6.2", DOCOPT_HASH)}


@pytest.mark.parametrize("mutation", ["name", "version", "digest", "url", "direct", "yanked"])
def test_docopt_exception_cannot_expand(mutation):
    report = docopt_report()
    item = report["install"][0]
    if mutation == "name": item["metadata"]["name"] = "different"
    if mutation == "version": item["metadata"]["version"] = "0.6.3"
    if mutation == "digest": item["download_info"]["archive_info"]["hashes"]["sha256"] = "b" * 64
    if mutation == "url": item["download_info"]["url"] = DOCOPT_URL.replace("/a2/", "/a3/")
    if mutation == "direct": item["is_direct"] = True
    if mutation == "yanked": item["is_yanked"] = True
    with pytest.raises(ValueError):
        artifact_pins(report, allow_docopt=True)


@pytest.mark.parametrize("suffix", ["?token=x", "#fragment", ":443"])
def test_extra_url_parts_rejected(suffix):
    url = "https://files.pythonhosted.org/packages/example-1.0-py3-none-any.whl" + suffix
    with pytest.raises(ValueError):
        artifact_pins(one_report(url))


def test_cross_target_keeps_actual_resolver_and_cannot_claim_windows_install():
    data = one_report()
    raw = (ROOT / "pyproject.toml").read_bytes()
    with pytest.raises(ValueError, match="native report"):
        build_lock(data, target="windows-py313", evidence_kind="native-install", pyproject=raw)
    text = build_lock(data, target="windows-py313", evidence_kind="cross-target-dry-run", pyproject=raw)
    context = json.loads(next(x[len(META_PREFIX):] for x in text.splitlines() if x.startswith(META_PREFIX)))
    assert context["resolver_environment"]["sys_platform"] == "linux"
    assert context["environment"]["sys_platform"] == "win32"
    assert "cross-target-dry-run" in text


@pytest.mark.parametrize("key", ["implementation_name", "python_full_version", "sys_platform", "platform_machine"])
def test_missing_resolver_environment_rejected(key):
    data = one_report()
    del data["environment"][key]
    with pytest.raises(ValueError, match="resolver"):
        build_lock(data, target="linux-py313", evidence_kind="native-dry-run", pyproject=b"test")


@pytest.mark.parametrize("path,target,count", [(LINUX, "linux-py313", 85), (WINDOWS, "windows-py313", 54)])
def test_committed_closures_have_tools_required_extras_and_frozen_versions(path, target, count):
    context, pins = verify.read_lock(path)
    assert len(pins) == count
    assert context["target"] == target
    verify.preflight(context, pins, ROOT, environment=TARGETS[target])
    assert pins["pip"][0] == "26.2.1"
    assert pins["setuptools"][0] == "84.0.0"
    if target == "linux-py313":
        assert pins["docopt"] == ("0.6.2", DOCOPT_HASH)
        assert pins["cryptography"][0] == "50.0.1"
    else:
        assert "pywin32" in pins and "colorama" in pins
        assert pins["cryptography"][0] == "50.0.2"
        assert context["resolver_environment"]["sys_platform"] == "linux"


@pytest.mark.parametrize("key,value", [("python_version", "3.12"), ("sys_platform", "darwin"),
                                     ("platform_machine", "aarch64"), ("implementation_name", "pypy")])
def test_platform_mismatch_fails_before_install(key, value):
    context, pins = verify.read_lock(LINUX)
    environment = dict(TARGETS["linux-py313"], **{key: value})
    with pytest.raises(ValueError, match="platform mismatch"):
        verify.preflight(context, pins, ROOT, environment=environment)


def test_pyproject_drift_rejected(tmp_path):
    context, pins = verify.read_lock(LINUX)
    (tmp_path / "pyproject.toml").write_bytes((ROOT / "pyproject.toml").read_bytes() + b"\n# change\n")
    with pytest.raises(ValueError, match="pyproject drift"):
        verify.preflight(context, pins, tmp_path, environment=TARGETS["linux-py313"])


def test_missing_or_wrong_required_extra_fails():
    context, pins = verify.read_lock(LINUX)
    for value in [None, ("1.0", "a" * 64)]:
        changed = dict(pins)
        changed.pop("pipecat-ai")
        if value: changed["pipecat-ai"] = value
        with pytest.raises(ValueError, match="required root dependency"):
            verify.preflight(context, changed, ROOT, environment=TARGETS["linux-py313"])


@pytest.mark.parametrize("change", ["duplicate", "missing", "option", "bad-hash", "extra-metadata", "tool-drift", "docopt-drift"])
def test_lock_text_tampering_fails(tmp_path, change):
    text = LINUX.read_text()
    first_pin = next(x for x in text.splitlines() if x and not x.startswith("#"))
    if change == "duplicate": text += first_pin + "\n"
    if change == "missing": text = text.replace(first_pin + "\n", "")
    if change == "option": text += "--extra-index-url https://evil.invalid\n"
    if change == "bad-hash": text = text.replace(DOCOPT_HASH, "not-a-hash")
    if change == "extra-metadata": text += next(x for x in text.splitlines() if x.startswith(META_PREFIX)) + "\n"
    if change == "tool-drift": text = text.replace("setuptools==84.0.0", "setuptools==85.0.0")
    if change == "docopt-drift": text = text.replace(DOCOPT_HASH, "a" * 64)
    path = tmp_path / "bad.lock"
    path.write_text(text)
    with pytest.raises(ValueError): verify.read_lock(path)


@pytest.mark.parametrize("actual", [{"a": "1"}, {"a": "1", "b": "2", "c": "3"}, {"a": "1", "b": "3"}])
def test_installed_missing_unexpected_version_drift_all_fail(actual):
    with pytest.raises(ValueError, match="installed dependency drift"):
        verify.compare_installed({"a": "1", "b": "2"}, actual)


def test_exact_installed_set_passes():
    verify.compare_installed({"a": "1", "b": "2"}, {"a": "1", "b": "2"})


@pytest.mark.parametrize("origin", [None, {"url": "https://example.invalid/src", "dir_info": {}},
                                    {"url": ROOT.resolve().as_uri(), "dir_info": {"editable": True}}])
def test_local_project_origin_must_be_exact_noneditable(monkeypatch, origin):
    config = {"project": {"name": "mygpt-brain-prototype", "version": "0.1.0"}}
    dist = SimpleNamespace(metadata={"Name": "mygpt-brain-prototype"}, version="0.1.0",
                           read_text=lambda path: json.dumps(origin))
    monkeypatch.setattr(verify.metadata, "distributions", lambda: [dist])
    with pytest.raises(ValueError, match="verified exact local source"):
        verify.verify_installed({}, ROOT, config)


def test_cli_rejects_wrong_platform_before_writing_bootstrap(tmp_path):
    wrong_target = WINDOWS if sys.platform == "linux" else LINUX
    out = tmp_path / "bootstrap.lock"
    result = subprocess.run([sys.executable, str(ROOT / "scripts/verify_dependency_lock.py"),
                             str(wrong_target), "--project", str(ROOT), "--bootstrap-output", str(out)],
                            capture_output=True, text=True, timeout=5)
    assert result.returncode == 1
    assert "platform mismatch" in result.stdout
    assert not out.exists()


def native_report(pins):
    return {"version": "1", "environment": TARGETS["linux-py313"], "install": [
        {"metadata": {"name": name, "version": pair[0]},
         "download_info": {"archive_info": {"hashes": {"sha256": pair[1]}}}}
        for name, pair in pins.items()]}


def test_native_report_complete_hash_set_matches():
    context, pins = verify.read_lock(LINUX)
    verify.verify_install_report(native_report(pins), context, pins)


@pytest.mark.parametrize("change", ["missing", "extra", "hash", "version", "target", "duplicate", "direct"])
def test_native_report_drift_fails(change):
    context, pins = verify.read_lock(LINUX)
    data = copy.deepcopy(native_report(pins))
    if change == "missing": data["install"].pop()
    if change == "extra":
        entry = copy.deepcopy(data["install"][0]); entry["metadata"]["name"] = "unexpected"; data["install"].append(entry)
    if change == "hash": data["install"][0]["download_info"]["archive_info"]["hashes"]["sha256"] = "0" * 64
    if change == "version": data["install"][0]["metadata"]["version"] = "999"
    if change == "target": data["environment"]["sys_platform"] = "win32"
    if change == "duplicate": data["install"].append(copy.deepcopy(data["install"][0]))
    if change == "direct": data["install"][0]["is_direct"] = True
    with pytest.raises(ValueError): verify.verify_install_report(data, context, pins)


@pytest.mark.parametrize("libc", [("musl", "1.2"), ("glibc", "2.33"), ("", "")])
def test_unsupported_linux_libc_fails(monkeypatch, libc):
    context, pins = verify.read_lock(LINUX)
    monkeypatch.setattr(verify, "runtime_environment", lambda: TARGETS["linux-py313"])
    monkeypatch.setattr(verify.sys, "platform", "linux")
    monkeypatch.setattr(verify.platform, "libc_ver", lambda: libc)
    with pytest.raises(ValueError, match="glibc"):
        verify.preflight(context, pins, ROOT)


def test_free_threaded_runtime_fails(monkeypatch):
    context, pins = verify.read_lock(LINUX)
    monkeypatch.setattr(verify, "runtime_environment", lambda: TARGETS["linux-py313"])
    monkeypatch.setattr(verify.sysconfig, "get_config_var", lambda _: 1)
    with pytest.raises(ValueError, match="GIL-enabled"):
        verify.preflight(context, pins, ROOT)
