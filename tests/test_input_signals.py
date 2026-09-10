from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from codex_taskbar.usage import UsageCursor,event_from_line
from tests.test_usage import record


class InputSignalTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.path=Path(self.folder.name)/'log.jsonl'
        self.now=datetime.now().astimezone();self.cursor=UsageCursor(self.path)
    def tearDown(self):self.folder.cleanup()
    def request(self,call='question',name='functions.request_user_input'):
        return json.dumps({'type':'response_item','timestamp':self.now.isoformat(),'payload':{'type':'function_call','name':name,'call_id':call,
                    'arguments':json.dumps({'questions':[{'id':'choice','question':'Private question text'}]})}}).encode()+b'\n'
    def answer(self,call='question'):
        return json.dumps({'type':'response_item','timestamp':self.now.isoformat(),'payload':{'type':'function_call_output','call_id':call,'output':'Private answer'}}).encode()+b'\n'

    def test_request_and_matching_response_only_retain_metadata(self):
        self.path.write_bytes(record('task_started',self.now)+self.request());self.cursor.update()
        self.assertEqual(set(self.cursor.pending_input),{'question'})
        self.assertNotIn('Private',repr(self.cursor.pending_input));self.assertNotIn('Private',repr(event_from_line(self.request())))
        with self.path.open('ab') as f:f.write(self.answer('unrelated'))
        self.cursor.update();self.assertTrue(self.cursor.pending_input)
        with self.path.open('ab') as f:f.write(self.answer())
        self.cursor.update();self.assertFalse(self.cursor.pending_input)

    def test_parallel_requests_restart_and_completion(self):
        self.path.write_bytes(record('task_started',self.now)+self.request('one')+self.request('two')+self.answer('one'))
        self.cursor.update();self.assertEqual(set(self.cursor.pending_input),{'two'})
        restored=UsageCursor(self.path);restored.update();self.assertEqual(restored.pending_input,self.cursor.pending_input)
        with self.path.open('ab') as f:f.write(record('turn_aborted',self.now+timedelta(seconds=1)))
        restored.update();self.assertFalse(restored.pending_input)

    def test_unrelated_names_and_unstarted_or_inherited_requests_do_not_mark_waiting(self):
        self.assertIsNone(event_from_line(self.request(name='functions.exec')))
        self.path.write_bytes(self.request());self.cursor.update();self.assertFalse(self.cursor.pending_input)
        inherited=UsageCursor(self.path,created_after=self.now.timestamp()+10);inherited.update();self.assertFalse(inherited.pending_input)

    def test_new_turn_clears_pending_but_duplicate_start_does_not(self):
        self.path.write_bytes(record('task_started',self.now)+self.request()+record('task_started',self.now))
        self.cursor.update();self.assertTrue(self.cursor.pending_input)
        with self.path.open('ab') as f:f.write(record('task_started',self.now,turn='next'))
        self.cursor.update();self.assertFalse(self.cursor.pending_input)


