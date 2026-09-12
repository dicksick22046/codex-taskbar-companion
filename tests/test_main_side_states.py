from datetime import datetime,timedelta
from pathlib import Path
import tempfile,threading,unittest
from unittest.mock import Mock
from codex_taskbar.provider import Provider
from codex_taskbar.usage import UsageCursor
from codex_taskbar.tasks import category_counts,panel_rows,task_rows,task_category,task_role_label
from codex_taskbar.task_finder import finder_rows
from tests.test_usage import record


class MainSideStateTests(unittest.TestCase):
    def test_independent_state_matrix_and_shared_counts(self):
        start=datetime.now().astimezone().replace(hour=0,minute=0,second=10,microsecond=0)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);path=root/'main.jsonl'
            for main_kind in ('running','waiting','recent','stopped','failed'):
                for side_kind in ('running','session_idle','task_complete','turn_aborted'):
                    for unread in (set(),{'side'},None):
                        with self.subTest(main=main_kind,side=side_kind,unread=unread):
                            end='task_complete' if main_kind=='recent' else 'turn_aborted' if main_kind=='stopped' else None
                            path.write_bytes(record('task_started',start)+record('token_count',start+timedelta(seconds=1),100)+
                                             (record(end,start+timedelta(seconds=20)) if end else b''))
                            cursor=UsageCursor(path);cursor.update()
                            if main_kind=='waiting':cursor.pending_input={'question':start.isoformat()}
                            provider=Provider.__new__(Provider);provider.runtime_dir=root;provider.lock=threading.Lock()
                            provider.boot_time=start.timestamp()-100;provider.quota_history=[];provider.unread_state=Mock()
                            provider.unread_state.read.return_value=unread
                            active=side_kind=='running'
                            provider.side_rows=[dict(id='side',parent_id='main',running=active,
                                completion_kind=None if active else side_kind,started_at=start.timestamp()+2,
                                ended_at=None if active else start.timestamp()+12,activity_at=start.timestamp()+12)]
                            turns={'main':dict(id=cursor.turn,status='failed',error={'message':'fixture'},completedAt=start.timestamp()+20)} if main_kind=='failed' else {}
                            provider._publish([dict(id='main',name='Shared title')],[],{'main':cursor},[],None,None,turns)
                            data=provider.snapshot;rows={r['id']:r for r in task_rows(data)}
                            self.assertEqual(set(rows),{'main','side'});self.assertEqual(task_category(rows['main']),main_kind)
                            expected_side='running' if active else 'stopped' if side_kind=='turn_aborted' else 'unread' if unread else 'recent'
                            self.assertEqual(task_category(rows['side']),expected_side)
                            self.assertFalse(rows['side']['needs_input']);self.assertIsNone(rows['side']['tokens'])
                            self.assertEqual(data['totals']['total_tokens'],100)
                            counts=category_counts(data)
                            for kind in ('waiting','running','unread','stopped','failed','recent'):
                                expected=int(main_kind==kind)+int(expected_side==kind)
                                self.assertEqual(counts[kind],expected)
                                if kind!='recent':self.assertEqual(len(panel_rows(data,kind)),expected)
                            daily=panel_rows(data,'daily')
                            self.assertEqual([r['id'] for r in daily],['main'])
                            self.assertEqual(daily[0]['tokens'],100);self.assertIsNone(task_role_label(daily[0]))
                            self.assertEqual(task_role_label(rows['main']),'Main')
                            self.assertEqual(task_role_label(rows['side']),'Side')
                            search={r['id']:r for r in finder_rows(data,'en')}
                            self.assertEqual(set(search),{'main'});self.assertIsNone(task_role_label(search['main']))
                            self.assertEqual(search['main']['kind'],'' if main_kind=='recent' else main_kind)
                            self.assertEqual(rows['side']['navigation_id'],'main')
