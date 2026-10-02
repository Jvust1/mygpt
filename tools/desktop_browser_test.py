"""Real Windows executable plus browser math/persistence; synthetic data only."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright, expect
from build_windows_delivery import native_process_options

KATEX_SHA256 = '694a531495903e374957e9a9c904a402e2f413762635df486c4cf6163320d1aa'


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
    exe, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    checks, errors, external_requests = [], [], []
    report = {'ok': False, 'os': sys.platform, 'checks': checks,
              'native_math_preview': False, 'live_model_calls': 0,
              'actual_user_device_tested': False}
    proc = browser = stop = None
    with tempfile.TemporaryDirectory(prefix='mygpt-ui-') as tmp, sync_playwright() as pw:
        home = Path(tmp)
        try:
            proc, stop, url = start(exe, home, 'first')
            try:
                browser = pw.chromium.launch(channel='msedge', headless=True)
                engine = 'Microsoft Edge'
            except Exception:
                browser = pw.chromium.launch(headless=True)
                engine = 'Chromium fallback'
            context = browser.new_context(viewport={'width': 1400, 'height': 950}, service_workers='block')
            base = url.removesuffix('/desktop/')

            def only_loopback(route):
                requested = urlsplit(route.request.url)
                if requested.scheme + '://' + requested.netloc != base:
                    external_requests.append('blocked_external_request')
                    return route.abort()
                return route.continue_()

            context.route('**/*', only_loopback)
            context.on('page', lambda page: page.on('pageerror', lambda error: errors.append('javascript_error')))
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
            page.locator('[data-tab=chat]').click()
            page.locator('#ask').click()
            expect(page.locator('#chat-status')).to_contain_text('请先确认')
            checks.append('model_default_no_consent_no_request')
            page.goto(base + '/host/selection.html')
            expect(page.locator('#import')).to_be_disabled()
            checks.append('legacy_intake_default_disabled')
            page.close()
            end(proc, stop)
            checks.append('graceful_native_exit')
            proc, stop, url = start(exe, home, 'second')
            base = url.removesuffix('/desktop/')
            page = context.new_page()
            page.goto(url)
            expect(page.locator('#status')).to_contain_text('本机记录已加载', timeout=25000)
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
            report.update(ok=True, browser=engine, browser_version=browser.version,
                          native_math_preview=True)
        finally:
            report.update(javascript_error_count=len(errors), external_request_count=len(external_requests))
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
