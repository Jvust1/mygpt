"""Render public PyPI artifact hashes from a real pip report, without resolving.

A dry-run report is resolution evidence, never evidence of an actual installation.
Cross-target reports retain the real resolver environment. Reinstall and test the
lock on its named native target before accepting it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

TARGETS = {
    "linux-py313": {"implementation_name": "cpython", "python_version": "3.13",
                     "sys_platform": "linux", "platform_machine": "x86_64"},
    "windows-py313": {"implementation_name": "cpython", "python_version": "3.13",
                       "sys_platform": "win32", "platform_machine": "AMD64"},
}
EXTRAS = {"linux-py313": ["test", "integrations", "realtime", "lexical-test"],
          "windows-py313": ["test", "integrations"]}
DOCOPT_URL = ("https://files.pythonhosted.org/packages/a2/55/"
              "8f8cab2afd404cf578136ef2cc5dfb50baa1761b68c9da1fb1e4eed343c9/docopt-0.6.2.tar.gz")
DOCOPT_HASH = "49b3a825280bd66b3aa83585ef59c4a8c82f2c8a522dbe754a8bc8d08c85c491"
META_PREFIX = "# mygpt-lock-v1 "


def normalized(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def artifact_pins(report: dict, *, allow_docopt: bool = False) -> dict:
    entries = report.get("install")
    if report.get("version") != "1" or not isinstance(entries, list) or not entries:
        raise ValueError("nonempty pip installation report version 1 required")
    pins = {}
    for item in entries:
        meta, download = item["metadata"], item["download_info"]
        name, version = meta["name"], meta["version"]
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", name):
            raise ValueError("invalid distribution name")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.+!-]*", version):
            raise ValueError("invalid version")
        name = normalized(name)
        digest = download["archive_info"]["hashes"]["sha256"]
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("missing or invalid artifact SHA-256")
        source_exception = (allow_docopt and name == "docopt" and version == "0.6.2"
                            and download["url"] == DOCOPT_URL and digest == DOCOPT_HASH)
        url = urlsplit(download["url"])
        if (url.scheme != "https" or url.hostname != "files.pythonhosted.org"
                or url.username is not None or url.password is not None or url.query
                or url.fragment or url.port is not None or item.get("is_direct")
                or item.get("is_yanked")
                or (not url.path.endswith(".whl") and not source_exception)):
            raise ValueError("only public PyPI wheels or the exact docopt source exception are accepted")
        if name in pins:
            raise ValueError("duplicate distribution")
        pins[name] = (version, digest)
    return pins


def build_lock(report: dict, *, target: str | None = None,
               evidence_kind: str = "unspecified-pip-report", pyproject: bytes | None = None) -> str:
    pins = artifact_pins(report, allow_docopt=target == "linux-py313")
    environment = report.get("environment", {})
    context = {key: environment.get(key) for key in (
        "implementation_name", "python_full_version", "sys_platform", "platform_machine")}
    if target is None:
        header = "# Pip report artifact hashes; installation status is not inferred.\n# " + json.dumps(context, sort_keys=True)
    else:
        if target not in TARGETS or pyproject is None:
            raise ValueError("explicit target and pyproject bytes required")
        if evidence_kind not in {"native-install", "native-dry-run", "cross-target-dry-run"}:
            raise ValueError("explicit report evidence kind required")
        if not all(isinstance(value, str) and value for value in context.values()):
            raise ValueError("complete real resolver environment required")
        native = all(context[key] == value for key, value in TARGETS[target].items()
                     if key != "python_version") and context["python_full_version"].startswith("3.13.")
        if evidence_kind != "cross-target-dry-run" and not native:
            raise ValueError("native report does not match target")
        metadata = {"target": target, "environment": TARGETS[target],
                    "resolver_environment": context, "evidence_kind": evidence_kind,
                    "pyproject_sha256": hashlib.sha256(pyproject).hexdigest(),
                    "extras": EXTRAS[target], "artifact_count": len(pins)}
        header = ("# Public PyPI hashes from " + evidence_kind + "; native acceptance is separate.\n"
                  + META_PREFIX + json.dumps(metadata, sort_keys=True))
    lines = [f"{name}=={version} --hash=sha256:{digest}"
             for name, (version, digest) in sorted(pins.items())]
    return header + "\n# Platform-specific, not a universal lock. Reinstall with --require-hashes.\n" + "\n".join(lines) + "\n"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--target", choices=TARGETS)
    parser.add_argument("--evidence-kind", default="unspecified-pip-report")
    parser.add_argument("--pyproject", type=Path)
    args = parser.parse_args()
    content = build_lock(json.loads(args.report.read_text()), target=args.target,
                         evidence_kind=args.evidence_kind,
                         pyproject=args.pyproject.read_bytes() if args.pyproject else None)
    with args.output.open("x", encoding="utf-8", newline="\n") as file:
        file.write(content)
