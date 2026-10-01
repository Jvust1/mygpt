import tempfile
import unittest
from pathlib import Path
from desktop_state import Store, empty, validate

class DesktopStateTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.store=Store(self.root)
    def test_restart_persistence(self):
        state=self.store.read();state['value']['notes']['one']={'title':'标题','body':'正文'}
        saved=self.store.save(state['revision'],state['value'])
        self.assertEqual(saved,Store(self.root).read())
    def test_stale_revision_refused(self):
        state=empty();state['goal']='first';self.store.save(0,state)
        with self.assertRaisesRegex(ValueError,'revision_conflict'):self.store.save(0,empty())
        self.assertEqual(self.store.read()['value']['goal'],'first')
    def test_unchanged_save_is_noop(self):
        self.assertEqual(self.store.save(0,empty())['revision'],0)
    def test_merge_preserves_conflict_and_is_idempotent(self):
        first=empty();first['notes']['same']={'title':'local','body':'keep'};self.store.save(0,first)
        incoming=empty();incoming['notes']['same']={'title':'other','body':'also keep'}
        packet={'schema':'mygpt-workspace-backup-v1','value':incoming}
        result=self.store.merge(packet);repeat=self.store.merge(packet)
        self.assertEqual(result,repeat);self.assertEqual(len(result['value']['notes']),2)
        self.assertEqual(result['value']['notes']['same']['body'],'keep')
    def test_import_does_not_resume_foreign_timer(self):
        value=empty();value['active']={'id':'x','goal':'t','started_ms':10,'target_sec':60}
        self.assertIsNone(self.store.merge({'schema':'mygpt-workspace-backup-v1','value':value})['value']['active'])
    def test_invalid_payloads_do_not_mutate_state(self):
        values=[None,{},dict(empty(),unknown=1)]
        n=empty();n['notes']={'bad':{'title':'a','body':0}};values.append(n)
        n=empty();n['sessions']={'x':{'goal':'a','seconds':-1,'ended_at':'now'}};values.append(n)
        n=empty();n['active']={'id':'x','goal':'t','started_ms':True,'target_sec':60};values.append(n)
        for value in values:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):self.store.save(0,value)
        self.assertEqual(self.store.read()['revision'],0)
    def test_corrupt_store_is_not_replaced(self):
        p=self.root/'broken';p.mkdir();(p/'workspace.sqlite').write_bytes(b'bad database')
        with self.assertRaises(Exception):Store(p)
        self.assertEqual((p/'workspace.sqlite').read_bytes(),b'bad database')
    def test_notes_limit(self):
        n=empty();n['notes']={'x':{'title':'x','body':'a'*20001}}
        with self.assertRaises(ValueError):validate(n)

if __name__=='__main__':unittest.main()
