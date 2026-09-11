from datetime import datetime
import json
import base64
import hashlib
from pathlib import Path
import tempfile
import threading
import unittest

from codex_taskbar.provider import Provider
from codex_taskbar.unread import UnreadState,identity_key,LOCAL_HOST_KEY
from codex_taskbar.usage import UsageCursor
from tests.test_usage import record


class UnreadTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.path=self.root/'state.json';self.reader=UnreadState(self.path)

    def tearDown(self):self.temp.cleanup()

    def write(self,ids):
        self.path.write_text(json.dumps({'electron-persisted-atom-state':{'unread-thread-ids-by-host-v1':{'local':ids,'remote':['other']}}}),encoding='utf-8')

    def test_only_local_ids_and_no_writeback(self):
        self.write(['a','a','b']);before=self.path.read_bytes()
        self.assertEqual(self.reader.read(),{'a','b'})
        self.assertEqual(self.path.read_bytes(),before)

    def test_mark_read_in_codex_is_reflected(self):
        self.write(['a','b']);self.reader.read()
        self.write(['b']);self.assertEqual(self.reader.read(),{'b'})

    def test_modern_state_selects_identity_and_local_host_and_clears_on_read(self):
        data={'electron-thread-read-state-v1':{'version':1,'unreadByIdentity':{
            'current':{LOCAL_HOST_KEY:['side'],'remote:fixture':['remote']},'other':{LOCAL_HOST_KEY:['other-user']}},
            'legacyMigration':{'identityKey':'old','unreadThreadIdsByHostId':{'local':['stale']}}}}
        self.path.write_text(json.dumps(data));self.reader.set_identity('current')
        self.assertEqual(self.reader.read(),{'side'})
        self.reader.set_identity('other');self.assertEqual(self.reader.read(),{'other-user'})
        self.reader.set_identity('current');data['electron-thread-read-state-v1']['unreadByIdentity']['current'][LOCAL_HOST_KEY]=[]
        self.path.write_text(json.dumps(data));before=self.path.read_bytes()
        self.assertEqual(self.reader.read(),set());self.assertEqual(before,self.path.read_bytes())
        self.reader.set_identity(None);self.assertIsNone(self.reader.read())

    def test_modern_unavailable_does_not_fall_back_to_stale_legacy(self):
        self.write(['stale']);data=json.loads(self.path.read_text())
        data['electron-thread-read-state-v1']={'version':1,'unreadByIdentity':{'current':{'local:different-execution-host':['wrong']}}}
        self.path.write_text(json.dumps(data));self.assertIsNone(self.reader.read())
        self.reader.set_identity('current');self.assertIsNone(self.reader.read())
        self.reader.set_identity('new-user');self.assertEqual(self.reader.read(),set())
        data['electron-thread-read-state-v1']['version']=99;self.path.write_text(json.dumps(data));self.assertIsNone(self.reader.read())

    def test_identity_matches_desktop_algorithm_without_retaining_token(self):
        claims={'https://api.openai.com/auth':{'chatgpt_account_id':'account','user_id':'user','chatgpt_user_id':'old-user'}}
        payload=base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip('=')
        auth={'authMethod':'chatgpt','authToken':'header.'+payload+'.signature'}
        expected=hashlib.sha256(b'["chatgpt","account","user"]').hexdigest()
        self.assertEqual(identity_key(auth),expected)
        self.reader.set_identity(identity_key(auth));self.assertNotIn(payload,repr(self.reader.__dict__))
        self.assertIsNone(identity_key({'authMethod':'chatgpt','authToken':'bad'}))
        self.assertIsNone(identity_key({'authMethod':None,'requiresOpenaiAuth':True}))
        self.assertEqual(identity_key({'authMethod':None,'requiresOpenaiAuth':False}),hashlib.sha256(b'["execution-storage","none"]').hexdigest())

    def test_unknown_is_distinct_from_known_empty(self):
        self.assertIsNone(self.reader.read())
        self.write([]);self.assertEqual(self.reader.read(),set())
        self.path.write_text('{',encoding='utf-8');self.assertIsNone(self.reader.read())
        self.write('bad format');self.assertIsNone(self.reader.read())

    def test_only_completed_nonrunning_tasks_count_as_unread(self):
        self.write(['done','aborted','running'])
        now=datetime.now().astimezone();cursors={}
        for name,end in [('done','task_complete'),('aborted','turn_aborted'),('running',None)]:
            path=self.root/(name+'.jsonl')
            path.write_bytes(record('task_started',now)+record('token_count',now,100)+(record(end,now) if end else b''))
            cursor=UsageCursor(path);cursor.update();cursors[name]=cursor
        provider=Provider.__new__(Provider);provider.lock=threading.Lock()
        provider.runtime_dir=self.root;provider.boot_time=now.timestamp()-10
        provider.quota_history=[];provider.unread_state=self.reader
        threads=[{'id':name,'name':name} for name in cursors]
        provider._publish(threads,[],cursors,[],None,None)
        self.assertEqual(provider.snapshot['unread_count'],1)
        self.assertFalse(provider.snapshot['tasks'][0]['unread'])
        recent={t['id']:t for t in provider.snapshot['recent_tasks']}
        self.assertTrue(recent['done']['unread']);self.assertFalse(recent['aborted']['unread'])
        self.write([]);provider._publish(threads,[],cursors,[],None,None)
        self.assertEqual(provider.snapshot['unread_count'],0)
