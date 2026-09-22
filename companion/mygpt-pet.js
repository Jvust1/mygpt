import { ATLAS, ANIMATIONS, STATUSES, lookFrame } from './animations.js';

const spriteURL = new URL('./assets/jonah.png', import.meta.url).href;
const template = document.createElement('template');
template.innerHTML = `
  <style>
    :host { position:fixed; display:block; width:var(--pet-size,112px); z-index:var(--pet-z-index,1000);
      right:max(12px,env(safe-area-inset-right)); bottom:calc(var(--pet-bottom,76px) + env(safe-area-inset-bottom));
      color:#312e45; font:13px/1.5 system-ui,sans-serif; color-scheme:light; }
    :host([hidden]) { display:none!important }
    *, *::before, *::after { box-sizing:border-box }
    button { font:inherit; cursor:pointer; color:inherit; border:0; }
    button:focus-visible { outline:3px solid #7761be; outline-offset:3px }
    .avatar { display:block; width:100%; padding:0; background:none; border-radius:24px;
      touch-action:none; user-select:none; -webkit-user-select:none; cursor:grab; }
    .avatar:active { cursor:grabbing }
    .sprite { display:block; width:100%; aspect-ratio:192/208; background-repeat:no-repeat;
      background-size:800% 1100%; pointer-events:none; filter:drop-shadow(0 4px 4px #30254920); }
    .label { display:block; width:100%; border-radius:24px; background:#fffffff2; border:1px solid #e0daeb;
      min-height:44px; box-shadow:0 4px 18px #30254912; padding:5px 6px; }
    .label span { display:block; font-size:11px; color:#6d657e; }
    .panel { margin:0 0 6px; padding:8px; border-radius:18px; background:#fff; border:1px solid #e0daeb;
      max-height:var(--pet-panel-max-height,240px); overflow-y:auto;
      box-shadow:0 6px 24px #30254916; }
    .panel[hidden] { display:none }
    .panel button { display:block; width:100%; min-height:44px; border-radius:10px; background:#f4f0fa; margin:3px 0; }
    .panel button:hover { background:#e9e2f5 }
    .fallback { display:none; padding:12px 4px; text-align:center; color:#625671; font-size:12px; }
    :host([asset-error]) .fallback { display:block }
    :host([asset-error]) .sprite { display:none }
    .sr { position:absolute; width:1px; height:1px; overflow:hidden; clip-path:inset(50%); }
  </style>
  <section class="panel" id="controls" hidden aria-label="约拿的操作">
    <button type="button" data-action="chat">找约拿聊聊</button>
    <button type="button" data-action="wave">打个招呼</button>
    <button type="button" data-action="reset">回到右下角</button>
    <button type="button" data-action="hide">暂时隐藏</button>
  </section>
  <button class="avatar" type="button" aria-label="约拿：点击打开操作，拖动可移动；方向键可微调" aria-expanded="false" aria-controls="controls">
    <span class="sprite" aria-hidden="true"></span><span class="fallback">约拿图片未加载</span>
  </button>
  <button class="label" type="button" aria-expanded="false" aria-controls="controls">约拿<span>安静陪伴</span></button>
  <span class="sr" role="status" aria-live="polite"></span>
`;

/** Framework-neutral, local-only companion. Mount directly under document.body. */
export class MyGPTPet extends HTMLElement {
  static observedAttributes = ['status', 'animation', 'paused', 'hidden', 'size'];

  constructor() {
    super();
    this.attachShadow({ mode: 'open' }).append(template.content.cloneNode(true));
    this._sprite = this.shadowRoot.querySelector('.sprite');
    this._avatar = this.shadowRoot.querySelector('.avatar');
    this._label = this.shadowRoot.querySelector('.label');
    this._panel = this.shadowRoot.querySelector('.panel');
    this._sprite.style.backgroundImage = `url("${spriteURL}")`;
    this._row = 0; this._column = 0; this._timer = null; this._transient = null;
    this._position = null; this._drag = null; this._suppressClick = false;
  }

  connectedCallback() {
    if (this._events) return;
    this._events = new AbortController();
    const options = { signal: this._events.signal };
    this._motion = matchMedia('(prefers-reduced-motion: reduce)');
    this._motion.addEventListener('change', () => this._restart(), options);
    document.addEventListener('visibilitychange', () => this._restart(), options);
    window.addEventListener('resize', () => this._fit(), options);
    window.visualViewport?.addEventListener('resize', () => this._fit(), options);
    window.visualViewport?.addEventListener('scroll', () => this._fit(), options);
    this._avatar.addEventListener('pointerdown', e => this._pointerDown(e), options);
    this._avatar.addEventListener('pointermove', e => this._pointerMove(e), options);
    this._avatar.addEventListener('pointerup', () => this._pointerEnd(), options);
    this._avatar.addEventListener('pointercancel', () => this._pointerEnd(true), options);
    this._avatar.addEventListener('lostpointercapture', () => this._pointerEnd(true), options);
    this._avatar.addEventListener('keydown', e => this._key(e), options);
    this.shadowRoot.addEventListener('click', e => this._click(e), options);
    this.shadowRoot.addEventListener('keydown', e => {
      if (e.key === 'Escape') { this._togglePanel(false); this._avatar.focus(); }
    }, options);
    const saved = this._read();
    if (saved?.position && Number.isFinite(saved.position.x) && Number.isFinite(saved.position.y)) this._position = saved.position;
    if (saved?.hidden === true) this.hidden = true;
    this._size(); this._restart(); this._fit();
    this._image = new Image();
    this._image.onload = () => {
      if (!this.isConnected) return;
      const valid = this._image.naturalWidth === ATLAS.width && this._image.naturalHeight === ATLAS.height;
      this.toggleAttribute('asset-error', !valid);
      this._restart(); this._fit();
      if (!valid) this._emit('pet-error', { reason: 'invalid-atlas-size' });
    };
    this._image.onerror = () => {
      if (!this.isConnected) return;
      this.setAttribute('asset-error', ''); this._restart(); this._fit();
      this._emit('pet-error', { reason: 'asset-load-failed' });
    };
    this._image.src = spriteURL;
  }

  disconnectedCallback() {
    clearTimeout(this._timer); this._timer = null;
    this._events?.abort(); this._events = null; this._drag = null;
    if (this._image) { this._image.onload = null; this._image.onerror = null; }
  }

  attributeChangedCallback(name) {
    if (!this.isConnected || !this._events) return;
    if (name === 'size') this._size();
    if (name === 'status' || name === 'animation') this._transient = null;
    this._restart(); this._fit();
  }

  get status() { return Object.hasOwn(STATUSES, this.getAttribute('status')) ? this.getAttribute('status') : 'idle'; }
  set status(value) {
    if (!Object.hasOwn(STATUSES, value)) throw new RangeError('Unknown pet status');
    this.setAttribute('status', value);
  }
  setStatus(value) { this.status = value; }
  show() { this.hidden = false; this._save(); this._emit('pet-visibility-change', { visible: true }); }
  hide() {
    this._togglePanel(false); this.hidden = true; this._save();
    this._emit('pet-visibility-change', { visible: false });
  }
  resetPosition() {
    this._position = null;
    this.style.removeProperty('left'); this.style.removeProperty('top');
    this.style.removeProperty('right'); this.style.removeProperty('bottom');
    this._fit(); this._save();
  }
  play(name) {
    if (!Object.hasOwn(ANIMATIONS, name)) throw new RangeError('Unknown pet animation');
    this._transient = { animation: name }; this._restart();
  }
  look(degrees) { this._transient = { look: lookFrame(degrees) }; this._restart(); }
  resume() { this._transient = null; this._restart(); }

  _size() {
    const input = Number(this.getAttribute('size') ?? 112);
    this.style.setProperty('--pet-size', `${Math.max(72, Math.min(192, Number.isFinite(input) ? input : 112))}px`);
  }
  _emit(name, detail) { this.dispatchEvent(new CustomEvent(name, { detail, bubbles: true, composed: true })); }
  _read() {
    try { return JSON.parse(localStorage.getItem(this.getAttribute('storage-key') || 'mygpt:jonah:v1')); }
    catch { return null; }
  }
  _save() {
    try { localStorage.setItem(this.getAttribute('storage-key') || 'mygpt:jonah:v1', JSON.stringify({ position: this._position, hidden: this.hidden })); }
    catch { /* Storage may be disabled. The pet still works for this session. */ }
  }
  _canAnimate() {
    return this.isConnected && !this.hidden && !document.hidden && !this._motion?.matches
      && !this.hasAttribute('paused') && !this.hasAttribute('asset-error');
  }
  _frame(row, column) {
    this._row = row; this._column = column;
    this._sprite.style.backgroundPosition = `${column / (ATLAS.columns - 1) * 100}% ${row / (ATLAS.rows - 1) * 100}%`;
  }
  _restart() {
    clearTimeout(this._timer); this._timer = null;
    const status = STATUSES[this.status];
    this._label.querySelector('span').textContent = status.label;
    const live = this.shadowRoot.querySelector('[role="status"]');
    if (live.textContent !== status.label) live.textContent = status.label;
    if (this._transient?.look) {
      this._frame(this._transient.look.row, this._transient.look.column); return;
    }
    const requested = this._transient?.animation || this.getAttribute('animation');
    const name = Object.hasOwn(ANIMATIONS, requested) ? requested : status.animation;
    const animation = ANIMATIONS[name];
    let column = 0;
    this._frame(animation.row, column);
    const next = () => {
      this._timer = null;
      if (!this._canAnimate()) return;
      column += 1;
      if (column >= animation.durations.length) {
        if (this._transient?.animation) { this._transient = null; this._restart(); return; }
        column = 0;
      }
      this._frame(animation.row, column);
      this._timer = setTimeout(next, animation.durations[column]);
    };
    if (this._canAnimate()) this._timer = setTimeout(next, animation.durations[0]);
  }
  _togglePanel(open = this._panel.hidden) {
    this._panel.hidden = !open;
    this._avatar.setAttribute('aria-expanded', String(open));
    this._label.setAttribute('aria-expanded', String(open));
    this._fit();
  }
  _click(event) {
    const button = event.target.closest('button');
    if (!button) return;
    if (button === this._avatar && this._suppressClick) { this._suppressClick = false; return; }
    switch (button.dataset.action) {
      case 'hide': this.hide(); break;
      case 'reset': this._togglePanel(false); this.resetPosition(); break;
      case 'chat': this._togglePanel(false); this._emit('pet-chat-request', { pet: 'jonah' }); break;
      case 'wave': this.play('waving'); this._togglePanel(false); break;
      default: this._togglePanel();
    }
  }
  _pointerDown(event) {
    if (!event.isPrimary || event.button !== 0) return;
    const rect = this.getBoundingClientRect();
    this._suppressClick = false;
    this._drag = { id: event.pointerId, x: event.clientX, y: event.clientY, left: rect.left, top: rect.top, moved: false };
    this._avatar.setPointerCapture(event.pointerId);
  }
  _pointerMove(event) {
    const drag = this._drag;
    if (!drag || event.pointerId !== drag.id) return;
    const dx = event.clientX - drag.x, dy = event.clientY - drag.y;
    if (!drag.moved && Math.hypot(dx, dy) < 6) return;
    drag.moved = true;
    this._position = { x: drag.left + dx, y: drag.top + dy };
    this._fit();
  }
  _pointerEnd(cancelled = false) {
    if (!this._drag) return;
    this._suppressClick = this._drag.moved || cancelled;
    this._drag = null; this._save();
  }
  _key(event) {
    const deltas = { ArrowLeft: [-16, 0], ArrowRight: [16, 0], ArrowUp: [0, -16], ArrowDown: [0, 16] };
    if (!Object.hasOwn(deltas, event.key)) return;
    event.preventDefault();
    const rect = this.getBoundingClientRect(), [dx, dy] = deltas[event.key];
    this._position = { x: rect.left + dx, y: rect.top + dy }; this._fit(); this._save();
  }
  _fit() {
    if (!this.isConnected || this.hidden) return;
    const viewport = window.visualViewport;
    const left = viewport?.offsetLeft || 0, top = viewport?.offsetTop || 0;
    const width = viewport?.width || window.innerWidth, height = viewport?.height || window.innerHeight;
    this.style.setProperty('--pet-panel-max-height', `${Math.max(44, height - this._avatar.offsetHeight - this._label.offsetHeight - 28)}px`);
    // Preserve the anchor in storage; keyboard/rotation clamping is temporary.
    if (!this._position) {
      this.style.removeProperty('left'); this.style.removeProperty('top');
      this.style.removeProperty('right'); this.style.removeProperty('bottom');
    }
    const rect = this.getBoundingClientRect();
    const point = this._position || { x: rect.left, y: rect.top };
    const x = Math.max(left + 8, Math.min(point.x, left + width - rect.width - 8));
    const y = Math.max(top + 8, Math.min(point.y, top + height - rect.height - 8));
    this.style.left = `${x}px`; this.style.top = `${y}px`;
    this.style.right = 'auto'; this.style.bottom = 'auto';
  }
}

if (!customElements.get('mygpt-pet')) customElements.define('mygpt-pet', MyGPTPet);
