import json,tempfile,unittest
from pathlib import Path
from codex_taskbar.status_summaries import StatusSummaries


def task(identifier='a',turn='one',category='running',**extra):
    return dict(id=identifier,turn_id=turn,running=category in ('running','waiting'),needs_input=category=='waiting',
                unread=category=='unread',status=category if category in ('failed','stopped') else 'idle',**extra)


def snapshot(*tasks,account='account-a',**extra):
    return dict(tasks=list(tasks),task_account=account,**extra)


class StatusSummaryTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.addCleanup(self.folder.cleanup)
        self.path=Path(self.folder.name)/'dismissals.json';self.model=StatusSummaries(self.path)

    def test_defaults_and_master_data_have_no_pin_dependency(self):
        self.model.update(snapshot(*(task(str(i),category=kind) for i,kind in enumerate(('waiting','running','unread','failed','stopped','recent')))))
        self.assertEqual(self.model.active,['waiting','running','unread','failed'])

    def test_dismiss_entire_group_and_refresh_time_names_subsets_do_not_reopen(self):
        a=task();b=task('b');self.model.update(snapshot(a,b));self.model.dismiss('running')
        for rows in ((dict(a,title='Renamed',round_seconds=999),b),(b,),(),(b,)):
            self.model.update(snapshot(*rows));self.assertNotIn('running',self.model.active)

    def test_new_task_or_new_turn_reopens_and_prefers_new_arrival(self):
        self.model.update(snapshot(task()));self.model.dismiss('running')
        self.model.update(snapshot(task(),task('b')))
        self.assertIn('running',self.model.active);self.assertEqual(self.model.preferred['running'],'b')
        self.model.dismiss('running');self.model.update(snapshot(task(turn='two'),task('b')))
        self.assertEqual(self.model.preferred['running'],'a');self.assertIn('running',self.model.active)

    def test_state_transition_and_same_turn_return_are_new_events(self):
        self.model.update(snapshot(task()));self.model.dismiss('running')
        self.model.update(snapshot(task(category='waiting')));self.assertEqual(self.model.active,['waiting'])
        self.model.dismiss('waiting');self.model.update(snapshot(task()))
        self.assertEqual(self.model.active,['running'])
        self.model.update(snapshot(task(category='unread')));self.assertEqual(self.model.active,['unread'])

    def test_unknown_unread_and_error_snapshots_do_not_create_a_new_episode(self):
        row=task(category='unread');self.model.update(snapshot(row));self.model.dismiss('unread')
        unknown=dict(row,unread=None);self.model.update(snapshot(unknown));self.model.update(snapshot(row))
        self.assertNotIn('unread',self.model.active)
        self.model.update(snapshot(error='catalog unavailable'));self.model.update(snapshot(loading=True))
        self.model.update(snapshot(row));self.assertNotIn('unread',self.model.active)
        self.model.update(snapshot(dict(row,unread=False)));self.model.update(snapshot(row))
        self.assertIn('unread',self.model.active)

    def test_restart_and_account_isolation(self):
        self.model.update(snapshot(task()));self.model.dismiss('running')
        restored=StatusSummaries(self.path);restored.update(snapshot(task()))
        self.assertNotIn('running',restored.active)
        restored.update(snapshot(task(),account=None));self.assertNotIn('running',restored.active)
        restored.update(snapshot(task()));self.assertNotIn('running',restored.active)
        restored.update(snapshot(task(),account='account-b'));self.assertIn('running',restored.active)
        restored.update(snapshot(task(),account='account-a'));self.assertNotIn('running',restored.active)
        self.assertEqual(json.loads(self.path.read_text())['account-a'],{'running':{'a':'one'}})

    def test_side_uses_own_start_when_no_turn_id(self):
        row=task('side',turn=None,started_at='2026-09-17T10:00:00+08:00',side_chat=True,parent_id='parent')
        self.model.update(snapshot(row));self.model.dismiss('running')
        self.model.update(snapshot(dict(row,started_at='2026-09-17T10:01:00+08:00')))
        self.assertIn('running',self.model.active)

    def test_new_question_in_same_execution_reopens_waiting(self):
        row=task(category='waiting',input_ids=['question-a'])
        self.model.update(snapshot(row));self.model.dismiss('waiting')
        self.model.update(snapshot(dict(row,input_ids=['question-a'])));self.assertNotIn('waiting',self.model.active)
        self.model.update(snapshot(dict(row,input_ids=['question-b'])));self.assertIn('waiting',self.model.active)

    def test_dismissal_stores_no_task_text_and_unknown_account_is_not_persisted(self):
        self.model.update(snapshot(task(title='PRIVATE',project='PRIVATE'),account=None));self.model.dismiss('running')
        self.assertFalse(self.path.exists())
        self.model.update(snapshot(task(title='PRIVATE',project='PRIVATE')));self.model.dismiss('running')
        self.assertNotIn('PRIVATE',self.path.read_text())
