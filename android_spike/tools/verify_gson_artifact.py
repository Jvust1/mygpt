"""Verify the exact small Maven artifact and bundled attribution, without extraction."""
import hashlib
import json
from pathlib import Path
import struct
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]


def verify(jar):
    provenance = json.loads((ROOT / "third_party/gson/PROVENANCE.json").read_text())
    if jar.stat().st_size != provenance["artifact_bytes"]:
        raise ValueError("unexpected Gson artifact size")
    if hashlib.sha256(jar.read_bytes()).hexdigest() != provenance["artifact_sha256"]:
        raise ValueError("Gson artifact SHA-256 mismatch")
    with zipfile.ZipFile(jar) as archive:
        versions = {struct.unpack(">H", archive.read(name)[6:8])[0]
                    for name in archive.namelist()
                    if name.endswith(".class") and not name.startswith("META-INF/versions/")}
    if versions != {provenance["java_base_class_major"]}:
        raise ValueError("Gson base classes are not the pinned Java 8 bytecode")
    license = (ROOT / "third_party/gson/LICENSE").read_bytes()
    if hashlib.sha1(b"blob " + str(len(license)).encode() + b"\0" + license).hexdigest() != provenance["license_git_blob"]:
        raise ValueError("Gson license differs from pinned upstream")
    airi_license = (ROOT / "third_party/airi/LICENSE").read_bytes()
    for module in ("android_spike/app", "android_llm_spike/app", "android_voice_spike/app"):
        assets = ROOT / module / "src/main/assets"
        if (assets / "GSON_LICENSE.txt").read_bytes() != license:
            raise ValueError("Android Gson license asset mismatch")
        if (assets / "AIRI_LICENSE.txt").read_bytes() != airi_license:
            raise ValueError("Android AIRI license asset mismatch")
        if not all((assets / name).is_file() for name in ("GSON_NOTICE.txt", "AIRI_NOTICE.txt")):
            raise ValueError("Android attribution is missing")
    consumers = {"android_spike/app"}
    for build in ROOT.glob("android_*/**/build.gradle.kts"):
        if "build" in build.parts or ".gradle" in build.parts:
            continue
        if "android_spike/src/main/java" in build.read_text():
            consumers.add(build.parent.relative_to(ROOT).as_posix())
    expected = {"android_spike/app", "android_llm_spike/app", "android_llm_spike/companion", "android_voice_spike/app"}
    if consumers != expected:
        raise ValueError("Shared Java-source consumer inventory changed; audit dependencies/notices")
    for module in consumers:
        if 'implementation("com.google.code.gson:gson:2.14.0")' not in (ROOT / module / "build.gradle.kts").read_text():
            raise ValueError("Android dependency version mismatch: " + module)
    companion_build = (ROOT / "android_llm_spike/companion/build.gradle.kts").read_text()
    if 'assets.srcDir("../../android_spike/app/src/main/assets")' not in companion_build:
        raise ValueError("Companion V2 does not inherit bundled notices")
    print("Gson artifact/license PASS: exact SHA-256, 313604 bytes, Java 8 base classes")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: verify_gson_artifact.py GSON_JAR")
    verify(Path(sys.argv[1]))
