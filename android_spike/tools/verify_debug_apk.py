"""Inspect the built evaluation APK; publish metadata only, never the binary."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile


REQUIRED = (
    "classes.dex",
    "lib/arm64-v8a/libgdx.so",
    "assets/SPINE_RUNTIME_LICENSE.txt",
)


def inspect_apk(apk, source_commit, license_path):
    if not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        raise ValueError("source commit must be an exact Git SHA")
    entries = []
    with zipfile.ZipFile(apk) as archive:
        names = archive.namelist()
        for name in REQUIRED:
            if names.count(name) != 1:
                raise ValueError(f"APK must contain exactly one {name}")
            data = archive.read(name)
            if not data:
                raise ValueError(f"APK member is empty: {name}")
            if name == "classes.dex" and not data.startswith(b"dex\n"):
                raise ValueError("classes.dex has no DEX header")
            if name.endswith(".so") and not data.startswith(b"\x7fELF"):
                raise ValueError("libgdx.so has no ELF header")
            if name.endswith("LICENSE.txt") and data != Path(license_path).read_bytes():
                raise ValueError("Spine license differs from the tracked notice")
            entries.append({"path": name, "bytes": len(data),
                            "sha256": hashlib.sha256(data).hexdigest()})
    return {"schema": "mygpt_android_debug_build_v1", "source_commit": source_commit,
            "status": "BUILD_PAYLOAD_VERIFIED", "apk_bytes": Path(apk).stat().st_size,
            "apk_sha256": hashlib.sha256(Path(apk).read_bytes()).hexdigest(),
            "required_entries": entries, "apk_published": False,
            "device_acceptance": False, "distribution_license_verified": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("apk", type=Path)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--license", type=Path, default=Path(__file__).resolve().parents[1]
                        / "app/src/main/assets/SPINE_RUNTIME_LICENSE.txt")
    args = parser.parse_args()
    report = inspect_apk(args.apk, args.source_commit, args.license)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for entry in report["required_entries"]:
        print("APK payload PASS:", entry["path"])
    print("Android debug build verified; no APK publication or device acceptance")


if __name__ == "__main__":
    main()
