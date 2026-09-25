import copy
from pathlib import Path
import pytest
from scripts.lock_from_report import build_lock
from scripts.verify_integrations import inspect_junit, required_versions


def report():
    return {"version": "1", "environment": {"python_full_version": "3.13.5"},
            "install": [{"metadata": {"name": "test-pkg", "version": "1.0"},
                         "download_info": {"url": "https://files.pythonhosted.org/packages/test.whl",
                             "archive_info": {"hashes": {"sha256": "a" * 64}}}}]}


def test_pip_report_hash_lock():
    result = build_lock(report())
    assert "test-pkg==1.0 --hash=sha256:" + "a" * 64 in result
    assert "Platform-specific" in result


@pytest.mark.parametrize("url", ["http://files.pythonhosted.org/a.whl", "https://evil.invalid/a.whl",
                                "https://user:password@files.pythonhosted.org/a.whl",
                                "https://files.pythonhosted.org/a.tar.gz", "file:///tmp/a.whl",
                                "https://files.pythonhosted.org/a.whl?token=anything"])
def test_reject_non_public_wheel(url):
    data = report()
    data["install"][0]["download_info"]["url"] = url
    with pytest.raises(ValueError):
        build_lock(data)


@pytest.mark.parametrize("digest", ["x", "a" * 63, "G" * 64])
def test_reject_bad_hash(digest):
    data = report()
    data["install"][0]["download_info"]["archive_info"]["hashes"]["sha256"] = digest
    with pytest.raises(ValueError):
        build_lock(data)


def test_reject_duplicate_and_empty():
    data = report()
    data["install"].append(copy.deepcopy(data["install"][0]))
    with pytest.raises(ValueError):
        build_lock(data)
    with pytest.raises(ValueError):
        build_lock({"version": "1", "install": []})


def test_exact_requirements():
    assert required_versions()["mcp"] == "2.2.0"
    assert required_versions()["pydantic-ai-slim"] == "2.46.0"


@pytest.mark.parametrize("child", ["<skipped/>", "<failure/>", "<error/>"])
def test_acceptance_rejects_bad_cases(tmp_path, child):
    path = tmp_path / "results.xml"
    path.write_text('<testsuites><testsuite><testcase name="test_pydantic_ai_test_model_only">' + child +
                    '</testcase><testcase name="test_mcp_in_memory_read_only"/></testsuite></testsuites>')
    assert inspect_junit(path)["accepted"] is False


def test_acceptance_requires_both_integrations(tmp_path):
    path = tmp_path / "results.xml"
    path.write_text('<testsuites><testsuite><testcase name="unrelated"/></testsuite></testsuites>')
    assert len(inspect_junit(path)["missing_required_cases"]) == 2
    path.write_text('<testsuites><testsuite><testcase name="test_pydantic_ai_test_model_only"/>'
                    '<testcase name="test_mcp_in_memory_read_only"/></testsuite></testsuites>')
    assert inspect_junit(path)["accepted"] is True
