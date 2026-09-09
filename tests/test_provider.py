import copy
from datetime import datetime
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from codex_taskbar.provider import Provider
from codex_taskbar.unread import UnreadState
from codex_taskbar.usage import UsageCursor
from tests.test_usage import record


class ProviderFailureTests(unittest.TestCase):
    def run_failure(self, failure):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);now=datetime.now().astimezone();path=root/'task.jsonl'
            path.write_bytes(record('task_started',now)+record('token_count',now,100))
            class Stop:
                ticks=0
                def is_set(self):return self.ticks>=3
                def wait(self,seconds):self.ticks+=1
            stop=Stop()
            class Api:
                quota_calls=0;catalog_calls=0;turn_calls=0;closed=0
                def call(self,method):
                    self.quota_calls+=1
                    if self.quota_calls==2 and failure=='quota_timeout':raise TimeoutError('quota fixture')
                    if self.quota_calls==2 and failure=='quota_empty':return {'rateLimits':{}}
                    used=20 if self.quota_calls<3 else 25
                    return {'rateLimits':{'primary':{'usedPercent':used,'windowDurationMins':10080,'resetsAt':now.timestamp()+86400}}}
                def catalog(self):
                    self.catalog_calls+=1
                    if self.catalog_calls==2 and failure=='catalog_timeout':raise TimeoutError('catalog fixture')
                    return [],[{'id':'task','name':'Task','path':str(path),'updatedAt':self.catalog_calls}]
                def latest_turn(self,thread_id):
                    self.turn_calls+=1
                    if self.turn_calls==2 and failure=='turn_timeout':raise TimeoutError('turn fixture')
                    return None
                def close(self):self.closed+=1
            api=Api();provider=Provider.__new__(Provider)
            provider.runtime_dir=root;provider.quota_history_path=root/'quota_history.json';provider.quota_history=[]
            provider.lock=threading.Lock();provider.stop_event=stop;provider.refresh_event=threading.Event()
            provider.unread_state=UnreadState(root/'missing.json');provider.boot_time=now.timestamp()-100
            provider.snapshot={};provider.api=None
            snapshots=[];publish=provider._publish
            def capture(*args,**kwargs):
                publish(*args,**kwargs);snapshots.append(copy.deepcopy(provider.snapshot))
            with patch('codex_taskbar.provider.CodexApi',return_value=api) as factory,patch('codex_taskbar.provider.time.monotonic',side_effect=lambda:1000+stop.ticks*31),patch.object(provider,'_publish',side_effect=capture),patch('builtins.print'):
                provider._run()
            self.assertEqual(factory.call_count,1)
            self.assertEqual(api.closed,1)
            self.assertEqual(len(snapshots),3)
            self.assertTrue(all(len(s['tasks'])==1 for s in snapshots))
            self.assertTrue(all(s['quota'] for s in snapshots))
            self.assertEqual(snapshots[-1]['quota'][0]['remaining'],75)
            self.assertIsNone(snapshots[-1]['quota_error'])
            return snapshots

    def test_quota_timeout_does_not_clear_other_data(self):
        snapshots=self.run_failure('quota_timeout')
        self.assertEqual(snapshots[1]['quota'],snapshots[0]['quota'])
        self.assertIsNotNone(snapshots[1]['quota_error'])

    def test_empty_quota_response_is_not_a_new_empty_balance(self):
        snapshots=self.run_failure('quota_empty')
        self.assertEqual(snapshots[1]['quota'],snapshots[0]['quota'])
        self.assertIsNotNone(snapshots[1]['quota_error'])

    def test_auxiliary_turn_timeout_does_not_invalidate_quota(self):
        snapshots=self.run_failure('turn_timeout')
        self.assertIsNone(snapshots[1]['error'])
        self.assertIsNone(snapshots[1]['quota_error'])

    def test_catalog_timeout_keeps_known_tasks_and_fresh_quota(self):
        snapshots=self.run_failure('catalog_timeout')
        self.assertIsNotNone(snapshots[1]['error'])
        self.assertIsNone(snapshots[1]['quota_error'])


class SideChatAggregationTests(unittest.TestCase):
    def test_side_only_activity_counts_parent_once_and_restores_parent_after_completion(self):
        from datetime import timedelta
        from unittest.mock import patch
        now=datetime.now().astimezone()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);path=root/'parent.jsonl'
            path.write_bytes(record('task_started',now-timedelta(seconds=60))+record('token_count',now-timedelta(seconds=50),100)+record('task_complete',now-timedelta(seconds=40)))
            cursor=UsageCursor(path);cursor.update()
            provider=Provider.__new__(Provider);provider.runtime_dir=root;provider.lock=threading.Lock()
            provider.quota_history=[];provider.unread_state=UnreadState(root/'missing.json');provider.boot_time=now.timestamp()-1000
            provider.side_rows=[{'id':str(i),'parent_id':'main','running':True,'started_at':now.timestamp()-20+i,'activity_at':now.timestamp()-20+i} for i in range(2)]
            threads=[{'id':'main','name':'Parent task'}]
            with patch('codex_taskbar.provider.time.time',return_value=now.timestamp()):
                provider._publish(threads,[],{'main':cursor},[],None,None)
            tasks=provider.snapshot['tasks']
            self.assertEqual(len(tasks),1);self.assertEqual(tasks[0]['id'],'main');self.assertTrue(tasks[0]['side_chat'])
            self.assertEqual(tasks[0]['tokens'],100);self.assertEqual(tasks[0]['round_seconds'],20)
            for side in provider.side_rows:side.update(running=False,ended_at=now.timestamp(),activity_at=now.timestamp())
            provider._publish(threads,[],{'main':cursor},[],None,None)
            self.assertEqual(provider.snapshot['tasks'],[])
            self.assertFalse(provider.snapshot['recent_tasks'][0].get('side_chat',False))
