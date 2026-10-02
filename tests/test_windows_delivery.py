"""Execute artifact-root HTTP regressions; do not substitute for Windows EXE CI."""
import hashlib
import http.client
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'brain'))
from desktop_adapter import start
from mygpt_brain.local_service import STATIC_FILES

SPEC = importlib.util.spec_from_file_location('windows_delivery_test', ROOT / 'tools/build_windows_delivery.py')
build = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build)
WINDOWS = ROOT / '.github/workflows/desktop-delivery.yml'
FUSION = ROOT / '.github/workflows/companion-fusion-acceptance.yml'


def job(path, name):
    match = re.search(r'^  ' + re.escape(name) + r':\n(.*?)(?=^  [\w-]+:|\Z)',
                      path.read_text(), re.MULTILINE | re.DOTALL)
    if match is None:
        raise AssertionError(f'missing required workflow job: {name}')
    return match.group(1)


def copy_build_resources(destination):
    # Consume the actual PyInstaller command, not a second test-only resource list.
    args = build.pyinstaller_command()
    for index, arg in enumerate(args):
        if arg != '--add-data':
            continue
        source, target = args[index + 1].split(':')
        origin, dest = ROOT / source, destination / target
        if origin.is_dir():
            shutil.copytree(origin, dest)
        else:
            dest.mkdir(parents=True, exist_ok=True)
            shutil.copy2(origin, dest / origin.name)


class ArtifactRootTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='mygpt-artifact-root-')
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.artifact = self.home / '_internal'
        copy_build_resources(self.artifact)

    def start_server(self):
        self.service = start(self.home / 'synthetic-user', self.artifact)
        self.addCleanup(self.service.close)

    def get(self, path):
        connection = http.client.HTTPConnection('127.0.0.1', self.service.server.httpd.server_port, timeout=3)
        try:
            connection.request('GET', path)
            response = connection.getresponse()
            return response.status, response.getheader('Content-Type'), response.read()
        finally:
            connection.close()

    def test_isolated_actual_build_resources_serve_entire_static_allowlist(self):
        report = build.verify_bundled_assets(self.artifact)
        self.assertTrue(set(STATIC_FILES.values()).issubset({row['path'] for row in report}))
        self.start_server()
        for route, path in STATIC_FILES.items():
            with self.subTest(route=route):
                status, content_type, raw = self.get(route)
                self.assertEqual(status, 200)
                self.assertEqual(raw, (ROOT / path).read_bytes())
                if route.endswith('.mjs'):
                    self.assertIn('javascript', content_type)
        for route in ('/desktop/', '/desktop/app.js'):
            self.assertEqual(self.get(route)[0], 200)
        self.assertEqual(self.service.server.httpd.engine.status()['paid_model_calls'], 0)

    def test_complete_pinned_runtime_license_notice_no_fonts_no_new_http_routes(self):
        report = build.verify_bundled_assets(self.artifact)
        for name, digest in build.KATEX_SHA256.items():
            raw = (self.artifact / 'third_party/katex' / name).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), digest)
            self.assertEqual(raw, (ROOT / 'third_party/katex' / name).read_bytes())
        self.assertFalse(any(path.suffix.lower() in build.FONT_SUFFIXES for path in self.artifact.rglob('*')))
        self.assertNotIn('MIT License', json.dumps(report))
        self.start_server()
        for name in ('LICENSE', 'NOTICE.md', 'fonts/KaTeX_Main-Regular.woff2'):
            self.assertEqual(self.get('/third_party/katex/' + name)[0], 404)

    def test_allowlisted_scripts_ignore_host_mime_registry_without_changing_bytes(self):
        self.start_server()
        scripts = {route: path for route, path in STATIC_FILES.items()
                   if route.endswith(('.js', '.mjs'))}
        self.assertIn('/third_party/katex/katex.mjs', scripts)
        for guessed in ('text/plain', 'text/html', None):
            with patch('mygpt_brain.local_service.mimetypes.guess_type', return_value=(guessed, None)):
                for route, path in scripts.items():
                    with self.subTest(guessed=guessed, route=route):
                        status, content_type, raw = self.get(route)
                        self.assertEqual(status, 200)
                        self.assertEqual(content_type, 'text/javascript; charset=utf-8')
                        self.assertEqual(raw, (ROOT / path).read_bytes())
                self.assertEqual(self.get('/third_party/katex/private.js')[0], 404)
                self.assertEqual(self.get('/third_party/katex/LICENSE')[0], 404)

    def test_each_missing_or_changed_required_resource_fails(self):
        report = build.verify_bundled_assets(self.artifact)
        for row in report:
            path = self.artifact / row['path']
            original = path.read_bytes()
            for mutation in ('missing', 'empty', 'changed'):
                with self.subTest(path=row['path'], mutation=mutation):
                    if mutation == 'missing':
                        path.unlink()
                    else:
                        path.write_bytes(b'' if mutation == 'empty' else b'SYNTHETIC_INVALID_RESOURCE')
                    with self.assertRaises(ValueError):
                        build.verify_bundled_assets(self.artifact)
                    path.write_bytes(original)

    def test_legacy_missing_renderer_reproduces_real_http_404_and_is_rejected(self):
        shutil.rmtree(self.artifact / 'third_party/katex')
        self.start_server()
        self.assertEqual(self.get('/host/brain.js')[0], 200)
        self.assertEqual(self.get('/host/math-preview.js')[0], 200)
        self.assertEqual(self.get('/third_party/katex/katex.mjs')[0], 404)
        with self.assertRaises(ValueError):
            build.verify_bundled_assets(self.artifact)

    def test_renderer_extra_file_and_wrong_resource_root_are_rejected(self):
        extra = self.artifact / 'third_party/katex/private-font.woff2'
        extra.write_bytes(b'SYNTHETIC_FONT')
        with self.assertRaises(ValueError):
            build.verify_bundled_assets(self.artifact)
        extra.unlink()
        with self.assertRaises(ValueError):
            build.verify_bundled_assets(self.home)


class WindowsWorkflowTests(unittest.TestCase):
    def test_reusable_native_gate_retires_obsolete_standalone_public_delivery(self):
        text = WINDOWS.read_text()
        self.assertIn('  workflow_call:', text)
        self.assertNotRegex(text, re.compile(r'^  (push|pull_request|workflow_dispatch):', re.MULTILINE))
        self.assertNotIn('feat/desktop-delivery-20260925', text)
        self.assertNotIn('continue-on-error', text)
        self.assertNotIn('brain/tests', text)
        body = job(WINDOWS, 'windows-native')
        self.assertIn("if: github.repository == 'Jvust1/mygpt'", body)
        self.assertIn('runs-on: windows-latest', body)
        self.assertIn('ref: ${{ github.sha }}', body)
        self.assertIn('persist-credentials: false', body)
        self.assertIn('--source-commit "$env:GITHUB_SHA"', body)
        self.assertIn('tests/test_windows_delivery.py', body)
        self.assertIn("('failures','errors','skipped')", body)
        self.assertIn('tools/build_windows_delivery.py', body)
        self.assertNotIn('--local-package-dir', body)
        for use in re.findall(r'uses: (\S+)', text):
            self.assertRegex(use, r'^actions/[a-z-]+@[0-9a-f]{40}$')

    def test_linux_strict_gate_precedes_windows_and_complete_aggregate_is_required(self):
        body = job(FUSION, 'windows-desktop')
        self.assertIn('needs: production-components', body)
        self.assertIn('uses: ./.github/workflows/desktop-delivery.yml', body)
        body = job(FUSION, 'fusion-required-gate')
        self.assertIn('if: ${{ always() }}', body)
        self.assertIn('needs: [production-components, android-java-boundaries, source-recovery, windows-desktop]', body)
        self.assertIn('REQUIRED_JOB_RESULTS: ${{ toJSON(needs) }}', body)
        self.assertIn('run: python scripts/assert_required_jobs.py production-components android-java-boundaries source-recovery windows-desktop', body)
        production = job(FUSION, 'production-components')
        self.assertIn('runs-on: ubuntu-24.04', production)
        self.assertIn('scripts/verify_integrations.py', production)
        self.assertIn('scripts/verify_fusion_upstreams.py', production)
        self.assertNotIn('continue-on-error', production)
        body = job(WINDOWS, 'windows-required-gate')
        self.assertIn('if: ${{ always() }}', body)
        self.assertIn('needs: [windows-native]', body)
        self.assertIn('run: python scripts/assert_required_jobs.py windows-native', body)

    def test_every_missing_unsuccessful_or_skipped_component_fails_closed(self):
        for names in [('windows-native',),
                      ('production-components', 'android-java-boundaries', 'source-recovery', 'windows-desktop')]:
            for name in names:
                for status in ('success', 'skipped', 'failure', 'cancelled', '', None, True, 'missing'):
                    report = {key: {'result': 'success'} for key in names}
                    if status == 'missing':
                        del report[name]
                    else:
                        report[name]['result'] = status
                    with self.subTest(name=name, status=status):
                        result = subprocess.run([sys.executable, str(ROOT / 'scripts/assert_required_jobs.py'), *names],
                            env=dict(os.environ, REQUIRED_JOB_RESULTS=json.dumps(report)),
                            capture_output=True, text=True, timeout=5)
                        self.assertEqual(result.returncode, 0 if status == 'success' else 1)

    def test_upload_allowlist_contains_only_synthetic_evidence(self):
        text = WINDOWS.read_text()
        block = text.split('          path: |\n', 1)[1].split('          retention-days:', 1)[0]
        paths = {line.strip() for line in block.splitlines() if line.strip()}
        filenames = {'source-commit.txt', 'dependencies.txt', 'pytest.xml', 'pytest.txt',
                     'node-tests.txt', 'build.txt', 'build-evidence.json', 'native-smoke.json', 'browser.json',
                     'native-self-test-diagnostics.txt', 'native-browser-diagnostics.txt', 'native-math.png'}
        self.assertEqual(paths, {'${{ runner.temp }}/windows-evidence/' + name for name in filenames})
        self.assertEqual(text.count('uses: actions/upload-artifact@'), 1)
        self.assertNotIn('boot.log', block)
        self.assertNotIn('Copy-Item', text)
        self.assertIn('if-no-files-found: error', text)
        browser = (ROOT / 'tools/desktop_browser_test.py').read_text()
        self.assertEqual(browser.count('page.screenshot('), 1)
        self.assertIn("page.screenshot(path=str(out / 'native-math.png'), full_page=True)", browser)

    def test_changes_to_native_builder_ui_and_workflow_trigger_aggregate(self):
        text = FUSION.read_text()
        for path in ('desktop*.py', 'desktop_ui/**', 'tools/build_windows_delivery.py',
                     'tools/desktop_browser_test.py', '.github/workflows/desktop-delivery.yml'):
            self.assertIn("      - '" + path + "'", text)
        self.assertIn('      - fix/windows-exact-head-dot-20261002', text)


class LocalArchiveCompatibilityTests(unittest.TestCase):
    def test_optional_local_archives_preserve_original_outputs_without_publication(self):
        with tempfile.TemporaryDirectory(prefix='mygpt-local-archive-') as temp:
            home = Path(temp)
            source, package, evidence = home / 'source', home / 'package', home / 'evidence'
            source.mkdir()
            (source / 'docs').mkdir()
            (source / 'docs/DESKTOP_DELIVERY.md').write_text(
                'Synthetic local archive instructions\n', encoding='utf-8', newline='\n')
            subprocess.run(['git', 'init', '-q'], cwd=source, check=True, capture_output=True)
            # Reproduce Windows conversion settings, then apply the real repository's
            # no-conversion policy. Archive and working bytes must remain identical.
            for key, value in (('core.autocrlf', 'true'), ('core.eol', 'crlf')):
                subprocess.run(['git', 'config', key, value], cwd=source, check=True, capture_output=True)
            (source / '.gitattributes').write_bytes((ROOT / '.gitattributes').read_bytes())
            subprocess.run(['git', 'add', '.'], cwd=source, check=True, capture_output=True)
            subprocess.run(['git', '-c', 'user.name=synthetic-test', '-c', 'user.email=test@example.invalid',
                            'commit', '-qm', 'synthetic archive fixture'], cwd=source, check=True, capture_output=True)
            commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=source, text=True).strip()
            package.mkdir()
            (package / 'mygpt.exe').write_bytes(b'SYNTHETIC_ARCHIVE_MEMBER_NOT_AN_EXECUTABLE')
            evidence.mkdir()
            (evidence / 'browser.json').write_text('{"scope":"synthetic archive helper only"}\n')
            report = {'source_commit': commit, 'exe_published': False, 'actual_user_device_tested': False}
            for unsafe in (package / 'recursive-output', evidence / 'recursive-output'):
                with self.assertRaises(ValueError):
                    build.write_local_archives(package, evidence, unsafe, report, source)
            destination = home / 'new-local-delivery'
            build.write_local_archives(package, evidence, destination, report, source)
            self.assertEqual({path.name for path in destination.iterdir()}, {
                'mygpt-Windows-Portable.zip', 'mygpt-Source-and-Tests.zip',
                'mygpt-Verification.zip', 'release.json', 'SHA256SUMS.txt'})
            for line in (destination / 'SHA256SUMS.txt').read_text().splitlines():
                digest, filename = line.split('  ')
                self.assertEqual(hashlib.sha256((destination / filename).read_bytes()).hexdigest(), digest)
            with zipfile.ZipFile(destination / 'mygpt-Windows-Portable.zip') as archive:
                manifest = json.loads(archive.read('mygpt/PACKAGE_MANIFEST.json'))
                self.assertEqual(manifest['source_commit'], commit)
                self.assertFalse(manifest['exe_published'])
                for row in manifest['files']:
                    self.assertEqual(hashlib.sha256(archive.read('mygpt/' + row['path'])).hexdigest(), row['sha256'])
            with zipfile.ZipFile(destination / 'mygpt-Source-and-Tests.zip') as archive:
                self.assertEqual(archive.read('docs/DESKTOP_DELIVERY.md'), (source / 'docs/DESKTOP_DELIVERY.md').read_bytes())
            with self.assertRaises(FileExistsError):
                build.write_local_archives(package, evidence, destination, report, source)


if __name__ == '__main__':
    unittest.main()
