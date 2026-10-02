"""Execute artifact-root HTTP regressions; do not substitute for Windows EXE CI."""
import asyncio
import copy
import hashlib
import http.client
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'brain'))
from desktop_adapter import start
from mygpt_brain.local_service import STATIC_FILES

SPEC = importlib.util.spec_from_file_location('windows_delivery_test', ROOT / 'tools/build_windows_delivery.py')
build = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build)
sys.path.insert(0, str(ROOT / 'tools'))
BROWSER_SPEC = importlib.util.spec_from_file_location('native_browser_test', ROOT / 'tools/desktop_browser_test.py')
native_browser = importlib.util.module_from_spec(BROWSER_SPEC)
BROWSER_SPEC.loader.exec_module(native_browser)
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
        # Only these platform-safe lock tools may run here; full Brain/POSIX
        # suites remain mandatory on Linux and forbidden in the Windows job.
        lock_cases = 'brain/tests/test_dependency_lock.py brain/tests/test_acceptance_tools.py'
        self.assertEqual(text.count(lock_cases), 1)
        self.assertNotIn('brain/tests', text.replace(lock_cases, ''))
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
        self.assertIn('needs: [production-components, android-java-boundaries, llama-native, source-recovery, windows-desktop]', body)
        self.assertIn('REQUIRED_JOB_RESULTS: ${{ toJSON(needs) }}', body)
        self.assertIn('run: python scripts/assert_required_jobs.py production-components android-java-boundaries llama-native source-recovery windows-desktop', body)
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
        filenames = {'source-commit.txt', 'dependencies.txt', 'dependency-preflight.json',
                     'native-install-report.json', 'installed-dependencies.json', 'dependency-tests.xml',
                     'dependency-tests.txt', 'pytest.xml', 'pytest.txt',
                     'node-tests.txt', 'build.txt', 'build-evidence.json', 'native-smoke.json', 'browser.json',
                     'native-self-test-diagnostics.txt', 'native-browser-diagnostics.txt', 'native-math.png',
                     'native-text-chat.png', 'native-text-restored.png'}
        self.assertEqual(paths, {'${{ runner.temp }}/windows-evidence/' + name for name in filenames})
        self.assertEqual(text.count('uses: actions/upload-artifact@'), 1)
        self.assertNotIn('boot.log', block)
        self.assertNotIn('Copy-Item', text)
        self.assertIn('if-no-files-found: error', text)
        browser = (ROOT / 'tools/desktop_browser_test.py').read_text()
        self.assertEqual(browser.count('page.screenshot('), 3)
        for screenshot in ('native-math.png', 'native-text-chat.png', 'native-text-restored.png'):
            self.assertIn(f"page.screenshot(path=str(out / '{screenshot}'), full_page=True)", browser)

    def test_changes_to_native_builder_ui_and_workflow_trigger_aggregate(self):
        text = FUSION.read_text()
        for path in ('desktop*.py', 'desktop_ui/**', 'tools/build_windows_delivery.py',
                     'tools/desktop_browser_test.py', '.github/workflows/desktop-delivery.yml'):
            self.assertIn("      - '" + path + "'", text)
        self.assertIn('      - fix/windows-exact-head-dot-20261002', text)


class NativeProcessIsolationTests(unittest.TestCase):
    def test_both_exe_launches_use_clean_python_settings_and_temporary_cwd(self):
        with tempfile.TemporaryDirectory(prefix='mygpt-native-isolation-') as temp:
            home = Path(temp).resolve()
            with patch.dict(os.environ, PYTHONPATH='SYNTHETIC_SOURCE_FALLBACK',
                            PYTHONHOME='SYNTHETIC_INVALID_PYTHON_HOME',
                            LOCALAPPDATA='SYNTHETIC_NON_TEST_PROFILE'):
                options = build.native_process_options(home)
                result = subprocess.run([sys.executable, '-c',
                    "import json, os; print(json.dumps({'cwd': os.getcwd(), "
                    "'pythonpath': os.environ.get('PYTHONPATH'), "
                    "'pythonhome': os.environ.get('PYTHONHOME'), "
                    "'profile': os.environ['LOCALAPPDATA']}))"],
                    **options, check=True, capture_output=True, text=True, timeout=10)
                self.assertEqual(os.environ['PYTHONPATH'], 'SYNTHETIC_SOURCE_FALLBACK')
                self.assertEqual(os.environ['PYTHONHOME'], 'SYNTHETIC_INVALID_PYTHON_HOME')
                self.assertEqual(os.environ['LOCALAPPDATA'], 'SYNTHETIC_NON_TEST_PROFILE')
            actual = json.loads(result.stdout)
            self.assertEqual(Path(actual['cwd']), home)
            self.assertNotEqual(Path(actual['cwd']), ROOT)
            self.assertIsNone(actual['pythonpath'])
            self.assertIsNone(actual['pythonhome'])
            self.assertEqual(Path(actual['profile']), home / 'synthetic-profile')
        builder = (ROOT / 'tools/build_windows_delivery.py').read_text()
        browser = (ROOT / 'tools/desktop_browser_test.py').read_text()
        self.assertIn('**native_process_options(Path(temp))', builder)
        self.assertIn('**native_process_options(home)', browser)



class SyntheticTextEvidenceTests(unittest.TestCase):
    def test_previous_port_reservation_prevents_reuse_without_contacting_listener(self):
        original = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        original.bind(('127.0.0.1', 0))
        original.listen(1)
        port = original.getsockname()[1]
        try:
            with self.assertRaises((TimeoutError, OSError)):
                with native_browser.reserve_previous_port(port, timeout=0):
                    self.fail('must not share or replace an existing listener')
        finally:
            original.close()
        with native_browser.reserve_previous_port(port, timeout=0) as held:
            self.assertEqual(held.getsockname(), ('127.0.0.1', port))
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as other:
                other.bind(('127.0.0.1', 0))
                other.listen(1)
                self.assertNotEqual(other.getsockname()[1], port)
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as collision:
                with self.assertRaises(OSError):
                    collision.bind(('127.0.0.1', port))
        self.assertEqual(held.fileno(), -1)

    def test_windows_reservation_uses_exclusive_option_before_binding(self):
        with patch.object(native_browser.sys, 'platform', 'win32'), \
             patch.object(native_browser.socket, 'SO_EXCLUSIVEADDRUSE', 123456, create=True), \
             patch.object(native_browser.socket, 'socket') as factory:
            with native_browser.reserve_previous_port(10001):
                factory.return_value.setsockopt.assert_called_once_with(socket.SOL_SOCKET, 123456, 1)
                factory.return_value.bind.assert_called_once_with(('127.0.0.1', 10001))
                factory.return_value.listen.assert_called_once_with(1)
            factory.return_value.close.assert_called_once()
            names = [entry[0] for entry in factory.return_value.method_calls]
            self.assertEqual(names, ['setsockopt', 'bind', 'listen', 'close'])

    def test_test_owned_provider_records_exact_wire_bytes_and_stops_generation(self):
        provider = native_browser.SyntheticOllama()
        self.addCleanup(provider.close)
        for index, (prompt, reply) in enumerate(native_browser.SYNTHETIC_TURNS):
            messages = [{'role': 'system', 'content': 'Synthetic persona only'}]
            for old_prompt, old_reply in native_browser.SYNTHETIC_TURNS[:index]:
                messages.extend([{'role': 'user', 'content': old_prompt},
                                 {'role': 'assistant', 'content': old_reply}])
            messages.append({'role': 'user', 'content': prompt})
            raw = json.dumps({'model': native_browser.SYNTHETIC_MODEL, 'stream': False,
                              'messages': messages}, ensure_ascii=False).encode('utf-8')
            connection = http.client.HTTPConnection('127.0.0.1', provider.port, timeout=3)
            try:
                connection.request('POST', '/api/chat', body=raw,
                                   headers={'Content-Type': 'application/json'})
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertEqual(json.loads(response.read())['message']['content'], reply)
            finally:
                connection.close()
            self.assertEqual(provider.snapshot()[index]['body_utf8'].encode('utf-8'), raw)
        native_browser.verify_provider_requests(provider.snapshot())
        broken = copy.deepcopy(provider.snapshot())
        body = json.loads(broken[1]['body_utf8'])
        body['messages'] = [body['messages'][0], body['messages'][-1]]
        broken[1]['body_utf8'] = json.dumps(body, ensure_ascii=False)
        broken[1]['body_sha256'] = hashlib.sha256(broken[1]['body_utf8'].encode('utf-8')).hexdigest()
        with self.assertRaises(AssertionError):
            native_browser.verify_provider_requests(broken)
        provider.stop_provider()
        self.assertFalse(provider.thread.is_alive())
        with socket.create_connection(('127.0.0.1', provider.port), timeout=3) as refused:
            # No HTTP responder remains; an attempted provider call cannot succeed.
            self.assertEqual(refused.recv(1), b'')
        self.assertEqual(provider.stopped_connection_attempts, 1)
        self.assertEqual(len(provider.snapshot()), 2)

    def make_chat_database(self, path):
        from mygpt_brain.companion_chat import CompanionChatRuntime, CompanionPersona
        from mygpt_brain.session_store import ChatSessionStore
        store = ChatSessionStore(path)
        request_ids = [str(uuid4()), str(uuid4())]
        replies = iter(pair[1] for pair in native_browser.SYNTHETIC_TURNS)

        async def responder(_):
            return next(replies)

        runtime = CompanionChatRuntime(
            persona=CompanionPersona(persona_id=native_browser.CHAT_PERSONA,
                display_name='Synthetic verification', visual_skin_id='synthetic',
                instructions='Synthetic fixed persona'), responder=responder, session_store=store)

        async def send():
            for request_id, (prompt, _) in zip(request_ids, native_browser.SYNTHETIC_TURNS):
                await runtime.send({'request_id': request_id, 'session_id': native_browser.CHAT_SESSION,
                                    'persona_id': native_browser.CHAT_PERSONA, 'text': prompt})

        try:
            asyncio.run(send())
            messages = [message.model_dump(mode='json')
                        for message in store.load_messages(native_browser.CHAT_SESSION)
                        if message.role != 'system']
        finally:
            store.close()
            runtime.memory_store.close()
        return {'session_id': native_browser.CHAT_SESSION, 'messages': messages,
                'next_before': None}, request_ids

    def test_sqlite_evidence_requires_verbatim_text_order_pairs_and_durable_receipts(self):
        with tempfile.TemporaryDirectory(prefix='mygpt-text-evidence-') as temp:
            path = Path(temp) / 'chat.sqlite3'
            history, request_ids = self.make_chat_database(path)
            rows = native_browser.verify_chat_sqlite(path, history, request_ids)
            self.assertEqual(len(rows), 4)
            for mutation in ('text', 'pair', 'receipt'):
                with self.subTest(mutation=mutation):
                    connection = sqlite3.connect(path)
                    try:
                        connection.execute('BEGIN')
                        if mutation == 'text':
                            connection.execute('UPDATE chat_messages SET content=? WHERE message_id=?',
                                               ('changed', rows[0]['message_id']))
                        elif mutation == 'pair':
                            connection.execute('UPDATE chat_messages SET reply_to_message_id=? WHERE message_id=?',
                                               ('wrong', rows[1]['message_id']))
                        else:
                            connection.execute('DELETE FROM chat_request_receipts WHERE request_id=?',
                                               (request_ids[0],))
                        connection.commit()
                        with self.assertRaises(AssertionError):
                            native_browser.verify_chat_sqlite(path, history, request_ids)
                        if mutation == 'text':
                            connection.execute('UPDATE chat_messages SET content=? WHERE message_id=?',
                                               (rows[0]['content'], rows[0]['message_id']))
                        elif mutation == 'pair':
                            connection.execute('UPDATE chat_messages SET reply_to_message_id=? WHERE message_id=?',
                                               (rows[0]['message_id'], rows[1]['message_id']))
                        connection.commit()
                    finally:
                        connection.close()
            # Missing databases must never be silently created by verification.
            with self.assertRaises(AssertionError):
                native_browser.verify_chat_sqlite(Path(temp) / 'absent.sqlite3', history, request_ids)
            self.assertFalse((Path(temp) / 'absent.sqlite3').exists())

    def valid_report(self):
        return {'ok': True, 'os': 'win32', 'browser': 'Microsoft Edge', 'browser_version': 'synthetic',
                'exe_sha256': 'a'*64, 'native_math_preview': True, 'native_text_chat': True,
                'native_text_restart_restore': True, 'synthetic_provider_calls': 2, 'synthetic_model_calls': 2,
                'stopped_provider_connection_attempts': 0, 'live_model_calls': 0,
                'javascript_error_count': 0, 'external_request_count': 0,
                'text_chat': {'session_id': native_browser.CHAT_SESSION, 'turns': 2,
                    'first_port': 10001, 'second_port': 10002, 'previous_port_reserved': True,
                    'sqlite_rows': [{}, {}, {}, {}],
                    'request_ids': ['synthetic-a', 'synthetic-b'],
                    'read_only_restart_requests': [{'method': 'GET', 'path': '/desktop-api/chat-history'}]}}

    def test_builder_requires_native_edge_text_sqlite_restart_and_zero_restore_calls(self):
        report = self.valid_report()
        build.verify_browser_report(report, 'a'*64)
        for key in report:
            with self.subTest(missing=key):
                missing = copy.deepcopy(report)
                del missing[key]
                with self.assertRaises(ValueError):
                    build.verify_browser_report(missing, 'a'*64)
        for key, value in [('browser', 'Chromium fallback'), ('exe_sha256', 'b'*64),
                           ('native_text_chat', 1), ('synthetic_provider_calls', 3), ('synthetic_model_calls', 0),
                           ('stopped_provider_connection_attempts', 1), ('live_model_calls', 1),
                           ('javascript_error_count', 1), ('external_request_count', 1)]:
            with self.subTest(key=key, value=value):
                changed = copy.deepcopy(report)
                changed[key] = value
                with self.assertRaises(ValueError):
                    build.verify_browser_report(changed, 'a'*64)
        for key, value in [('second_port', 10001), ('first_port', True), ('previous_port_reserved', False),
                           ('sqlite_rows', [{}, {}]),
                           ('request_ids', ['same', 'same']), ('read_only_restart_requests', []),
                           ('read_only_restart_requests', [{'method': 'POST', 'path': '/desktop-api/local-chat'}])]:
            with self.subTest(text_key=key):
                changed = copy.deepcopy(report)
                changed['text_chat'][key] = value
                with self.assertRaises(ValueError):
                    build.verify_browser_report(changed, 'a'*64)

    def test_browser_script_keeps_native_boundary_and_has_no_fallback_browser(self):
        text = (ROOT / 'tools/desktop_browser_test.py').read_text()
        self.assertIn("pw.chromium.launch(channel='msedge', headless=True)", text)
        self.assertNotIn('Chromium fallback', text)
        self.assertIn('provider.stop_provider()', text)
        self.assertIn("home / 'user/data/chat.sqlite3'", text)
        self.assertIn("mode=ro", text)
        self.assertIn('response.request.post_data_json', text)
        self.assertIn('messages.all_text_contents() == expected', text)
        self.assertIn('assert after_rows == before_rows', text)
        self.assertIn("entry['method'] == 'GET'", text)
        self.assertIn('provider.stopped_connection_attempts == 0', text)
        self.assertIn('with reserve_previous_port(first_port):', text)
        self.assertIn("oversized = '测' * 4001", text)
        self.assertIn("input_value() == oversized", text)
        self.assertIn("to_contain_text('不会截断或发送')", text)


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
