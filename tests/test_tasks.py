from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import threading
import unittest

from codex_taskbar.provider import Provider
from codex_taskbar.tasks import task_rows, task_metrics, thread_url
from codex_taskbar.usage import UsageCursor
from codex_taskbar.unread import UnreadState
from tests.test_usage import record


class TaskTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.path=Path(self.folder.name)/'task.jsonl'
        self.now=datetime.now().astimezone()

    def tearDown(self):self.folder.cleanup()

    def test_latest_run_is_not_the_daily_total(self):
        self.path.write_bytes(record('token_count',self.now-timedelta(days=1),1000)
            +record('task_started',self.now,turn='a')+record('token_count',self.now,1300)
            +record('task_complete',self.now,turn='a')
            +record('task_started',self.now,turn='b')+record('token_count',self.now,1340))
        cursor=UsageCursor(self.path);cursor.update()
        self.assertEqual(cursor.daily['total_tokens'],340)
        self.assertEqual(cursor.run_tokens,40)
        self.assertIsNone(cursor.ended_at)

    def test_cross_midnight_run_keeps_full_run_total(self):
        midnight=self.now.replace(hour=0,minute=0,second=0,microsecond=0)
        self.path.write_bytes(record('token_count',midnight-timedelta(hours=2),1000)
            +record('task_started',midnight-timedelta(hours=1))
            +record('token_count',midnight-timedelta(minutes=1),1200)
            +record('token_count',self.now,1250))
        cursor=UsageCursor(self.path);cursor.update()
        self.assertEqual(cursor.run_tokens,250)
        self.assertEqual(cursor.daily['total_tokens'],50)

    def test_unknown_run_start_stays_unknown(self):
        self.path.write_bytes(record('token_count',self.now,200))
        cursor=UsageCursor(self.path);cursor.update()
        self.assertIsNone(cursor.run_tokens)
        self.assertIsNone(cursor.elapsed_today())

    def test_completion_is_retained_today_and_not_rotated(self):
        self.path.write_bytes(record('task_started',self.now)+record('token_count',self.now,100)
            +record('task_complete',self.now+timedelta(seconds=3)))
        cursor=UsageCursor(self.path);cursor.update()
        provider=Provider.__new__(Provider)
        provider.lock=threading.Lock();provider.runtime_dir=Path(self.folder.name)
        provider.boot_time=self.now.timestamp()-100;provider.quota_history=[]
        provider.unread_state=UnreadState(Path(self.folder.name)/'missing.json')
        provider._publish([{'id':'a','name':'真实标题'}],[],{'a':cursor},[],None,None)
        self.assertEqual(provider.snapshot['tasks'],[])
        self.assertEqual(provider.snapshot['recent_tasks'][0]['run_tokens'],100)
        self.assertEqual(provider.snapshot['recent_tasks'][0]['title'],'真实标题')

    def test_task_states_require_explicit_evidence_for_the_current_turn(self):
        self.path.write_bytes(record('task_started',self.now,turn='current'))
        cursor=UsageCursor(self.path);cursor.update()
        provider=Provider.__new__(Provider)
        provider.lock=threading.Lock();provider.runtime_dir=Path(self.folder.name)
        provider.boot_time=self.now.timestamp()-100;provider.quota_history=[]
        provider.unread_state=UnreadState(Path(self.folder.name)/'missing.json')
        def publish(turn):
            provider._publish([{'id':'a','name':'Task'}],[],{'a':cursor},[],None,None,{'a':turn})
            return (provider.snapshot['tasks']+provider.snapshot['recent_tasks'])[0]
        self.assertEqual(publish({'id':'current','status':'interrupted'})['status'],'running')
        self.assertEqual(publish({'id':'old','status':'failed','error':{'message':'old error'}})['status'],'running')
        self.assertEqual(publish({'id':'current','status':'failed','error':None})['status'],'running')
        failed=publish({'id':'current','status':'failed','error':{'message':'retry exhausted'},'completedAt':self.now.timestamp()+10})
        self.assertEqual(failed['status'],'failed');self.assertFalse(failed['running'])
        self.assertEqual(failed['daily_seconds'],10)
        with self.path.open('ab') as f:f.write(record('turn_aborted',self.now+timedelta(seconds=11),turn='current'))
        cursor.update()
        self.assertEqual(publish(None)['status'],'stopped')
        with self.path.open('ab') as f:f.write(record('task_started',self.now+timedelta(seconds=12),turn='next'))
        cursor.update()
        self.assertEqual(publish({'id':'current','status':'failed','error':{'message':'retry exhausted'}})['status'],'running')

    def test_running_then_today_each_use_recent_activity_order_without_duplicates(self):
        a={'id':'a','project':'A','activity_at':'2026-09-07T00:00:00+00:00','running':True}
        b={'id':'b','project':'B','activity_at':'2026-09-07T01:00:00+00:00','running':True}
        c={'id':'c','project':'A','activity_at':'2026-09-07T02:00:00+00:00'}
        data={'tasks':[a,b],'recent_tasks':[c,a]}
        self.assertEqual([t['id'] for t in task_rows(data)],['b','a','c'])

    def test_display_uses_daily_duration_not_latest_turn(self):
        task={'started_at':self.now.isoformat(),'ended_at':(self.now+timedelta(seconds=90)).isoformat(),
              'daily_seconds':7500,'tokens':1200,'running':False}
        self.assertEqual(task_metrics(task),('2h 5m','1.2K'))
        self.assertEqual(task_metrics({'tokens':1200}),('—','1.2K'))

    def test_daily_duration_sums_turns_and_excludes_gaps(self):
        midnight=self.now.replace(hour=0,minute=0,second=0,microsecond=0)
        self.path.write_bytes(record('task_started',midnight+timedelta(hours=1),turn='a')
            +record('task_complete',midnight+timedelta(hours=2),turn='a')
            +record('task_complete',midnight+timedelta(hours=2),turn='a')
            +record('task_started',midnight+timedelta(hours=3),turn='b')
            +record('task_complete',midnight+timedelta(hours=3,minutes=1),turn='a')
            +record('turn_aborted',midnight+timedelta(hours=3,minutes=20),turn='b')
            +record('task_started',midnight+timedelta(hours=5),turn='c'))
        c=UsageCursor(self.path);c.update()
        self.assertEqual(c.elapsed_today(midnight+timedelta(hours=5,minutes=10)),90*60)
        self.assertEqual(c.elapsed_today(include_running=False),80*60)
        with self.path.open('ab') as f:f.write(record('task_complete',midnight+timedelta(hours=5,minutes=15),turn='c'))
        c.update();c.update()
        self.assertEqual(c.elapsed_today(midnight+timedelta(hours=10)),95*60)

    def test_duration_bootstrap_recovers_overnight_start_before_token_baseline(self):
        midnight=self.now.replace(hour=0,minute=0,second=0,microsecond=0)
        filler=b'{"type":"response_item","payload":"'+b'x'*1_100_000+b'"}\n'
        self.path.write_bytes(record('task_started',midnight-timedelta(hours=3))+filler
            +record('token_count',midnight-timedelta(minutes=1),100)
            +record('task_complete',midnight+timedelta(minutes=30)))
        c=UsageCursor(self.path);c.update()
        self.assertEqual(c.elapsed_today(self.now),30*60)

    def test_duration_reloads_on_day_change_and_truncation(self):
        midnight=self.now.replace(hour=0,minute=0,second=0,microsecond=0)
        self.path.write_bytes(record('task_started',midnight-timedelta(hours=1))
            +record('task_complete',midnight+timedelta(minutes=20)))
        c=UsageCursor(self.path,today=(midnight-timedelta(days=1)).date());c.bootstrap()
        self.assertEqual(c.elapsed_today(),3600)
        c.update()
        self.assertEqual(c.elapsed_today(),1200)
        self.path.write_bytes(record('task_complete',self.now));c.update()
        self.assertIsNone(c.elapsed_today())

    def test_duration_excludes_inherited_turns_and_clips_overnight_running(self):
        midnight=self.now.replace(hour=0,minute=0,second=0,microsecond=0)
        self.path.write_bytes(record('task_started',midnight-timedelta(hours=2),turn='old')
            +record('task_complete',midnight+timedelta(minutes=15),turn='old')
            +record('task_started',midnight+timedelta(hours=1),turn='new'))
        c=UsageCursor(self.path,created_after=midnight.timestamp());c.update()
        self.assertEqual(c.elapsed_today(midnight+timedelta(hours=2)),3600)
        self.path.write_bytes(record('task_started',midnight-timedelta(hours=2)))
        c=UsageCursor(self.path);c.update()
        self.assertEqual(c.elapsed_today(midnight+timedelta(hours=2)),7200)

    def test_display_uses_today_total_instead_of_latest_run(self):
        self.assertEqual(task_metrics({'tokens':3500,'run_tokens':80})[1],'3.5K')

    def test_link_opens_only_a_valid_existing_thread_identifier(self):
        value='00000000-0000-4000-8000-000000000001'
        self.assertEqual(thread_url(value),'codex://threads/'+value)
        with self.assertRaises(ValueError):thread_url('https://example.com')

    def test_side_completion_unread_uses_child_id_and_clears_when_codex_marks_read(self):
        from unittest.mock import Mock
        from codex_taskbar.tasks import task_category,category_counts
        start=self.now-timedelta(seconds=100)
        self.path.write_bytes(record('task_started',start)+record('turn_aborted',start+timedelta(seconds=5)))
        cursor=UsageCursor(self.path);cursor.update()
        provider=Provider.__new__(Provider);provider.lock=threading.Lock();provider.runtime_dir=Path(self.folder.name)
        provider.boot_time=start.timestamp()-100;provider.quota_history=[];provider.unread_state=Mock()
        provider.side_rows=[{'id':'side','parent_id':'a','running':False,'completion_kind':'task_complete',
                             'started_at':start.timestamp()+10,'ended_at':start.timestamp()+25,'activity_at':start.timestamp()+25}]
        def publish(ids):
            provider.unread_state.read.return_value=ids
            provider._publish([{'id':'a','name':'Parent'}],[],{'a':cursor},[],None,None)
            return provider.snapshot['recent_tasks'][0]
        row=publish({'side'})
        self.assertTrue(row['unread']);self.assertTrue(row['side_chat'])
        self.assertEqual(task_category(row),'unread');self.assertEqual(row['round_seconds'],15)
        self.assertEqual(category_counts(provider.snapshot)['unread'],1)
        row=publish(set());self.assertFalse(row['unread']);self.assertFalse(row.get('side_chat',False))
        self.assertEqual(category_counts(provider.snapshot)['unread'],0)
        self.assertIsNone(publish(None)['unread'])
        provider.side_rows[0]['completion_kind']='turn_aborted'
        self.assertFalse(publish({'side'})['unread'])
        provider.side_rows[0]['completion_kind']='session_idle'
        self.assertTrue(publish({'side'})['unread'])
        self.assertFalse(publish(set())['unread'])
        self.assertEqual(category_counts(provider.snapshot)['running'],0)

    def test_task_activity_order_compares_instants_across_offsets(self):
        data={'tasks':[{'id':'older','running':True,'activity_at':'2026-09-11T09:00:00+08:00'},
                       {'id':'newer','running':True,'activity_at':'2026-09-11T05:00:00+00:00'}]}
        self.assertEqual([t['id'] for t in task_rows(data)],['newer','older'])

    def test_side_unread_survives_parent_running_then_finishing_without_double_counting(self):
        from unittest.mock import Mock
        from codex_taskbar.tasks import category_counts
        start=self.now-timedelta(seconds=100)
        self.path.write_bytes(record('task_started',start));cursor=UsageCursor(self.path);cursor.update()
        provider=Provider.__new__(Provider);provider.lock=threading.Lock();provider.runtime_dir=Path(self.folder.name)
        provider.boot_time=start.timestamp()-100;provider.quota_history=[];provider.unread_state=Mock()
        provider.unread_state.read.return_value={'side'}
        provider.side_rows=[{'id':'side','parent_id':'a','running':False,'completion_kind':'task_complete',
                             'started_at':start.timestamp()+10,'ended_at':start.timestamp()+25,'activity_at':start.timestamp()+25}]
        def publish():provider._publish([{'id':'a','name':'Parent'}],[],{'a':cursor},[],None,None)
        publish();self.assertEqual(category_counts(provider.snapshot)['running'],1)
        self.assertEqual(category_counts(provider.snapshot)['unread'],0)
        self.assertTrue(provider.snapshot['tasks'][0]['side_chat'])
        with self.path.open('ab') as stream:stream.write(record('task_complete',self.now))
        cursor.update();publish()
        self.assertEqual(category_counts(provider.snapshot)['running'],0)
        self.assertEqual(category_counts(provider.snapshot)['unread'],1)
        self.assertEqual(provider.snapshot['recent_tasks'][0]['round_seconds'],15)


if __name__=='__main__':unittest.main()
