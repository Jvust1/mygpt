"""Actual loopback synthetic-provider tests; no downloaded or real model.

Hosted frozen-EXE/Edge coverage lives in tools/desktop_browser_test.py.
"""
import asyncio
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sqlite3
import socket
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'brain'))
from desktop_adapter import start
from desktop_chat import SESSION_ID, PERSONA_ID
from mygpt_brain.companion_chat import CompanionChatRuntime


class SyntheticProvider:
    def __init__(self):
        self.calls = []
        self.status = 200
        self.reply = '合成回复\nUnicode 🦉 <b>不执行 HTML</b>'
        self.started = threading.Event()
        self.release = threading.Event()
        self.release.set()
        owner = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_): pass
            def do_POST(self):
                owner.calls.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
                owner.started.set()
                owner.release.wait(timeout=3)
                raw = json.dumps({'message': {'content': owner.reply}}, ensure_ascii=False).encode()
                try:
                    self.send_response(owner.status)
                    if owner.status == 302:
                        self.send_header('Location', 'http://127.0.0.1:1/never-follow')
                    self.send_header('Content-Length', str(len(raw)))
                    self.end_headers();self.wfile.write(raw)
                except (BrokenPipeError, ConnectionResetError): pass
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_port
    def close(self):
        self.release.set();self.server.shutdown();self.server.server_close();self.thread.join(timeout=3)


class DesktopChatTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.provider = SyntheticProvider();self.addCleanup(self.provider.close)
        self.restart()
    def restart(self):
        if hasattr(self, 'service'): self.service.close()
        self.service = start(self.home, ROOT);self.addCleanup(self.service.close)
        self.httpd = self.service.server.httpd
        status, headers, _ = self.request('/desktop/', headers={})
        self.assertEqual(status, 200)
        self.cookie = headers['Set-Cookie'].split(';')[0]
    def headers(self):
        return {'Cookie':self.cookie, 'Origin':self.httpd.origin,
                'X-MyGPT-Client':'mygpt-desktop-v1', 'Content-Type':'application/json'}
    def request(self, path, value=None, headers=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.httpd.server_port, timeout=5)
        try:
            conn.request('GET' if value is None else 'POST', path,
                         None if value is None else json.dumps(value),
                         self.headers() if headers is None else headers)
            response=conn.getresponse()
            return response.status,dict(response.getheaders()),response.read()
        finally:conn.close()
    def send(self, value):
        code,_,raw=self.request('/desktop-api/local-chat',value)
        return code,json.loads(raw)
    def question(self, text='合成问题\n保留空白 🦉'):
        return {'consent':True,'port':self.provider.port,'model':'synthetic-test-only',
                'prompt':text,'request_id':str(uuid4())}
    def history(self, suffix=''):
        code,_,raw=self.request('/desktop-api/chat-history'+suffix)
        self.assertEqual(code,200)
        return json.loads(raw)
    def test_two_turns_restart_without_provider_and_no_runtime_cache(self):
        q1=self.question();q2=self.question('第二问，精确保留\n\n尾行 ')
        for q in (q1,q2):
            code, result=self.send(q);self.assertEqual(code,200)
            self.assertTrue(result['saved']);self.assertEqual(result['reply'],self.provider.reply)
        for request in self.provider.calls:
            self.assertEqual(request['keep_alive'], '0')
            self.assertEqual(request['options'], {'num_predict': 2048})
        visible=self.history()['messages']
        self.assertEqual([m['content'] for m in visible],[q1['prompt'],self.provider.reply,q2['prompt'],self.provider.reply])
        self.assertIn({'role':'user','content':q1['prompt']},self.provider.calls[1]['messages'])
        self.assertIn({'role':'assistant','content':self.provider.reply},self.provider.calls[1]['messages'])
        self.assertEqual(self.httpd.desktop_chat.runtime._sessions,{})
        self.assertEqual(self.httpd.desktop_chat.runtime._requests,{})
        with sqlite3.connect(self.home/'data/chat.sqlite3') as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM chat_request_receipts').fetchone()[0],2)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM chat_messages WHERE role!='system'").fetchone()[0],4)
        self.provider.close();self.provider.close=lambda:None
        old_port=self.httpd.server_port;self.restart()
        self.assertNotEqual(self.httpd.server_port,old_port)
        self.assertEqual(self.history()['messages'],visible)
        self.assertEqual(len(self.provider.calls),2)
    def test_commit_then_lost_reply_recovers_receipt_without_inference(self):
        q=self.question()
        # Actual HTTP cut after atomic commit but before any response bytes.
        from desktop_workspace import WorkspaceHandler
        original=WorkspaceHandler._json
        def drop_reply(handler, status, result):
            if handler.path == '/desktop-api/local-chat' and result.get('saved') is True:
                handler.close_connection=True
                handler.connection.shutdown(socket.SHUT_RDWR)
                return
            return original(handler, status, result)
        with patch.object(WorkspaceHandler, '_json', drop_reply):
            with self.assertRaises(http.client.RemoteDisconnected):self.send(q)
        self.assertIsNotNone(self.httpd.desktop_chat.store.get_receipt(q['request_id']))
        code,replay=self.send(q)
        self.assertEqual(code,200);self.assertTrue(replay['replayed'])
        self.assertEqual(self.provider.reply,replay['reply']);self.assertEqual(len(self.provider.calls),1)
        self.assertEqual(len(self.history()['messages']),2)
        self.restart();self.assertTrue(self.send(q)[1]['replayed'])
        self.assertEqual(len(self.provider.calls),1)
    def test_same_id_different_text_model_or_port_conflicts(self):
        q=self.question();self.assertEqual(self.send(q)[0],200)
        for field,value in [('prompt','different'),('model','different'),('port',1)]:
            changed={**q,field:value};code,result=self.send(changed)
            self.assertEqual(code,409);self.assertEqual(result['code'],'request_id_conflict')
        self.assertEqual(len(self.provider.calls),1)
    def test_inflight_duplicate_is_busy_not_second_dispatch(self):
        self.provider.release.clear();q=self.question();result=[]
        worker=threading.Thread(target=lambda:result.append(self.send(q)));worker.start()
        self.assertTrue(self.provider.started.wait(timeout=2))
        self.assertEqual(self.send(q)[0],429)
        self.provider.release.set();worker.join(timeout=3)
        self.assertEqual(result[0][0],200);self.assertTrue(self.send(q)[1]['replayed'])
        self.assertEqual(len(self.provider.calls),1)
    def test_provider_failure_claim_blocks_retry_after_restart(self):
        self.provider.status=500;q=self.question()
        self.assertEqual(self.send(q)[0],400)
        self.assertEqual(self.history()['messages'],[])
        self.restart();self.provider.status=200
        self.assertEqual(self.send(q)[0],409);self.assertEqual(len(self.provider.calls),1)
        self.assertEqual(self.history()['messages'],[])
    def test_save_failure_leaves_no_pair_or_receipt_and_never_reexecutes(self):
        q=self.question()
        with patch.object(self.httpd.desktop_chat.store, 'commit_exchange', side_effect=sqlite3.OperationalError('synthetic disk failure')):
            code,result=self.send(q);self.assertEqual(code,400);self.assertNotIn('saved',result)
        self.assertEqual(self.history()['messages'],[])
        self.assertIsNone(self.httpd.desktop_chat.store.get_receipt(q['request_id']))
        self.assertEqual(self.send(q)[0],409);self.assertEqual(len(self.provider.calls),1)
    def test_mid_transaction_failure_rolls_back_user_assistant_and_receipt(self):
        store=self.httpd.desktop_chat.store;q=self.question()
        with store._lock,store._db:
            store._db.execute("CREATE TRIGGER synthetic_save_failure BEFORE INSERT ON chat_messages "
                "WHEN NEW.role='assistant' BEGIN SELECT RAISE(ABORT, 'synthetic disk failure'); END")
        self.assertEqual(self.send(q)[0],400)
        self.assertEqual(self.history()['messages'],[])
        self.assertIsNone(store.get_receipt(q['request_id']))
        with store._lock:
            self.assertEqual(store._db.execute('SELECT COUNT(*) FROM chat_sessions').fetchone()[0],0)
            self.assertEqual(store._db.execute('SELECT COUNT(*) FROM chat_messages').fetchone()[0],0)
        self.assertEqual(self.send(q)[0],409);self.assertEqual(len(self.provider.calls),1)

    def test_claim_failure_never_contacts_provider(self):
        with patch.object(self.httpd.desktop_chat.store, 'claim_dispatch', side_effect=sqlite3.OperationalError('synthetic disk failure')):
            self.assertEqual(self.send(self.question())[0],500)
        self.assertEqual(self.provider.calls,[]);self.assertEqual(self.history()['messages'],[])
    def test_claim_before_dispatch_crash_is_unknown_after_restart(self):
        from desktop_chat import validate_request
        q=self.question();request,fingerprint,_,_=validate_request(q)
        self.httpd.desktop_chat.store.claim_dispatch(request.request_id,SESSION_ID,fingerprint)
        self.restart();self.assertEqual(self.send(q)[0],409)
        self.assertEqual(self.provider.calls,[]);self.assertEqual(self.history()['messages'],[])
    def test_late_provider_response_after_deadline_is_not_saved(self):
        q=self.question();self.provider.release.clear()
        self.httpd.desktop_chat.runtime.request_timeout_seconds=.5
        code,result=self.send(q);self.assertEqual(code,400);self.assertNotIn('saved',result)
        self.provider.release.set();time.sleep(.1)
        self.assertEqual(self.history()['messages'],[]);self.assertEqual(self.send(q)[0],409)
        self.assertEqual(len(self.provider.calls),1)
    def test_close_cancels_inflight_and_cannot_commit_late(self):
        self.provider.release.clear();q=self.question();result=[]
        worker=threading.Thread(target=lambda:result.append(self.send(q)));worker.start()
        self.assertTrue(self.provider.started.wait(timeout=2))
        self.service.close();self.provider.release.set();worker.join(timeout=3)
        self.restart();self.assertEqual(self.history()['messages'],[])
        self.assertEqual(self.send(q)[0],409);self.assertEqual(len(self.provider.calls),1)
    def test_history_is_protected_and_cursor_bounded(self):
        for headers in ({}, {**self.headers(),'Origin':'https://unrelated.invalid'}, {**self.headers(),'X-MyGPT-Client':'other'}):
            self.assertEqual(self.request('/desktop-api/chat-history',headers=headers)[0],403)
        for suffix in ('?before=0','?before=-1','?before=9223372036854775808','?before=x','?before=1&before=2','?limit=100000'):
            self.assertEqual(self.request('/desktop-api/chat-history'+suffix)[0],400)
        self.assertEqual(self.provider.calls,[])
    def test_history_pages_without_deleting_old_messages(self):
        # Populate via existing atomic runtime; injected synthetic responder only.
        async def populate():
            async def respond(_): return 'saved reply'
            runtime=CompanionChatRuntime(persona=self.httpd.desktop_chat.runtime.persona,
                responder=respond,session_store=self.httpd.desktop_chat.store)
            try:
                for index in range(25):
                    await runtime.send({'request_id':'history-'+str(index),'session_id':SESSION_ID,
                        'persona_id':PERSONA_ID,'text':'question '+str(index)})
            finally:runtime.memory_store.close()
        asyncio.run(populate())
        first=self.history();self.assertEqual(len(first['messages']),40)
        older=self.history('?before='+str(first['next_before']));self.assertEqual(len(older['messages']),10)
        self.assertIsNone(older['next_before'])
        self.assertEqual(len({m['message_id'] for m in older['messages']+first['messages']}),50)
        self.assertEqual(len(self.httpd.desktop_chat.store.load_messages(SESSION_ID)),51)
        self.assertEqual(self.provider.calls,[])
    def test_explicit_session_delete_clears_claims_and_allows_new_lifecycle(self):
        q=self.question();self.assertEqual(self.send(q)[0],200)
        store=self.httpd.desktop_chat.store
        self.assertTrue(store.delete_session(SESSION_ID));self.assertIsNone(store.get_receipt(q['request_id']))
        self.assertEqual(self.history()['messages'],[])
        self.assertEqual(self.send(q)[0],200);self.assertEqual(len(self.provider.calls),2)

    def test_explicit_delete_of_claim_only_session_invalidates_inflight_commit(self):
        q=self.question();self.provider.release.clear();result=[]
        worker=threading.Thread(target=lambda:result.append(self.send(q)));worker.start()
        self.assertTrue(self.provider.started.wait(timeout=2))
        self.assertTrue(self.httpd.desktop_chat.store.delete_session(SESSION_ID))
        self.provider.release.set();worker.join(timeout=3)
        self.assertEqual(result[0][0],400);self.assertEqual(self.history()['messages'],[])
        self.assertEqual(self.send(q)[0],200);self.assertEqual(len(self.provider.calls),2)

    def test_delete_after_claim_before_prompt_snapshot_revokes_old_admission(self):
        store=self.httpd.desktop_chat.store;original=store.claim_dispatch;q=self.question()
        def claim_then_delete(*args):
            result=original(*args)
            self.assertTrue(store.delete_session(SESSION_ID))
            return result
        with patch.object(store, 'claim_dispatch', claim_then_delete):
            self.assertEqual(self.send(q)[0],400)
        self.assertEqual(self.provider.calls,[]);self.assertEqual(self.history()['messages'],[])
        self.assertEqual(self.send(q)[0],200)

    def test_delete_then_reclaim_same_id_cannot_revive_old_generation(self):
        store=self.httpd.desktop_chat.store;original=store.claim_dispatch;q=self.question()
        def claim_delete_reclaim(*args):
            old=original(*args)
            self.assertTrue(store.delete_session(SESSION_ID))
            current=original(*args)
            self.assertNotEqual(old[1],current[1])
            return old
        with patch.object(store, 'claim_dispatch', claim_delete_reclaim):
            self.assertEqual(self.send(q)[0],400)
        self.assertEqual(self.provider.calls,[]);self.assertEqual(self.history()['messages'],[])

    def test_deep_history_page_uses_an_index_seek(self):
        from mygpt_brain.session_store import ChatSessionStore
        with ChatSessionStore() as store:
            with store._db:
                store._db.execute("INSERT INTO chat_sessions VALUES(?,?,?,?,?)",(SESSION_ID,PERSONA_ID,'2026-10-02T00:00:00+00:00','2026-10-02T00:00:00+00:00','v'))
                store._db.executemany("INSERT INTO chat_messages VALUES(?,?,?,?,?,?,?,?)",[
                    ('m-'+str(i),SESSION_ID,i,'user',None,'synthetic','2026-10-02T00:00:00+00:00',None)
                    for i in range(1,10001)])
            steps=[]
            def budget():steps.append(1);return len(steps)>100
            store._db.set_progress_handler(budget,100)
            page=store.history_page(SESSION_ID,persona_id=PERSONA_ID,before=100)
            store._db.set_progress_handler(None,0)
            self.assertEqual(len(page['messages']),40)
            self.assertLess(len(steps),100)  # <10,000 VM steps independent of newer history

    def test_exact_4000_and_over_limit_no_truncation(self):
        q=self.question('界'*4000);self.assertEqual(self.send(q)[0],200)
        self.assertEqual(self.provider.calls[0]['messages'][-1]['content'],'界'*4000)
        self.assertEqual(self.send(self.question('界'*4001))[0],400)
        self.assertEqual(len(self.provider.calls),1)
    def test_no_consent_invalid_uuid_or_config_never_dispatches(self):
        q=self.question()
        for updates in ({'consent':False},{'request_id':'bad'},{'port':True},{'model':'remote-cloud'},{'prompt':''}):
            self.assertEqual(self.send({**q,**updates})[0],400)
        self.assertEqual(self.provider.calls,[])
    def test_redirect_is_not_followed(self):
        self.provider.status=302;self.assertEqual(self.send(self.question())[0],400)
        self.assertEqual(len(self.provider.calls),1);self.assertEqual(self.history()['messages'],[])


if __name__=='__main__':unittest.main()
