import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {randomUUID} from 'node:crypto';

const script=fs.readFileSync(new URL('../desktop_ui/app.js',import.meta.url),'utf8').replace("import '/companion/mygpt-pet.js';",'');
const page=(handler)=>{
  const elements=new Map(),calls=[];
  const element=(id='')=>({id,value:'',checked:false,disabled:false,textContent:'',children:[],listeners:{},
    addEventListener(name,fn){this.listeners[name]=fn},setAttribute(){},append(...items){this.children.push(...items)},
    replaceChildren(...items){this.children=items;this.textContent=''},click(){},dataset:{}});
  const $=id=>{if(!elements.has(id))elements.set(id,element(id));return elements.get(id)};
  const context={document:{getElementById:$,querySelectorAll:()=>[],createElement:()=>element()},
    window:{addEventListener(){}},crypto:{randomUUID},structuredClone,Blob,URL,
    setInterval(){},setTimeout(){},confirm:()=>false,
    fetch:async(url,options)=>{const call={url,body:options.body?JSON.parse(options.body):undefined};calls.push(call);
      let body=await handler(call);
      if(body===undefined)body=url.includes('chat-history')?{messages:[],next_before:null}:{revision:0,value:{notes:{},sessions:{},active:null,goal:''}};
      return {ok:body.ok!==false,json:async()=>body};}};
  vm.runInNewContext(script,context);
  return {$,calls,ready:async()=>{for(let i=0;i<8;i++)await Promise.resolve()}};
};
const deferred=()=>{let resolve;const promise=new Promise(r=>resolve=r);return{promise,resolve}};

test('startup and explicit history refresh only read; no model or HTML injection',async()=>{
  const text='<img src=x onerror=alert(1)>\n字 🦉';
  const h=page(({url})=>url.includes('chat-history')?{messages:[{role:'assistant',content:text}],next_before:null}:undefined);
  await h.ready();assert.equal(h.calls.filter(c=>c.body).length,0);
  assert.equal(h.$('chat-history').children[0].children[1].textContent,text);
  await h.$('chat-refresh').onclick();assert.equal(h.calls.filter(c=>c.url.endsWith('local-chat')).length,0);
});

test('double click during request dispatches once; saved status requires matching committed receipt',async()=>{
  const pending=deferred();const h=page(({url})=>url.endsWith('local-chat')?pending.promise:undefined);await h.ready();
  h.$('prompt').value='one';h.$('model').value='synthetic';h.$('port').value='1234';h.$('consent').checked=true;
  const first=h.$('ask').onclick();await h.$('ask').onclick();
  const requests=h.calls.filter(c=>c.url.endsWith('local-chat'));assert.equal(requests.length,1);
  assert.equal(h.$('consent').checked,false);assert.equal(h.$('ask').disabled,true);
  assert.doesNotMatch(h.$('chat-status').textContent,/本机问答已保存/);
  pending.resolve({saved:true,request_id:requests[0].body.request_id,reply:'exact\nreply'});await first;
  assert.equal(h.$('reply').textContent,'exact\nreply');assert.match(h.$('chat-status').textContent,/本机问答已保存/);
  assert.equal(h.$('ask').disabled,false);
});

test('failed or unconfirmed reply preserves input, no retry and no saved claim',async()=>{
  for(const result of [{ok:false,code:'chat_outcome_unknown_check_history_no_automatic_retry'},{saved:false,reply:'bad'},{saved:true,request_id:'wrong',reply:'bad'}]){
    const h=page(({url})=>url.endsWith('local-chat')?result:undefined);await h.ready();
    h.$('prompt').value='keep draft';h.$('consent').checked=true;await h.$('ask').onclick();
    assert.equal(h.$('prompt').value,'keep draft');assert.equal(h.$('reply').textContent,'');
    assert.match(h.$('chat-status').textContent,/未确认保存/);assert.equal(h.$('consent').checked,false);
    await h.$('chat-refresh').onclick();assert.equal(h.calls.filter(c=>c.url.endsWith('local-chat')).length,1);
  }
});

test('late startup history cannot replace history from a completed turn',async()=>{
  const initial=deferred();let historyReads=0;
  const h=page(({url,body})=>{
    if(url.includes('chat-history'))return ++historyReads===1?initial.promise:{messages:[{role:'assistant',content:'latest'}],next_before:null};
    if(url.endsWith('local-chat'))return {saved:true,request_id:body.request_id,reply:'latest'};
  });await h.ready();h.$('prompt').value='new';h.$('consent').checked=true;await h.$('ask').onclick();
  initial.resolve({messages:[{role:'assistant',content:'stale'}],next_before:20});await h.ready();
  assert.equal(h.$('chat-history').children[0].children[1].textContent,'latest');assert.equal(h.$('chat-older').disabled,true);
});

test('consent and visible 4000-character limit reject before dispatch, no silent truncation',async()=>{
  const h=page(()=>undefined);await h.ready();h.$('prompt').value='one';await h.$('ask').onclick();
  h.$('consent').checked=true;h.$('prompt').value='x'.repeat(4001);await h.$('ask').onclick();
  assert.equal(h.$('prompt').value.length,4001);assert.equal(h.calls.filter(c=>c.body).length,0);
  assert.match(h.$('chat-status').textContent,/不会截断/);
});

test('editing model, port or text clears previously given consent',async()=>{
  const h=page(()=>undefined);await h.ready();
  for(const name of ['model','port','prompt']){
    h.$('consent').checked=true;h.$(name).listeners.input();assert.equal(h.$('consent').checked,false);
  }
  assert.equal(h.calls.filter(c=>c.body).length,0);
});

test('stale refresh success or failure never masks a newer unknown-send warning',async()=>{
  for(const staleFailure of [false,true]){
    const pending=deferred();let historyCalls=0;
    const h=page(({url})=>{
      if(url.includes('chat-history'))return ++historyCalls===2?pending.promise:undefined;
      if(url.endsWith('local-chat'))return {ok:false,code:'chat_outcome_unknown_check_history_no_automatic_retry'};
    });await h.ready();const refresh=h.$('chat-refresh').onclick();
    h.$('prompt').value='new uncertain question';h.$('consent').checked=true;await h.$('ask').onclick();
    assert.match(h.$('chat-status').textContent,/未确认保存/);
    pending.resolve(staleFailure?{ok:false,code:'history_failed'}:{messages:[],next_before:null});await refresh;
    assert.match(h.$('chat-status').textContent,/未确认保存/);
  }
});

test('prompt has no browser maxlength that would silently truncate pasted input',()=>{
  const html=fs.readFileSync(new URL('../desktop_ui/index.html',import.meta.url),'utf8');
  const tag=html.match(/<textarea[^>]*id="prompt"[^>]*>/)[0];assert.doesNotMatch(tag,/maxlength/i);
});
