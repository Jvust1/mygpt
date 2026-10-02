"""Real Windows EXE plus Edge math/text/restart evidence; synthetic data only."""
from contextlib import contextmanager
import errno
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from urllib.parse import urlsplit
from uuid import UUID

from build_windows_delivery import native_process_options

KATEX_SHA256 = '694a531495903e374957e9a9c904a402e2f413762635df486c4cf6163320d1aa'
SYNTHETIC_MODEL = 'synthetic-desktop-text-verification'
CHAT_SESSION = 'desktop-local-chat-v1'
CHAT_PERSONA = 'mygpt-desktop-v1'
SYNTHETIC_TURNS = (
    ('仅为合成测试：第一问 🧪\n  原文 <img src="/never-chat-image" onerror="window.chatInjected=1"> & 2 < 3',
     '仅为合成测试：第一答 🧪\n  <script>window.chatInjected=1</script> & 原样保留'),
    ('仅为合成测试：第二问\n请接续上一问；空格  与 café、中文必须保持。',
     '仅为合成测试：第二答\n已收到前一轮问答。<b>这仍是纯文本</b>  完毕。'),
)


class SyntheticOllama:
    """Test-owned loopback HTTP responder; never invokes or downloads a model."""

    def __init__(self):
        self.requests = []
        self.stopped_connection_attempts = 0
        self._lock = threading.Lock()
        self._guard_stop = threading.Event()
        self._stopped = False
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_POST(self):
                size = int(self.headers.get('Content-Length', '0'))
                raw = self.rfile.read(size) if 0 < size <= 100_000 else b''
                with owner._lock:
                    owner.requests.append({'method': self.command, 'path': self.path,
                        'body_utf8': raw.decode('utf-8'),
                        'body_sha256': hashlib.sha256(raw).hexdigest()})
                    index = len(owner.requests) - 1
                if self.path != '/api/chat' or index >= len(SYNTHETIC_TURNS) or not raw:
                    status, value = 500, {'error': 'unexpected synthetic provider request'}
                else:
                    status, value = 200, {'message': {'role': 'assistant',
                        'content': SYNTHETIC_TURNS[index][1]}, 'done': True}
                body = json.dumps(value, ensure_ascii=False).encode('utf-8')
                self.send_response(status)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.send_header('Connection', 'close')
                self.end_headers()
                self.wfile.write(body)

            # Unexpected probes count too: no endpoint may silently contact a model.
            do_GET = do_PUT = do_DELETE = do_PATCH = do_POST

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.port = self.server.server_port
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.guard = None

    def snapshot(self):
        with self._lock:
            return list(self.requests)

    def stop_provider(self):
        """Stop HTTP generation; retain a refusal sentinel for attempted contact.

        No HTTP handler/model remains running. A separate socket acceptor closes
        every connection immediately and records attempts during EXE restoration.
        Keeping the original bound socket avoids port races on Windows.
        """
        if self._stopped:
            return
        self.server.shutdown()
        self.thread.join(timeout=5)
        assert not self.thread.is_alive(), 'synthetic provider did not stop'
        self._stopped = True
        self.server.socket.settimeout(.1)

        def refuse():
            while not self._guard_stop.is_set():
                try:
                    connection, _ = self.server.socket.accept()
                except socket.timeout:
                    continue
                with self._lock:
                    self.stopped_connection_attempts += 1
                connection.close()

        self.guard = threading.Thread(target=refuse, daemon=True)
        self.guard.start()

    def close(self):
        self.stop_provider()
        self._guard_stop.set()
        self.guard.join(timeout=5)
        assert not self.guard.is_alive(), 'stopped-provider sentinel did not stop'
        self.server.server_close()



@contextmanager
def reserve_previous_port(port, *, timeout=75):
    """Hold the retired EXE port so port=0 must select a different origin.

    Windows must use exclusive binding, never SO_REUSEADDR's sharing semantics.
    Wait only for recently closed TCP connections to release the address; no
    requests are sent, existing listeners are never displaced, and timeout fails.
    """
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError('invalid previous loopback port')
    reservation = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if sys.platform == 'win32':
            reservation.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        else:
            # POSIX permits reuse after TIME_WAIT without sharing a listener.
            reservation.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        deadline = time.monotonic() + timeout
        while True:
            try:
                reservation.bind(('127.0.0.1', port))
                break
            except OSError as error:
                if error.errno not in (errno.EADDRINUSE, 10048):
                    raise
                if time.monotonic() >= deadline:
                    raise TimeoutError('previous loopback port could not be exclusively reserved') from error
                time.sleep(.1)
        reservation.listen(1)
        yield reservation
    finally:
        reservation.close()


def verify_provider_requests(requests):
    assert len(requests) == 2, 'exactly two synthetic provider calls required'
    for index, record in enumerate(requests):
        assert record['method'] == 'POST' and record['path'] == '/api/chat'
        raw = record['body_utf8'].encode('utf-8')
        assert hashlib.sha256(raw).hexdigest() == record['body_sha256']
        body = json.loads(raw)
        assert body['model'] == SYNTHETIC_MODEL and body['stream'] is False
        assert body['messages'][0]['role'] == 'system'
        assert all(item['role'] == 'system' for item in body['messages'][:-1-2*index])
        expected = []
        for prompt, reply in SYNTHETIC_TURNS[:index]:
            expected.extend([{'role': 'user', 'content': prompt},
                             {'role': 'assistant', 'content': reply}])
        expected.append({'role': 'user', 'content': SYNTHETIC_TURNS[index][0]})
        actual = [item for item in body['messages'] if item['role'] != 'system']
        assert actual == expected, 'provider must receive exact prior Q/A and current prompt'


def verify_chat_sqlite(path, history, request_ids):
    """Read actual native SQLite without creating or modifying the database."""
    assert path.is_file(), 'native chat SQLite database missing'
    connection = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)
    connection.row_factory = sqlite3.Row
    try:
        assert connection.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        sessions = connection.execute('SELECT session_id, persona_id FROM chat_sessions').fetchall()
        assert [tuple(row) for row in sessions] == [(CHAT_SESSION, CHAT_PERSONA)]
        rows = [dict(row) for row in connection.execute(
            'SELECT message_id, session_id, ordinal, role, content, reply_to_message_id '
            'FROM chat_messages WHERE session_id=? AND role!=? ORDER BY ordinal',
            (CHAT_SESSION, 'system'))]
        assert [(row['role'], row['content']) for row in rows] == [
            (role, content) for pair in SYNTHETIC_TURNS
            for role, content in zip(('user', 'assistant'), pair)]
        assert len({row['message_id'] for row in rows}) == 4
        assert len({row['ordinal'] for row in rows}) == 4
        for question, answer in zip(rows[::2], rows[1::2]):
            assert answer['reply_to_message_id'] == question['message_id']
            assert question['reply_to_message_id'] is None
        assert history['session_id'] == CHAT_SESSION and history['next_before'] is None
        assert [{key: item[key] for key in ('message_id', 'role', 'content')}
                for item in history['messages']] == [
                    {key: row[key] for key in ('message_id', 'role', 'content')} for row in rows]
        receipts = connection.execute(
            'SELECT request_id, session_id, result_json FROM chat_request_receipts').fetchall()
        assert {row['request_id'] for row in receipts} == set(request_ids)
        assert len(receipts) == 2
        for row in receipts:
            result = json.loads(row['result_json'])
            index = request_ids.index(row['request_id'])
            assert row['session_id'] == CHAT_SESSION
            assert result['user_message']['message_id'] == rows[index*2]['message_id']
            assert result['assistant_message']['message_id'] == rows[index*2+1]['message_id']
            assert result['user_message']['content'] == SYNTHETIC_TURNS[index][0]
            assert result['assistant_message']['content'] == SYNTHETIC_TURNS[index][1]
        return rows
    finally:
        connection.close()


def read_history(page):
    return page.evaluate("""async () => {
      const response = await fetch('/desktop-api/chat-history', {
        headers: {'X-MyGPT-Client': 'mygpt-desktop-v1'}});
      if (!response.ok) throw Error('history read failed');
      return response.json();
    }""")


def assert_history_ui(page, expected):
    from playwright.sync_api import expect
    messages = page.locator('#chat-history .chat-message pre')
    expect(messages).to_have_count(len(expected))
    # text_content intentionally avoids Playwright's whitespace-normalizing matcher.
    assert messages.all_text_contents() == expected
    assert page.locator('#chat-history script, #chat-history img, #chat-history b, '
                        '#chat-history iframe, #reply script, #reply img, #reply b').count() == 0
    assert page.evaluate('typeof window.chatInjected') == 'undefined'


def verify_text_chat(page, provider, checks):
    from playwright.sync_api import expect
    page.locator('[data-tab=chat]').click()
    page.locator('#model').fill(SYNTHETIC_MODEL)
    page.locator('#port').fill(str(provider.port))
    assert not provider.snapshot(), 'page load must not contact the model'
    history = read_history(page)
    assert history == {'session_id': CHAT_SESSION, 'messages': [], 'next_before': None}
    oversized = '测' * 4001
    page.locator('#prompt').fill(oversized)
    assert page.locator('#prompt').input_value() == oversized, 'input silently truncated the draft'
    expect(page.locator('#consent')).not_to_be_checked()
    page.locator('#ask').click()
    expect(page.locator('#chat-status')).to_contain_text('请先确认')
    page.locator('#consent').check()
    page.locator('#ask').click()
    expect(page.locator('#chat-status')).to_contain_text('4000')
    expect(page.locator('#chat-status')).to_contain_text('不会截断或发送')
    assert page.locator('#prompt').input_value() == oversized
    assert not provider.snapshot(), 'oversized draft must not contact the provider'
    checks.append('oversized_prompt_preserved_and_rejected_before_provider_contact')
    requests = []
    for index, (prompt, reply) in enumerate(SYNTHETIC_TURNS):
        page.locator('#prompt').fill(prompt)
        expect(page.locator('#consent')).not_to_be_checked()
        page.locator('#ask').click()
        expect(page.locator('#chat-status')).to_contain_text('请先确认')
        assert len(provider.snapshot()) == index, 'each new turn needs explicit consent'
        page.locator('#consent').check()
        with page.expect_response(lambda response:
                urlsplit(response.url).path == '/desktop-api/local-chat' and
                response.request.method == 'POST') as response_info:
            page.locator('#ask').click()
        response = response_info.value
        assert response.status == 200, 'synthetic desktop chat failed'
        result = response.json()
        request = response.request.post_data_json
        assert set(request) == {'consent', 'port', 'model', 'prompt', 'request_id'}
        assert request['consent'] is True and request['prompt'] == prompt
        assert request['model'] == SYNTHETIC_MODEL and request['port'] == provider.port
        assert str(UUID(request['request_id'])) == request['request_id']
        assert result['reply'] == reply and result['saved'] is True and result['replayed'] is False
        assert result['session_id'] == CHAT_SESSION and result['request_id'] == request['request_id']
        requests.append(request)
        expect(page.locator('#ask')).to_be_enabled()
        expect(page.locator('#consent')).not_to_be_checked()
        assert page.locator('#reply').text_content() == reply
        assert_history_ui(page, [content for pair in SYNTHETIC_TURNS[:index+1] for content in pair])
        assert len(provider.snapshot()) == index + 1
    assert len({request['request_id'] for request in requests}) == 2
    checks.extend(['model_default_no_consent_no_request', 'each_text_turn_requires_fresh_consent',
                   'native_two_turn_text_chat_saved', 'chat_text_verbatim_no_html_execution'])
    replay = page.evaluate("""async value => {
      const response = await fetch('/desktop-api/local-chat', {method: 'POST',
        headers: {'X-MyGPT-Client': 'mygpt-desktop-v1', 'Content-Type': 'application/json'},
        body: JSON.stringify(value)});
      return {status: response.status, value: await response.json()};
    }""", requests[-1])
    assert replay['status'] == 200 and replay['value']['replayed'] is True
    assert replay['value']['saved'] is True and replay['value']['reply'] == SYNTHETIC_TURNS[-1][1]
    assert replay['value']['request_id'] == requests[-1]['request_id']
    assert replay['value']['session_id'] == CHAT_SESSION
    assert len(provider.snapshot()) == 2, 'duplicate request must replay without another provider call'
    checks.append('native_text_duplicate_post_idempotent')
    with page.expect_response(lambda response: urlsplit(response.url).path == '/desktop-api/chat-history'):
        page.locator('#chat-refresh').click()
    assert_history_ui(page, [content for pair in SYNTHETIC_TURNS for content in pair])
    expect(page.locator('#chat-older')).to_be_disabled()
    verify_provider_requests(provider.snapshot())
    assert len(provider.snapshot()) == 2
    checks.extend(['second_provider_prompt_contains_exact_prior_pair', 'history_refresh_read_only'])
    return read_history(page), [request['request_id'] for request in requests]


def start(exe, home, tag):
    ready, stop = home / (tag + '.json'), home / (tag + '.stop')
    proc = subprocess.Popen([str(exe), '--headless', '--data-dir', str(home / 'user'),
                             '--ready-file', str(ready), '--stop-file', str(stop)],
                            **native_process_options(home))
    try:
        deadline = time.monotonic() + 80
        while not ready.exists():
            if proc.poll() is not None:
                raise RuntimeError('native application exited before readiness')
            if time.monotonic() > deadline:
                raise TimeoutError('native readiness')
            time.sleep(.15)
        url = json.loads(ready.read_text(encoding='utf-8'))['url']
        parsed = urlsplit(url)
        if parsed.scheme != 'http' or parsed.hostname != '127.0.0.1' or parsed.path != '/desktop/':
            raise ValueError('native readiness must use the loopback desktop origin')
        return proc, stop, url
    except BaseException:
        if proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=10)
        raise


def end(proc, stop):
    stop.write_text('stop', encoding='utf-8')
    try:
        proc.wait(timeout=20)
    except subprocess.TimeoutExpired:
        proc.terminate()
        proc.wait(timeout=10)
        raise
    assert proc.returncode == 0, 'native executable did not exit cleanly'


def verify_math(page, base, checks, out):
    from playwright.sync_api import expect
    response = page.request.get(base + '/third_party/katex/katex.mjs')
    assert response.status == 200
    assert hashlib.sha256(response.body()).hexdigest() == KATEX_SHA256
    checks.append('frozen_katex_http_pinned_bytes')
    # Legal notices belong in the package; they are never public HTTP endpoints.
    for name in ('LICENSE', 'NOTICE.md'):
        assert page.request.get(base + '/third_party/katex/' + name).status == 404
    checks.append('legal_notices_remain_unserved')
    page.goto(base + '/host/brain.html')
    expect(page.locator('body')).to_have_attribute('data-host-state', 'empty', timeout=25000)
    expect(page.locator('#records math').first).to_be_visible()
    bounds = page.locator('#records math').first.bounding_box()
    assert bounds and bounds['width'] > 0 and bounds['height'] > 0
    expect(page.locator('#request-count')).to_have_text('0')
    checks.append('native_brain_initial_mathml_no_model_request')
    page.locator('#select-record-1').select_option('a-source')
    expect(page.locator('body')).to_have_attribute('data-host-state', 'selected')
    expect(page.locator('#source-parts math')).to_have_count(1)
    selected = page.evaluate("""async () => {
      const {catalogue} = await import('/host/fixtures.js');
      const entry = catalogue.entries.find(item => item.id === 'a-source');
      return {latex:JSON.parse(entry.evidence_text).parts.find(p=>p.kind==='math').latex,
              sourceHash:entry.context.source_sha256, reply:entry.fixture_reply};
    }""")
    assert page.locator('#source-parts .math-raw').text_content() == selected['latex']
    expect(page.locator('#selected-hash')).to_have_text(selected['sourceHash'])
    checks.append('selected_mathml_preserves_exact_latex_and_source_hash')
    page.locator('#explain').click()
    expect(page.locator('body')).to_have_attribute('data-host-state', 'ready', timeout=30000)
    expect(page.locator('#reply-box')).to_be_visible()
    expect(page.locator('#reply')).to_have_text(selected['reply'])
    expect(page.locator('#selected-hash')).to_have_text(selected['sourceHash'])
    expect(page.locator('#model-calls')).to_have_text('0')
    checks.append('windows_loopback_brain_testmodel')
    # One app-page image only: fixed synthetic catalogue/reply, never the desktop.
    page.screenshot(path=str(out / 'native-math.png'), full_page=True)
    checks.append('synthetic_native_math_visual_evidence')
    bounded = page.evaluate(r"""async () => {
      const {renderSourceParts} = await import('/host/math-preview.js');
      const target = document.createElement('div');
      const unsafe = ['\\href{javascript:alert(1)}{x}', '\\includegraphics{https://invalid.example/never}',
        '\\htmlStyle{position:fixed}{x}', '\\def\\a{\\a}\\a', '\\unknownFunction{x}', '\\frac{1}{', 'x'.repeat(1001)];
      const exactFallback = unsafe.every(latex => {
        renderSourceParts(target, [{kind:'math',latex,display:true}]);
        return target.querySelectorAll('[data-math-preview="raw"]').length === 1 &&
          target.querySelector('.math-raw').textContent === latex &&
          !target.querySelector('math,[href],[src],script,iframe,img,svg,style');
      });
      renderSourceParts(target, Array.from({length:20},()=>({kind:'math',latex:'x+1',display:false})));
      const capped = target.querySelectorAll('math').length === 16 && target.querySelectorAll('[data-math-preview="raw"]').length === 4;
      renderSourceParts(target, [{kind:'math',latex:'z',display:false}]);
      const replaced = target.querySelectorAll('math').length === 1 && target.querySelector('.math-raw').textContent === 'z';
      renderSourceParts(target, []);
      return exactFallback && capped && replaced && target.childNodes.length === 0;
    }""")
    assert bounded, 'native browser math safety/replacement regression'
    checks.append('native_math_raw_fallback_bounds_replace_and_clear')


def main():
    if sys.platform != 'win32':
        raise RuntimeError('this verification requires the actual Windows executable')
    from playwright.sync_api import sync_playwright, expect
    exe, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    checks, errors, external_requests = [], [], []
    exe_sha256 = hashlib.sha256(exe.read_bytes()).hexdigest()
    report = {'ok': False, 'os': sys.platform, 'checks': checks,
              'native_math_preview': False, 'native_text_chat': False,
              'native_text_restart_restore': False, 'live_model_calls': 0,
              'model_kind': 'SYNTHETIC_OLLAMA_HTTP_FIXTURE',
              'exe_sha256': exe_sha256, 'actual_user_device_tested': False}
    proc = browser = stop = provider = None
    api_requests = []
    phase = 'first'
    with tempfile.TemporaryDirectory(prefix='mygpt-ui-') as tmp, sync_playwright() as pw:
        home = Path(tmp)
        try:
            provider = SyntheticOllama()
            proc, stop, url = start(exe, home, 'first')
            first_port = urlsplit(url).port
            browser = pw.chromium.launch(channel='msedge', headless=True)
            engine = 'Microsoft Edge'
            context = browser.new_context(viewport={'width': 1400, 'height': 950}, service_workers='block')
            base = url.removesuffix('/desktop/')

            def only_loopback(route):
                requested = urlsplit(route.request.url)
                if requested.scheme + '://' + requested.netloc != base:
                    external_requests.append('blocked_external_request')
                    return route.abort()
                return route.continue_()

            def record_request(request):
                path = urlsplit(request.url).path
                if path.startswith('/desktop-api/'):
                    api_requests.append({'phase': phase, 'method': request.method, 'path': path})

            def observe(context):
                context.route('**/*', only_loopback)
                context.on('request', record_request)
                context.on('page', lambda page: page.on('pageerror', lambda error: errors.append('javascript_error')))

            observe(context)
            page = context.new_page()
            page.on('dialog', lambda dialog: dialog.accept())
            page.goto(url)
            expect(page.locator('#status')).to_contain_text('本机记录已加载', timeout=25000)
            checks.append('workspace_load')
            page.locator('#goal').fill('测试学习目标')
            page.locator('#start').click()
            expect(page.locator('#finish')).to_be_enabled()
            checks.append('focus_start_saved')
            page.reload()
            expect(page.locator('#finish')).to_be_enabled()
            checks.append('active_timer_reload')
            page.locator('#finish').click()
            expect(page.locator('#sessions')).to_contain_text('测试学习目标')
            checks.append('focus_history_saved')
            page.locator('[data-tab=notes]').click()
            page.locator('#note-title').fill('Native note')
            page.locator('#note-body').fill('仅为测试的笔记')
            page.locator('#save-note').click()
            expect(page.locator('#status')).to_contain_text('已保存到本机')
            checks.append('note_save')
            with page.expect_download() as download:
                page.locator('#export').click()
            backup = home / 'backup.json'
            download.value.save_as(backup)
            assert json.loads(backup.read_text('utf-8'))['schema'] == 'mygpt-workspace-backup-v1'
            checks.append('backup_download')
            for _ in range(2):
                page.locator('#import').set_input_files(str(backup))
                expect(page.locator('#status')).to_contain_text('备份合并完成')
            assert page.locator('#notes .item').count() == 1
            checks.append('repeat_import_idempotent')
            verify_math(page, base, checks, out)
            page.goto(url)
            expect(page.locator('#status')).to_contain_text('本机记录已加载', timeout=25000)
            history, request_ids = verify_text_chat(page, provider, checks)
            before_rows = verify_chat_sqlite(home / 'user/data/chat.sqlite3', history, request_ids)
            checks.append('native_sqlite_exact_paired_qa_and_receipts')
            page.screenshot(path=str(out / 'native-text-chat.png'), full_page=True)
            page.goto(base + '/host/selection.html')
            expect(page.locator('#import')).to_be_disabled()
            checks.append('legacy_intake_default_disabled')
            page.close()
            end(proc, stop)
            checks.append('graceful_native_exit')
            provider.stop_provider()
            assert not provider.thread.is_alive()
            checks.append('synthetic_provider_stopped_before_restart')
            # Fresh Edge context prevents cookies, localStorage, or renderer state
            # from masquerading as durable native-history restoration.
            context.close()
            phase = 'restoration'
            with reserve_previous_port(first_port):
                proc, stop, url = start(exe, home, 'second')
                second_port = urlsplit(url).port
                assert second_port != first_port, 'restart must demonstrate a new loopback origin'
            checks.append('previous_loopback_port_reserved_during_restart')
            base = url.removesuffix('/desktop/')
            context = browser.new_context(viewport={'width': 1400, 'height': 950}, service_workers='block')
            observe(context)
            page = context.new_page()
            page.goto(url)
            expect(page.locator('#status')).to_contain_text('本机记录已加载', timeout=25000)
            # Startup itself must restore history before any chat refresh click.
            page.locator('[data-tab=chat]').click()
            expected_text = [content for pair in SYNTHETIC_TURNS for content in pair]
            assert_history_ui(page, expected_text)
            expect(page.locator('#consent')).not_to_be_checked()
            page.screenshot(path=str(out / 'native-text-restored.png'), full_page=True)
            assert read_history(page) == history
            with page.expect_response(lambda response: urlsplit(response.url).path == '/desktop-api/chat-history'):
                page.locator('#chat-refresh').click()
            assert_history_ui(page, expected_text)
            after_rows = verify_chat_sqlite(home / 'user/data/chat.sqlite3', read_history(page), request_ids)
            assert after_rows == before_rows, 'read-only restoration changed durable text or IDs'
            checks.extend(['native_new_port_startup_restores_chat_verbatim',
                           'offline_refresh_preserves_sqlite_messages_and_receipts'])
            page.locator('[data-tab=notes]').click()
            expect(page.locator('#notes')).to_contain_text('Native note')
            checks.append('native_restart_persistence')
            page.locator('#notes button').click()
            expect(page.locator('#note-body')).to_have_value('仅为测试的笔记')
            checks.append('restored_note_editable')
            page.goto(base + '/host/brain.html')
            expect(page.locator('body')).to_have_attribute('data-host-state', 'empty', timeout=25000)
            expect(page.locator('#records math').first).to_be_visible()
            checks.append('native_restart_mathml')
            assert not errors, 'browser JavaScript errors'
            assert not external_requests, 'browser attempted external network'
            checks.extend(['no_javascript_errors', 'no_external_browser_requests'])
            page.close()
            end(proc, stop)
            checks.append('second_graceful_native_exit')
            first_chat_posts = [entry for entry in api_requests if entry['phase'] == 'first'
                                and entry['path'] == '/desktop-api/local-chat']
            assert len(first_chat_posts) == 3 and all(entry['method'] == 'POST' for entry in first_chat_posts)
            assert len(provider.snapshot()) == 2
            assert provider.stopped_connection_attempts == 0, 'restoration attempted provider contact'
            restoration_requests = [entry for entry in api_requests if entry['phase'] == 'restoration']
            assert restoration_requests and all(entry['method'] == 'GET' for entry in restoration_requests)
            assert all(entry['path'] != '/desktop-api/local-chat' for entry in restoration_requests)
            assert hashlib.sha256(exe.read_bytes()).hexdigest() == exe_sha256
            checks.extend(['restart_and_refresh_no_provider_connection_or_chat_post',
                           'same_frozen_executable_both_launches'])
            report.update(ok=True, browser=engine, browser_version=browser.version,
                          native_math_preview=True, native_text_chat=True,
                          native_text_restart_restore=True,
                          text_chat={'session_id': CHAT_SESSION, 'turns': 2,
                              'first_port': first_port, 'second_port': second_port,
                              'previous_port_reserved': True,
                              'sqlite_rows': before_rows, 'request_ids': request_ids,
                              'read_only_restart_requests': restoration_requests})
        finally:
            report.update(javascript_error_count=len(errors), external_request_count=len(external_requests))
            if provider is not None:
                provider.close()
                report.update(synthetic_provider_calls=len(provider.snapshot()),
                              synthetic_model_calls=len(provider.snapshot()),
                              stopped_provider_connection_attempts=provider.stopped_connection_attempts,
                              synthetic_provider_requests=provider.snapshot())
            (out / 'browser.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            # These bytes can only come from the temporary synthetic native process.
            log = home / 'synthetic-profile/mygptDesktop/boot.log'
            (out / 'native-browser-diagnostics.txt').write_bytes(
                log.read_bytes() if log.is_file() else b'No synthetic native boot output.\n')
            if browser:
                browser.close()
            if proc is not None and proc.poll() is None:
                end(proc, stop)


if __name__ == '__main__':
    main()
