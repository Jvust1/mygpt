import '../companion/mygpt-pet.js';
import { ANIMATIONS } from '../companion/animations.js';
const pet = document.querySelector('#pet');
const visibility = document.querySelector('#visibility');
function syncVisibility() { visibility.textContent = pet.hidden ? '显示约拿' : '隐藏约拿'; }
visibility.addEventListener('click', () => pet.hidden ? pet.show() : pet.hide());
pet.addEventListener('pet-visibility-change', syncVisibility);
syncVisibility();
document.querySelectorAll('[data-status]').forEach(button => button.addEventListener('click', () => {
  pet.removeAttribute('animation'); pet.resume(); pet.setStatus(button.dataset.status);
  document.querySelectorAll('[data-status]').forEach(b => b.setAttribute('aria-pressed', String(b === button)));
}));
document.querySelector('#size').addEventListener('input', e => {
  pet.setAttribute('size', e.target.value); document.querySelector('#size-value').textContent = e.target.value;
});
document.querySelector('#pause').addEventListener('change', e => pet.toggleAttribute('paused', e.target.checked));
document.querySelector('#reset').addEventListener('click', () => pet.resetPosition());
const labels = ['待机','向右跑','向左跑','挥手','跳跃','遇到问题','等待','处理中','阅读'];
Object.keys(ANIMATIONS).forEach((name, index) => {
  const button = document.createElement('button'); button.textContent = labels[index];
  button.addEventListener('click', () => { pet.resume(); pet.setAttribute('animation', name); });
  document.querySelector('#animations').append(button);
});
document.querySelector('#look').addEventListener('input', e => {
  pet.look(Number(e.target.value)); document.querySelector('#look-value').textContent = `${e.target.value}°`;
});
document.querySelector('#resume').addEventListener('click', () => { pet.removeAttribute('animation'); pet.resume(); });
pet.addEventListener('pet-chat-request', () => {
  const panel = document.querySelector('#chat'); panel.hidden = false; panel.focus(); panel.scrollIntoView({ behavior:'smooth', block:'center' });
});
document.querySelector('#close-chat').addEventListener('click', () => {
  document.querySelector('#chat').hidden = true; pet.shadowRoot.querySelector('.avatar').focus();
});
