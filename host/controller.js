/** Small host-side UI state machine. It never claims transport/model truth.
 * Adapters may be a fixed browser replay or the loopback Python Brain demo.
 * No source text is persisted. A lease belongs to this UI selection only.
 */
const MODES = new Set(['preview', 'learn', 'review', 'practice']);
const ACTIVE = new Set(['selected', 'working', 'ready', 'error']);
const PET = {empty:'needs-input',selected:'idle',working:'working',ready:'ready',
  error:'blocked',expired:'blocked',paused:'idle',revoked:'blocked',disposed:'idle'};
let instances = 0;
function freeze(value) {
  if (value && typeof value === 'object') {
    Object.values(value).forEach(freeze); Object.freeze(value);
  }
  return value;
}

export function createHostController({catalogue, adapter, now = () => Date.now(),
  monotonic = () => performance.now(), setTimer = setTimeout, clearTimer = clearTimeout,
  ttlMs = 120000, timeoutMs = 8000} = {}) {
  const imported = catalogue?.schema === 'mygpt.host-selection.v1'
    && catalogue.scope === 'LOCAL_UNVERIFIED_SELECTION';
  const replay = catalogue?.schema === 'mygpt.host-replay.v1'
    && catalogue.scope === 'SYNTHETIC_FIXED_REPLAY';
  if ((!imported && !replay)
      || catalogue.live_book_connected !== false || catalogue.model_calls !== 0
      || !Array.isArray(catalogue.entries) || !catalogue.entries.length || catalogue.entries.length > 32
      || typeof adapter !== 'function') throw new TypeError('invalid replay configuration');
  if (!Number.isSafeInteger(ttlMs) || ttlMs < 1 || ttlMs > 300000
      || !Number.isSafeInteger(timeoutMs) || timeoutMs < 1 || timeoutMs > 30000)
    throw new RangeError('invalid time budget');
  const entries = new Map();
  for (const item of catalogue.entries) {
    const entry = freeze(structuredClone(item));
    if (typeof entry.id !== 'string' || entries.has(entry.id)
        || entry.context?.schema_version !== (imported?'mygpt.imported-reader-context.v1':'mygpt.reader-context.v2')
        || entry.context.evidence_kind !== (imported?'USER_SUPPLIED_UNVERIFIED':'SIMULATED')
        || typeof entry.source_ref !== 'string' || !entry.source_ref.startsWith(imported?'unverified-import:v1:reader:v2:':'reader:v2:')
        || !/^[a-f0-9]{64}$/.test(entry.context.source_sha256))
      throw new TypeError('invalid replay entry');
    entries.set(entry.id, entry);
  }
  const instance = ++instances;
  const instanceKey = (globalThis.crypto?.randomUUID?.() || `${Date.now()}-${instance}`)
    .replace(/[^A-Za-z0-9_.-]/g,'-').slice(0,70);
  const listeners = new Set();
  let state = {status:'empty',mode:'learn',entry:null,reply:null,reason:'choose_a_record',
    revision:0,expiresAt:null,requests:0,modelCalls:0};
  let lease = null, expiryTimer = null, pending = null;
  const snapshot = () => Object.freeze({...state,petStatus:PET[state.status]});
  function notify() { for (const fn of [...listeners]) fn(snapshot()); }
  function stopExpiry() { clearTimer(expiryTimer); expiryTimer = null; }
  function settlePending(reason) {
    if (!pending) return;
    const old = pending; pending = null;
    clearTimer(old.timer); old.abort.abort(); old.resolve({status:reason});
  }
  function invalidate(status, reason) {
    settlePending(reason); stopExpiry(); lease = null;
    state = {...state,status,reason,entry:null,reply:null,expiresAt:null,revision:state.revision+1};
    notify();
  }
  function fresh() {
    if (!lease || !ACTIVE.has(state.status)) return false;
    const wall = now(), mono = monotonic();
    // Detect backwards clocks as well as elapsed deadlines, even when a browser
    // throttles timers while hidden. A timer firing is not the source of truth.
    if (!Number.isFinite(wall) || !Number.isFinite(mono) || wall < lease.lastWall
        || mono < lease.lastMono || wall >= lease.wallEnd || mono >= lease.monoEnd) {
      invalidate('expired','selection_expired'); return false;
    }
    lease.lastWall = wall; lease.lastMono = mono;
    return true;
  }
  function armExpiry() {
    stopExpiry();
    if (fresh()) expiryTimer = setTimer(() => { expiryTimer = null; armExpiry(); },
      Math.max(1, Math.min(lease.wallEnd-now(), lease.monoEnd-monotonic())));
  }
  const alive = () => state.status !== 'disposed';
  const selectable = () => alive() && state.status !== 'revoked';
  function choose(id) {
    if (!selectable()) return false;
    const entry = entries.get(id);
    if (!entry) { invalidate('empty','unknown_selection'); return false; }
    settlePending('selection_changed'); stopExpiry();
    const wall = now(), mono = monotonic();
    if (!Number.isFinite(wall) || !Number.isFinite(mono)) {
      invalidate('expired','invalid_clock'); return false;
    }
    const remaining = imported ? Math.min(ttlMs, Date.parse(entry.context.expires_at)-wall) : ttlMs;
    if (!Number.isFinite(remaining) || remaining <= 0) {
      invalidate('expired','selection_expired'); return false;
    }
    lease = {wallEnd:wall+remaining,monoEnd:mono+remaining,lastWall:wall,lastMono:mono};
    state = {...state,status:'selected',entry,reply:null,reason:'explicit_selection',
      revision:state.revision+1,expiresAt:lease.wallEnd};
    armExpiry(); notify(); return true;
  }
  function changeMode(mode) {
    if (!MODES.has(mode)) throw new RangeError('unknown mode');
    if (!selectable()) return false;
    if (mode === state.mode) return true;
    state = {...state,mode}; invalidate('empty','mode_changed_choose_again'); return true;
  }
  function explain() {
    if (!selectable() || !fresh()) return Promise.resolve({status:'not_available'});
    if (pending) return pending.promise; // one UI request, not one per tap
    const revision = state.revision, entry = state.entry, mode = state.mode;
    const request = freeze({request_id:`ui-${instanceKey}-${state.requests+1}`,
      revision,entry_id:entry.id,mode,source_ref:entry.source_ref,
      source_sha256:entry.context.source_sha256,selection_expires_at_ms:lease.wallEnd,
      scope:catalogue.scope});
    const abort = new AbortController();
    let resolve;
    const promise = new Promise(done => {resolve = done;});
    const token = {request,abort,resolve,promise,timer:null}; pending = token;
    state = {...state,status:'working',reply:null,reason:'replaying_fixture',requests:state.requests+1};
    function fail(code) {
      if (pending !== token) return;
      if (!fresh()) return;
      pending = null; clearTimer(token.timer); abort.abort();
      state = {...state,status:'error',reply:null,reason:code}; notify(); resolve({status:code});
    }
    token.timer = setTimer(() => fail('request_timeout'), timeoutMs);
    notify();
    Promise.resolve().then(() => {
      if (pending !== token || abort.signal.aborted) return null;
      return adapter(request, entry, {signal:abort.signal});
    }).then(reply => {
      if (pending !== token || abort.signal.aborted || state.revision !== revision || !fresh()) return;
      if (!reply || reply.scope !== request.scope || reply.request_id !== request.request_id
          || reply.entry_id !== entry.id || reply.revision !== revision || reply.mode !== mode
          || reply.source_ref !== entry.source_ref || reply.source_sha256 !== request.source_sha256
          || typeof reply.text !== 'string' || !reply.text.trim() || reply.text.length > 4000
          || (imported && reply.source_trust !== 'USER_SUPPLIED_UNVERIFIED')
          || reply.model_called !== false) { fail('response_identity_mismatch'); return; }
      pending = null; clearTimer(token.timer);
      state = {...state,status:'ready',reply:reply.text,reason:'fixture_ready'};
      notify(); resolve({status:'ready'});
    }).catch(() => fail('replay_failed')); // never render arbitrary exception text
    return promise;
  }
  function cancel() {
    if (!alive() || !pending || !fresh()) return false;
    settlePending('cancelled');
    state = {...state,status:'selected',reply:null,reason:'cancelled',revision:state.revision+1};
    notify(); return true;
  }
  return Object.freeze({
    getState() { if (ACTIVE.has(state.status)) fresh(); return snapshot(); },
    subscribe(fn) {
      if (typeof fn !== 'function') throw new TypeError('listener required');
      if (!alive()) return () => {};
      listeners.add(fn); fn(snapshot()); return () => listeners.delete(fn);
    },
    choose, changeMode, explain, cancel,
    pause() { if (selectable()) invalidate('paused','paused_choose_again'); },
    revoke() { if (alive()) invalidate('revoked','replay_disabled'); },
    dispose() { if (alive()) { invalidate('disposed','closed'); listeners.clear(); } },
  });
}
