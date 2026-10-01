"""Generate a platform-specific wheel hash lock from a real clean pip install report.

No resolution is invented. Reinstall the output with --require-hashes in a fresh
venv and run strict SDK acceptance before calling this a verified dependency lock.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from urllib.parse import urlsplit


def build_lock(report: dict) -> str:
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
        url = urlsplit(download["url"])
        if (url.scheme != "https" or url.hostname != "files.pythonhosted.org"
                or url.username is not None or url.password is not None or url.query
                or not url.path.endswith(".whl") or item.get("is_direct")):
            raise ValueError("only ordinary public PyPI wheels are accepted")
        digest = download["archive_info"]["hashes"]["sha256"]
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("missing or invalid wheel SHA-256")
        normalized = re.sub(r"[-_.]+", "-", name).lower()
        if normalized in pins:
            raise ValueError("duplicate distribution")
        pins[normalized] = f"{normalized}=={version} --hash=sha256:{digest}"
    environment = report.get("environment", {})
    context = {key: environment.get(key) for key in (
        "implementation_name", "python_full_version", "sys_platform", "platform_machine")}
    return ("# Generated from an actual clean pip install; one observed wheel per package.\n"
            "# Platform-specific, not a universal lock. Reinstall with --require-hashes.\n"
            "# " + json.dumps(context, sort_keys=True) + "\n" +
            "\n".join(pins[key] for key in sorted(pins)) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    content = build_lock(json.loads(args.report.read_text()))
    with args.output.open("x") as file:
        file.write(content)
