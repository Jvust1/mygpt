import test from 'node:test';
import assert from 'node:assert/strict';
import { createBrainAdapter } from '../host/brain-adapter.js';

const ok = value => new Response(JSON.stringify(value),{status:200,headers:{'Content-Type':'application/json'}});
const request = {request_id:'ui-test-1',revision:1,entry_id:'a-source',mode:'learn',
  source_ref:'reader:v2:fixture',source_sha256:'a'.repeat(64),selection_expires_at_ms:Date.now()+60000,
  scope:'SYNTHETIC_FIXED_REPLAY'};

test('status uses same-origin credentials and fixed client header',async()=>{
  const calls=[];const old=globalThis.fetch;
  globalThis.fetch=async(...args)=>{calls.push(args);return ok({authorized:true});};
  try{const adapter=createBrainAdapter();assert.deepEqual(await adapter.status(),{authorized:true});
    const [url,options]=calls[0];assert.equal(url,'/api/v1/status');assert.equal(options.method,'GET');
    assert.equal(options.credentials,'same-origin');assert.equal(options.cache,'no-store');
    assert.equal(options.headers['X-MyGPT-Client'],'mygpt-reader-brain-v1');
  }finally{globalThis.fetch=old;}
});

test('explain sends only bounded identity request and returns JSON',async()=>{
  const calls=[];const old=globalThis.fetch;
  globalThis.fetch=async(url,options)=>{calls.push([url,options]);return ok({...request,text:'fixture',model_called:false});};
  try{const adapter=createBrainAdapter();const result=await adapter(request,{}, {signal:new AbortController().signal});
    assert.equal(result.text,'fixture');const [url,options]=calls[0];assert.equal(url,'/api/v1/explain');
    const body=JSON.parse(options.body);assert.equal(body.schema_version,'mygpt.local-explain.v1');
    assert.equal(body.source_sha256,request.source_sha256);assert.equal(body.selection_expires_at_ms,request.selection_expires_at_ms);
    assert.equal(body.text,undefined);assert.equal(options.credentials,'same-origin');
  }finally{globalThis.fetch=old;}
});

test('abort attempts bounded cancel with keepalive and never invents response',async()=>{
  const calls=[];const old=globalThis.fetch;let rejectExplain;
  globalThis.fetch=(url,options)=>{calls.push([url,options]);
    if(url==='/api/v1/cancel')return Promise.resolve(ok({status:'cancelled'}));
    return new Promise((_resolve,reject)=>{rejectExplain=reject;options.signal.addEventListener('abort',()=>reject(new DOMException('Cancelled','AbortError')),{once:true});});
  };
  try{const adapter=createBrainAdapter(),abort=new AbortController();const done=adapter(request,{}, {signal:abort.signal});
    await Promise.resolve();abort.abort();await assert.rejects(done,{name:'AbortError'});await new Promise(r=>setTimeout(r,0));
    const cancel=calls.find(([u])=>u==='/api/v1/cancel');assert(cancel);assert.equal(cancel[1].keepalive,true);
    assert.deepEqual(JSON.parse(cancel[1].body),{schema_version:'mygpt.local-cancel.v1',request_id:request.request_id});
  }finally{globalThis.fetch=old;}
});

test('revoke is explicit and errors expose only bounded code',async()=>{
  const calls=[];const old=globalThis.fetch;
  globalThis.fetch=async(url,options)=>{calls.push([url,options]);
    if(url==='/api/v1/revoke')return ok({status:'revoked'});
    return new Response(JSON.stringify({code:'authorization_revoked_or_expired',private:'not surfaced'}),{status:403,headers:{'Content-Type':'application/json'}});
  };
  try{const adapter=createBrainAdapter();assert.deepEqual(await adapter.revoke(),{status:'revoked'});
    await assert.rejects(adapter.status(),e=>e.code==='authorization_revoked_or_expired'&&e.status===403&&!String(e).includes('not surfaced'));
  }finally{globalThis.fetch=old;}
});
