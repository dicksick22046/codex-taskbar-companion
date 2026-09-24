from datetime import datetime, timedelta
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from codex_taskbar.pricing import estimate_usd, sum_costs
from codex_taskbar.usage import UsageCursor, event_from_line
from codex_taskbar.provider import Provider


def usage(inputs=1000, cached=300, written=100, outputs=100):
    return {'input_tokens':inputs, 'cached_input_tokens':cached,
            'cache_write_input_tokens':written, 'output_tokens':outputs,
            'reasoning_output_tokens':50, 'total_tokens':inputs+outputs}


def add(left, right):
    return {key:left.get(key, 0)+value for key,value in right.items()}


def record(at, kind, payload):
    return (json.dumps({'timestamp':at.isoformat(), 'type':kind, 'payload':payload})+'\n').encode()


def context(at, model='gpt-6-astra'):
    return record(at, 'turn_context', {'model':model, 'turn_id':'t', 'cwd':'private-path', 'summary':'private text'})


def count(at, total, step):
    return record(at, 'event_msg', {'type':'token_count', 'info':{'total_token_usage':total, 'last_token_usage':step}})


class PricingTests(unittest.TestCase):
    def test_cache_read_write_and_reasoning_are_not_double_counted(self):
        self.assertAlmostEqual(estimate_usd('gpt-6-astra', usage()), .01255)
        self.assertAlmostEqual(estimate_usd('gpt-6-sol', usage()), .00251)
        self.assertAlmostEqual(estimate_usd('gpt-6-luna', usage()), .0001255)
        self.assertAlmostEqual(estimate_usd('gpt-5.6-sol', usage()), .00502)
        self.assertAlmostEqual(estimate_usd('gpt-5.5', usage()), .00665)
        self.assertAlmostEqual(estimate_usd('gpt-5.6-terra', usage()), .00271)
        self.assertAlmostEqual(estimate_usd('gpt-5.6-luna', usage()), .000271)
        self.assertAlmostEqual(estimate_usd('gpt-5.4', usage()), .003325)

    def test_long_context_uses_call_input_and_strict_boundary(self):
        at_limit=usage(272000, 100000, 10000, 1000)
        above=usage(272001, 100000, 10000, 1000)
        self.assertAlmostEqual(estimate_usd('gpt-6-astra', at_limit), 1.895)
        self.assertAlmostEqual(estimate_usd('gpt-6-astra', above), 3.76502)
        self.assertAlmostEqual(estimate_usd('gpt-6-sol', at_limit), .379)
        self.assertAlmostEqual(estimate_usd('gpt-6-sol', above), .753004)
        self.assertAlmostEqual(estimate_usd('gpt-6-luna', at_limit), .01895)
        self.assertAlmostEqual(estimate_usd('gpt-6-luna', above), .0376502)
        self.assertAlmostEqual(estimate_usd('gpt-5.6-luna', at_limit), .0381)
        self.assertAlmostEqual(estimate_usd('gpt-5.6-luna', above), .0756004)

    def test_mini_does_not_have_a_long_context_surcharge(self):
        large=usage(300000,100000,0,1000)
        self.assertAlmostEqual(estimate_usd('gpt-5.4-mini',large),.162)
        self.assertAlmostEqual(estimate_usd('gpt-5.4',large),1.0725)

    def test_unknown_models_and_incomplete_or_inconsistent_counts_stay_unknown(self):
        self.assertIsNone(estimate_usd('gpt-6-astra-unverified', usage()))
        for edit in ({'input_tokens':None}, {'cached_input_tokens':True}, {'total_tokens':999},
                     {'cache_write_input_tokens':800}, {'output_tokens':-1}):
            self.assertIsNone(estimate_usd('gpt-6-astra', dict(usage(), **edit)))
        missing=usage();del missing['cache_write_input_tokens']
        self.assertIsNone(estimate_usd('gpt-6-astra', missing))
        self.assertAlmostEqual(estimate_usd('gpt-5.5', missing), .00665)

    def test_incomplete_positive_cost_poisons_sum_but_absent_zero_does_not(self):
        self.assertIsNone(sum_costs([(100, .1), (200, None)]))
        self.assertEqual(sum_costs([(100, .1), (0, None)]), .1)
        self.assertEqual(sum_costs([(0, 0.)]), 0.)
        self.assertIsNone(sum_costs([]))


class CursorCostTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.path=Path(self.folder.name)/'usage.jsonl'
        self.now=datetime.now().astimezone().replace(hour=12, minute=0, second=0, microsecond=0)

    def tearDown(self):self.folder.cleanup()

    def cursor(self, data, **kwargs):
        self.path.write_bytes(data)
        cursor=UsageCursor(self.path, **kwargs);cursor.update();return cursor

    def test_projection_retains_only_pricing_context_and_not_activity(self):
        event=event_from_line(context(self.now))
        self.assertNotIn('private', repr(event))
        cursor=UsageCursor(self.path);cursor.apply(event)
        self.assertIsNone(cursor.activity_at)
        self.assertEqual(cursor.model, 'gpt-6-astra')

    def test_incremental_mixed_models_equal_replay_and_duplicate_is_free(self):
        first=usage();second=usage(2000, 1000, 0, 200)
        cursor=self.cursor(context(self.now)+count(self.now, first, first))
        initial=cursor.daily_usd
        with self.path.open('ab') as stream:
            stream.write(count(self.now, first, first)+context(self.now, 'gpt-5.6-sol')+
                         count(self.now, add(first, second), second))
        cursor.update();cursor.update()
        expected=initial+estimate_usd('gpt-5.6-sol', second)
        self.assertAlmostEqual(cursor.daily_usd, expected)
        replay=UsageCursor(self.path);replay.update()
        self.assertEqual(replay.daily_usd, cursor.daily_usd)
        self.assertEqual(replay.daily, cursor.daily)
        self.assertEqual(cursor.by_day_usd, {self.now.date().isoformat():expected})

    def test_new_model_steps_complete_daily_and_period_totals(self):
        sol=usage();luna=usage(2000,1000,100,200)
        periods=(('current',self.now.timestamp()-1,self.now.timestamp()+60),)
        data=context(self.now,'gpt-6-sol')+count(self.now,sol,sol)
        data+=context(self.now,'gpt-6-luna')+count(self.now,add(sol,luna),luna)
        cursor=self.cursor(data,periods=periods)
        expected=estimate_usd('gpt-6-sol',sol)+estimate_usd('gpt-6-luna',luna)
        self.assertAlmostEqual(cursor.daily_usd,expected)
        self.assertAlmostEqual(cursor.by_day_usd[self.now.date().isoformat()],expected)
        self.assertAlmostEqual(cursor.period_usd['current'],expected)
        self.assertEqual(cursor.daily['total_tokens'],sol['total_tokens']+luna['total_tokens'])

    def test_cumulative_inputs_do_not_trigger_long_context_price(self):
        step=usage(200000, 100000, 0, 1000)
        cursor=self.cursor(context(self.now)+count(self.now, step, step)+count(self.now, add(step,step), step))
        self.assertAlmostEqual(cursor.daily_usd, 2*estimate_usd('gpt-6-astra', step))

    def test_unknown_partial_and_counter_reset_never_expose_known_subtotal(self):
        step=usage()
        fixtures=(context(self.now, 'unknown')+count(self.now, step, step),
                  context(self.now)+count(self.now, add(step,step), step),
                  context(self.now)+count(self.now, add(step,step), add(step,step))+count(self.now, step,add(step,step)),
                  context(self.now)+count(self.now,step,None))
        for data in fixtures:
            cursor=self.cursor(data)
            self.assertIsNone(cursor.daily_usd)
            self.assertIsNone(cursor.by_day_usd[self.now.date().isoformat()])

    def test_reset_is_priced_only_when_each_token_delta_proves_the_single_call(self):
        step=usage();double=add(step,step)
        cursor=self.cursor(context(self.now)+count(self.now,double,double)+count(self.now,step,step))
        self.assertAlmostEqual(cursor.daily_usd,3*estimate_usd('gpt-6-astra',step))
        # Output grew while the total counter reset: the original output delta is
        # smaller than the reported call, so it cannot use the new total as proof.
        before=usage(2000,300,100,100);after=usage(1000,100,50,200)
        mixed=self.cursor(context(self.now)+count(self.now,before,before)+count(self.now,after,after))
        self.assertIsNone(mixed.daily_usd)

    def test_fork_baseline_and_period_boundaries(self):
        old=self.now-timedelta(days=1);step=usage()
        periods=(('old',old.timestamp(),self.now.timestamp()),('new',self.now.timestamp(),self.now.timestamp()+60))
        data=context(old)+count(old, step, step)+context(self.now, 'gpt-5.6-sol')+count(self.now,add(step,step),step)
        cursor=self.cursor(data, created_after=self.now.timestamp(), periods=periods)
        self.assertNotIn('old',cursor.period_usd)
        self.assertAlmostEqual(cursor.period_usd['new'],estimate_usd('gpt-5.6-sol',step))
        self.assertEqual(cursor.period_totals, {'old':0,'new':1100})
        missing=self.cursor(context(self.now)+count(self.now,step,step),created_after=self.now.timestamp())
        self.assertIsNone(missing.daily_usd)

    def test_zero_and_absent_observations_are_distinct(self):
        cursor=self.cursor(context(self.now))
        self.assertIsNone(cursor.daily_usd)
        zero=usage(0,0,0,0)
        with self.path.open('ab') as stream:stream.write(count(self.now,zero,zero))
        cursor.update();self.assertEqual(cursor.daily_usd,0.)

    def test_next_turn_without_context_does_not_reuse_previous_model(self):
        step=usage()
        data=context(self.now)+count(self.now,step,step)
        data+=record(self.now,'event_msg',{'type':'task_started','turn_id':'next'})
        data+=count(self.now,add(step,step),step)
        self.assertIsNone(self.cursor(data).daily_usd)

    def test_tail_without_model_keeps_existing_scan_bound_and_unknown_cost(self):
        old=self.now-timedelta(days=1);step=usage()
        start=record(old,'event_msg',{'type':'task_started','turn_id':'t'})
        ignored=record(old,'response_item',{'type':'message','text':'x'*1100000})
        data=start+context(old)+ignored+count(old,step,step)+start+count(self.now,add(step,step),step)
        with patch('codex_taskbar.usage.event_from_line', wraps=event_from_line) as parser:
            cursor=self.cursor(data)
        self.assertLess(parser.call_count,5)
        self.assertIsNone(cursor.daily_usd)
        self.assertEqual(cursor.daily['total_tokens'],1100)

    def test_unknown_and_counter_reset_only_poison_their_own_day_and_period(self):
        old=self.now-timedelta(days=2);middle=self.now-timedelta(days=1);step=usage()
        periods=(('a',old.timestamp(),middle.timestamp()),('b',middle.timestamp(),self.now.timestamp()),
                 ('c',self.now.timestamp(),self.now.timestamp()+60))
        data=context(old,'unknown')+count(old,add(step,step),step)
        data+=context(middle)+count(middle,step,add(step,step))
        data+=context(self.now)+count(self.now,add(step,step),step)
        cursor=self.cursor(data,since=old,periods=periods)
        expected=estimate_usd('gpt-6-astra',step)
        self.assertIsNone(cursor.by_day_usd[old.date().isoformat()])
        self.assertIsNone(cursor.by_day_usd[middle.date().isoformat()])
        self.assertAlmostEqual(cursor.by_day_usd[self.now.date().isoformat()],expected)
        self.assertEqual(cursor.period_usd,{'a':None,'b':None,'c':expected})
        self.assertAlmostEqual(cursor.daily_usd,expected)

    def test_provider_projects_costs_without_side_duplicates_or_partial_totals(self):
        step=usage();start=self.now.timestamp();periods=(('p',start-1,start+60),)
        cursor=self.cursor(context(self.now)+count(self.now,step,step),periods=periods)
        provider=Provider.__new__(Provider);provider.runtime_dir=Path(self.folder.name)
        provider.lock=threading.Lock();provider.boot_time=start-100;provider.quota_history=[]
        provider.unread_state=Mock();provider.unread_state.read.return_value=set()
        provider.resets=Mock();provider.resets.periods.return_value=periods
        provider.resets.view.side_effect=lambda:{'reset_events':[{'id':'p'}]}
        provider.side_rows=[dict(id='side',parent_id='main',running=True,started_at=start,
                                ended_at=None,activity_at=start)]
        threads=[{'id':'main','name':'Fixture'}]
        provider._publish(threads,[],{'main':cursor},[],None,None)
        data=provider.snapshot;amount=estimate_usd('gpt-6-astra',step)
        self.assertAlmostEqual(data['daily_usd'],amount)
        self.assertAlmostEqual(data['history_usd'][self.now.date().isoformat()],amount)
        self.assertAlmostEqual(data['reset_events'][0]['usd'],amount)
        rows={row['id']:row for row in data['tasks']+data['recent_tasks']}
        self.assertAlmostEqual(rows['main']['usd'],amount)
        self.assertNotIn('usd',rows['side'])
        unknown_path=Path(self.folder.name)/'unknown.jsonl'
        unknown_path.write_bytes(context(self.now,'unknown')+count(self.now,step,step))
        unknown=UsageCursor(unknown_path,periods=periods);unknown.update()
        provider._publish(threads+[{'id':'other','name':'Unknown'}],[],{'main':cursor,'other':unknown},[],None,None)
        self.assertIsNone(provider.snapshot['daily_usd'])
        self.assertIsNone(provider.snapshot['history_usd'][self.now.date().isoformat()])
        self.assertIsNone(provider.snapshot['reset_events'][0]['usd'])
