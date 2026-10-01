// Real Chromium -> real loopback intake -> actual pinned KaTeX DOM rendering.
// All source data is synthetic; no model, clipboard, remote font or private data.
const {chromium}=require('playwright');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {spawn}=require('node:child_process'),{createHash}=require('node:crypto');
const root=path.join(__dirname,'..');
const sorted=x=>Array.isArray(x)?x.map(sorted):x&&typeof x==='object'?Object.fromEntries(Object.keys(x).sort().map(k=>[k,sorted(x[k])])):x;
function address(child){return new Promise((resolve,reject)=>{
  let text='';const stop=()=>{clearTimeout(timer);child.stdout.off('data',data);child.off('error',fail);child.off('exit',exit);};
  const fail=e=>{stop();reject(e);},exit=c=>fail(new Error('server exited '+c));
  const data=b=>{text+=b;const m=text.match(/mygpt local brain: (http:\/\/127\.0\.0\.1:\d+)\r?\n/);if(m){stop();resolve(m[1]);}};
  const timer=setTimeout(()=>fail(new Error('startup timeout')),10000);
  child.stdout.on('data',data);child.on('error',fail);child.on('exit',exit);
});}
(async()=>{
  const out=process.env.MYGPT_TEST_OUTPUT||path.join(root,'test-output','math-preview');fs.mkdirSync(out,{recursive:true});
  const report={result:'RUNNING',checks:[],errors:[],externalRequests:[],apiRequests:[],maxRenderMillis:0};
  const check=(name,ok)=>{assert(ok,name);report.checks.push(name);};
  const server=spawn(process.env.MYGPT_PYTHON||'python',['-m','mygpt_brain.local_service','--port','0','--enable-selection-intake','--demo-delay-ms','100'],{
    cwd:root,stdio:['ignore','pipe','pipe'],env:{...process.env,PYTHONPATH:path.join(root,'brain'),PYTHONUNBUFFERED:'1',OTEL_SDK_DISABLED:'true'}});
  let browser,stderr='';server.stderr.on('data',x=>stderr+=x);
  try{
    const base=await address(server);
    browser=await chromium.launch({headless:true,...(process.env.MYGPT_CHROMIUM_PATH?{executablePath:process.env.MYGPT_CHROMIUM_PATH,args:['--no-sandbox','--disable-dev-shm-usage']}: {})});
    report.browser=browser.version();report.playwright=require('playwright/package.json').version;
    const context=await browser.newContext({viewport:{width:393,height:852},isMobile:true,hasTouch:true});
    await context.route('**/*',route=>{
      const u=new URL(route.request().url());
      if(u.origin!==base){report.externalRequests.push(u.origin);return route.abort();}
      if(u.pathname.startsWith('/api/'))report.apiRequests.push(u.pathname);
      return route.continue();
    });
    const page=await context.newPage();page.setDefaultTimeout(8000);
    page.on('pageerror',e=>report.errors.push(e.message));
    page.on('console',m=>{if(m.type()==='error')report.errors.push(m.text());});
    await page.goto(base+'/host/brain.html');
    await page.waitForFunction(()=>document.body.dataset.hostState==='empty');
    check('actual Brain page renders pinned KaTeX MathML',await page.locator('#records math').count()>0);
    check('presentation does not call Brain',!report.apiRequests.includes('/api/v1/explain'));
    await page.locator('#select-record-1').selectOption('a-source');
    check('selected context also renders MathML',await page.locator('#selected-context math').count()>0);
    await page.locator('#explain').click();await page.waitForFunction(()=>document.body.dataset.hostState==='ready');
    check('existing Brain response and source identity still work',await page.locator('#reply').innerText().then(t=>t.includes('SIMULATED')));
    await page.goto(base+'/host/selection.html');
    await page.waitForFunction(()=>!document.querySelector('#packet-file').disabled);
    const sample=JSON.parse(fs.readFileSync(path.join(root,'host/examples/selection-demo.json'),'utf8'));
    const submit=async(parts)=>{
      const packet=structuredClone(sample);packet.source.parts=parts;
      packet.source_sha256=createHash('sha256').update(JSON.stringify(sorted(packet.source))).digest('hex');
      const sourceBefore=JSON.stringify(packet);
      await page.locator('#clear').click();
      await page.locator('#packet-file').setInputFiles({name:'synthetic-math.json',mimeType:'application/json',buffer:Buffer.from(sourceBefore)});
      await page.waitForFunction(()=>document.querySelector('#file-preview').textContent.length>0);
      check('formula preview still requires explicit consent',await page.locator('#import').isDisabled());
      await page.locator('#consent').check();await page.locator('#import').click();
      await page.waitForFunction(()=>document.body.dataset.hostState==='selected');
      check('accepted source hash unchanged by rendering',await page.locator('#source-hash').innerText()===packet.source_sha256);
      check('raw packet remains byte-identical',await page.locator('#file-preview').textContent()===sourceBefore);
      return packet;
    };
    const formula=String.raw`\frac{1}{2}+\sqrt{x^2+1}`;
    await submit([{kind:'text',text:'<img src="https://invalid.example/x" onerror="window.bad=1"> 合成数学'},
      {kind:'math',latex:formula,display:true}]);
    check('accepted fraction and root are real MathML nodes',await page.locator('#source-parts mfrac').count()===1&&await page.locator('#source-parts msqrt').count()===1);
    check('native MathML has nonzero rendered geometry',await page.locator('#source-parts math').evaluate(n=>{const r=n.getBoundingClientRect();return r.width>20&&r.height>20;}));
    check('LaTeX annotation is exact',await page.locator('#source-parts annotation').textContent()===formula);
    await page.locator('#source-parts summary').click();
    check('accessible raw formula stays exact',await page.locator('#source-parts .math-raw').textContent()===formula);
    check('ordinary text is never interpreted as HTML',await page.locator('#source-parts img').count()===0&&await page.evaluate(()=>window.bad===undefined));
    check('mobile viewport has no page overflow',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    await page.screenshot({path:path.join(out,'math-preview-mobile.png'),fullPage:true});
    await page.locator('#explain').click();await page.waitForFunction(()=>document.body.dataset.hostState==='ready');
    check('rendered imported source reaches real Brain TestModel unchanged',await page.locator('#reply').innerText().then(t=>t.includes('SIMULATED')));
    for(const latex of [String.raw`\href{javascript:alert(1)}{x}`,String.raw`\includegraphics{https://invalid.example/never}`,String.raw`\htmlStyle{position:fixed}{x}`,String.raw`\def\a{\a}\a`,String.raw`\unknownFunction{x}`,String.raw`\frac{1}{`, 'x'.repeat(1001)]){
      await submit([{kind:'math',latex,display:true}]);
      check('unsafe/unsupported/oversized expression keeps exact raw fallback',await page.locator('#source-parts [data-math-preview="raw"]').count()===1&&await page.locator('#source-parts .math-raw').textContent()===latex);
      check('fallback cannot create resource or executable DOM',await page.locator('#source-parts math, #source-parts [href], #source-parts [src], #source-parts script, #source-parts iframe').count()===0);
    }
    const bounded=await page.evaluate(async()=>{
      const {renderSourceParts}=await import('/host/math-preview.js');const target=document.createElement('div');
      const parts=Array.from({length:20},()=>({kind:'math',latex:'x+1',display:false}));const before=JSON.stringify(parts);
      let started=performance.now();renderSourceParts(target,parts);const countMillis=performance.now()-started;
      const count=[target.querySelectorAll('math').length,target.querySelectorAll('[data-math-preview="raw"]').length];
      const long=Array.from({length:10},()=>({kind:'math',latex:'x'.repeat(1000),display:true}));
      started=performance.now();renderSourceParts(target,long);const totalMillis=performance.now()-started;
      const total=[target.querySelectorAll('math').length,target.querySelectorAll('[data-math-preview="raw"]').length];
      const deep={kind:'math',latex:'{'.repeat(33)+'x'+'}'.repeat(33),display:true};
      renderSourceParts(target,[deep]);const deepRaw=target.querySelector('.math-raw').textContent;
      renderSourceParts(target,[{kind:'math',latex:'z',display:false}]);const replaced=target.querySelectorAll('math').length===1&&target.querySelector('.math-raw').textContent==='z';
      renderSourceParts(target,[]);return{count,total,countMillis,totalMillis,unaltered:before===JSON.stringify(parts),deepRaw:deepRaw===deep.latex,replaced,cleared:target.childNodes.length===0};
    });
    check('per-view formula count cap preserves remaining raw text',bounded.count.join(',')==='16,4');
    check('per-view total input budget preserves remaining raw text',bounded.total.join(',')==='8,2');
    check('deep input, repeated replacement and clear are safe',bounded.deepRaw&&bounded.replaced&&bounded.cleared&&bounded.unaltered);
    report.maxRenderMillis=Math.max(bounded.countMillis,bounded.totalMillis);
    check('bounded actual rendering finishes within 1500ms smoke budget',report.maxRenderMillis<1500);
    await page.locator('#clear').click();
    check('actual clear removes old MathML/raw source',await page.locator('#source-parts').textContent()==='');
    check('no external fonts/scripts/network requests',report.externalRequests.length===0);
    check('no browser errors',report.errors.length===0);
    report.result='PASS';console.log(JSON.stringify(report,null,2));
  }catch(e){report.result='FAIL';report.failure=e.stack;report.stderr=stderr;throw e;}
  finally{fs.writeFileSync(path.join(out,'math-preview-browser.json'),JSON.stringify(report,null,2)+'\n');if(browser)await browser.close();server.kill('SIGTERM');}
})().catch(e=>{console.error(e);process.exitCode=1;});
