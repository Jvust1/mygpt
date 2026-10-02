import test from 'node:test';
import assert from 'node:assert/strict';
import {createHostController} from '../host/controller.js';

function catalogue(){return {schema:'mygpt.host-selection.v1',scope:'LOCAL_UNVERIFIED_SELECTION',
  model_calls:0,live_book_connected:false,entries:[{id:'import-1',source_ref:'unverified-import:v1:reader:v2:example',
  context:{schema_version:'mygpt.imported-reader-context.v1',evidence_kind:'USER_SUPPLIED_UNVERIFIED',
    source_sha256:'a'.repeat(64),expires_at:new Date(11000).toISOString()}}]};}
function setup(options={}){
  let time=10000;const calls=[];
  const c=createHostController({catalogue:catalogue(),now:()=>time,monotonic:()=>time-10000,
    ttlMs:120000,adapter:async(request)=>{calls.push(request);return {...request,text:'[SIMULATED]',model_called:false,
      source_trust:'USER_SUPPLIED_UNVERIFIED'};},...options});
  return {c,calls,advance:ms=>time+=ms};
}
test('explicit imported profile sends unverified scope and caps lease by server deadline',async()=>{
  const {c,calls}=setup();c.choose('import-1');await c.explain();
  assert.equal(calls[0].scope,'LOCAL_UNVERIFIED_SELECTION');assert.equal(calls[0].selection_expires_at_ms,11000);
  assert.equal(c.getState().status,'ready');c.dispose();
});
test('renewing UI selection never renews the server import deadline',()=>{
  const {c,advance}=setup();c.choose('import-1');advance(900);c.choose('import-1');
  assert.equal(c.getState().expiresAt,11000);advance(101);
  assert.equal(c.choose('import-1'),false);assert.equal(c.getState().status,'expired');c.dispose();
});
for(const field of ['schema_version','evidence_kind'])test(`import cannot use an old ${field} claim`,()=>{
  const data=catalogue();data.entries[0].context[field]=field==='schema_version'?'mygpt.reader-context.v2':'SIMULATED';
  assert.throws(()=>setup({catalogue:data}),TypeError);
});
test('unverified reference cannot look like an authenticated Reader reference',()=>{
  const data=catalogue();data.entries[0].source_ref='reader:v2:example';assert.throws(()=>setup({catalogue:data}),TypeError);
});
test('response cannot upgrade provenance',async()=>{
  const {c}=setup({adapter:async r=>({...r,text:'claims verified',model_called:false,source_trust:'VERIFIED_BOOK'})});
  c.choose('import-1');assert.equal((await c.explain()).status,'response_identity_mismatch');c.dispose();
});
test('invalid source expiry cannot become an unbounded selection',()=>{
  const data=catalogue();data.entries[0].context.expires_at='invalid';const {c}=setup({catalogue:data});
  assert.equal(c.choose('import-1'),false);c.dispose();
});

import {manualPacket} from '../host/selection-manual.js';
import {createHash} from 'node:crypto';
const ordered=x=>Array.isArray(x)?x.map(ordered):x&&typeof x==='object'?Object.fromEntries(Object.keys(x).sort().map(k=>[k,ordered(x[k])])):x;
test('manual text is byte-preserving and never declares a real book version',async()=>{
  const text='e\u0301 ≠ é\n <script>not executable</script> x+x';const packet=await manualPacket(text,'synthetic');
  assert.equal(packet.source.parts[0].text,text);assert.equal(packet.trust,'USER_SUPPLIED_UNVERIFIED');
  assert.equal(packet.source.book_version_id,'manual-unversioned');
  assert.equal(packet.source_sha256,createHash('sha256').update(JSON.stringify(ordered(packet.source))).digest('hex'));
});
for(const input of ['', ' ', 'x'.repeat(8001), 123])test(`invalid manual input ${String(input).slice(0,10)} is rejected`,async()=>{
  await assert.rejects(manualPacket(input),TypeError);
});
