#!/usr/bin/env python3
"""Actual loopback HTTP security/contract smoke test with an injected fixture responder.

No Pydantic AI dependency, provider, Book endpoint, external request or persistent
file is used. The only socket is the server/client pair on 127.0.0.1.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import http.client
import json
from pathlib import Path
import sys
from types import SimpleNamespace

# Make direct `python scripts/smoke_local_service.py` execution work without
# relying on an inherited PYTHONPATH. This only adds the local brain source root.
BRAIN_ROOT = Path(__file__).resolve().parents[1]
if str(BRAIN_ROOT) not in sys.path:
    sys.path.insert(0, str(BRAIN_ROOT))

from mygpt_brain.host_fixtures import build_catalogue
from mygpt_brain.local_service import CLIENT_HEADER, create_local_server


def call(origin, method, path, *, cookie=None, value=None, origin_header=True, referer=True,
         client=True, host=None, fetch_site=None):
    port=int(origin.rsplit(':',1)[1]); conn=http.client.HTTPConnection('127.0.0.1',port,timeout=5)
    body=None if value is None else json.dumps(value,separators=(',',':')).encode()
    headers={}
    if cookie: headers['Cookie']=cookie
    if client: headers['X-MyGPT-Client']=CLIENT_HEADER
    if origin_header: headers['Origin']=origin
    if referer: headers['Referer']=origin+'/host/brain.html'
    if fetch_site is not None: headers['Sec-Fetch-Site']=fetch_site
    if body is not None: headers['Content-Type']='application/json';headers['Content-Length']=str(len(body))
    if host is None:
        conn.request(method,path,body=body,headers=headers)
    else:
        conn.putrequest(method,path,skip_host=True);conn.putheader('Host',host)
        for k,v in headers.items():conn.putheader(k,v)
        conn.endheaders(body)
    response=conn.getresponse();raw=response.read();result=None
    if raw:
        try: result=json.loads(raw)
        except ValueError: result=raw.decode('utf-8','replace')
    info=(response.status,dict(response.getheaders()),result);conn.close();return info


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[2])
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    async def responder(_brain,_evidence,_question,fixture_text,_now):
        return SimpleNamespace(text=fixture_text)
    checks=[]
    with create_local_server(root=args.root,responder=responder,authorization_seconds=60) as server:
        origin=server.origin
        status,headers,body=call(origin,'GET','/host/brain.html',origin_header=False,referer=False,client=False)
        assert status==200 and '本机 Brain' in body
        set_cookie=headers.get('Set-Cookie','');cookie=set_cookie.split(';',1)[0]
        assert cookie.startswith('mygpt_local_brain=') and 'HttpOnly' in set_cookie and 'SameSite=Strict' in set_cookie
        assert cookie.split('=',1)[1] not in body;checks.append('html_sets_httponly_cookie_without_echo')
        status,_,body=call(origin,'GET','/api/v1/status',cookie=cookie,origin_header=False)
        assert status==200 and body['scope']=='SYNTHETIC_LOCAL_PYTHON_BRAIN' and body['paid_model_calls']==0
        assert body['test_model'] is False and body['responder_kind']=='INJECTED_TEST_FIXTURE'
        checks.append('authorized_same_origin_status')
        status,_,body=call(origin,'GET','/api/v1/status',cookie=cookie,origin_header=False,referer=False,fetch_site='same-origin')
        assert status==200 and body['authorized'] is True
        checks.append('no_referrer_same_origin_browser_get_supported')
        assert call(origin,'GET','/api/v1/status',origin_header=False)[0]==403;checks.append('missing_cookie_rejected')
        assert call(origin,'GET','/api/v1/status',cookie=cookie,origin_header=False,referer=False)[0]==403
        checks.append('origin_evidence_required_without_fetch_metadata')
        assert call(origin,'GET','/api/v1/status',cookie=cookie,origin_header=False,referer=False,fetch_site='cross-site')[0]==403
        checks.append('cross_site_fetch_metadata_rejected')
        assert call(origin,'GET','/api/v1/status',cookie=cookie,origin_header=False,host='localhost:1')[0]==403
        checks.append('host_header_pinned')
        assert call(origin,'GET','/../SECURITY_POLICY.md',origin_header=False,referer=False,client=False)[0]==404
        checks.append('static_allowlist_blocks_traversal')
        entry={x['id']:x for x in build_catalogue()['entries']}['a-source']
        now_ms=int(datetime.now(timezone.utc).timestamp()*1000)
        request={'schema_version':'mygpt.local-explain.v1','scope':'SYNTHETIC_FIXED_REPLAY',
                 'request_id':'smoke-1','revision':1,'entry_id':'a-source','mode':'learn',
                 'source_ref':entry['source_ref'],'source_sha256':entry['context']['source_sha256'],
                 'selection_expires_at_ms':now_ms+60000}
        status,_,body=call(origin,'POST','/api/v1/explain',cookie=cookie,value=request)
        assert status==200 and body['brain_action']=='explain' and body['text']==entry['fixture_reply'] and body['replayed'] is False
        checks.append('real_brain_policy_path_over_loopback')
        status,_,body=call(origin,'POST','/api/v1/explain',cookie=cookie,value=request)
        assert status==200 and body['replayed'] is True;checks.append('identical_request_deduplicated')
        forged=dict(request,entry_id='b-source')
        assert call(origin,'POST','/api/v1/explain',cookie=cookie,value=forged)[0]==409
        checks.append('request_id_conflict_rejected')
        assert call(origin,'POST','/api/v1/explain',cookie=cookie,value={**request,'request_id':'smoke-2'},
                    origin_header=False)[0]==403
        checks.append('post_requires_exact_origin')
        assert call(origin,'OPTIONS','/api/v1/explain',cookie=cookie,value={})[0]==405
        checks.append('cors_preflight_not_enabled')
        assert call(origin,'PUT','/api/v1/explain',cookie=cookie,value=request)[0]==405
        checks.append('unexpected_methods_rejected')
        status,_,body=call(origin,'POST','/api/v1/cancel',cookie=cookie,
            value={'schema_version':'mygpt.local-cancel.v1','request_id':'unknown'})
        assert status==200 and body['status']=='unknown_request';checks.append('bounded_cancel_endpoint')
        status,_,body=call(origin,'POST','/api/v1/revoke',cookie=cookie,
            value={'schema_version':'mygpt.local-revoke.v1'})
        assert status==200 and body['status']=='revoked';checks.append('explicit_revocation')
        assert call(origin,'GET','/api/v1/status',cookie=cookie,origin_header=False)[0]==403
        checks.append('revocation_blocks_further_api')
    report={'schema_version':'mygpt.local-http-smoke.v1','result':'PASS','checks':checks,
            'checks_passed':len(checks),'external_requests':0,'model_calls':0}
    text=json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+'\n'
    print(text,end='')
    if args.output:
        with args.output.open('x',encoding='utf-8') as f:f.write(text)
    return 0

if __name__=='__main__':raise SystemExit(main())
