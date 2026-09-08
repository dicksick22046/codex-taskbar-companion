import copy
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from provider import Provider
from resets import ResetLedger, latest_credit


def credit(name='new', granted=None, expiry=None):
    now=time.time()
    return {'id':name,'status':'available','resetType':'codexRateLimits','grantedAt':now-100 if granted is None else granted,
            'expiresAt':now+86400 if expiry is None else expiry}


def response(account='fixture-account', used=70, reset=None, rows=None):
    return {'accountId':account,'rateLimits':{'primary':{'windowDurationMins':10080,'usedPercent':used,
            'resetsAt':reset if reset is not None else time.time()+604800}},
            'rateLimitResetCredits':{'availableCount':len(rows or [credit()]),'credits':rows or [credit()]}}


class ResetTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.path=Path(self.folder.name)/'reset_history.json'
        self.raw=response(reset=time.time()+604800)
        self.ledger=ResetLedger(self.path);self.ledger.observe(self.raw)

    def tearDown(self):self.folder.cleanup()

    def provider(self):
        provider=Provider.__new__(Provider)
        provider.lock=threading.Lock();provider.refresh_event=threading.Event()
        provider.reset_busy=False;provider.reset_request=None;provider.snapshot={};provider.resets=self.ledger
        provider.quota_history=[];provider.quota_history_path=Path(self.folder.name)/'quota_history.json'
        return provider

    def test_latest_means_newest_grant_not_earliest_expiry(self):
        now=time.time()
        rows=[credit('old',now-200,now+20),credit('new',now-100,now+500)]
        self.assertEqual(latest_credit({'availableCount':2,'credits':rows})['id'],'new')

    def test_incomplete_or_expired_credits_do_not_invent_a_choice(self):
        self.assertIsNone(latest_credit({'availableCount':2,'credits':[credit()]}))
        expired=credit(expiry=time.time()-1)
        self.assertIsNone(latest_credit({'availableCount':1,'credits':[expired]}))
        unknown=credit();unknown['expiresAt']=None
        self.assertEqual(latest_credit({'availableCount':1,'credits':[unknown]})['id'],'new')

    def test_granting_an_opportunity_is_not_a_reset_event(self):
        changed=copy.deepcopy(self.raw);changed['rateLimitResetCredits']['credits'].append(credit('other'))
        changed['rateLimitResetCredits']['availableCount']=2
        self.ledger.observe(changed)
        self.assertEqual(self.ledger.view()['reset_events'],[])

    def test_deadline_jitter_and_zero_balance_settling_are_not_resets(self):
        deadline=time.time()+604800
        for used in (10,0):
            ledger=ResetLedger(Path(self.folder.name)/f'jitter-{used}.json')
            for shift in (0,1,0,4,30):
                ledger.observe(response(used=used,reset=deadline+shift))
            self.assertEqual(ledger.view()['reset_events'],[])

    def test_unused_natural_window_rollover_is_still_recorded(self):
        self.ledger.observe(response(used=0,reset=1000),900)
        self.ledger.record['events']=[]
        self.ledger.observe(response(used=0,reset=605800),1001)
        events=self.ledger.view()['reset_events']
        self.assertEqual([e['kind'] for e in events],['scheduled'])
        self.assertEqual(events[0]['before']['10080']['resets_at'],1000)

    def test_scheduled_and_unknown_changes_are_distinct(self):
        first=response(reset=1000)
        self.ledger.observe(first,100)
        self.ledger.record['events']=[]
        self.ledger.observe(response(used=0,reset=1000+604800),1001)
        self.assertEqual(self.ledger.view()['reset_events'][0]['kind'],'scheduled')
        self.ledger.observe(response(used=20,reset=1000+604800),1100)
        self.ledger.observe(response(used=0,reset=1000+604800),1200)
        self.assertEqual(self.ledger.view()['reset_events'][0]['kind'],'unknown')
        self.assertNotIn('official',[e['kind'] for e in self.ledger.view()['reset_events']])

    def test_success_is_one_manual_event_not_an_extra_unknown(self):
        params=self.ledger.begin('fixture-account','new')
        self.ledger.finish('reset')
        after=copy.deepcopy(self.raw);after['rateLimits']['primary']['usedPercent']=0
        self.ledger.observe(after)
        events=self.ledger.view()['reset_events']
        self.assertEqual(len(events),1);self.assertEqual(events[0]['kind'],'manual')
        self.assertEqual(events[0]['id'],params['idempotencyKey']);self.assertEqual(events[0]['windows'],['10080'])

    def test_restart_and_uncertain_retry_keep_same_credit_and_key(self):
        original=self.ledger.begin('fixture-account','new');self.ledger.failed()
        restarted=ResetLedger(self.path)
        after=copy.deepcopy(self.raw);after['rateLimits']['primary']['usedPercent']=0
        after['rateLimitResetCredits']={'availableCount':1,'credits':[credit('another')]}
        restarted.observe(after)
        self.assertEqual(restarted.view()['reset_events'],[])
        self.assertEqual(restarted.view()['reset_selected']['id'],'new')
        self.assertEqual(restarted.begin('fixture-account','new'),original)
        restarted.finish('alreadyRedeemed');restarted.observe(after)
        self.assertEqual([e['kind'] for e in restarted.view()['reset_events']],['manual'])

    def test_no_credit_and_nothing_to_reset_do_not_record_success(self):
        for outcome in ['noCredit','nothingToReset']:
            self.ledger.begin('fixture-account','new');self.ledger.finish(outcome)
            self.assertEqual(self.ledger.view()['reset_events'],[])

    def test_switching_account_never_reuses_another_accounts_pending_request(self):
        self.ledger.begin('fixture-account','new')
        self.ledger.observe(response(account='different-account'))
        self.assertIsNone(self.ledger.record['pending'])
        with self.assertRaises(ValueError):self.ledger.begin('fixture-account','new')
        self.ledger.observe(self.raw)
        self.assertTrue(self.ledger.view()['reset_retry'])

    def test_duplicate_click_is_queued_once_and_consumption_is_mocked(self):
        provider=self.provider();calls=[];raw=self.raw
        class FakeApi:
            def call(self,method,params=None):
                calls.append((method,params))
                if method=='account/rateLimits/read':return raw
                return {'outcome':'reset'}
        self.assertTrue(provider.request_reset('fixture-account','new'))
        self.assertFalse(provider.request_reset('fixture-account','new'))
        provider._process_reset(FakeApi())
        self.assertEqual([c[0] for c in calls],['account/rateLimits/read','account/rateLimitResetCredit/consume'])
        self.assertFalse(provider.reset_busy)
        self.assertEqual(provider.quota_history[-1]['used'],70)

    def test_storage_failure_prevents_consumption(self):
        provider=self.provider();calls=[];raw=self.raw
        class FakeApi:
            def call(self,method,params=None):calls.append(method);return raw
        provider.request_reset('fixture-account','new')
        with patch.object(self.ledger,'save',side_effect=OSError('fixture write failure')),patch('builtins.print'):
            provider._process_reset(FakeApi())
        self.assertEqual(calls,['account/rateLimits/read'])

    def test_fresh_account_or_credit_change_is_rejected_before_consumption(self):
        for raw in [response(account='other'),response(rows=[credit('different')])]:
            provider=self.provider();calls=[]
            class FakeApi:
                def call(self,method,params=None):calls.append(method);return raw
            provider.request_reset('fixture-account','new')
            with patch('builtins.print'):provider._process_reset(FakeApi())
            self.assertEqual(calls,['account/rateLimits/read'])
            self.ledger.observe(self.raw)

    def test_post_success_save_failure_cannot_switch_to_another_credit(self):
        original=self.ledger.begin('fixture-account','new')
        with patch.object(self.ledger,'save',side_effect=OSError('fixture save failure')):
            with self.assertRaises(OSError):self.ledger.finish('reset')
        after=copy.deepcopy(self.raw);after['rateLimits']['primary']['usedPercent']=0
        after['rateLimitResetCredits']={'availableCount':1,'credits':[credit('another')]}
        self.ledger.observe(after)
        self.assertEqual(self.ledger.view()['reset_selected']['id'],'new')
        self.assertEqual(self.ledger.begin('fixture-account','new'),original)
        self.ledger.finish('alreadyRedeemed');self.ledger.observe(after)
        self.assertEqual([e['kind'] for e in self.ledger.view()['reset_events']],['manual'])

    def test_session_curve_keeps_only_observed_points_in_current_window(self):
        raw=copy.deepcopy(self.raw)
        raw['rateLimits']['secondary']={'windowDurationMins':300,'usedPercent':20,'resetsAt':20000}
        self.ledger.observe(raw,5000)
        raw['rateLimits']['secondary']['usedPercent']=30;self.ledger.observe(raw,5030)
        self.assertEqual([s['remaining'] for s in self.ledger.view()['session_history']],[80,70])
        raw['rateLimits']['secondary']['resetsAt']=38000;self.ledger.observe(raw,20001)
        self.assertEqual(len(self.ledger.view()['session_history']),1)
