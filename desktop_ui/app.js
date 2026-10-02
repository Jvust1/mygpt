import '/companion/mygpt-pet.js';
const $=id=>document.getElementById(id);
let snapshot=null, noteId=null, dirty=false, saving=false;
const message=t=>{$('status').textContent=t};
const id=()=>crypto.randomUUID();
const api=async(path,value)=>{const r=await fetch('/desktop-api/'+path,{method:value===undefined?'GET':'POST',headers:{'X-MyGPT-Client':'mygpt-desktop-v1',...(value===undefined?{}:{'Content-Type':'application/json'})},...(value===undefined?{}:{body:JSON.stringify(value)})});let d;try{d=await r.json()}catch{throw Error('服务响应不可读；请保留草稿。')}if(!r.ok)throw Error(d.code||'请求失败');return d};
const download=(name,value)=>{const u=URL.createObjectURL(new Blob([JSON.stringify(value,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=u;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(u),1000)};
async function commit(value){if(saving)throw Error('正在保存，请稍后再操作。');saving=true;message('正在保存…');try{snapshot=await api('state',{revision:snapshot.revision,value});renderLists();message('已保存到本机。');return true}finally{saving=false}}
function clone(){if(!snapshot)throw Error('本机记录尚未加载。');return structuredClone(snapshot.value)}
function safe(fn){return async()=>{try{await fn()}catch(e){message('操作未完成：'+e.message+'。未覆盖其他窗口的新记录；可导出当前草稿。')}}}
function renderLists(){for(const [section,render] of [['notes',(k,v)=>{const el=document.createElement('div');el.className='item';const span=document.createElement('span');span.textContent=v.title||'未命名笔记';const b=document.createElement('button');b.textContent='打开';b.onclick=()=>{if(saving)return;if(dirty&&!confirm('当前草稿未保存，确定切换？'))return;noteId=k;$('note-title').value=v.title;$('note-body').value=v.body;dirty=false};el.append(span,b);return el}],['sessions',(k,v)=>{const el=document.createElement('div');el.className='item';el.textContent=v.goal+' · '+Math.floor(v.seconds/60)+' 分钟 · '+v.ended_at;return el}]]){const out=$(section);out.replaceChildren();let items=Object.entries(snapshot.value[section]);if(section==='sessions')items.sort((a,b)=>b[1].ended_at.localeCompare(a[1].ended_at));for(const [k,v] of items.slice(0,section==='notes'?1000:30))out.append(render(k,v));if(!items.length)out.textContent='还没有记录。'}tick()}
function tick(){const a=snapshot?.value.active;const elapsed=a?Math.max(0,Math.floor((Date.now()-a.started_ms)/1000)):0;$('timer').textContent=String(Math.floor(elapsed/60)).padStart(2,'0')+':'+String(elapsed%60).padStart(2,'0');$('start').disabled=!snapshot||!!a;$('finish').disabled=!a;}
for(const b of document.querySelectorAll('[data-tab]'))b.onclick=()=>{for(const s of document.querySelectorAll('[data-view]'))s.hidden=s.dataset.view!==b.dataset.tab;for(const x of document.querySelectorAll('[data-tab]'))x.setAttribute('aria-selected',String(x===b));};
for(const name of ['note-title','note-body'])$(name).addEventListener('input',()=>{dirty=true});
window.addEventListener('beforeunload',e=>{if(dirty||saving||chatBusy){e.preventDefault();e.returnValue=''}});
$('save-note').onclick=safe(async()=>{const v=clone();const key=noteId||id();v.notes[key]={title:$('note-title').value,body:$('note-body').value};const title=v.notes[key].title,body=v.notes[key].body;await commit(v);noteId=key;dirty=$('note-title').value!==title||$('note-body').value!==body});
$('new-note').onclick=()=>{if(saving)return;if(dirty&&!confirm('当前草稿未保存，确定新建？'))return;noteId=null;$('note-title').value='';$('note-body').value='';dirty=false};
$('save-goal').onclick=safe(async()=>{const v=clone();v.goal=$('goal').value;await commit(v)});
$('start').onclick=safe(async()=>{const minutes=Number($('minutes').value);if(!Number.isInteger(minutes)||minutes<1||minutes>240)throw Error('分钟数应为1–240的整数');const v=clone();v.goal=$('goal').value;v.active={id:id(),goal:v.goal,started_ms:Date.now(),target_sec:minutes*60};await commit(v)});
$('finish').onclick=safe(async()=>{const v=clone(),a=v.active;if(!a)return;v.sessions[a.id]={goal:a.goal,seconds:Math.min(86400,Math.max(0,Math.floor((Date.now()-a.started_ms)/1000))),ended_at:new Date().toISOString()};v.active=null;await commit(v)});
$('export').onclick=safe(async()=>{const latest=await api('state');download('mygpt-workspace-backup.json',{schema:'mygpt-workspace-backup-v1',value:latest.value});message('已导出笔记、目标与计时记录；不包含聊天历史，未保存草稿请另行导出。')});
$('export-draft').onclick=()=>download('mygpt-unsaved-note.json',{schema:'mygpt-workspace-backup-v1',value:{goal:$('goal').value,notes:{[noteId||id()]:{title:$('note-title').value,body:$('note-body').value}},sessions:{},active:null}});
$('import').onchange=safe(async()=>{const file=$('import').files[0];if(!file)return;if(file.size>2*1024*1024+4096)throw Error('备份文件超过限制');if(!confirm('将个人备份合并到本机，冲突笔记保留副本。继续？'))return;snapshot=await api('merge',JSON.parse(await file.text()));$('goal').value=snapshot.value.goal;renderLists();message('备份合并完成。');$('import').value=''});
let chatBusy=false, historyEpoch=0, nextBefore=null;
const chatStatus=t=>{$('chat-status').textContent=t};
function chatControls(){
  $('ask').disabled=chatBusy;
  $('chat-refresh').disabled=chatBusy;
  $('chat-older').disabled=chatBusy||nextBefore===null;
  for(const name of ['model','port','prompt','consent'])$(name).disabled=chatBusy;
}
async function loadChatHistory(before=null){
  const epoch=++historyEpoch;
  let result;
  try{result=await api('chat-history'+(before===null?'':'?before='+encodeURIComponent(before)))}
  catch(error){if(epoch!==historyEpoch)return false;throw error}
  if(epoch!==historyEpoch)return false;
  const list=$('chat-history');list.replaceChildren();
  for(const item of result.messages){
    const entry=document.createElement('article');entry.className='chat-message';
    const label=document.createElement('strong');label.textContent=item.role==='user'?'你':'mygpt';
    const body=document.createElement('pre');body.textContent=item.content;
    entry.append(label,body);list.append(entry);
  }
  if(!result.messages.length)list.textContent='还没有已保存的对话。';
  nextBefore=result.next_before;
  $('chat-history-status').textContent='本机已保存对话 · 当前窗口 '+result.messages.length+' 条；全部历史保留在本机。';
  chatControls();return true;
}
$('chat-refresh').onclick=async()=>{try{if(await loadChatHistory())chatStatus('已读取最新的本机记录，没有请求模型。')}catch{chatStatus('历史读取失败；请保留数据目录，不会重新生成回复。')}};
$('chat-older').onclick=async()=>{if(nextBefore===null)return;try{await loadChatHistory(nextBefore)}catch{chatStatus('较早记录读取失败；未删除历史。')}};
for(const name of ['model','port','prompt'])$(name).addEventListener('input',()=>{$('consent').checked=false});
$('ask').onclick=async()=>{
  if(chatBusy)return;
  if(!$('consent').checked){chatStatus('请先确认本次发送。');return}
  const prompt=$('prompt').value;
  if(!prompt.trim()||Array.from(prompt).length>4000){chatStatus('请输入1–4000字符，超出限制不会截断或发送。');return}
  const request={consent:true,port:Number($('port').value),model:$('model').value,prompt,request_id:id()};
  chatBusy=true;++historyEpoch;$('consent').checked=false;chatControls();
  chatStatus('正在请求本机模型；只有问答原子保存成功才显示已保存，不会自动重试…');
  $('reply').textContent='';
  try{
    const result=await api('local-chat',request);
    if(result.request_id!==request.request_id||result.saved!==true)throw Error('unconfirmed_chat_receipt');
    $('reply').textContent=result.reply;
    chatStatus('本机问答已保存 · 模型回复未独立核验');
    try{await loadChatHistory()}catch{chatStatus('本次问答已保存；历史列表读取失败，可稍后只读刷新。')}
  }catch(e){
    chatStatus(e.message==='model_busy'?'另一条提问仍在处理，请稍后只读刷新记录。':'本次结果未确认保存。请点“只读刷新记录”核对；不会自动重试。再次发送是新的显式提问。');
  }finally{chatBusy=false;chatControls()}
};
setInterval(tick,1000);
(async()=>{try{snapshot=await api('state');$('goal').value=snapshot.value.goal;renderLists();message('本机记录已加载。未发送任何模型请求。')}catch(e){message('读取失败：'+e.message+'。请保留原数据目录。')}})();

loadChatHistory().catch(()=>{chatStatus('聊天历史读取失败；没有请求模型。请保留数据目录。')});
