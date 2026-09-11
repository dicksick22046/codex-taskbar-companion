from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from codex_taskbar.task_statistics import TaskStatistics
from codex_taskbar.usage import event_from_line
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

    def test_fork_without_inherited_baseline_is_a_lower_bound(self):
        self.log.write_bytes(self.event('task_started',50)+self.event('token_count',51,100)+self.event('token_count',52,130)+self.event('task_complete',70))
        self.sync(forkedFromId='parent',createdAt=(self.start+timedelta(seconds=40)).timestamp())
        row=self.index.view()['task'];self.assertEqual(row['tokens'],30);self.assertTrue(row['tokens_partial'])

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
        self.cache.write_text(json.dumps({'version':TaskStatistics.VERSION,'entries':{'bad':42,'broken':{'offset':0}}}))
        self.assertEqual(TaskStatistics(self.cache).entries,{})

    def test_budget_can_yield_and_resume_without_losing_counts(self):
        self.log.write_bytes(b''.join(self.event('token_count',i,i*100) for i in range(1,100)))
        self.index.CHUNK=100;self.index.sync([{'id':'task','path':str(self.log)}])
        clock=iter(i*.02 for i in range(1000))
        with patch('codex_taskbar.task_statistics.time.monotonic',side_effect=lambda:next(clock)):self.index.step(budget=.06)
        self.assertFalse(self.index.view()['task']['ready'])
        self.index.step(budget=1);self.assertEqual(self.index.view()['task']['tokens'],9900)

    def test_append_during_slice_waits_for_next_stat_without_resetting_cache(self):
        initial=self.event('token_count',1,100);self.log.write_bytes(initial)
        self.index.sync([{'id':'task','path':str(self.log)}]);original=self.index._entry
        def append_after_stat(key):
            result=original(key)
            with self.log.open('ab') as stream:stream.write(self.event('token_count',2,130))
            return result
        with patch.object(self.index,'_entry',side_effect=append_after_stat):self.index.step(budget=1)
        self.assertEqual(self.index.entries['task']['offset'],len(initial));self.assertEqual(self.index.view()['task']['tokens'],100)
        self.index.step(budget=1);self.assertEqual(self.index.view()['task']['tokens'],130)

    def test_partial_values_are_lower_bounds_without_extending_old_open_turn(self):
        first=self.event('task_started',0)+self.event('token_count',1,100)
        self.log.write_bytes(first+self.event('task_complete',10))
        self.index.sync([{'id':'task','path':str(self.log)}]);_,_,entry=self.index._entry('task')
        self.index.consume(entry,first);entry['offset']=len(first)
        row=self.index.view(['task'],now=self.start.timestamp()+86400)['task']
        self.assertEqual((row['tokens'],row['seconds'],row['turns']),(100,0,1))
        self.assertFalse(row['ready']);self.assertTrue(row['tokens_partial']);self.assertTrue(row['turns_partial'])
        self.index.step(budget=1);row=self.index.view()['task']
        self.assertEqual((row['tokens'],row['seconds'],row['turns']),(100,10,1))
        self.assertFalse(row['partial']);self.assertFalse(row['turns_partial'])

    def test_large_irrelevant_record_resumes_after_restart_without_payload_cache(self):
        for kind in ('response_item','event_msg'):
            with self.subTest(kind=kind):
                first=self.event('token_count',1,100)
                ignored=json.dumps({'timestamp':self.start.isoformat(),'type':kind,
                                    'payload':{'type':'agent_message','text':'private-text'*10000}}).encode()+b'\n'
                self.log.write_bytes(first+ignored+self.event('token_count',2,130))
                self.index=TaskStatistics(self.cache);self.index.sync([{'id':'task','path':str(self.log)}])
                _,_,entry=self.index._entry('task');chunk=(first+ignored)[:len(first)+1024]
                self.index.consume(entry,chunk);entry['offset']=len(chunk);self.index.save(force=True)
                self.assertTrue(entry['discarding']);self.assertEqual(entry['pending'],b'')
                self.assertNotIn('private-text',self.cache.read_text())
                self.index=TaskStatistics(self.cache)
                with patch('codex_taskbar.task_statistics.event_from_line',wraps=event_from_line) as parser:
                    self.sync();self.assertEqual(parser.call_count,1)
                self.assertEqual(self.index.view()['task']['tokens'],130)

    def test_unfamiliar_envelopes_use_parser_and_old_cache_is_retained(self):
        event=json.loads(self.event('token_count',1,100))
        self.log.write_bytes((json.dumps({'payload':event['payload'],'type':event['type'],'timestamp':event['timestamp']})+'\n').encode())
        self.sync();self.index.save(force=True)
        saved=json.loads(self.cache.read_text());saved['entries']['task'].pop('discarding');saved['entries']['task'].pop('size')
        self.cache.write_text(json.dumps(saved));self.index=TaskStatistics(self.cache)
        with patch.object(TaskStatistics,'apply') as apply:self.sync();apply.assert_not_called()
        self.assertEqual(self.index.view()['task']['tokens'],100)
