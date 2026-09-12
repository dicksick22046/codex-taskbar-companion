from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from codex_taskbar.usage import UsageCursor, event_from_line, quota_windows, daily_quota_text, reset_countdown_text, remaining_time_fraction
from codex_taskbar.codex_api import project_name


def record(kind, at, total=None, turn="turn-1"):
    payload={"type":kind,"turn_id":turn}
    if total is not None:
        payload['info']={'total_token_usage':{'total_tokens':total,'input_tokens':total-10,'cached_input_tokens':total-20,'output_tokens':10,'reasoning_output_tokens':5}}
    return (json.dumps({'type':'event_msg','timestamp':at.isoformat(),'payload':payload})+'\n').encode()


class UsageTests(unittest.TestCase):
    def test_time_ring_uses_remaining_fraction_without_changing_countdown(self):
        window={'starts_at':1000,'resets_at':2000}
        self.assertEqual(remaining_time_fraction(window,1250),.75)
        self.assertEqual(remaining_time_fraction(window,2100),0)
        self.assertIsNone(remaining_time_fraction(None,1250))

    def test_countdown_shows_readable_duration_and_zero_after_reset(self):
        window={'resets_at':100000}
        self.assertEqual(reset_countdown_text(window,100000-2*86400-3*3600),'2d 3h')
        self.assertEqual(reset_countdown_text(window,100000-13*3600-42*60),'13h 42m')
        self.assertEqual(reset_countdown_text(window,100001),'0m')
        self.assertEqual(reset_countdown_text(None,1250),'—')

    def test_same_window_reset_preserves_pre_reset_daily_consumption(self):
        now=datetime.now().astimezone();start=now.replace(hour=0,minute=0,second=0,microsecond=0).timestamp()
        reset=now.timestamp()+604800
        rows=[{'at':start+i,'used':used,'reset':reset} for i,used in enumerate([20,40,0,5])]
        self.assertEqual(daily_quota_text(rows,{'remaining':95,'resets_at':reset},now),'25%')

    def test_daily_percentage_can_exceed_one_cycle_without_wrapping_the_ring(self):
        from codex_taskbar.usage import visible_metrics
        fields=visible_metrics({'quota':[{'minutes':10080,'remaining':75}],'daily_quota':'125%'},{'show_week':False,'show_countdown':False})
        self.assertEqual(fields,[('spent','125%',1.)])

    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.path=Path(self.folder.name)/'thread.jsonl'
        self.now=datetime.now().astimezone();self.old=self.now-timedelta(days=1)
    def tearDown(self):self.folder.cleanup()

    def test_today_is_delta_including_cache_without_double_counting_reasoning(self):
        self.path.write_bytes(record('token_count',self.old,100)+record('task_started',self.now)+record('token_count',self.now,150))
        c=UsageCursor(self.path);c.update()
        self.assertEqual(c.daily['total_tokens'],50)
        self.assertEqual(c.daily['cached_input_tokens'],50)
        self.assertTrue(c.running)

    def test_partial_record_waits_for_newline_and_counts_once(self):
        self.path.write_bytes(record('task_started',self.now))
        c=UsageCursor(self.path);c.update()
        line=record('token_count',self.now,70)
        with self.path.open('ab') as f:f.write(line[:-3])
        c.update();self.assertEqual(c.daily['total_tokens'],0)
        with self.path.open('ab') as f:f.write(line[-3:])
        c.update();c.update();self.assertEqual(c.daily['total_tokens'],70)

    def test_midnight_clears_today_without_new_events_and_retains_delta_baseline(self):
        midnight=self.now.replace(hour=0,minute=0,second=0,microsecond=0)
        before=midnight-timedelta(minutes=1)
        class Clock(datetime):
            current=before
            @classmethod
            def now(cls,tz=None):return cls.current.astimezone(tz)
        self.path.write_bytes(record('token_count',before-timedelta(days=1),800)+record('token_count',before,1000))
        with patch('codex_taskbar.usage.datetime',Clock):
            cursor=UsageCursor(self.path);cursor.update()
            self.assertEqual(cursor.daily['total_tokens'],200)
            Clock.current=midnight+timedelta(seconds=1)
            cursor.update()
            self.assertEqual(cursor.daily['total_tokens'],0)
            with self.path.open('ab') as f:f.write(record('token_count',Clock.current,1200))
            cursor.update()
            self.assertEqual(cursor.daily['total_tokens'],200)
            restarted=UsageCursor(self.path);restarted.update()
            self.assertEqual(restarted.daily['total_tokens'],200)

    def test_truncation_reloads_instead_of_adding_old_total(self):
        self.path.write_bytes(record('task_started',self.now)+record('token_count',self.now,900))
        c=UsageCursor(self.path);c.update()
        self.path.write_bytes(record('token_count',self.now,40));c.update()
        self.assertEqual(c.daily['total_tokens'],40)

    def test_late_completion_of_previous_turn_does_not_stop_current(self):
        self.path.write_bytes(record('task_started',self.now,turn='a')+record('task_started',self.now,turn='b')+record('task_complete',self.now,turn='a'))
        c=UsageCursor(self.path);c.update();self.assertTrue(c.running)
        with self.path.open('ab') as f:f.write(record('task_complete',self.now,turn='b'))
        c.update();self.assertFalse(c.running)

    def test_counter_reset_and_abort(self):
        self.path.write_bytes(record('task_started',self.now)+record('token_count',self.now,90)+record('token_count',self.now,20)+record('turn_aborted',self.now))
        c=UsageCursor(self.path);c.update()
        self.assertEqual(c.daily['total_tokens'],110);self.assertFalse(c.running)

    def test_duplicate_start_does_not_restart_the_same_round_clock(self):
        self.path.write_bytes(record('task_started',self.now)+record('task_started',self.now+timedelta(seconds=3))
                              +record('task_complete',self.now+timedelta(seconds=10)))
        cursor=UsageCursor(self.path);cursor.update()
        self.assertEqual(datetime.fromisoformat(cursor.started_at),self.now)
        self.assertEqual(cursor.elapsed_today(),10)

    def test_long_tail_recovers_day_baseline_before_large_tool_output(self):
        filler=(json.dumps({'type':'response_item','payload':'x'*1_100_000})+'\n').encode()
        self.path.write_bytes(record('token_count',self.old,100)+record('task_started',self.now)+filler+record('token_count',self.now,170))
        c=UsageCursor(self.path);c.update();self.assertEqual(c.daily['total_tokens'],70);self.assertTrue(c.running)

    def test_midday_week_reset_still_recovers_midnight_baseline(self):
        midnight=self.now.replace(hour=0,minute=0,second=0,microsecond=0)
        reset=midnight+timedelta(hours=10)
        filler=(json.dumps({'type':'response_item','payload':'x'*1_100_000})+'\n').encode()
        self.path.write_bytes(record('token_count',midnight-timedelta(minutes=1),1000)
            +record('task_started',midnight+timedelta(hours=2))
            +record('token_count',midnight+timedelta(hours=3),1100)+filler
            +record('token_count',reset-timedelta(seconds=1),1300)
            +record('token_count',reset+timedelta(seconds=1),1400)
            +record('task_complete',reset+timedelta(seconds=2)))
        cursor=UsageCursor(self.path,since=reset);cursor.update()
        self.assertEqual(cursor.daily['total_tokens'],400)
        self.assertEqual(cursor.by_day[self.now.date().isoformat()],100)

    def test_missing_quota_is_not_zero_and_used_is_converted(self):
        self.assertEqual(quota_windows({}),[])
        data={'rateLimits':{'primary':{'usedPercent':77,'windowDurationMins':10080}}}
        self.assertEqual(quota_windows(data)[0]['remaining'],23)

    def test_project_uses_root_membership_not_similar_prefix(self):
        projects=[{'id':'1','name':'项目甲','roots':[{'path':str(Path(self.folder.name)/'repo')}]}]
        self.assertEqual(project_name({'cwd':str(Path(self.folder.name)/'repo'/'sub')},projects),'项目甲')
        self.assertEqual(project_name({'cwd':str(Path(self.folder.name)/'repo-other')},projects),'')

    def test_first_day_starts_from_first_record_and_empty_data_stays_unknown(self):
        midnight=self.now.replace(hour=0,minute=0,second=0,microsecond=0).timestamp()
        window={'remaining':23,'resets_at':self.now.timestamp()+86400,'starts_at':midnight-6*86400}
        rows=[{'at':midnight-20,'used':67,'reset':window['resets_at']},
              {'at':midnight+20,'used':67,'reset':window['resets_at']}]
        self.assertEqual(daily_quota_text(rows,window,self.now),'10%')
        rows[-1]['used']=68
        self.assertEqual(daily_quota_text(rows,window,self.now),'9%')
        self.assertEqual(daily_quota_text([],window,self.now),'—')
        rows=[{'at':midnight+20,'used':75,'reset':window['resets_at']}]
        self.assertEqual(daily_quota_text(rows,window,self.now),'2%')
        window['remaining']=25
        self.assertEqual(daily_quota_text(rows,window,self.now),'0%')

    def test_period_chart_excludes_inherited_fork_tokens(self):
        earlier=self.now-timedelta(hours=1)
        self.path.write_bytes(record('token_count',earlier,100)+record('task_started',self.now)+record('token_count',self.now,130))
        c=UsageCursor(self.path,since=self.now-timedelta(days=7),created_after=self.now.timestamp()-1)
        c.update()
        self.assertEqual(c.daily['total_tokens'],30)
        self.assertEqual(c.by_day[self.now.date().isoformat()],30)

    def test_daily_quota_keeps_observed_consumption_across_week_reset(self):
        now=self.now.replace(hour=14,minute=0,second=0,microsecond=0)
        midnight=now.replace(hour=0).timestamp()
        old_reset=midnight+10*3600;new_reset=old_reset+7*86400
        samples=[{'at':midnight-30,'used':80,'reset':old_reset},
                 {'at':midnight+30,'used':81,'reset':old_reset},
                 {'at':old_reset-30,'used':88,'reset':old_reset},
                 {'at':old_reset+30,'used':1,'reset':new_reset},
                 {'at':now.timestamp(),'used':4,'reset':new_reset}]
        window={'remaining':96,'resets_at':new_reset}
        self.assertEqual(daily_quota_text(samples,window,now),'10%')
        self.assertEqual(daily_quota_text(samples[1:],window,now),'10%')
        # Sampling gaps are not filled by assuming a fully consumed old week.
        self.assertNotEqual(daily_quota_text(samples,window,now),'23%')


if __name__=='__main__':unittest.main()
