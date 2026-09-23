import '../companion/mygpt-pet.js';
import { catalogue } from './fixtures.js';
import { createHostController } from './controller.js';
import { createReplayAdapter } from './replay.js';

const $ = id => document.getElementById(id);
const pet = $('pet'), panel = $('help-panel');
const labels = {source:'原文层（合成转录）',correction:'校正层（非官方勘误）',derived:'AI 推导层（非标准答案）'};
const reasons = {empty:'请先选择具体内容',selected:'已选择 · 等你明确求助',working:'正在回放预写样本…',
  ready:'样本已就绪 · 不是实时 AI 回复',error:'回放失败，可重新选择后再试',expired:'选择已失效，请重新选择',
  paused:'已暂停；重新选择内容后继续',revoked:'本页演示已关闭，刷新后恢复',disposed:'界面已关闭'};
const controller = createHostController({catalogue,adapter:createReplayAdapter()});
let returnFocus = null;
const element = (tag,text,className) => {
  const node = document.createElement(tag); if (text !== undefined) node.textContent = text;
  if (className) node.className = className; return node;
};
function renderParts(target,parts) {
  target.replaceChildren(...parts.map(p => element(p.kind==='math'?'code':'p',p.kind==='math'?p.latex:p.text,p.kind==='math'?'math':undefined)));
}
for (const rid of new Set(catalogue.entries.map(e=>e.context.source_id))) {
  const choices = catalogue.entries.filter(e=>e.context.source_id===rid);
  const original = JSON.parse(choices.find(e=>e.context.source_layer==='source').evidence_text);
  const card = element('article',undefined,'record'); card.dataset.recordId = rid;
  card.append(element('h3',original.title));
  const body = element('div'); renderParts(body,original.parts);card.append(body);
  const label = element('label','选择要讨论的内容层');
  const select = element('select'); select.id = `select-${rid}`; select.setAttribute('aria-label',`${original.title} 内容层`);
  select.append(new Option('请选择具体内容…',''));
  for (const choice of choices) select.append(new Option(choice.label,choice.id));
  label.append(select);card.append(label);$('records').append(card);
  select.addEventListener('change',()=>{
    if (select.value) {controller.choose(select.value); openPanel(false);}
    else controller.pause();
  });
}
function openPanel(focus=true) {
  panel.hidden = false;
  if (focus) {
    returnFocus = document.activeElement?.shadowRoot?.activeElement || document.activeElement;
    $('help-heading').focus({preventScroll:true});
    panel.scrollIntoView({block:'start',behavior:'auto'});
  }
}
function closePanel() {
  controller.cancel();panel.hidden=true;
  if (returnFocus?.isConnected && !returnFocus.closest?.('[hidden]')) returnFocus.focus({preventScroll:true});
  else $('open-panel').focus({preventScroll:true});
}
let renderedEntry = null;
controller.subscribe(state=>{
  document.body.dataset.hostState = state.status;
  pet.setStatus(state.petStatus);
  pet.toggleAttribute('paused',['paused','revoked','disposed'].includes(state.status));
  $('state-label').textContent = state.reason==='request_timeout'?'等待已超时，没有自动重试。':reasons[state.status];
  $('model-calls').textContent = String(state.modelCalls);$('request-count').textContent = String(state.requests);
  $('explain').disabled = !['selected','ready','error'].includes(state.status);
  $('cancel').hidden = state.status!=='working';
  $('selected-context').hidden=!state.entry;$('empty-message').hidden=!!state.entry;
  $('reply-box').hidden=state.reply===null;$('reply').textContent=state.reply||'';
  $('mode').value=state.mode;$('mode').disabled=['revoked','disposed'].includes(state.status);
  $('pause').disabled=['revoked','disposed'].includes(state.status);
  document.querySelectorAll('#records select').forEach(s=>{
    s.value=state.entry?.context.source_id===s.id.slice(7)?state.entry.id:'';
    s.disabled=['revoked','disposed'].includes(state.status);
    s.closest('article').classList.toggle('chosen',s.value!=='');
  });
  if (state.entry) {
    if (renderedEntry!==state.entry.id) {
      const payload=JSON.parse(state.entry.evidence_text);
      $('selected-title').textContent=state.entry.label;
      $('selected-layer').textContent=labels[state.entry.context.source_layer];
      $('selected-version').textContent=state.entry.context.book_version;
      $('selected-hash').textContent=state.entry.context.source_sha256;
      $('selected-ref').textContent=state.entry.source_ref;
      renderParts($('source-parts'),payload.parts);
      $('source-warning').textContent=payload.warnings.length?'此处展示所选来源层，不保证与 Book 最终屏幕渲染一致。':'';
      renderedEntry=state.entry.id;
    }
    $('selected-expiry').textContent=new Date(state.expiresAt).toLocaleTimeString('zh-CN',{hour12:false});
  } else {
    renderedEntry=null;
    for (const id of ['selected-title','selected-layer','selected-version','selected-expiry','selected-hash','selected-ref','source-warning']) $(id).textContent='';
    $('source-parts').replaceChildren();
  }
});
$('mode').addEventListener('change',e=>controller.changeMode(e.target.value));
$('explain').addEventListener('click',()=>{void controller.explain();});
$('cancel').addEventListener('click',()=>{controller.cancel();$('explain').focus({preventScroll:true});});
$('pause').addEventListener('click',()=>controller.pause());
$('revoke').addEventListener('click',()=>controller.revoke());
$('open-panel').addEventListener('click',()=>openPanel());
$('close-panel').addEventListener('click',closePanel);
panel.addEventListener('keydown',e=>{if(e.key==='Escape'){e.preventDefault();closePanel();}});
pet.addEventListener('pet-chat-request',()=>openPanel()); // opening is NOT sending
pet.addEventListener('pet-error',()=>{$('pet-fallback').hidden=false;});
pet.addEventListener('pet-visibility-change',()=>{
  $('toggle-pet').textContent=pet.hidden?'显示约拿':'隐藏约拿';
  if(pet.hidden) controller.pause();
});
$('toggle-pet').textContent=pet.hidden?'显示约拿':'隐藏约拿';
$('toggle-pet').addEventListener('click',()=>pet.hidden?pet.show():pet.hide());
document.addEventListener('visibilitychange',()=>{if(document.hidden)controller.pause();});
window.addEventListener('pagehide',()=>controller.pause());
// BFCache restores a paused UI; there is no implicit resume or replay.
// No global test hooks, model key settings, fetch, or upload endpoints are exposed.
