// Browser integration on a test-owned loopback server; no live Book/model calls.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { spawn } = require('node:child_process');

function address(server) {
  return new Promise((resolve,reject)=>{
    let output='';
    const cleanup=()=>{clearTimeout(timer);server.stdout.off('data',data);server.off('error',fail);server.off('exit',exit);};
    const fail=e=>{cleanup();reject(e);},exit=code=>fail(new Error(`server exited ${code}`));
    const data=b=>{output+=b;const m=output.match(/mygpt companion preview: (http:\/\/127\.0\.0\.1:\d+)\r?\n/);if(m){cleanup();resolve(m[1]);}};
    const timer=setTimeout(()=>fail(new Error('server startup timed out')),5000);
    server.stdout.on('data',data);server.on('error',fail);server.on('exit',exit);
  });
}
(async()=>{
  const out=process.env.MYGPT_TEST_OUTPUT||path.join(__dirname,'..','host-test-output');
  fs.mkdirSync(out,{recursive:true});
  const report={result:'RUNNING',checks:[],errors:[],externalRequests:[],notVerified:[
    'Android physical device','real Book export/transport','live Python Brain in browser','real model quality','independent review']};
  const check=(name,value)=>{assert(value,name);report.checks.push(name);};
  const server=spawn(process.execPath,[path.join(__dirname,'..','scripts','serve.mjs')],{
    stdio:['ignore','pipe','inherit'],env:{...process.env,PORT:'0'}});
  let browser,page;
  try {
    const base=await address(server);
    browser=await chromium.launch({headless:true,...(process.env.MYGPT_CHROMIUM_PATH?{
      executablePath:process.env.MYGPT_CHROMIUM_PATH,args:['--no-sandbox','--disable-dev-shm-usage']}: {})});
    report.browser=browser.version();report.node=process.version;report.playwright=require('playwright/package.json').version;
    const context=await browser.newContext({viewport:{width:393,height:852},isMobile:true,hasTouch:true,deviceScaleFactor:1});
    await context.route('**/*',route=>{
      if(new URL(route.request().url()).origin!==base){report.externalRequests.push(route.request().url());return route.abort();}
      return route.continue();
    });
    page=await context.newPage();page.setDefaultTimeout(7000);
    page.on('pageerror',e=>report.errors.push(e.message));
    page.on('console',m=>{if(m.type()==='error')report.errors.push(m.text());});
    const state=()=>page.locator('body').getAttribute('data-host-state');
    const wait=desired=>page.waitForFunction(s=>document.body.dataset.hostState===s,desired);
    const count=()=>page.locator('#request-count').innerText();
    const choose=id=>page.locator(`#select-record-${id.startsWith('b-')?'2':'1'}`).selectOption(id);
    const fits=async name=>check(name,await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    await page.goto(base+'/host/reader.html');await wait('empty');
    await page.waitForFunction(()=>document.querySelector('#pet')._image?.complete);
    check('no initial selection or request',await count()==='0'&&await page.locator('#explain').isDisabled());
    check('simulation boundary is visible',await page.locator('.notice').innerText().then(t=>t.includes('Book 未连接')&&t.includes('预写样本')));
    check('local sprite loads',await page.$eval('#pet',p=>!p.hasAttribute('asset-error')));
    await fits('393px mobile has no horizontal overflow');
    check('docked pet does not overlap the reading viewport',await page.evaluate(()=>document.querySelector('main').getBoundingClientRect().bottom<=document.querySelector('#pet').getBoundingClientRect().top));
    await page.screenshot({path:path.join(out,'host-mobile-initial.png')});
    await page.locator('mygpt-pet .avatar').tap();await page.locator('mygpt-pet [data-action="chat"]').tap();
    check('Jonah event opens panel without sending',await page.locator('#help-panel').isVisible()&&await count()==='0');
    check('opening help transfers focus',await page.locator('#help-heading').evaluate(e=>document.activeElement===e));
    await page.keyboard.press('Escape');
    check('Escape closes panel and returns focus',await page.locator('#help-panel').isHidden()&&await page.$eval('#pet',p=>p.shadowRoot.activeElement===p._avatar));
    await choose('a-source');await wait('selected');
    check('explicit selection opens context, still no request',await count()==='0'&&await page.locator('#selected-context').isVisible());
    check('version @ and original layer shown',await page.locator('#selected-version').innerText().then(t=>t.includes('@'))&&await page.locator('#selected-layer').innerText().then(t=>t.includes('原文')));
    await page.locator('#explain').tap();await wait('working');
    check('working state follows actual UI request',await page.$eval('#pet',p=>p.status==='working')&&await page.locator('#cancel').isVisible());
    await page.locator('#cancel').tap();await wait('selected');await page.waitForTimeout(800);
    check('cancel immediately returns control and no late answer',await page.locator('#reply-box').isHidden()&&await count()==='1');
    await page.locator('#explain').tap();await wait('ready');
    check('replay result visibly non-AI and pet ready',await page.locator('#reply-heading').innerText().then(t=>t.includes('非实时'))&&await page.$eval('#pet',p=>p.status==='ready'));
    await page.screenshot({path:path.join(out,'host-mobile-reply.png')});
    for(const id of ['a-correction','a-hint','a-solution','b-source']) {
      await choose(id);await page.locator('#explain').tap();await wait('ready');
      check(`layer ${id} replies with matching selected title`,await page.locator('#selected-title').innerText().then(t=>t.includes(id==='b-source'?'练习 B':'练习 A'))&&await page.locator('#reply').innerText().then(t=>t.includes('预先编写')));
    }
    await choose('a-source');await page.locator('#explain').tap();await wait('working');
    await choose('b-source');await page.waitForTimeout(800);
    check('changing record clears and suppresses old reply',await state()==='selected'&&await page.locator('#reply-box').isHidden());
    for(const mode of ['preview','review','practice','learn']) {
      await page.locator('#mode').selectOption(mode);await wait('empty');
      check(`mode ${mode} requires a new explicit selection`,await page.locator('#explain').isDisabled());await choose('a-source');
    }
    await page.locator('#explain').tap();await wait('working');await page.locator('#close-panel').tap();
    await page.waitForTimeout(800);check('closing panel cancels request',await state()==='selected'&&await page.locator('#reply-box').isHidden());
    await page.locator('#open-panel').tap();await page.locator('#explain').tap();await wait('working');
    await page.locator('#pause').tap();await page.waitForTimeout(800);
    check('pause drops context and all pending answers',await state()==='paused'&&await page.locator('#selected-context').isHidden()&&await page.$eval('#pet',p=>p._timer===null));
    await choose('a-source');await page.locator('#explain').tap();await wait('working');
    await page.evaluate(()=>window.dispatchEvent(new PageTransitionEvent('pagehide',{persisted:true})));
    await page.waitForTimeout(800);await page.evaluate(()=>window.dispatchEvent(new PageTransitionEvent('pageshow',{persisted:true})));
    check('synthetic BFCache lifecycle does not auto resume',await state()==='paused'&&await page.locator('#reply-box').isHidden());
    await choose('a-source');await page.locator('#toggle-pet').tap();
    check('hiding pet pauses without removing help entry',await state()==='paused'&&await page.locator('#pet').isHidden()&&await page.locator('#open-panel').isVisible());
    await page.locator('#toggle-pet').tap();check('showing pet does not silently resume',await state()==='paused');
    await choose('a-source');await page.evaluate(()=>{const original=Date.now;Date.now=()=>original()+121000;});
    await page.locator('#explain').tap();await wait('expired');
    check('clock-expired selection is blocked before sending',await page.locator('#selected-context').isHidden()&&await page.$eval('#pet',p=>p.status==='blocked'));
    await page.reload();await wait('empty');await choose('a-source');
    await page.emulateMedia({reducedMotion:'reduce'});await page.waitForFunction(()=>document.querySelector('#pet')._timer===null);check('reduced motion remains respected',await page.$eval('#pet',p=>p._timer===null));
    await page.locator('.scope summary').click();await page.locator('#revoke').click();await wait('revoked');
    check('disable closes this instance with selection controls disabled',await page.locator('#select-record-1').isDisabled()&&await page.locator('#mode').isDisabled());
    await page.reload();await wait('empty');
    check('reload restores no content or stale selection',await count()==='0'&&await page.locator('#select-record-1').inputValue()==='');
    for(const size of [{width:320,height:568},{width:640,height:280},{width:1280,height:900}]){
      await page.setViewportSize(size);await fits(`${size.width}px viewport has no horizontal overflow`);
    }
    await page.waitForTimeout(80);
    await choose('a-solution');await page.locator('#explain').click();await wait('ready');await page.evaluate(()=>document.querySelector('main').scrollTo(0,0));
    await page.screenshot({path:path.join(out,'host-desktop-reply.png')});
    await page.locator('#close-panel').click();await page.locator('mygpt-pet .avatar').focus();await page.keyboard.press('Enter');
    await page.keyboard.press('Enter');check('keyboard can open Jonah then host panel',await page.locator('#help-panel').isVisible()&&await page.locator('#help-heading').evaluate(e=>document.activeElement===e));
    await context.addInitScript(()=>{Storage.prototype.getItem=()=>{throw new Error('disabled');};Storage.prototype.setItem=()=>{throw new Error('disabled');};});
    await page.reload();await wait('empty');await choose('a-source');await page.locator('#explain').click();await wait('ready');
    check('storage disabled still permits explicit replay',await page.locator('#reply-box').isVisible());
    check('no runtime or CSP errors',report.errors.length===0);
    check('no external requests',report.externalRequests.length===0);
    check('model-call counter never changes',await page.locator('#model-calls').innerText()==='0');
    report.result='PASS';
  } catch(error) {
    report.result='FAIL';report.failure=String(error);if(page)await page.screenshot({path:path.join(out,'failure.png')}).catch(()=>{});throw error;
  } finally {
    fs.writeFileSync(path.join(out,'host-browser-report.json'),JSON.stringify(report,null,2)+'\n');
    console.log(JSON.stringify(report,null,2));
    try{await browser?.close();}finally{server.kill('SIGTERM');}
  }
})().catch(error=>{console.error(error);process.exitCode=1;});
