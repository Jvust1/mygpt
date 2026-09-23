// Real loopback browser -> Python Brain/TestModel integration; synthetic data only.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { spawn } = require('node:child_process');

function serverAddress(child) {
  return new Promise((resolve,reject)=>{
    let output='';
    const cleanup=()=>{clearTimeout(timer);child.stdout.off('data',data);child.off('error',fail);child.off('exit',exit);};
    const fail=e=>{cleanup();reject(e);},exit=code=>fail(new Error(`python server exited ${code}`));
    const data=b=>{output+=b;const m=output.match(/mygpt local brain: (http:\/\/127\.0\.0\.1:\d+)\r?\n/);if(m){cleanup();resolve(m[1]);}};
    const timer=setTimeout(()=>fail(new Error('python server startup timed out')),10000);
    child.stdout.on('data',data);child.on('error',fail);child.on('exit',exit);
  });
}

(async()=>{
  const out=process.env.MYGPT_TEST_OUTPUT||path.join(__dirname,'..','brain-host-test-output');
  fs.mkdirSync(out,{recursive:true});
  const report={result:'RUNNING',checks:[],errors:[],expectedHttpErrors:[],externalRequests:[],apiRequests:[],notVerified:[
    'real Book export','paid/live model quality','Android device','production multi-user transport','independent review']};
  const check=(name,value)=>{assert(value,name);report.checks.push(name);};
  const python=process.env.MYGPT_PYTHON||'python';
  const server=spawn(python,['-m','mygpt_brain.local_service','--port','0','--authorization-seconds','600','--demo-delay-ms','650'],{
    cwd:path.join(__dirname,'..'),stdio:['ignore','pipe','pipe'],
    env:{...process.env,PYTHONPATH:path.join(__dirname,'..','brain'),PYTHONUNBUFFERED:'1',OTEL_SDK_DISABLED:'true'}});
  let stderr='';server.stderr.on('data',b=>stderr+=b);
  let browser,page;
  try {
    const base=await serverAddress(server);check('server binds an ephemeral 127.0.0.1 origin',/^http:\/\/127\.0\.0\.1:\d+$/.test(base));
    browser=await chromium.launch({headless:true,...(process.env.MYGPT_CHROMIUM_PATH?{
      executablePath:process.env.MYGPT_CHROMIUM_PATH,args:['--no-sandbox','--disable-dev-shm-usage']}: {})});
    report.browser=browser.version();report.node=process.version;report.playwright=require('playwright/package.json').version;
    const context=await browser.newContext({viewport:{width:393,height:852},isMobile:true,hasTouch:true,deviceScaleFactor:1});
    await context.route('**/*',route=>{
      const url=new URL(route.request().url());
      if(url.origin!==base){report.externalRequests.push(route.request().url());return route.abort();}
      if(url.pathname.startsWith('/api/'))report.apiRequests.push({method:route.request().method(),path:url.pathname});
      return route.continue();
    });
    page=await context.newPage();page.setDefaultTimeout(10000);
    page.on('pageerror',e=>report.errors.push(e.message));
    page.on('console',m=>{
      if(m.type()!=='error')return;
      const text=m.text();
      const match=text.match(/Failed to load resource: the server responded with a status of (403|409)/);
      if(match) report.expectedHttpErrors.push(Number(match[1]));
      else report.errors.push(text);
    });
    const state=()=>page.locator('body').getAttribute('data-host-state');
    const wait=s=>page.waitForFunction(x=>document.body.dataset.hostState===x,s);
    const choose=id=>page.locator(`#select-record-${id.startsWith('b-')?'2':'1'}`).selectOption(id);
    const status=()=>page.evaluate(async()=>{
      const r=await fetch('/api/v1/status',{credentials:'same-origin',cache:'no-store',headers:{'X-MyGPT-Client':'mygpt-reader-brain-v1'}});
      return {status:r.status,body:await r.json()};
    });
    await page.goto(base+'/host/brain.html');await wait('empty');
    await page.waitForFunction(()=>document.querySelector('#pet')._image?.complete);
    check('visible notice says local Python Brain and no Book connection',await page.locator('#transport-notice').innerText().then(t=>t.includes('本机 Python Brain 已连接')&&t.includes('Book 未连接')));
    check('authorization cookie is HttpOnly to page script',await page.evaluate(()=>document.cookie)==='');
    let s=await status();check('status proves TestModel-only local service',s.status===200&&s.body.test_model===true&&s.body.paid_model_calls===0&&s.body.live_book_connected===false);
    check('selection controls enabled only after status succeeds',!(await page.locator('#mode').isDisabled()));
    await choose('a-correction');await wait('selected');
    check('selection alone has not invoked Python explain', (await status()).body.requests_started===0);
    await page.locator('#explain').tap();await wait('working');
    check('working state represents a real pending loopback request',await page.$eval('#pet',p=>p.status==='working'));
    await page.waitForTimeout(100);await page.locator('#cancel').tap();await wait('selected');
    await page.waitForFunction(async()=>{const r=await fetch('/api/v1/status',{credentials:'same-origin',headers:{'X-MyGPT-Client':'mygpt-reader-brain-v1'}});const j=await r.json();return j.cancel_requests>=1&&j.requests_cancelled>=1;});
    check('browser abort reaches bounded Python cancel endpoint',true);
    await page.waitForTimeout(750);check('cancelled Python result never appears late',await page.locator('#reply-box').isHidden());
    await page.locator('#explain').tap();await wait('ready');
    check('successful answer came through Python TestModel fixture',await page.locator('#reply').innerText().then(t=>t.includes('预先编写的演示回复')));
    s=await status();check('Python records one completed request and zero paid calls',s.body.requests_completed===1&&s.body.paid_model_calls===0);
    await page.screenshot({path:path.join(out,'brain-mobile-ready.png')});
    for(const id of ['a-source','a-hint','a-solution','b-source']){
      await choose(id);await page.locator('#explain').tap();await wait('ready');
      check(`Python path preserves ${id} selection identity`,await page.locator('#selected-title').innerText().then(t=>t.includes(id==='b-source'?'练习 B':'练习 A')));
    }
    const invalid=await page.evaluate(async()=>{
      const r=await fetch('/api/v1/explain',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-MyGPT-Client':'mygpt-reader-brain-v1'},body:JSON.stringify({
        schema_version:'mygpt.local-explain.v1',scope:'SYNTHETIC_FIXED_REPLAY',request_id:'forged-browser-1',revision:1,
        entry_id:'a-source',mode:'learn',source_ref:'reader:v2:forged',source_sha256:'a'.repeat(64),selection_expires_at_ms:Date.now()+60000})});
      return {status:r.status,body:await r.json()};
    });
    check('forged browser source identity is rejected by Python',invalid.status===409&&invalid.body.code==='source_identity_mismatch');
    await page.locator('.scope summary').click();await page.locator('#revoke').click();await wait('revoked');
    const after=await page.evaluate(async()=>{const r=await fetch('/api/v1/status',{credentials:'same-origin',headers:{'X-MyGPT-Client':'mygpt-reader-brain-v1'}});return r.status;});
    check('explicit revocation blocks the server authorization',after===403);
    check('revocation disables selection controls',await page.locator('#select-record-1').isDisabled()&&await page.locator('#mode').isDisabled());
    check('no external browser requests',report.externalRequests.length===0);
    check('API surface used only allowlisted paths',report.apiRequests.every(x=>['/api/v1/status','/api/v1/explain','/api/v1/cancel','/api/v1/revoke'].includes(x.path)));
    check('model-call counter stays zero',await page.locator('#model-calls').innerText()==='0');
    check('only the two intentional negative HTTP fetches reached console error status',
      report.expectedHttpErrors.length===2&&report.expectedHttpErrors.includes(409)&&report.expectedHttpErrors.includes(403));
    check('no runtime/CSP errors',report.errors.length===0);
    report.result='PASS';
  } catch(error) {
    report.result='FAIL';report.failure=String(error);report.serverStderr=stderr.slice(-4000);
    if(page)await page.screenshot({path:path.join(out,'failure.png')}).catch(()=>{});
    throw error;
  } finally {
    fs.writeFileSync(path.join(out,'brain-host-browser-report.json'),JSON.stringify(report,null,2)+'\n');
    console.log(JSON.stringify(report,null,2));
    try{await browser?.close();}finally{server.kill('SIGTERM');setTimeout(()=>server.kill('SIGKILL'),1500).unref();}
  }
})().catch(error=>{console.error(error);process.exitCode=1;});
