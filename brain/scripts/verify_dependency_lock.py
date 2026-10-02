"""Fail closed on unsupported targets, lock drift, and unexpected installed packages.

Run preflight before pip and installed verification after --no-deps installation
of the exact local source. pip and setuptools are ordinary explicit lock entries;
only that checked local project is outside the public-artifact lock.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata as metadata
import json
from pathlib import Path
import platform
import re
import sys
import sysconfig
import struct
import tomllib

try:
    from .lock_from_report import DOCOPT_HASH, EXTRAS, META_PREFIX, TARGETS, normalized
except ImportError:
    from lock_from_report import DOCOPT_HASH, EXTRAS, META_PREFIX, TARGETS, normalized

PIN = re.compile(r"([a-z0-9][a-z0-9-]*)==([A-Za-z0-9][A-Za-z0-9_.+!-]*) --hash=sha256:([0-9a-f]{64})")
TOOLS = {"pip": "26.2.1", "setuptools": "84.0.0"}


def read_lock(path: Path) -> tuple[dict, dict]:
    pins, contexts = {}, []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(META_PREFIX):
            contexts.append(json.loads(line[len(META_PREFIX):]))
        elif line and not line.startswith("#"):
            match = PIN.fullmatch(line)
            if not match or match[1] in pins:
                raise ValueError("invalid or duplicate lock entry")
            pins[match[1]] = (match[2], match[3])
    if len(contexts) != 1 or not pins:
        raise ValueError("one explicit target metadata record and nonempty pins required")
    context = contexts[0]
    target = context.get("target")
    if target not in TARGETS or context.get("environment") != TARGETS[target]:
        raise ValueError("unsupported lock target")
    if context.get("artifact_count") != len(pins) or context.get("extras") != EXTRAS[target]:
        raise ValueError("lock metadata/pin count or extras drift")
    if context.get("evidence_kind") not in {"native-install", "native-dry-run", "cross-target-dry-run"}:
        raise ValueError("missing pip report provenance")
    for name, version in TOOLS.items():
        if pins.get(name, (None,))[0] != version:
            raise ValueError("build/bootstrap tools must be exactly locked")
    if "docopt" in pins and (target != "linux-py313" or pins["docopt"] != ("0.6.2", DOCOPT_HASH)):
        raise ValueError("only the exact reviewed docopt source exception is permitted")
    return context, pins


def runtime_environment() -> dict:
    machine = platform.machine()
    if sys.platform == "linux" and machine.lower() in {"x86_64", "amd64"}:
        machine = "x86_64"
    elif sys.platform == "win32" and machine.lower() in {"x86_64", "amd64"}:
        machine = "AMD64"
    return {"implementation_name": sys.implementation.name, "python_version": f"{sys.version_info.major}.{sys.version_info.minor}",
            "sys_platform": sys.platform, "platform_machine": machine}


def preflight(context: dict, pins: dict, project: Path, environment: dict | None = None) -> dict:
    actual = runtime_environment() if environment is None else environment
    if actual != context["environment"]:
        raise ValueError(f"platform mismatch: expected {context['environment']}, actual {actual}")
    if environment is None:
        if sysconfig.get_config_var("Py_GIL_DISABLED") or struct.calcsize("P") != 8:
            raise ValueError("only 64-bit, GIL-enabled CPython is covered by this lock")
        if sys.platform == "linux":
            libc, version = platform.libc_ver()
            if libc != "glibc" or not re.fullmatch(r"[0-9]+\.[0-9]+", version) or tuple(map(int, version.split("."))) < (2, 34):
                raise ValueError("Linux wheels require glibc >= 2.34")
    raw = (project / "pyproject.toml").read_bytes()
    if hashlib.sha256(raw).hexdigest() != context.get("pyproject_sha256"):
        raise ValueError("pyproject drift; regenerate and verify the target lock")
    config = tomllib.loads(raw.decode("utf-8"))
    if config["build-system"].get("build-backend") != "setuptools.build_meta":
        raise ValueError("unreviewed build backend")
    requirements = list(config["project"]["dependencies"])
    for extra in context["extras"]:
        requirements += config["project"]["optional-dependencies"][extra]
    if context["target"] == "windows-py313":
        requirements += ["pyinstaller==6.22.3", "playwright==1.63.0"]
    for requirement in requirements:
        name, separator, version = requirement.partition("==")
        if not separator or pins.get(normalized(name), (None,))[0] != version:
            raise ValueError(f"required root dependency is absent or changed: {requirement}")
    return config


def compare_installed(expected: dict, actual: dict) -> None:
    missing = sorted(set(expected) - set(actual))
    unexpected = sorted(set(actual) - set(expected))
    changed = sorted(name for name in set(expected) & set(actual) if expected[name] != actual[name])
    if missing or unexpected or changed:
        raise ValueError(f"installed dependency drift: missing={missing}, unexpected={unexpected}, changed={changed}")


def verify_installed(pins: dict, project: Path, config: dict) -> dict:
    actual, local = {}, None
    project_name = normalized(config["project"]["name"])
    for dist in metadata.distributions():
        name = normalized(dist.metadata["Name"])
        if name in actual:
            raise ValueError(f"duplicate installed distribution: {name}")
        actual[name] = dist.version
        if name == project_name:
            local = json.loads(dist.read_text("direct_url.json") or "null")
    # Exactly this noneditable local source installation, not arbitrary editable/VCS packages.
    if local != {"url": project.resolve().as_uri(), "dir_info": {}}:
        raise ValueError("project must be installed from the verified exact local source without editable mode")
    expected = {name: value[0] for name, value in pins.items()}
    expected[project_name] = config["project"]["version"]
    compare_installed(expected, actual)
    return actual


def verify_install_report(report: dict, context: dict, pins: dict) -> None:
    """Bind the actual native installation's full artifact set back to the lock.

    The caller supplies pip's actual installation report, not a dry-run report.
    pip's JSON format cannot independently prove whether an install ran; the
    native CI command, installed-set check, and acceptance tests provide that proof.
    """
    env = report.get("environment", {})
    actual_env = {key: env.get(key) for key in context["environment"]}
    if actual_env != context["environment"] or report.get("version") != "1":
        raise ValueError("native install report target mismatch")
    actual = {}
    for item in report.get("install", []):
        name = normalized(item["metadata"]["name"])
        if name in actual or item.get("is_direct") or item.get("is_yanked"):
            raise ValueError("invalid native install report entry")
        actual[name] = (item["metadata"]["version"], item["download_info"]["archive_info"]["hashes"]["sha256"])
    compare_installed(pins, actual)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("lock", type=Path)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--installed", action="store_true")
    parser.add_argument("--install-report", type=Path, help="Actual full native pip install report")
    parser.add_argument("--bootstrap-output", type=Path,
                        help="Extract only the locked pip/setuptools wheel pins before source builds")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        context, pins = read_lock(args.lock)
        config = preflight(context, pins, args.project)
        if args.bootstrap_output:
            args.bootstrap_output.write_text("\n".join(
                f"{name}=={pins[name][0]} --hash=sha256:{pins[name][1]}" for name in sorted(TOOLS)) + "\n", encoding="utf-8")
        installed = verify_installed(pins, args.project, config) if args.installed else None
        if args.install_report:
            if not args.installed:
                raise ValueError("install report verification also requires installed-set verification")
            verify_install_report(json.loads(args.install_report.read_text(encoding="utf-8")), context, pins)
        result = {"accepted": True, "target": context["target"], "phase": "installed" if args.installed else "preflight",
                  "lock_sha256": hashlib.sha256(args.lock.read_bytes()).hexdigest(),
                  "installed_versions": installed, "source": str(args.project.resolve())}
    except (ValueError, KeyError, OSError, TypeError) as error:
        result = {"accepted": False, "error": str(error)}
    if args.output:
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["accepted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
