/** No fetch, WebSocket, live model, or implicit retries. Delay is visibly a demo. */
export function createReplayAdapter({delayMs=650, digest = bytes => crypto.subtle.digest('SHA-256',bytes)} = {}) {
  return async (request, entry, {signal}) => {
    if (signal.aborted) throw new DOMException('Cancelled','AbortError');
    const hash = [...new Uint8Array(await digest(new TextEncoder().encode(entry.evidence_text)))]
      .map(byte=>byte.toString(16).padStart(2,'0')).join('');
    if (hash !== request.source_sha256) throw new Error('fixture byte mismatch');
    if (signal.aborted) throw new DOMException('Cancelled','AbortError');
    await new Promise((resolve,reject) => {
      const stop = () => {clearTimeout(timer);reject(new DOMException('Cancelled','AbortError'));};
      const timer = setTimeout(() => {signal.removeEventListener('abort',stop);resolve();},delayMs);
      signal.addEventListener('abort',stop,{once:true});
    });
    if (signal.aborted) throw new DOMException('Cancelled','AbortError');
    return {...request,text:entry.fixture_reply,model_called:false};
  };
}
