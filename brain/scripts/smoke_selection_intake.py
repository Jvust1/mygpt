"""Actual bounded loopback tests. Uses synthetic packets and an injected responder."""
from __future__ import annotations
import argparse
import http.client
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from mygpt_brain.local_service import create_local_server, CLIENT_HEADER
from mygpt_brain.reader_demo import fixture, NOW
from mygpt_brain.selection_packet import export_reader_selection, encode_packet

async def fixed(_brain,_evidence,_question,text,_now):
    return SimpleNamespace(text=text)

def call(server, method, path, raw=None, *, cookie=None, extra=(), omit=()):
    c=http.client.HTTPConnection('127.0.0.1',int(server.origin.rsplit(':',1)[1]),timeout=5)
    headers=[('Host',server.origin.split('//')[1]),('Origin',server.origin),('X-MyGPT-Client',CLIENT_HEADER)]
    if cookie:headers.append(('Cookie',cookie))
    if raw is not None:headers.extend([('Content-Type','application/json'),('Content-Length',str(len(raw)))])
    c.putrequest(method,path,skip_host=True,skip_accept_encoding=True)
    for key,value in [*headers,*extra]:
        if key not in omit:c.putheader(key,value)
    c.endheaders(raw)
    r=c.getresponse();body=r.read(); result=(r.status,dict(r.getheaders()),body);c.close()
    return result

def run():
    checks=[]
    def check(name, condition):
        assert condition,name
        checks.append(name)
    m,s,snap=fixture()
    packet=export_reader_selection(m,s,snap,session_id=snap['session_id'],epoch=1,now=NOW)
    raw=encode_packet(packet)
    with create_local_server(responder=fixed) as server:
        status,headers,_=call(server,'GET','/host/selection.html')
        cookie=headers['Set-Cookie'].split(';')[0]
        check('default_off',call(server,'POST','/api/v1/selection',raw,cookie=cookie)[0]==403)
    with create_local_server(responder=fixed,enable_selection_intake=True) as server:
        status,headers,body=call(server,'GET','/host/selection.html')
        cookie=headers['Set-Cookie'].split(';')[0]
        check('selection_page_and_httponly_cookie',status==200 and 'HttpOnly' in headers['Set-Cookie'])
        check('frame_embedding_denied',headers.get('X-Frame-Options')=='DENY')
        check('connection_closed_after_response',headers.get('Connection')=='close')
        check('token_not_in_html',cookie.split('=',1)[1].encode() not in body)
        for name, kwargs in [('missing_cookie',{}),('missing_client',{'cookie':cookie,'omit':('X-MyGPT-Client',)}),
            ('missing_origin',{'cookie':cookie,'omit':('Origin',)}),
            ('cross_site',{'cookie':cookie,'extra':(('Sec-Fetch-Site','cross-site'),)})]:
            check(name,call(server,'POST','/api/v1/selection',raw,**kwargs)[0]==403)
        for name,value in [('Content-Length','1'),('Host','wrong.invalid'),('Cookie','x=y'),
                           ('Origin','http://wrong.invalid'),('Content-Type','text/plain')]:
            check('duplicate_'+name,call(server,'POST','/api/v1/selection',raw,cookie=cookie,extra=((name,value),))[0]==400)
        check('static_host_pinned',call(server,'GET','/host/selection.html',extra=(('Host','wrong.invalid'),))[0]==403)
        check('missing_length',call(server,'POST','/api/v1/selection',raw,cookie=cookie,omit=('Content-Length',))[0]==411)
        for label, bad in [('duplicate_json',b'{"a":1,"a":2}'),('nonfinite',b'{"x":NaN}'),
            ('surrogate',b'{"x":"\\ud800"}'),('utf8',b'{"x":"\xff"}'),
            ('depth',b'{"a":'+b'['*26+b'0'+b']'*26+b'}'),
            ('metadata',raw[:-2]+b',"notes":"not allowed"}')]:
            check('reject_'+label,call(server,'POST','/api/v1/selection',bad,cookie=cookie)[0]==400)
        check('size_limit',call(server,'POST','/api/v1/selection',b' '*65537,cookie=cookie)[0]==413)
        check('original_api_limit_unchanged',call(server,'POST','/api/v1/explain',b' '*8193,cookie=cookie)[0]==413)
        status,_,body=call(server,'POST','/api/v1/selection',raw,cookie=cookie);entry=json.loads(body)['entry']
        check('one_record_received',status==200 and entry['context']['evidence_kind']=='USER_SUPPLIED_UNVERIFIED')
        check('import_does_not_explain',server.httpd.engine.status()['requests_started']==0)
        request={'schema_version':'mygpt.local-explain.v1','scope':'LOCAL_UNVERIFIED_SELECTION',
            'request_id':'smoke-selected-1','revision':1,'entry_id':entry['id'],'mode':'learn',
            'source_ref':entry['source_ref'],'source_sha256':entry['context']['source_sha256'],
            'selection_expires_at_ms':int(datetime.now(timezone.utc).timestamp()*1000)+60000}
        req=json.dumps(request).encode();status,_,body=call(server,'POST','/api/v1/explain',req,cookie=cookie)
        reply=json.loads(body)
        check('actual_brain_path',status==200 and reply['brain_action']=='explain' and reply['source_trust']=='USER_SUPPLIED_UNVERIFIED')
        status,_,body=call(server,'POST','/api/v1/explain',req,cookie=cookie)
        check('import_request_deduplication',status==200 and json.loads(body)['replayed'] is True)
        check('no_paid_model_or_live_book',reply['paid_model_calls']==0 and reply['live_book_connected'] is False)
        check('reply_does_not_claim_real_inference',reply['text'].startswith('[SIMULATED]'))
        status,_,_=call(server,'POST','/api/v1/revoke',b'{"schema_version":"mygpt.local-revoke.v1"}',cookie=cookie)
        check('revoke_clears_imports',status==200 and server.httpd.engine.status()['imports_active']==0)
        check('revoke_blocks_input',call(server,'POST','/api/v1/selection',raw,cookie=cookie)[0]==403)
    return {'result':'PASS','scope':'LOOPBACK_HTTP_SYNTHETIC_INPUT_INJECTED_RESPONDER',
            'checks':checks,'checks_passed':len(checks),'paid_model_calls':0,'external_requests':0}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path)
    args=parser.parse_args();result=run();text=json.dumps(result,ensure_ascii=False,indent=2)+'\n';print(text,end='')
    if args.output:
        with args.output.open('x') as file:file.write(text)
