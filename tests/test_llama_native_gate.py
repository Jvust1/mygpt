"""Synthetic negative toolchain/CI checks; never compile or execute Android code."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("llama_toolchain", ROOT / "scripts/verify_llama_toolchain.py")
toolchain = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(toolchain)
WORKFLOW = ROOT / ".github/workflows/llama-android-acceptance.yml"
FUSION = ROOT / ".github/workflows/companion-fusion-acceptance.yml"


def job(path, name):
    match = re.search(r"^  " + re.escape(name) + r":\n(.*?)(?=^  [\w-]+:|\Z)",
                      path.read_text(), re.MULTILINE | re.DOTALL)
    if match is None:
        raise AssertionError("missing declared job")
    return match[1]


class ToolchainTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.sdk = self.root / "sdk"
        self.java = self.root / "jdk"
        self.cmake = self.root / "cmake/bin/cmake"
        self.ninja = self.root / "ninja"
        self.ndk = self.sdk / "ndk" / toolchain.NDK
        self.package(self.sdk / "platforms/android-36", "platforms;android-36", (2, 0, 0), "android.jar")
        self.write(self.sdk / "platforms/android-36/source.properties", "AndroidVersion.ApiLevel=36\n")
        self.package(self.sdk / "build-tools/36.0.0", "build-tools;36.0.0", (36, 0, 0), "aapt2")
        self.package(self.ndk, "ndk;" + toolchain.NDK, (29, 0, 14206865), "build/cmake/android.toolchain.cmake")
        self.write(self.ndk / "source.properties", "Pkg.Revision=" + toolchain.NDK)
        self.write(self.sdk / "licenses/android-sdk-license", hashlib.sha1(b"SYNTHETIC LICENSE").hexdigest())
        self.write(self.java / "release", 'JAVA_VERSION="17.0.16"\n')
        for p in (self.java / "bin/java", self.java / "bin/javac", self.cmake, self.ninja,
                  self.ndk / "toolchains/llvm/prebuilt/linux-x86_64/bin/clang"):
            self.write(p, "synthetic executable placeholder")
            p.chmod(0o700)

    def write(self, p, text):
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)

    def package(self, path, identity, revision, required):
        self.write(path / required, "SYNTHETIC")
        self.write(path / "package.xml", '<repository><license id="android-sdk-license" type="text">SYNTHETIC LICENSE</license>'
                   + '<localPackage path="' + identity + '"><revision>'
                   + ''.join('<' + k + '>' + str(v) + '</' + k + '>' for k, v in zip(('major', 'minor', 'micro'), revision))
                   + '</revision><uses-license ref="android-sdk-license"/></localPackage></repository>')

    def outputs(self, args):
        name = Path(args[0]).name
        return {"cmake": "cmake version 3.31.6\n", "ninja": "1.13.2\n", "java": 'openjdk version "17.0.16"\n',
                "javac": "javac 17.0.16\n", "clang": "Android clang version 21.0.0\n"}[name]

    def inspect(self):
        with patch.object(toolchain, "command", side_effect=self.outputs):
            return toolchain.preflight(self.sdk, self.java, self.cmake, self.ninja)

    def test_exact_preinstalled_files_and_stored_license_pass_read_only(self):
        before = {str(p): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        report = self.inspect()
        self.assertTrue(report["licenses_verified"])
        self.assertEqual(report["ndk"], str(self.ndk))
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.root.rglob("*") if p.is_file()})

    def test_each_missing_tool_license_or_component_fails(self):
        targets = [self.sdk / "licenses/android-sdk-license", self.sdk / "platforms/android-36/android.jar",
                   self.sdk / "build-tools/36.0.0/aapt2", self.ndk / "source.properties",
                   self.ndk / "package.xml", self.ndk / "build/cmake/android.toolchain.cmake", self.cmake,
                   self.ninja, self.java / "release", self.java / "bin/javac"]
        for target in targets:
            with self.subTest(target=target.name):
                old = target.read_bytes()
                mode = target.stat().st_mode
                target.unlink()
                with self.assertRaises((ValueError, OSError)):
                    self.inspect()
                target.write_bytes(old)
                target.chmod(mode)

    def test_wrong_versions_preview_and_unaccepted_license_fail(self):
        changes = [(self.ndk / "source.properties", "Pkg.Revision=29.0.13113456"),
                   (self.java / "release", 'JAVA_VERSION="21.0.8"'),
                   (self.sdk / "platforms/android-36/source.properties", "AndroidVersion.ApiLevel=35"),
                   (self.sdk / "licenses/android-sdk-license", "a" * 40),
                   (self.ndk / "package.xml", (self.ndk / "package.xml").read_text().replace('</revision>', '<preview>1</preview></revision>'))]
        for p, content in changes:
            old = p.read_text()
            with self.subTest(path=p.name):
                p.write_text(content)
                with self.assertRaises(ValueError):
                    self.inspect()
                p.write_text(old)
        for name, wrong in (("cmake", "cmake version 3.31.5\n"), ("ninja", "1.13.1\n"),
                            ("javac", "javac 21.0.8\n"), ("clang", "generic host clang\n")):
            with self.subTest(tool=name), patch.object(toolchain, "command", side_effect=lambda args: wrong if Path(args[0]).name == name else self.outputs(args)):
                with self.assertRaises(ValueError):
                    toolchain.preflight(self.sdk, self.java, self.cmake, self.ninja)

    def test_toolchain_error_diagnostics_are_closed_and_never_echo_private_text(self):
        import contextlib
        import io
        for error, expected in ((toolchain.ToolchainError('ndk_revision'), 'LLAMA_TOOLCHAIN_CHECK_FAILED:ndk_revision'),
                                (toolchain.ToolchainError('SECRET-SENTINEL'), 'LLAMA_TOOLCHAIN_CHECK_FAILED:toolchain_check_failed'),
                                (OSError('/private/SECRET-SENTINEL'), 'LLAMA_TOOLCHAIN_CHECK_FAILED')):
            output = io.StringIO()
            argv = ['verify', 'preflight', '--sdk', '/sdk', '--java', '/java', '--cmake', '/cmake',
                    '--ninja', '/ninja', '--private-output', '/unused']
            with self.subTest(error=type(error).__name__), patch.object(sys, 'argv', argv), \
                 patch.object(toolchain, 'preflight', side_effect=error), contextlib.redirect_stderr(output):
                self.assertEqual(toolchain.main(), 1)
                self.assertEqual(output.getvalue().strip(), expected)
                self.assertNotIn('SECRET-SENTINEL', output.getvalue())

    def test_gradle_checks_archive_and_installed_files_before_execution(self):
        archive = self.root / "gradle.zip"
        home = self.root / "gradle-8.14.3"
        self.write(home / "bin/gradle", "SYNTHETIC SCRIPT")
        self.write(home / "lib/core.jar", "SYNTHETIC JAR")
        with zipfile.ZipFile(archive, 'w') as z:
            for p in home.rglob("*"):
                if p.is_file():
                    z.write(p, p.relative_to(self.root))
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        with patch.object(toolchain, "GRADLE_SHA256", digest), patch.object(toolchain, "command", return_value="Gradle 8.14.3\n") as run:
            toolchain.verify_gradle(archive, home / "bin/gradle")
            self.assertEqual(run.call_count, 1)
            for mutation in ("modified", "extra"):
                target = home / ("lib/core.jar" if mutation == "modified" else "lib/extra.jar")
                old = target.read_text() if target.exists() else None
                target.write_text("TAMPERED")
                run.reset_mock()
                with self.assertRaises(ValueError):
                    toolchain.verify_gradle(archive, home / "bin/gradle")
                run.assert_not_called()
                if old is None:
                    target.unlink()
                else:
                    target.write_text(old)
        with patch.object(toolchain, "command") as run:
            with self.assertRaises(ValueError):
                toolchain.verify_gradle(archive, home / "bin/gradle")
            run.assert_not_called()

    def test_failures_are_fixed_and_do_not_echo_private_paths(self):
        report = self.root / 'output.json'
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/verify_llama_toolchain.py'), 'preflight',
                                 '--sdk', '/PRIVATE-SENTINEL', '--java', str(self.java), '--cmake', str(self.cmake),
                                 '--ninja', str(self.ninja), '--private-output', str(report)],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr.strip(), 'LLAMA_TOOLCHAIN_CHECK_FAILED')
        self.assertFalse(report.exists())
        self.assertNotIn('PRIVATE-SENTINEL', result.stdout + result.stderr)


class ConfiguredToolchainTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.private = {"sdk": str(self.root / "sdk"), "ndk": str(self.root / "sdk/ndk" / toolchain.NDK),
                        "java": str(self.root / "jdk"), "java_version": "17.0.16", "cmake": str(self.root / "cmake/bin/cmake"),
                        "ninja": str(self.root / "bin/ninja"), "licenses_verified": True, "gradle": str(self.root / "gradle-8.14.3/bin/gradle")}
        self.commit = "a" * 40
        self.observed = {"sourceCommit": self.commit, "sdkDir": self.private["sdk"],
                         "cmakeDir": str(self.root / "cmake"), "gradleVersion": "8.14.3", "javaHome": self.private["java"],
                         "sdkDownload": "false", "javaDownload": "false", "modules": "app,bridge,llama-lib",
                         "llama-lib.cmakeVersion": "3.31.6", "llama-lib.abis": "arm64-v8a,x86_64", "app.abis": "arm64-v8a"}
        for module in ("app", "bridge", "llama-lib"):
            self.observed.update({module + ".ndkVersion": toolchain.NDK, module + ".compileSdk": "36",
                                  module + ".buildToolsVersion": "36.0.0", module + ".minSdk": "33",
                                  module + ".sdkDir": self.private["sdk"], module + ".agpVersion": "8.13.2"})
        self.report = self.root / "android_llm_spike/build/native-ci-config.properties"
        self.report.parent.mkdir(parents=True)
        self.write_config()
        compiler = Path(self.private["ndk"]) / "bin/clang++"
        compiler.parent.mkdir(parents=True)
        compiler.write_text("synthetic compiler placeholder")
        self.cache_data = {"CMAKE_COMMAND": self.private["cmake"], "CMAKE_MAKE_PROGRAM": self.private["ninja"],
                           "ANDROID_NDK": self.private["ndk"], "CMAKE_CXX_COMPILER": str(compiler),
                           "ANDROID_PLATFORM": "android-33", "CMAKE_BUILD_TYPE": "Release",
                           "CMAKE_HOME_DIRECTORY": str(self.root / toolchain.LIB / "src/main/cpp")}
        self.caches = []
        for abi in ("arm64-v8a", "x86_64"):
            cache = self.root / toolchain.LIB / ".cxx/Release/hash" / abi / "CMakeCache.txt"
            cache.parent.mkdir(parents=True)
            cache.write_text("ANDROID_ABI:STRING=" + abi + "\n" + ''.join(k + ':STRING=' + v + '\n' for k, v in self.cache_data.items()))
            self.caches.append(cache)
        self.kleidiai = self.caches[0].parent / "kleidiai-v1.24.0-src.tar.gz"
        self.kleidiai.write_bytes(b"SYNTHETIC ARCHIVE")

    def write_config(self):
        self.report.write_text(''.join(k + '=' + v + '\n' for k, v in self.observed.items()))

    def inspect(self):
        from types import SimpleNamespace
        with patch.object(toolchain, 'verify_source'), patch.object(toolchain, 'preflight', return_value={k: v for k, v in self.private.items() if k != 'gradle'}), \
             patch.object(toolchain.hashlib, 'md5', return_value=SimpleNamespace(hexdigest=lambda: '2f02ebe29573d45813e671eb304f2a00')):
            return toolchain.configured_toolchain(self.root, self.private, self.commit)

    def test_success_requires_finalized_dsl_and_actual_cmake_paths(self):
        value = self.inspect()
        self.assertTrue(value['configured_toolchain_verified'])
        self.assertTrue(value['ci_ndk_override'])
        self.assertFalse(value['auto_sdk_download'])
        self.assertNotIn(str(self.root), json.dumps(value))
        self.assertEqual(value['kleidiai_archive_sha256'], hashlib.sha256(b'SYNTHETIC ARCHIVE').hexdigest())

    def test_every_finalized_dsl_field_is_checked(self):
        for key in list(self.observed):
            old = self.observed[key]
            with self.subTest(key=key):
                self.observed[key] = 'WRONG'
                self.write_config()
                with self.assertRaises(ValueError):
                    self.inspect()
                self.observed[key] = old
                self.write_config()
        self.observed['PRIVATE-EXTRA'] = 'SENTINEL'
        self.write_config()
        with self.assertRaises(ValueError):
            self.inspect()

    def test_cache_toolchain_drift_missing_abi_and_missing_archive_fail(self):
        cache = self.caches[0]
        original = cache.read_text()
        for key in ('CMAKE_COMMAND', 'CMAKE_MAKE_PROGRAM', 'ANDROID_NDK', 'CMAKE_CXX_COMPILER', 'ANDROID_PLATFORM', 'CMAKE_BUILD_TYPE', 'CMAKE_HOME_DIRECTORY'):
            with self.subTest(key=key):
                cache.write_text(original.replace(key + ':STRING=' + self.cache_data[key], key + ':STRING=WRONG'))
                with self.assertRaises(ValueError):
                    self.inspect()
                cache.write_text(original)
        self.caches[1].unlink()
        with self.assertRaises(ValueError):
            self.inspect()
        self.caches[1].write_text(original.replace('arm64-v8a', 'x86_64'))
        self.kleidiai.unlink()
        with self.assertRaises(ValueError):
            self.inspect()

    def test_nested_fetchcontent_host_cache_is_not_a_native_configuration(self):
        nested = self.caches[0].parent / "_deps/kleidiai-subbuild/CMakeCache.txt"
        nested.parent.mkdir(parents=True)
        nested.write_text("CMAKE_HOME_DIRECTORY:INTERNAL=" + str(nested.parent) + "\nCMAKE_COMMAND:INTERNAL=/host/cmake\n")
        self.assertTrue(self.inspect()['configured_toolchain_verified'])
        # A nested host cache is not a replacement for either required main ABI.
        self.caches[0].unlink()
        with self.assertRaises(ValueError):
            self.inspect()

    def test_debug_cache_types_are_allowed_without_claiming_release_optimization(self):
        # assembleRelease/assembleDebug and exact artifact paths are separate CI
        # gates. This checker binds native toolchain/source/API/ABI identities,
        # not AGP-variant-to-CMake optimization flag ownership or performance.
        for cache in self.caches:
            cache.write_text(cache.read_text().replace('CMAKE_BUILD_TYPE:STRING=Release',
                                                       'CMAKE_BUILD_TYPE:STRING=Debug'))
        self.assertTrue(self.inspect()['configured_toolchain_verified'])

    def test_only_correct_source_directory_caches_can_supply_abi_coverage(self):
        for cache in self.caches:
            cache.write_text(cache.read_text().replace(self.cache_data['CMAKE_HOME_DIRECTORY'], '/wrong/source'))
        with self.assertRaises(ValueError):
            self.inspect()

    def test_source_and_upstream_identity_cannot_be_inherited(self):
        valid = [self.commit, toolchain.UPSTREAM, '', '']
        with patch.object(toolchain, 'command', side_effect=valid):
            toolchain.verify_source(self.root, self.commit)
        for index in range(4):
            results = valid[:]
            results[index] = 'WRONG'
            with self.subTest(index=index), patch.object(toolchain, 'command', side_effect=results):
                with self.assertRaises(ValueError):
                    toolchain.verify_source(self.root, self.commit)


class BuildFailureDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.log = self.root / 'private-build.log'

    def inspect(self, message):
        self.log.write_text(message)
        return toolchain.build_failure_summary(self.log, self.root)

    def test_unknown_private_text_is_never_projected(self):
        value = self.inspect('SECRET-SENTINEL /private/user/path secret=value')
        self.assertEqual(set(value), {'schema', 'status', 'stages', 'owned_locations', 'log_bytes', 'log_sha256'})
        self.assertEqual(value['stages'], ['UNKNOWN'])
        self.assertEqual(value['owned_locations'], [])
        self.assertEqual(value['log_sha256'], hashlib.sha256(self.log.read_bytes()).hexdigest())
        self.assertNotIn('SECRET', json.dumps(value))
        self.assertNotIn('/private', json.dumps(value))

    def test_each_stage_is_a_fixed_enum_without_raw_matched_text(self):
        samples = {'GRADLE_DSL': 'Script compilation error: SECRET-SENTINEL',
                   'DEPENDENCY_RESOLUTION': 'Could not resolve all files SECRET-SENTINEL',
                   'CMAKE_CONFIGURE': 'CMake Error SECRET-SENTINEL',
                   'NATIVE_COMPILE': '/private/SECRET-SENTINEL.cpp:42:3: error: hidden detail',
                   'NATIVE_LINK': 'ld.lld: error: SECRET-SENTINEL',
                   'JVM_COMPILE': "Execution failed for task ':bridge:compileReleaseKotlin' SECRET-SENTINEL",
                   'PACKAGING': "Execution failed for task ':app:packageDebug' SECRET-SENTINEL"}
        for stage, text in samples.items():
            with self.subTest(stage=stage):
                value = self.inspect(text)
                self.assertEqual(value['stages'], [stage])
                self.assertNotIn('SECRET', json.dumps(value))
                self.assertNotIn('hidden detail', json.dumps(value))

    def test_only_known_owned_file_labels_and_bounded_coordinates_escape(self):
        path = self.root / 'android_llm_spike/build.gradle.kts'
        value = self.inspect(f"e: file://{path}:69:23: SECRET-SENTINEL\nBuild file '{path}' line: 45\n"
                             + f'e: file://{path}:99999999999:23: PRIVATE\n/private/other.kt:11:1: PRIVATE')
        self.assertEqual(value['owned_locations'], [{'file': 'ROOT_GRADLE', 'line': 45, 'column': 0},
                                                    {'file': 'ROOT_GRADLE', 'line': 69, 'column': 23}])
        self.assertNotIn(str(self.root), json.dumps(value))
        self.assertNotIn('SECRET', json.dumps(value))
        self.assertNotIn('PRIVATE', json.dumps(value))

    def test_cli_failure_projection_is_valid_json_and_has_no_raw_text(self):
        self.log.write_bytes(b'CMake Error SECRET-SENTINEL\n')
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/verify_llama_toolchain.py'), 'diagnose',
                                 '--log', str(self.log), '--root', str(self.root)],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)['stages'], ['CMAKE_CONFIGURE'])
        self.assertEqual(result.stderr, '')
        self.assertNotIn('SECRET-SENTINEL', result.stdout)


class KotlinContinuationSourceTests(unittest.TestCase):
    """Source regressions for the exact hosted compiler failure, not compilation."""
    def setUp(self):
        self.source = (ROOT / 'android_llm_spike/app/src/main/java/dev/mygpt/llmaspike/MainActivity.kt').read_text()

    def test_model_import_status_is_one_parenthesized_expression(self):
        self.assertIn('''status.text = ("已导入 · GGUF v${installed.header.version}"
                    + " · tensors ${installed.header.tensorCount}"
                    + " · ${installed.sizeBytes / (1024L * 1024L)} MiB"
                    + " · SHA-256 ${installed.sha256.take(12)}…")''', self.source)

    def test_reply_emotion_and_intensity_are_one_parenthesized_expression(self):
        self.assertIn('''reply.text = (parsed.visibleText.trim()
                    + "\\n\\n情绪：${parsed.emotion.wireValue}"
                    + " · 强度：${"%.2f".format(parsed.intensity)}")''', self.source)


class NativeWorkflowTests(unittest.TestCase):
    def test_reusable_only_single_job_and_three_existing_targets(self):
        text = WORKFLOW.read_text()
        self.assertIn('on:\n  workflow_call:\n', text)
        self.assertNotRegex(text, r'^  (push|pull_request|workflow_dispatch):',)
        self.assertIn("if: github.repository == 'Jvust1/mygpt'", text)
        self.assertEqual(re.findall(r':(?:llama-lib|bridge|app):assemble(?:Release|Debug)', text),
                         [':llama-lib:assembleRelease', ':bridge:assembleRelease', ':app:assembleDebug'])
        self.assertNotIn(':companion:', text)
        self.assertNotIn(':book-sender-test:', text)
        self.assertNotIn('sdkmanager', text)
        self.assertNotIn('setup-android', text)
        self.assertNotIn('setup-java', text)
        self.assertNotIn('continue-on-error', text)
        self.assertNotIn('--recursive', text)
        self.assertIn('submodules: false', text)
        self.assertIn('submodule update --init --depth 1 -- third_party/llama.cpp/upstream', text)
        self.assertIn('persist-credentials: false', text)
        self.assertIn('outputs/aar/llama-lib-release.aar', text)
        self.assertNotIn('outputs/aar/lib-release.aar', text)
        self.assertIn('ref: ${{ github.sha }}', text)

    def test_preflight_precedes_download_then_verification_precedes_build(self):
        text = WORKFLOW.read_text()
        self.assertLess(text.index('verify_llama_toolchain.py preflight'), text.index('uses: gradle/actions/setup-gradle'))
        self.assertLess(text.index('verify_llama_toolchain.py gradle'), text.index('gradle -p android_llm_spike'))
        self.assertIn("gradle-version: '8.14.3'", text)
        self.assertIn('cache-disabled: true', text)
        self.assertIn('https://services.gradle.org/distributions/gradle-8.14.3-bin.zip', text)
        self.assertIn('-Pandroid.builder.sdkDownload=false', text)
        self.assertIn('-Porg.gradle.java.installations.auto-download=false', text)
        self.assertIn('-PmygptNativeNdk=29.0.14206865', text)
        self.assertIn('--no-build-cache', text)
        self.assertNotIn('yes |', text)

    def test_exactly_one_closed_json_upload_no_binary_or_raw_log(self):
        text = WORKFLOW.read_text()
        self.assertEqual(text.count('uses: actions/upload-artifact@'), 1)
        self.assertEqual(re.findall(r'^          path: (.+)$', text, re.M),
                         ['${{ runner.temp }}/llama-public/native-build-summary.json'])
        self.assertIn('if-no-files-found: error', text)
        self.assertIn('build-scan-publish: false', text)
        self.assertIn('add-job-summary: never', text)
        self.assertIn('> "$RUNNER_TEMP/llama-private/build.log" 2>&1', text)
        self.assertIn('verify_llama_toolchain.py diagnose', text)

    def test_ci_override_is_explicit_and_default_module_behavior_remains(self):
        settings = (ROOT / 'android_llm_spike/settings.gradle.kts').read_text()
        build = (ROOT / 'android_llm_spike/build.gradle.kts').read_text()
        self.assertIn('if (nativeCi != "true")', settings)
        for module in ('companion', 'book-sender-test', 'book-client-sdk'):
            self.assertIn('include(":' + module + '")', settings)
        self.assertIn('providers.gradleProperty("mygptNativeCi").orNull == "true"', build)
        self.assertEqual(build.count('.finalizeDsl { dsl ->'), 2)
        self.assertIn('components.sdkComponents.sdkDirectory.get()', build)
        self.assertIn('AndroidPluginVersion(8, 13, 2)', build)
        self.assertNotIn('pluginVersion.toString()', build)
        self.assertIn('gradle.projectsEvaluated', build)
        self.assertIn('llama-lib.abis', build)
        self.assertIn('distributionSha256Sum=' + toolchain.GRADLE_SHA256,
                      (ROOT / 'android_llm_spike/gradle/wrapper/gradle-wrapper.properties').read_text())

    def test_aggregate_requires_native_job_and_failure_or_skip_cannot_pass(self):
        body = job(FUSION, 'fusion-required-gate')
        self.assertIn('if: ${{ always() }}', body)
        required = ['production-components', 'android-java-boundaries', 'llama-native', 'source-recovery', 'windows-desktop']
        self.assertIn('needs: [' + ', '.join(required) + ']', body)
        self.assertIn('scripts/assert_required_jobs.py ' + ' '.join(required), body)
        self.assertIn('uses: ./.github/workflows/llama-android-acceptance.yml', job(FUSION, 'llama-native'))
        for status in ('success', 'failure', 'cancelled', 'skipped', 'missing'):
            data = {name: {'result': 'success'} for name in required}
            if status == 'missing':
                del data['llama-native']
            else:
                data['llama-native']['result'] = status
            with self.subTest(status=status):
                result = subprocess.run([sys.executable, str(ROOT / 'scripts/assert_required_jobs.py'), *required],
                                        env=dict(os.environ, REQUIRED_JOB_RESULTS=json.dumps(data)),
                                        capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 0 if status == 'success' else 1)
        text = FUSION.read_text()
        for trigger in ('fix/llama-native-gate-dot-20261002', "'android_llm_spike/**'", "'scripts/verify_llama_*.py'",
                        "'.github/workflows/llama-android-acceptance.yml'"):
            self.assertIn(trigger, text)


if __name__ == '__main__':
    unittest.main()
