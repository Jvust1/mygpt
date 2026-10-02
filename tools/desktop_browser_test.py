"""Native Windows executable plus real browser; no live models or user files."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from playwright.sync_api import sync_playwright, expect
exe=Path(sys.argv[1]).resolve();out=Path(sys.argv[2]);checks=[];errors=[]
def start(home,tag):
    ready=home/(tag+'.json');stop=home/(tag+'.stop')
    p=subprocess.Popen([str(exe),'--headless','--data-dir',str(home/'user'),'--ready-file',str(ready),'--stop-file',str(stop)])
    deadline=time.monotonic()+80
    while not ready.exists():
        if p.poll() is not None:raise RuntimeError('native application exited')
        if time.monotonic()>deadline:p.terminate();p.wait(timeout=10);raise TimeoutError('native readiness')
        time.sleep(.15)
    return p,stop,json.loads(ready.read_text())['url']
def end(p,stop):
    stop.write_text('stop');p.wait(timeout=20);assert p.returncode==0
with tempfile.TemporaryDirectory(prefix='mygpt-ui-') as tmp,sync_playwright() as pw:
    home=Path(tmp);proc,stop,url=start(home,'first');browser=None
    try:
        try:browser=pw.chromium.launch(channel='msedge',headless=True);engine='Microsoft Edge'
        except Exception:browser=pw.chromium.launch(headless=True);engine='Chromium fallback'
        page=browser.new_page(viewport={'width':1400,'height':950});page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('dialog',lambda d:d.accept())
        page.goto(url);expect(page.locator('#status')).to_contain_text('本机记录已加载',timeout=25000);checks.append('workspace_load')
        page.locator('#goal').fill('测试学习目标');page.locator('#start').click()
        expect(page.locator('#finish')).to_be_enabled();checks.append('focus_start_saved')
        page.reload();expect(page.locator('#finish')).to_be_enabled();checks.append('active_timer_reload')
        page.locator('#finish').click();expect(page.locator('#sessions')).to_contain_text('测试学习目标');checks.append('focus_history_saved')
        page.locator('[data-tab=notes]').click();page.locator('#note-title').fill('Native note');page.locator('#note-body').fill('仅为测试的笔记')
        page.locator('#save-note').click();expect(page.locator('#status')).to_contain_text('已保存到本机');checks.append('note_save')
        with page.expect_download() as dl:page.locator('#export').click()
        backup=home/'backup.json';dl.value.save_as(backup);data=json.loads(backup.read_text('utf-8'))
        assert data['schema']=='mygpt-workspace-backup-v1';checks.append('backup_download')
        for _ in range(2):
            page.locator('#import').set_input_files(str(backup));expect(page.locator('#status')).to_contain_text('备份合并完成')
        assert page.locator('#notes .item').count()==1;checks.append('repeat_import_idempotent')
        page.screenshot(path=str(out/'mygpt-notes.png'),full_page=True)
        brain_url=url.replace('/desktop/','/host/brain.html')
        page.goto(brain_url);expect(page.locator('body')).to_have_attribute('data-host-state','empty',timeout=25000)
        page.locator('#select-record-1').select_option('a-source')
        expect(page.locator('body')).to_have_attribute('data-host-state','selected')
        page.locator('#explain').click()
        expect(page.locator('body')).to_have_attribute('data-host-state','ready',timeout=30000)
        assert page.locator('#reply-box').is_visible();assert page.locator('#model-calls').inner_text()=='0'
        checks.append('windows_loopback_brain_testmodel')
        page.goto(url);expect(page.locator('#status')).to_contain_text('本机记录已加载',timeout=25000)
        page.locator('[data-tab=chat]').click();page.locator('#ask').click()
        expect(page.locator('#chat-status')).to_contain_text('请先确认');checks.append('model_default_no_consent_no_request')
        page.goto(url.replace('/desktop/','/host/selection.html'))
        expect(page.locator('#import')).to_be_disabled();checks.append('legacy_intake_default_disabled')
        page.close();end(proc,stop);checks.append('graceful_native_exit')
        proc,stop,url=start(home,'second');page=browser.new_page();page.goto(url)
        expect(page.locator('#status')).to_contain_text('本机记录已加载',timeout=25000)
        page.locator('[data-tab=notes]').click();expect(page.locator('#notes')).to_contain_text('Native note');checks.append('native_restart_persistence')
        page.locator('#notes button').click();expect(page.locator('#note-body')).to_have_value('仅为测试的笔记');checks.append('restored_note_editable')
        assert not errors,errors;checks.append('no_javascript_errors')
        (out/'browser.json').write_text(json.dumps({'ok':True,'os':sys.platform,'browser':engine,'checks':checks,'javascript_errors':errors,'live_model_calls':0},ensure_ascii=False,indent=2),encoding='utf-8')
    except BaseException:
        if browser:
            try:page.screenshot(path=str(out/'failure.png'),full_page=True)
            except Exception:pass
        for p in (home/'user').glob('*.log'):(out/p.name).write_bytes(p.read_bytes())
        raise
    finally:
        if browser:browser.close()
        if proc.poll() is None:end(proc,stop)
