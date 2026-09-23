import test from 'node:test';
import assert from 'node:assert/strict';
import { catalogue } from '../host/fixtures.js';
import { createHostController } from '../host/controller.js';
import { createReplayAdapter } from '../host/replay.js';

const flush = async()=>{for(let i=0;i<8;i++)await Promise.resolve();};
function harness(overrides={}) {
  let wall=10000, mono=0,serial=0; const timers=new Map(),calls=[];
  const h={calls,timers,clock(w,m){wall=w;mono=m;},
    async advance(ms){wall+=ms;mono+=ms;for(const [id,t] of [...timers])if(t.at<=mono){timers.delete(id);t.fn();}await flush();},
    reply(index=0,changes={}){const call=calls[index];call.resolve({...call.request,text:'预写样本',model_called:false,...changes});},
  };
  h.controller=createHostController({catalogue,now:()=>wall,monotonic:()=>mono,
    setTimer:(fn,ms)=>{const id=++serial;timers.set(id,{at:mono+ms,fn});return id;},clearTimer:id=>timers.delete(id),
    ttlMs:1000,timeoutMs:500,adapter:(request,entry,{signal})=>new Promise((resolve,reject)=>calls.push({request,entry,signal,resolve,reject})),...overrides});
  return h;
}

test('initial state and subscribing/opening do not select or send',()=>{
  const h=harness();let seen=0;h.controller.subscribe(()=>seen++);
  assert.equal(h.controller.getState().status,'empty');assert.equal(seen,1);
  assert.equal(h.controller.getState().petStatus,'needs-input');assert.equal(h.calls.length,0);assert.equal(h.timers.size,0);
});
for(const entry of catalogue.entries) test(`explicit selection ${entry.id} preserves layer and identity without calls`,()=>{
  const h=harness();assert.equal(h.controller.choose(entry.id),true);
  const state=h.controller.getState();assert.equal(state.entry.context.source_layer,entry.context.source_layer);
  assert.equal(state.entry.source_ref,entry.source_ref);assert.equal(state.petStatus,'idle');assert.equal(h.calls.length,0);
  assert.throws(()=>{state.entry.context.source_layer='invented';},TypeError);
  h.controller.dispose();assert.equal(h.timers.size,0);
});
for(const mode of ['preview','learn','review','practice']) test(`mode ${mode} binds outgoing request`,async()=>{
  const h=harness();h.controller.changeMode(mode);h.controller.choose('a-source');
  const done=h.controller.explain();await flush();assert.equal(h.calls[0].request.mode,mode);
  h.reply();assert.equal((await done).status,'ready');assert.equal(h.controller.getState().petStatus,'ready');
  h.controller.dispose();
});
test('mode change clears selection and does not send automatically',async()=>{
  const h=harness();h.controller.choose('a-source');h.controller.changeMode('practice');
  assert.equal(h.controller.getState().entry,null);await h.controller.explain();assert.equal(h.calls.length,0);
  assert.equal(h.timers.size,0);assert.throws(()=>h.controller.changeMode('unknown'),RangeError);
});
test('double click is exactly one adapter invocation and one settled UI request',async()=>{
  const h=harness();h.controller.choose('a-source');const a=h.controller.explain(),b=h.controller.explain();
  assert.equal(a,b);assert.equal(h.controller.getState().petStatus,'working');await flush();assert.equal(h.calls.length,1);
  h.reply();assert.equal((await a).status,'ready');assert.equal(h.controller.getState().requests,1);
  h.controller.dispose();assert.equal(h.timers.size,0);
});
for(const action of ['cancel','pause','revoke','dispose']) test(`${action} settles immediately and ignores adapter that ignores abort`,async()=>{
  const h=harness();h.controller.choose('a-source');const done=h.controller.explain();await flush();
  h.controller[action]();assert.notEqual((await done).status,'ready');assert.equal(h.calls[0].signal.aborted,true);
  const state=h.controller.getState();h.reply();await flush();assert.deepEqual(h.controller.getState(),state);
  if(action!=='cancel')assert.equal(h.timers.size,0);
  h.controller.dispose();
});
test('selection change discards old reply, correct new reply can complete',async()=>{
  const h=harness();h.controller.choose('a-source');const first=h.controller.explain();await flush();
  h.controller.choose('b-source');assert.equal((await first).status,'selection_changed');
  const second=h.controller.explain();await flush();h.reply(0);await flush();assert.equal(h.controller.getState().status,'working');
  h.reply(1);assert.equal((await second).status,'ready');assert.equal(h.controller.getState().entry.id,'b-source');
  assert.notEqual(h.calls[0].request.request_id,h.calls[1].request.request_id);h.controller.dispose();
});
test('same selection chosen again invalidates pending generation',async()=>{
  const h=harness();h.controller.choose('a-source');const done=h.controller.explain();await flush();h.controller.choose('a-source');
  await done;h.reply();await flush();assert.equal(h.controller.getState().reply,null);assert.equal(h.controller.getState().status,'selected');
  h.controller.dispose();
});
for(const [field,value] of [['request_id','old'],['revision',999],['mode','other'],['entry_id','b-source'],
 ['source_ref','forged'],['source_sha256','a'.repeat(64)],['scope','LIVE'],['model_called',true],['text',''],['text','x'.repeat(4001)]]) {
 test(`reply with wrong ${field} fails closed`,async()=>{
  const h=harness();h.controller.choose('a-source');const done=h.controller.explain();await flush();h.reply(0,{[field]:value});
  assert.equal((await done).status,'response_identity_mismatch');assert.equal(h.controller.getState().reply,null);
  assert.equal(h.controller.getState().petStatus,'blocked');h.controller.dispose();
 });
}
test('timeout stops waiting without an implicit retry',async()=>{
  const h=harness();h.controller.choose('a-source');const done=h.controller.explain();await flush();await h.advance(500);
  assert.equal((await done).status,'request_timeout');assert.equal(h.calls.length,1);assert.equal(h.calls[0].signal.aborted,true);
  h.reply();await flush();assert.equal(h.controller.getState().status,'error');h.controller.dispose();
});
test('adapter exception becomes bounded generic reason, not raw exception text',async()=>{
  const h=harness();h.controller.choose('a-source');const done=h.controller.explain();await flush();
  h.calls[0].reject(new Error('synthetic-private-detail'));await done;
  assert.equal(h.controller.getState().reason,'replay_failed');assert(!JSON.stringify(h.controller.getState()).includes('synthetic-private-detail'));
  h.controller.dispose();
});
test('expiry timer clears even a ready answer and does not send',async()=>{
  const h=harness();h.controller.choose('a-source');const done=h.controller.explain();await flush();h.reply();await done;
  await h.advance(1000);assert.equal(h.controller.getState().status,'expired');assert.equal(h.controller.getState().reply,null);
  assert.equal(h.timers.size,0);assert.equal(h.calls.length,1);
});
for(const [wall,mono] of [[11001,0],[10000,1001],[9999,0],[10000,-1],[NaN,0],[10000,Infinity]]) {
 test(`freshness rejects independent wall/monotonic clock ${wall}/${mono} without timers`,async()=>{
  const h=harness();h.controller.choose('a-source');h.clock(wall,mono);
  await h.controller.explain();assert.equal(h.calls.length,0);assert.equal(h.controller.getState().status,'expired');assert.equal(h.timers.size,0);
 });
}
test('late response checks lease even when timers never fired',async()=>{
  const h=harness();h.controller.choose('a-source');const done=h.controller.explain();await flush();
  h.clock(12000,2000);h.reply();assert.notEqual((await done).status,'ready');assert.equal(h.controller.getState().entry,null);
});
test('cancel before the adapter microtask prevents any adapter invocation',async()=>{
  const h=harness();h.controller.choose('a-source');const done=h.controller.explain();h.controller.cancel();await done;await flush();
  assert.equal(h.calls.length,0);h.controller.dispose();
});
test('revocation is final for this instance; refresh creates an independent instance',async()=>{
  const h=harness();h.controller.revoke();assert.equal(h.controller.choose('a-source'),false);
  assert.equal(h.controller.changeMode('practice'),false);assert.equal((await h.controller.explain()).status,'not_available');
  const other=harness();assert(other.controller.choose('a-source'));other.controller.dispose();
});
test('disposing unsubscribes handlers and clears timers',()=>{
  const h=harness();let seen=0;h.controller.subscribe(()=>seen++);h.controller.choose('a-source');h.controller.dispose();
  const count=seen;h.controller.choose('b-source');h.controller.subscribe(()=>seen++);assert.equal(seen,count);assert.equal(h.timers.size,0);
});
test('unknown selection clears previous context rather than preserving it',()=>{
  const h=harness();h.controller.choose('a-source');assert.equal(h.controller.choose('missing'),false);
  assert.equal(h.controller.getState().entry,null);assert.equal(h.timers.size,0);
});
test('request identity is scoped to different controller instances',async()=>{
  const a=harness(),b=harness();for(const h of[a,b]){h.controller.choose('a-source');h.controller.explain();}
  await flush();assert.notEqual(a.calls[0].request.request_id,b.calls[0].request.request_id);a.controller.dispose();b.controller.dispose();
});
test('reject malformed configuration and duplicate catalogue IDs',()=>{
  assert.throws(()=>harness({ttlMs:0}),RangeError);assert.throws(()=>harness({timeoutMs:30001}),RangeError);
  const copy=structuredClone(catalogue);copy.entries.push(copy.entries[0]);assert.throws(()=>harness({catalogue:copy}),TypeError);
  assert.throws(()=>harness({catalogue:{...catalogue,scope:'LIVE'}}),TypeError);
});
test('replay adapter checks actual text SHA and returns explicitly non-model result',async()=>{
  const entry=catalogue.entries[0];const request={source_sha256:entry.context.source_sha256,scope:'SYNTHETIC_FIXED_REPLAY'};
  const adapter=createReplayAdapter({delayMs:1});const signal=new AbortController().signal;
  const reply=await adapter(request,entry,{signal});assert.equal(reply.text,entry.fixture_reply);assert.equal(reply.model_called,false);
  await assert.rejects(adapter(request,{...entry,evidence_text:'tampered'},{signal}),/mismatch/);
});
test('replay adapter cancellation before hashing and during delay rejects',async()=>{
  const entry=catalogue.entries[0], request={source_sha256:entry.context.source_sha256};
  const adapter=createReplayAdapter({delayMs:500});const first=new AbortController();first.abort();
  await assert.rejects(adapter(request,entry,{signal:first.signal}),{name:'AbortError'});
  const second=new AbortController();const done=adapter(request,entry,{signal:second.signal});
  setTimeout(()=>second.abort(),5);await assert.rejects(done,{name:'AbortError'});
});
