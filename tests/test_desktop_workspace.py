import http.client
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'brain'))
from desktop_adapter import start
from desktop_chat import validate_request

class WorkspaceHTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.svc=start(Path(self.tmp.name),Path(__file__).resolve().parents[1])
        self.addCleanup(self.svc.close)
        self.httpd=self.svc.server.httpd
        status,headers,_=self.call('/desktop/')
        self.assertEqual(status,200);self.cookie=headers['Set-Cookie'].split(';')[0]
    def call(self,path,value=None,headers=None):
        conn=http.client.HTTPConnection('127.0.0.1',self.httpd.server_port,timeout=3)
        try:
            conn.request('GET' if value is None else 'POST',path,None if value is None else json.dumps(value),headers or {})
            r=conn.getresponse();return r.status,dict(r.getheaders()),r.read()
        finally:conn.close()
    def headers(self):
        return {'Cookie':self.cookie,'Origin':self.httpd.origin,'X-MyGPT-Client':'mygpt-desktop-v1','Content-Type':'application/json'}
    def test_notes_roundtrip(self):
        status,_,body=self.call('/desktop-api/state',headers=self.headers());self.assertEqual(status,200)
        state=json.loads(body);state['value']['notes']['test']={'title':'a','body':'b'}
        self.assertEqual(self.call('/desktop-api/state',state,self.headers())[0],200)
        self.assertEqual(json.loads(self.call('/desktop-api/state',headers=self.headers())[2])['value']['notes']['test']['body'],'b')
    def test_missing_cookie_and_cross_origin_refused(self):
        self.assertEqual(self.call('/desktop-api/state')[0],403)
        h=self.headers();h['Origin']='https://unrelated.invalid'
        self.assertEqual(self.call('/desktop-api/state',headers=h)[0],403)
    def test_invalid_host_refused(self):
        self.assertEqual(self.call('/desktop/',headers={'Host':'unrelated.invalid'})[0],403)
    def test_revision_conflict(self):
        state=json.loads(self.call('/desktop-api/state',headers=self.headers())[2]);state['value']['goal']='first'
        self.assertEqual(self.call('/desktop-api/state',state,self.headers())[0],200)
        state['value']['goal']='stale'
        self.assertEqual(self.call('/desktop-api/state',state,self.headers())[0],409)
    def test_no_implicit_provider_or_intake(self):
        status=self.httpd.engine.status()
        self.assertEqual(status['requests_started'],0);self.assertFalse(status['selection_intake_enabled'])
    def test_consent_required_before_any_local_call(self):
        with patch('desktop_chat.OllamaResponder') as op:
            status=self.call('/desktop-api/local-chat',{'consent':False,'port':11434,'model':'test','prompt':'x'},self.headers())[0]
            self.assertEqual(status,400);op.assert_not_called()
    def test_invalid_backup_preserves_state(self):
        before=self.httpd.workspace.read()
        self.assertEqual(self.call('/desktop-api/merge',{'schema':'bad'},self.headers())[0],400)
        self.assertEqual(self.httpd.workspace.read(),before)

class LocalModelBoundaryTests(unittest.TestCase):
    def test_cloud_model_and_invalid_port_refused(self):
        from uuid import uuid4
        for port,model in [(0,'test'),(True,'test'),(65536,'test'),(11434,'test-cloud')]:
            with patch('desktop_chat.OllamaResponder') as op:
                with self.assertRaises(ValueError):
                    validate_request({'consent':True,'port':port,'model':model,'prompt':'x','request_id':str(uuid4())})
                op.assert_not_called()

if __name__=='__main__':unittest.main()
