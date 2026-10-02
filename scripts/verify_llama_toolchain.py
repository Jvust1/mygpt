"""Read-only native CI toolchain checks. No tool installation or license acceptance.

Private reports contain runner-local paths and must never be uploaded. The final
projection contains only the fixed toolchain schema consumed by the payload gate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile

NDK = "29.0.14206865"
UPSTREAM_NDK = "29.0.13113456"
CMAKE = "3.31.6"
NINJA = "1.13.2"
GRADLE = "8.14.3"
# https://gradle.org/release-checksums/ (8.14.3 binary-only distribution)
GRADLE_SHA256 = "bd71102213493060956ec229d946beee57158dbd89d0e62b91bca0fa2c5f3531"
UPSTREAM = "ba0ba54d93b25faf1e149f4ccedd3e9d84798563"
LLAMA = Path("third_party/llama.cpp/upstream")
LIB = LLAMA / "examples/llama.android/lib"


TOOLCHAIN_ERROR_CODES = frozenset((
    "native_compiler_report_missing", "native_compiler_report_invalid", "native_compiler_id",
    "native_compiler_executable", "native_compiler_cache_mismatch",
    'cmake_duplicate_key', 'cmake_installation_layout', 'cmake_version',
    'existing_license_missing', 'finalized_dsl_mismatch', 'gradle_distribution_duplicate',
    'gradle_distribution_hash', 'gradle_distribution_path', 'gradle_installation_bytes',
    'gradle_installation_extra_files', 'gradle_installation_path', 'gradle_runtime_version',
    'invalid_properties', 'java_compiler', 'java_runtime',
    'java_version', 'kleidiai_archive_mismatch', 'kleidiai_upstream_hash',
    'missing_executable', 'missing_kleidiai_archive', 'missing_native_configuration',
    'missing_package_license', 'missing_sdk_component', 'native_configuration_abi',
    'native_configuration_compiler', 'native_configuration_incomplete', 'native_configuration_path',
    'native_configuration_target', 'ndk_compiler', 'ndk_revision',
    'ninja_version', 'package_identity', 'package_license_reference',
    'package_revision', 'preflight_fields', 'preflight_licenses',
    'sdk_api_level', 'source_head', 'source_identity',
    'source_modified', 'tool_command_failed', 'toolchain_changed',
    'unexpected_local_properties', 'unsafe_toolchain_path', 'upstream_head',
    'upstream_modified',
))


class ToolchainError(ValueError):
    """Only fixed, non-sensitive diagnostic codes may leave this checker."""
    def __init__(self, code):
        self.code = code if code in TOOLCHAIN_ERROR_CODES else "toolchain_check_failed"
        super().__init__(self.code)


def require(value, code):
    if not value:
        raise ToolchainError(code)


def properties(path):
    result = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.lstrip().startswith(("#", "!")):
            key, sep, value = line.partition("=")
            require(sep and key.strip() not in result, "invalid_properties")
            result[key.strip()] = value.strip()
    return result


def command(args):
    result = subprocess.run([str(x) for x in args], capture_output=True, text=True,
                            timeout=60, check=False)
    require(result.returncode == 0, "tool_command_failed")
    return result.stdout + result.stderr


def executable(path):
    path = Path(path).resolve(strict=True)
    require(path.is_file() and os.access(path, os.X_OK), "missing_executable")
    return path


def installed_package(sdk, directory, package_id, revision, required_file):
    """Match each installed package's license text to an already stored acceptance.

    Android repository License.getLicenseHash hashes the exact UTF-8 XML text;
    checking it is not accepting it. No license or package file is ever written.
    """
    require((directory / required_file).is_file(), "missing_sdk_component")
    package = ET.parse(directory / "package.xml").getroot()
    locals_ = package.findall("localPackage")
    require(len(locals_) == 1 and locals_[0].get("path") == package_id, "package_identity")
    local = locals_[0]
    r = local.find("revision")
    require(r is not None, "package_revision")
    actual = tuple(int(r.findtext(k, "0")) for k in ("major", "minor", "micro"))
    require((actual == revision if revision is not None else actual[0] > 0)
            and r.find("preview") is None, "package_revision")
    refs = [n.get("ref") for n in local.findall("uses-license")]
    require(len(refs) == 1 and refs[0] == "android-sdk-license", "package_license_reference")
    licenses = [x for x in package.findall("license") if x.get("id") == refs[0]]
    require(len(licenses) == 1 and licenses[0].text, "missing_package_license")
    digest = hashlib.sha1(licenses[0].text.encode("utf-8")).hexdigest()
    stored = (sdk / "licenses" / refs[0]).read_text(encoding="utf-8").splitlines()
    require(digest in stored, "existing_license_missing")
    return digest


def preflight(sdk, java, cmake, ninja):
    sdk, java = Path(sdk).resolve(strict=True), Path(java).resolve(strict=True)
    cmake, ninja = executable(cmake), executable(ninja)
    ndk = sdk / "ndk" / NDK
    installed_package(sdk, sdk / "platforms/android-36", "platforms;android-36", None, "android.jar")
    require(properties(sdk / "platforms/android-36/source.properties").get("AndroidVersion.ApiLevel") == "36", "sdk_api_level")
    installed_package(sdk, sdk / "build-tools/36.0.0", "build-tools;36.0.0", (36, 0, 0), "aapt2")
    installed_package(sdk, ndk, "ndk;" + NDK, (29, 0, 14206865), "build/cmake/android.toolchain.cmake")
    require(properties(ndk / "source.properties").get("Pkg.Revision") == NDK, "ndk_revision")
    compiler = executable(ndk / "toolchains/llvm/prebuilt/linux-x86_64/bin/clang")
    require("Android" in command([compiler, "--version"]), "ndk_compiler")
    require(command([cmake, "--version"]).splitlines()[0] == "cmake version " + CMAKE, "cmake_version")
    require(command([ninja, "--version"]).strip() == NINJA, "ninja_version")
    release = properties(java / "release")
    version = release.get("JAVA_VERSION", "").strip('"')
    require(re.fullmatch(r"17(?:\.[0-9]+){1,3}", version), "java_version")
    require(re.search(r'\b17(?:\.[0-9]+)+\b', command([executable(java / "bin/java"), "-version"])), "java_runtime")
    require(command([executable(java / "bin/javac"), "-version"]).strip() == "javac " + version, "java_compiler")
    # CMake installation prefix, used by AGP's documented cmake.dir setting.
    require(cmake.parent.name == "bin", "cmake_installation_layout")
    return {"sdk": str(sdk), "ndk": str(ndk.resolve()), "java": str(java),
            "java_version": version, "cmake": str(cmake), "ninja": str(ninja),
            "licenses_verified": True}


def verify_gradle(archive, executable_path):
    archive, executable_path = Path(archive), Path(executable_path).resolve(strict=True)
    require(hashlib.sha256(archive.read_bytes()).hexdigest() == GRADLE_SHA256, "gradle_distribution_hash")
    home = executable_path.parent.parent
    require(executable_path == home / "bin/gradle" and home.name == "gradle-" + GRADLE, "gradle_installation_path")
    with zipfile.ZipFile(archive) as z:
        names = z.namelist()
        require(len(names) == len(set(names)), "gradle_distribution_duplicate")
        expected = set()
        for entry in z.infolist():
            relative = Path(entry.filename)
            require(relative.parts[0] == home.name and not relative.is_absolute()
                    and ".." not in relative.parts, "gradle_distribution_path")
            if entry.is_dir():
                continue
            relative = Path(*relative.parts[1:])
            installed = home / relative
            require(not installed.is_symlink() and installed.is_file()
                    and installed.read_bytes() == z.read(entry), "gradle_installation_bytes")
            expected.add(relative.as_posix())
        require({p.relative_to(home).as_posix() for p in home.rglob("*") if p.is_file()} == expected,
                "gradle_installation_extra_files")
    require(re.search(r"(?m)^Gradle 8\.14\.3$", command([executable_path, "--version"])), "gradle_runtime_version")
    return str(executable_path)


def verify_source(root, source_commit):
    require(re.fullmatch(r"[0-9a-f]{40}", source_commit), "source_identity")
    require(command(["git", "-C", root, "rev-parse", "HEAD"]).strip() == source_commit, "source_head")
    require(command(["git", "-C", root / LLAMA, "rev-parse", "HEAD"]).strip() == UPSTREAM, "upstream_head")
    require(not command(["git", "-C", root / LLAMA, "status", "--porcelain", "--untracked-files=no"]).strip(),
            "upstream_modified")
    require(not command(["git", "-C", root, "diff", "--name-only", "--ignore-submodules=untracked"]).strip(), "source_modified")


def read_cache(path):
    result = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"([^/#][^:]*):[^=]+=(.*)", line)
        if match:
            require(match[1] not in result, "cmake_duplicate_key")
            result[match[1]] = match[2]
    return result


def verify_native_compiler(cache, data, ndk):
    """Read CMake's generated compiler identity without executing its script.

    The Android NDK sets CMAKE_CXX_COMPILER as a normal CMake variable, so a
    CMakeCache.txt entry is optional. CMake 3.31.6 persists the selected compiler
    in CMakeFiles/3.31.6/CMakeCXXCompiler.cmake independently of cache storage.
    """
    report = cache.parent / "CMakeFiles" / CMAKE / "CMakeCXXCompiler.cmake"
    require(report.is_file() and not report.is_symlink(), "native_compiler_report_missing")
    text = report.read_text(encoding="utf-8")

    def literal(name, quoted=True):
        # This is a bounded reader for the exact generated set(...) records,
        # not an interpreter. Variables, escapes and duplicate setters fail.
        setters = re.findall(r"(?m)^[ \t]*(?i:set)[ \t]*\([ \t]*" + name + r"(?=\s|\))[^\r\n]*$", text)
        require(len(setters) == 1, "native_compiler_report_invalid")
        value_pattern = r'"([^"\\\r\n]*)"' if quoted else r'([0-9]+)'
        match = re.fullmatch(r'[ \t]*(?i:set)[ \t]*\([ \t]*' + name
                             + r'[ \t]+' + value_pattern + r'[ \t]*\)[ \t]*', setters[0])
        require(match is not None, "native_compiler_report_invalid")
        return match[1]

    require(literal("CMAKE_CXX_COMPILER_ID") == "Clang", "native_compiler_id")
    require(literal("CMAKE_CXX_COMPILER_LOADED", quoted=False) == "1"
            and literal("CMAKE_CXX_COMPILER_ID_RUN", quoted=False) == "1", "native_compiler_report_invalid")
    declared = Path(literal("CMAKE_CXX_COMPILER"))
    require(declared.is_absolute() and "$" not in str(declared), "native_compiler_report_invalid")
    ndk = Path(ndk).resolve(strict=True)
    expected = ndk / "toolchains/llvm/prebuilt/linux-x86_64/bin/clang++"
    require(expected.is_file() and declared.is_file(), "native_compiler_executable")
    compiler, expected = declared.resolve(strict=True), expected.resolve(strict=True)
    require(compiler == expected and compiler.is_relative_to(ndk)
            and compiler.is_relative_to((ndk / "toolchains/llvm/prebuilt/linux-x86_64/bin").resolve())
            and os.access(compiler, os.X_OK), "native_compiler_executable")
    if "CMAKE_CXX_COMPILER" in data:
        cached = Path(data["CMAKE_CXX_COMPILER"])
        require(cached.is_absolute() and cached.resolve() == compiler, "native_compiler_cache_mismatch")


def configured_toolchain(root, private, source_commit):
    verify_source(root, source_commit)
    require(type(private) is dict and set(private) == {"sdk", "ndk", "java", "java_version", "cmake", "ninja", "licenses_verified", "gradle"}, "preflight_fields")
    require(private["licenses_verified"] is True, "preflight_licenses")
    # Repeat installed component/version/license checks after the build.
    fresh = preflight(private["sdk"], private["java"], private["cmake"], private["ninja"])
    require(fresh == {k: v for k, v in private.items() if k != "gradle"}, "toolchain_changed")
    observed = properties(root / "android_llm_spike/build/native-ci-config.properties")
    expected = {"sourceCommit": source_commit, "sdkDir": private["sdk"],
                "cmakeDir": str(Path(private["cmake"]).parent.parent),
                "gradleVersion": GRADLE, "javaHome": private["java"],
                "sdkDownload": "false", "javaDownload": "false", "modules": "app,bridge,llama-lib"}
    for module in ("app", "bridge", "llama-lib"):
        expected.update({module + ".ndkVersion": NDK, module + ".compileSdk": "36",
                         module + ".buildToolsVersion": "36.0.0", module + ".minSdk": "33",
                         module + ".sdkDir": private["sdk"], module + ".agpVersion": "8.13.2"})
    expected["llama-lib.cmakeVersion"] = CMAKE
    expected["llama-lib.abis"] = "arm64-v8a,x86_64"
    expected["app.abis"] = "arm64-v8a"
    require(observed == expected, "finalized_dsl_mismatch")
    caches = list((root / LIB / ".cxx").rglob("CMakeCache.txt"))
    require(caches, "missing_native_configuration")
    observed_abis = set()
    native_source = (root / LIB / "src/main/cpp").resolve()
    selected = []
    for cache in caches:
        data = read_cache(cache)
        # FetchContent adds independent host sub-build caches below .cxx.
        # Only the exact AGP native project's source directory defines this gate.
        home = data.get("CMAKE_HOME_DIRECTORY")
        if home is None or Path(home).resolve() != native_source:
            continue
        selected.append(cache)
        abi = data.get("ANDROID_ABI")
        require(abi in ("arm64-v8a", "x86_64"), "native_configuration_abi")
        observed_abis.add(abi)
        for key, value in (("CMAKE_COMMAND", private["cmake"]),
                           ("CMAKE_MAKE_PROGRAM", private["ninja"]),
                           ("ANDROID_NDK", private["ndk"])):
            require(key in data and Path(data[key]).resolve() == Path(value).resolve(), "native_configuration_path")
        verify_native_compiler(cache, data, private["ndk"])
        require(data.get("ANDROID_PLATFORM") == "android-33" and data.get("CMAKE_BUILD_TYPE") in ("Release", "Debug"),
                "native_configuration_target")
    require(selected and observed_abis == {"arm64-v8a", "x86_64"}, "native_configuration_incomplete")
    archives = list((root / LIB / ".cxx").rglob("kleidiai-v1.24.0-src.tar.gz"))
    require(archives, "missing_kleidiai_archive")
    hashes = set()
    for archive in archives:
        content = archive.read_bytes()
        require(hashlib.md5(content).hexdigest() == "2f02ebe29573d45813e671eb304f2a00", "kleidiai_upstream_hash")
        hashes.add(hashlib.sha256(content).hexdigest())
    require(len(hashes) == 1, "kleidiai_archive_mismatch")
    return {"kleidiai_version": "1.24.0", "kleidiai_archive_md5": "2f02ebe29573d45813e671eb304f2a00",
            "kleidiai_archive_sha256": hashes.pop(), "sdk": 36, "build_tools": "36.0.0", "ndk": NDK, "upstream_ndk": UPSTREAM_NDK,
            "cmake": CMAKE, "ninja": NINJA, "gradle": GRADLE,
            "gradle_distribution_sha256": GRADLE_SHA256, "agp": "8.13.2", "kotlin": "2.3.0",
            "java_major": 17, "java_version": private["java_version"], "ci_ndk_override": True,
            "existing_licenses_verified": True, "auto_sdk_download": False,
            "configured_toolchain_verified": True}


# This is a one-build, closed diagnostic projection, never a raw-log publisher.
# No matched text, dependency names, environment values or input paths are output.
FAILURE_PATTERNS = {
    "GRADLE_DSL": r"Script compilation errors?|\.gradle\.kts:[0-9]+:[0-9]+.*(?:Unresolved reference|Type mismatch)",
    "DEPENDENCY_RESOLUTION": r"Could not resolve all (?:files|artifacts|dependencies)|Could not (?:GET|HEAD|find) ",
    "CMAKE_CONFIGURE": r"CMake Error|CMake configuration failed|Configuring incomplete, errors occurred",
    "NATIVE_COMPILE": r"\.(?:cpp|cc|c|h|hpp):[0-9]+:[0-9]+: (?:fatal )?error:",
    "NATIVE_LINK": r"ld\.lld: error:|undefined reference to|linker command failed",
    "JVM_COMPILE": r"Execution failed for task ':(?:app|bridge|llama-lib):compile[^']*(?:Kotlin|JavaWithJavac)'",
    "PACKAGING": r"Execution failed for task ':(?:app|bridge|llama-lib):(?:package|bundle|merge)[^']*'",
}
OWNED_DIAGNOSTIC_FILES = {
    "ROOT_GRADLE": "android_llm_spike/build.gradle.kts",
    "SETTINGS_GRADLE": "android_llm_spike/settings.gradle.kts",
    "APP_GRADLE": "android_llm_spike/app/build.gradle.kts",
    "BRIDGE_GRADLE": "android_llm_spike/bridge/build.gradle.kts",
    "LOCAL_APP": "android_llm_spike/app/src/main/java/dev/mygpt/llmaspike/MainActivity.kt",
    "BRIDGE_ENGINE": "android_llm_spike/bridge/src/main/java/dev/mygpt/llama/LlamaCppCompanionEngine.kt",
}


def build_failure_summary(log_path, root):
    """Only fixed stage/file labels, bounded coordinates, hash and size escape."""
    raw = Path(log_path).read_bytes()
    text = raw.decode("utf-8", errors="replace")
    stages = [name for name, pattern in FAILURE_PATTERNS.items() if re.search(pattern, text)]
    locations = set()
    for label, relative in OWNED_DIAGNOSTIC_FILES.items():
        path = re.escape(str((Path(root) / relative).resolve()))
        patterns = ((r"(?:file://)?" + path + r":([0-9]+):([0-9]+)(?=[:\s])", True),
                    (r"(?:Build|Settings) file '" + path + r"' line: ([0-9]+)(?=\s|$)", False))
        for pattern, has_column in patterns:
            for match in re.finditer(pattern, text):
                line = int(match[1])
                column = int(match[2]) if has_column else 0
                if 0 < line <= 1000000 and 0 <= column <= 1000000:
                    locations.add((label, line, column))
    return {"schema": "mygpt.llama-build-failure.v1", "status": "FAIL",
            "stages": stages or ["UNKNOWN"],
            "owned_locations": [{"file": label, "line": line, "column": column}
                                for label, line, column in sorted(locations)[:32]],
            "log_bytes": len(raw), "log_sha256": hashlib.sha256(raw).hexdigest()}


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    pre = sub.add_parser("preflight")
    pre.add_argument("--sdk", type=Path, required=True)
    pre.add_argument("--java", type=Path, required=True)
    pre.add_argument("--cmake", type=Path, required=True)
    pre.add_argument("--ninja", type=Path, required=True)
    pre.add_argument("--private-output", type=Path, required=True)
    gr = sub.add_parser("gradle")
    gr.add_argument("--archive", type=Path, required=True)
    gr.add_argument("--executable", type=Path, required=True)
    gr.add_argument("--private-output", type=Path, required=True)
    gr.add_argument("--project", type=Path, required=True)
    post = sub.add_parser("configured")
    post.add_argument("--root", type=Path, default=Path.cwd())
    post.add_argument("--private-input", type=Path, required=True)
    post.add_argument("--source-commit", required=True)
    post.add_argument("--output", type=Path, required=True)
    diagnostic = sub.add_parser("diagnose")
    diagnostic.add_argument("--log", type=Path, required=True)
    diagnostic.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    try:
        if args.mode == "diagnose":
            print(json.dumps(build_failure_summary(args.log, args.root), sort_keys=True))
            return 0
        if args.mode == "preflight":
            dump(args.private_output, preflight(args.sdk, args.java, args.cmake, args.ninja))
        elif args.mode == "gradle":
            report = json.loads(args.private_output.read_text())
            report["gradle"] = verify_gradle(args.archive, args.executable)
            dump(args.private_output, report)
            local = args.project / "local.properties"
            require(not local.exists(), "unexpected_local_properties")
            # Controlled Linux runner paths; no arbitrary property injection.
            for value in (report["sdk"], str(Path(report["cmake"]).parent.parent)):
                require(re.fullmatch(r"/[A-Za-z0-9_./+-]+", value), "unsafe_toolchain_path")
            local.write_text("sdk.dir=" + report["sdk"] + "\ncmake.dir=" + str(Path(report["cmake"]).parent.parent) + "\n")
        else:
            dump(args.output, configured_toolchain(args.root, json.loads(args.private_input.read_text()), args.source_commit))
    except ToolchainError as error:
        print("LLAMA_TOOLCHAIN_CHECK_FAILED:" + error.code, file=sys.stderr)
        return 1
    except (ValueError, TypeError, KeyError, IndexError, OSError, ET.ParseError, zipfile.BadZipFile, subprocess.SubprocessError):
        print("LLAMA_TOOLCHAIN_CHECK_FAILED", file=sys.stderr)
        return 1
    print("LLAMA_TOOLCHAIN_CHECK_PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
