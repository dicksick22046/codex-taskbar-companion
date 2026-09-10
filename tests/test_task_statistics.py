from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from codex_taskbar.task_statistics import TaskStatistics
from tests.test_usage import record


class LifetimeTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.root=Path(self.folder.name);self.log=self.root/'task.jsonl'
        self.cache=self.root/'index.json';self.index=TaskStatistics(self.cache);self.start=datetime(2026,9,1,tzinfo=timezone.utc)
    def tearDown(self):self.folder.cleanup()
    def event(self,kind,seconds,total=None,turn='a'):return record(kind,self.start+timedelta(seconds=seconds),total,turn)
    def sync(self,**kwargs):self.index.sync([{'id':'task','path':str(self.log),**kwargs}]);self.index.step(budget=1)

    def test_total_counter_resets_turns_and_idle_gaps(self):
        self.log.write_bytes(self.event('task_started',0)+self.event('task_started',0)+self.event('token_count',1,100)+self.event('token_count',2,150)+self.event('task_complete',10)+
                             self.event('task_started',1000,turn='b')+self.event('token_count',1001,20,turn='b')+self.event('task_complete',1020,turn='b'))
        self.sync();row=self.index.view()['task']
        self.assertEqual((row['tokens'],row['seconds'],row['turns']),(170,30,2));self.assertFalse(row['partial'])

    def test_fork_excludes_inherited_counters_and_turns(self):
        self.log.write_bytes(self.event('task_started',0)+self.event('token_count',1,100)+self.event('task_complete',10)+
                             self.event('task_started',50,turn='b')+self.event('token_count',51,130,turn='b')+self.event('task_complete',70,turn='b'))
        self.sync(forkedFromId='parent',createdAt=(self.start+timedelta(seconds=40)).timestamp())
        row=self.index.view()['task'];self.assertEqual((row['tokens'],row['seconds'],row['turns']),(30,20,1))

    def test_cache_resume_partial_line_and_append(self):
        complete=self.event('token_count',1,100);next_line=self.event('token_count',2,130)
        self.log.write_bytes(complete+next_line[:20]);self.sync();self.index.save(force=True)
        saved=self.cache.read_text();self.assertNotIn('pending',saved)
        with self.log.open('ab') as stream:stream.write(next_line[20:])
        self.index=TaskStatistics(self.cache);self.sync();self.assertEqual(self.index.view()['task']['tokens'],130)
        with patch.object(TaskStatistics,'apply',wraps=TaskStatistics.apply) as apply:
            self.index.step();apply.assert_not_called()

    def test_replacement_and_truncation_rebuild_affected_record(self):
        self.log.write_bytes(self.event('token_count',1,100));self.sync()
        replacement=self.root/'replacement';replacement.write_bytes(self.event('token_count',2,25));replacement.replace(self.log)
        self.sync();self.assertEqual(self.index.view()['task']['tokens'],25)
        self.log.write_bytes(b'');self.sync();self.assertEqual(self.index.view()['task']['tokens'],0)

    def test_live_time_requires_verified_running_and_missing_end_is_lower_bound(self):
        self.log.write_bytes(self.event('task_started',0)+self.event('task_started',100,turn='b'))
        self.sync();row=self.index.view(['task'],now=self.start.timestamp()+120)['task']
        self.assertEqual(row['seconds'],20);self.assertTrue(row['partial'])
        self.assertEqual(self.index.view([],now=self.start.timestamp()+10000)['task']['seconds'],0)

    def test_missing_file_and_corrupt_cache_remain_unknown(self):
        self.sync();self.assertEqual(self.index.view()['task'],{'ready':False,'missing':True})
        self.cache.write_text(json.dumps({'version':1,'entries':{'bad':42,'broken':{'offset':0}}}))
        self.assertEqual(TaskStatistics(self.cache).entries,{})

    def test_budget_can_yield_and_resume_without_losing_counts(self):
        self.log.write_bytes(b''.join(self.event('token_count',i,i*100) for i in range(1,100)))
        self.index.CHUNK=100;self.index.sync([{'id':'task','path':str(self.log)}])
        clock=iter(i*.02 for i in range(1000))
        with patch('codex_taskbar.task_statistics.time.monotonic',side_effect=lambda:next(clock)):self.index.step(budget=.06)
        self.assertFalse(self.index.view()['task']['ready'])
        self.index.step(budget=1);self.assertEqual(self.index.view()['task']['tokens'],9900)
