// Developer-only browser check. Requires Playwright and its Chromium binary.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { spawn } = require('node:child_process');

async function waitForServer(url, timeout=5000) {
  const started=Date.now();
  while(Date.now()-started<timeout) {
    try { const response=await fetch(url); if(response.ok) return; } catch {}
    await new Promise(resolve=>setTimeout(resolve,50));
  }
  throw new Error(`Preview server did not start within ${timeout}ms`);
}

(async () => {
  const server=spawn(process.execPath,[path.join(__dirname,'..','scripts','serve.mjs')],{stdio:'ignore'});
  await waitForServer('http://127.0.0.1:4173/');
  const browser = await chromium.launch({ headless: true, ...(process.env.MYGPT_CHROMIUM_PATH ? { executablePath:process.env.MYGPT_CHROMIUM_PATH, args:['--no-sandbox','--disable-dev-shm-usage'] } : {}) });
  const context = await browser.newContext({ viewport: { width: 393, height: 852 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2 });
  const page = await context.newPage();
  const errors = [], external = [], checks = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('console', message => { if (message.type()==='error') errors.push(message.text()); });
  page.on('response', response => { if (!response.ok()) errors.push(`${response.status()} ${response.url()}`); });
  page.on('request', request => { if (!request.url().startsWith('http://127.0.0.1:4173/')) external.push(request.url()); });
  const verify = (name, ok) => { assert(ok, name); checks.push(name); };
  const state = () => page.$eval('#pet', p => ({ row:p._row, column:p._column, timer:p._timer, hidden:p.hidden, status:p.status, error:p.hasAttribute('asset-error') }));
  const bounds = () => page.$eval('#pet', p => { const r=p.getBoundingClientRect(); return { x:r.x,y:r.y,right:r.right,bottom:r.bottom,width:r.width,height:r.height }; });
  const inside = async (name) => {
    const r=await bounds(), v=page.viewportSize();
    assert(r.x>=0&&r.y>=0&&r.right<=v.width+1&&r.bottom<=v.height+1, `${name}: ${JSON.stringify({r,v})}`); checks.push(name);
  };
  try {
    await page.goto('http://127.0.0.1:4173/');
    await page.waitForFunction(() => customElements.get('mygpt-pet') && document.querySelector('#pet')._image?.complete, null, { timeout:10000 }).catch(async error => {
      throw new Error(`${error.message}; browser errors: ${errors.join(' | ') || 'none'}; debug: ${JSON.stringify(await page.evaluate(() => ({ defined:!!customElements.get('mygpt-pet'), image:document.querySelector('#pet')?._image?.src || null, ready:document.readyState })))}`);
    });
    verify('sprite decoded without error', !(await state()).error);
    const initial=await bounds();
    verify('initial anchor is bottom-right', initial.x > 230 && initial.bottom > 700 && initial.bottom < 852);
    await inside('mobile pet fits viewport');
    await page.waitForTimeout(360);
    verify('animation advances beyond first frame', (await state()).column>0);
    for (const [status,row] of [['working',7],['needs-input',6],['ready',3],['blocked',5],['idle',0]]) {
      await page.locator(`[data-status="${status}"]`).click();
      verify(`host status ${status} maps to expected atlas row`, (await state()).row===row);
    }
    await page.locator('mygpt-pet .avatar').tap();
    verify('touch tap opens controls', await page.locator('mygpt-pet .panel').isVisible());
    await page.locator('mygpt-pet [data-action="chat"]').tap();
    verify('chat event reaches host UI', await page.locator('#chat').isVisible());
    await page.locator('#close-chat').click();
    await page.evaluate(() => window.scrollTo(0,0));
    await page.locator('#reset').click();
    await page.evaluate(() => window.scrollTo(0,0));
    const avatar=await page.locator('mygpt-pet .avatar').boundingBox();
    const session=await context.newCDPSession(page);
    const x=avatar.x+avatar.width/2,y=avatar.y+avatar.height/2;
    await session.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x,y}]});
    await session.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x:90,y:260}]});
    await session.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
    verify('touch drag changes location', (await bounds()).x<160);
    verify('drag does not open controls', !(await page.locator('mygpt-pet .panel').isVisible()));
    await inside('drag position stays on screen');
    const dragged=await bounds();
    await page.reload();
    verify('position restores after reload', Math.abs((await bounds()).x-dragged.x)<2);
    await page.locator('#visibility').click();
    verify('hidden pet stops animation timer', (await state()).hidden&&(await state()).timer===null);
    await page.reload();
    verify('hidden choice survives reload', (await state()).hidden);
    await page.locator('#visibility').click();
    verify('host control restores pet', !(await state()).hidden);
    await page.emulateMedia({ reducedMotion:'reduce' });
    await page.waitForFunction(() => document.querySelector('#pet')._timer===null);
    verify('reduced motion stops timers', (await state()).timer===null);
    const frozen=(await state()).column; await page.waitForTimeout(400);
    verify('reduced motion remains still', (await state()).column===frozen);
    await page.emulateMedia({ reducedMotion:'no-preference' });
    await page.evaluate(() => document.querySelector('#pet').setAttribute('paused',''));
    verify('manual pause stops timer', (await state()).timer===null);
    for(let angle=0;angle<360;angle+=22.5) {
      await page.$eval('#pet',(p,a)=>p.look(a),angle);
      const s=await state(),n=Math.round(angle/22.5);
      verify(`look ${angle} selects correct frame`, s.row===9+Math.floor(n/8)&&s.column===n%8);
    }
    await page.$eval('#pet',p=>{p.resume();p.removeAttribute('paused');p.resetPosition();});
    await page.setViewportSize({ width:320,height:568 }); await page.waitForTimeout(100); await inside('narrow viewport fits');
    await page.setViewportSize({ width:640,height:280 });
    await page.waitForTimeout(100);
    await page.locator('mygpt-pet .label').click();
    await inside('landscape controls fit');
    await page.locator('mygpt-pet [data-action="reset"]').click();
    await page.setViewportSize({ width:393,height:852 }); await page.waitForTimeout(100);
    await page.$eval('#pet',p=>{p.resetPosition();p.status='idle';});
    await page.evaluate(() => window.scrollTo(0,0));
    const out=process.env.MYGPT_TEST_OUTPUT||path.join(__dirname,'..','test-output');fs.mkdirSync(out,{recursive:true});
    await page.screenshot({path:path.join(out,'jonah-mobile.png'),fullPage:false});
    await page.setViewportSize({width:1280,height:900});
    await page.waitForTimeout(100);
    await page.$eval('#pet',p=>p.resetPosition());
    await inside('desktop viewport fits');
    await page.screenshot({path:path.join(out,'jonah-desktop.png'),fullPage:false});
    // Detached elements must release timers and handlers before reconnecting.
    const detached=await page.evaluate(()=>{window.petTest=document.querySelector('#pet');petTest.remove();return petTest._timer===null&&petTest._events===null;});
    verify('disconnect cleans up timer and event handlers',detached);
    await page.evaluate(()=>document.body.append(window.petTest));
    verify('reconnect resumes animation', (await state()).timer!==null);
    // Privacy-preserving fallback: disabled local storage must not break rendering.
    await context.addInitScript(() => { Storage.prototype.getItem=()=>{throw new Error('disabled')}; Storage.prototype.setItem=()=>{throw new Error('disabled')}; });
    await page.reload();
    await page.locator('#visibility').click(); await page.locator('#visibility').click();
    verify('storage denial is handled', !(await state()).hidden);
    verify('no runtime exceptions',errors.length===0); verify('no external network requests',external.length===0);
    const report={result:'PASS',checks,errors,externalRequests:external,notVerified:['Android physical device','native Android overlay','production chat or Book bridge','independent human review']};
    fs.writeFileSync(path.join(out,'browser-report.json'),JSON.stringify(report,null,2)+'\n');
    console.log(JSON.stringify(report,null,2));
  } finally { await browser.close(); server.kill('SIGTERM'); }
})().catch(error=>{console.error(error);process.exitCode=1;});
