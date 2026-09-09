from datetime import datetime,timezone
from contextlib import closing
from pathlib import Path
import sqlite3
import os
import time
import tempfile
import unittest
from unittest.mock import patch

from codex_taskbar.side_chats import SideChats


class SideChatTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.log=self.root/'codex-desktop-session-123-t0-i1-000000-0.log'
        self.core=self.root/'core.sqlite';self.state=self.root/'state.sqlite'
        with closing(sqlite3.connect(self.core)) as c:
            c.execute('create table logs(ts integer,thread_id text,feedback_log_body text)')
            c.execute("insert into logs values(100,'side','app_server.request{rpc.request_id=fork-request}')");c.commit()
        with closing(sqlite3.connect(self.state)) as c:
            c.execute('create table threads(id text)');c.execute("insert into threads values('main')");c.commit()
        self.reader=SideChats(self.root,self.core,self.state)
        self.log.write_text(self.response(100,'main','thread/fork','fork-request')+self.response(102,'side','turn/start','start'),encoding='utf-8')

    def tearDown(self):self.temp.cleanup()

    def response(self,at,thread,method,request):
        stamp=datetime.fromtimestamp(at,timezone.utc).isoformat()
        return f'{stamp} info [AppServerConnection] response_routed conversationId={thread} durationMs=100 errorCode=null method={method} requestId={request}\n'

    def test_ephemeral_fork_maps_to_parent_and_completion_stops_it(self):
        with patch('codex_taskbar.side_chats.process_alive',return_value=True):
            rows=self.reader.update([{'id':'main'}])
            self.assertEqual([(r['parent_id'],r['running']) for r in rows],[('main',True)])
            self.assertEqual(self.reader.update([{'id':'main'}]),rows)
            with self.log.open('a',encoding='utf-8') as f:
                f.write('1970-01-01T00:02:00+00:00 info [electron-message-handler] [desktop-notifications] show turn-complete conversationId=side turnId=turn\n')
            completed=self.reader.update([{'id':'main'}])[0]
            self.assertFalse(completed['running']);self.assertEqual(completed['completion_kind'],'task_complete')
            with self.log.open('a',encoding='utf-8') as f:f.write(self.response(130,'side','turn/start','again'))
            self.assertEqual(self.reader.update([{'id':'main'}])[0]['started_at'],130)

    def test_regular_fork_and_exited_desktop_are_not_running_side_chats(self):
        with closing(sqlite3.connect(self.state)) as c:c.execute("insert into threads values('side')");c.commit()
        with patch('codex_taskbar.side_chats.process_alive',return_value=True):self.assertEqual(self.reader.update([{'id':'main'}]),[])
        with patch('codex_taskbar.side_chats.process_alive',return_value=False):self.assertEqual(self.reader.update([{'id':'main'}]),[])

    def test_interrupt_is_terminal_and_partial_line_waits_for_newline(self):
        with patch('codex_taskbar.side_chats.process_alive',return_value=True):
            self.reader.update([{'id':'main'}])
            line=self.response(120,'side','turn/interrupt','stop')
            with self.log.open('a',encoding='utf-8') as f:f.write(line[:-1])
            self.assertTrue(self.reader.update([{'id':'main'}])[0]['running'])
            with self.log.open('a',encoding='utf-8') as f:f.write('\n')
            self.assertFalse(self.reader.update([{'id':'main'}])[0]['running'])
            self.assertEqual(self.reader.update([{'id':'main'}])[0]['completion_kind'],'turn_aborted')

    def test_restart_retains_confirmed_link_after_core_logs_are_pruned(self):
        cache=self.root/'links.json'
        reader=SideChats(self.root,self.core,self.state,cache)
        with patch('codex_taskbar.side_chats.process_alive',return_value=True):
            self.assertTrue(reader.update([{'id':'main'}])[0]['running'])
            with closing(sqlite3.connect(self.core)) as c:c.execute('delete from logs');c.commit()
            restored=SideChats(self.root,self.core,self.state,cache)
            self.assertEqual(restored.update([{'id':'main'}])[0]['parent_id'],'main')
            with self.log.open('a',encoding='utf-8') as f:
                f.write('1970-01-01T00:02:00+00:00 info [electron-message-handler] [desktop-notifications] show turn-complete conversationId=side turnId=turn\n')
            restarted=SideChats(self.root,self.core,self.state,cache)
            self.assertFalse(restarted.update([{'id':'main'}])[0]['running'])
            self.assertEqual(restarted.update([{'id':'main'}])[0]['completion_kind'],'task_complete')
            self.assertNotIn('running',cache.read_text())

    def test_new_desktop_session_does_not_reuse_cached_links(self):
        cache=self.root/'links.json';reader=SideChats(self.root,self.core,self.state,cache)
        with patch('codex_taskbar.side_chats.process_alive',return_value=True):
            reader.update([{'id':'main'}])
            other=self.root/'codex-desktop-new-124-t0-i1-000000-0.log'
            other.write_text(self.response(140,'side','turn/start','other-start'),encoding='utf-8')
            os.utime(other,(time.time()+1,time.time()+1))
            self.assertEqual(SideChats(self.root,self.core,self.state,cache).update([{'id':'main'}]),[])

    def test_cache_write_failure_keeps_live_state_and_retries_later(self):
        cache=self.root/'links.json';reader=SideChats(self.root,self.core,self.state,cache)
        with patch('codex_taskbar.side_chats.process_alive',return_value=True):
            with patch('codex_taskbar.side_chats.write_json',side_effect=OSError('busy')):
                self.assertTrue(reader.update([{'id':'main'}])[0]['running'])
            self.assertFalse(cache.exists())
            self.assertTrue(reader.update([{'id':'main'}])[0]['running'])
            self.assertTrue(cache.exists())
