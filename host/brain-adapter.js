const CLIENT = 'mygpt-reader-brain-v1';
const JSON_HEADERS = {'Content-Type':'application/json','X-MyGPT-Client':CLIENT};

async function jsonRequest(path,{method='GET',body,signal,keepalive=false}={}) {
  const response = await fetch(path,{method,credentials:'same-origin',cache:'no-store',
    headers: method==='GET'?{'X-MyGPT-Client':CLIENT}:JSON_HEADERS,
    body: body===undefined?undefined:JSON.stringify(body),signal,keepalive});
  let value;
  try { value = await response.json(); } catch { value = null; }
  if (!response.ok) {
    const error = new Error(value?.code || `local_brain_http_${response.status}`);
    error.code = value?.code || 'local_brain_http_error'; error.status = response.status;
    throw error;
  }
  return value;
}

export function createBrainAdapter() {
  const cancel = requestId => jsonRequest('/api/v1/cancel',{method:'POST',keepalive:true,
    body:{schema_version:'mygpt.local-cancel.v1',request_id:requestId}}).catch(()=>null);
  const adapter = async (request,_entry,{signal}) => {
    let finished=false;
    const onAbort=()=>{ if(!finished) void cancel(request.request_id); };
    signal.addEventListener('abort',onAbort,{once:true});
    try {
      return await jsonRequest('/api/v1/explain',{method:'POST',signal,body:{
        schema_version:'mygpt.local-explain.v1',...request,
      }});
    } finally {
      finished=true; signal.removeEventListener('abort',onAbort);
    }
  };
  adapter.status = () => jsonRequest('/api/v1/status');
  adapter.revoke = () => jsonRequest('/api/v1/revoke',{method:'POST',
    body:{schema_version:'mygpt.local-revoke.v1'}});
  return adapter;
}
