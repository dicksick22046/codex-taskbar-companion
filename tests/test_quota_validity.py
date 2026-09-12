import copy
from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch

from codex_taskbar.usage import (
    chart_window, daily_observed_at, daily_quota_text, effective_quota_data,
    quota_is_cached, quota_window, visible_metrics,
)


class QuotaValidityTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 12, 14, tzinfo=timezone(timedelta(hours=8)))
        self.stamp = self.now.timestamp()
        self.week = dict(minutes=10080, remaining=80, starts_at=self.stamp-604800,
                         resets_at=self.stamp+86400)
        self.session = dict(minutes=300, remaining=69, starts_at=self.stamp-18000,
                            resets_at=self.stamp)

    def metrics(self, data, settings=None):
        now = self.now
        class Clock(datetime):
            @classmethod
            def now(cls, tz=None):return now
        with patch('codex_taskbar.usage.datetime', Clock):
            return {kind:(value, fraction) for kind,value,fraction in visible_metrics(data, settings or {})}

    def test_known_expiry_applies_at_boundary_with_or_without_read_errors(self):
        for error in ({}, {'quota_error':'timeout'}, {'error':'catalog timeout'}):
            with self.subTest(error=error):
                data = dict(quota=[self.week, self.session], daily_quota='3%', **error)
                before = effective_quota_data(data, self.stamp-1)
                self.assertIsNotNone(quota_window(before, 300))
                current = effective_quota_data(data, self.stamp)
                self.assertIsNone(quota_window(current, 300))
                self.assertEqual(current['quota'], [self.week])
                self.assertEqual(current['daily_quota'], '3%')
                after = effective_quota_data(data, self.stamp+86400)
                self.assertEqual(after['quota'], [])
                self.assertEqual(after['daily_quota'], '—')
                self.assertIsNone(after['daily_observed_at'])

    def test_unknown_reset_remains_unknown_and_keeps_known_balance(self):
        for reset in ({}, {'resets_at':None}):
            window = dict(minutes=300, remaining=69, **reset)
            data = dict(quota=[window], quota_error='timeout')
            self.assertEqual(effective_quota_data(data, self.stamp)['quota'], [window])
            self.assertEqual(self.metrics(data)['session'], ('5h 69%', .69))
            self.assertEqual(self.metrics(data)['clock'], ('—', None))

    def test_projection_preserves_raw_snapshot_and_historical_cycle(self):
        expired = dict(self.week, resets_at=self.stamp)
        data = dict(quota=[expired], daily_quota='3%', daily_observed_at=self.now.isoformat(),
                    history={'2026-09-12':123}, reset_events=[{'tokens':456}])
        original = copy.deepcopy(data)
        result = effective_quota_data(data, self.stamp)
        self.assertIsNot(result, data)
        self.assertEqual(result['quota'], [])
        self.assertEqual(result['history'], original['history'])
        self.assertEqual(result['reset_events'], original['reset_events'])
        self.assertEqual(chart_window(data), expired)
        self.assertEqual(data, original)
        retained = effective_quota_data(dict(quota=[self.week]), self.stamp)
        retained['quota'][0]['remaining'] = 0
        self.assertEqual(self.week['remaining'], 80)

    def test_expired_session_keeps_only_proven_capability_as_unknown(self):
        data = dict(quota=[self.week, self.session], daily_quota='3%')
        for error in ({}, {'quota_error':'timeout'}):
            metrics = self.metrics({**data, **error})
            self.assertEqual(metrics['session'], ('5h —', None))
            self.assertEqual(metrics['quota'], ('7d 80%', .8))
            self.assertNotEqual(metrics['clock'], ('—', None))
        self.assertNotIn('session', self.metrics(data, {'show_session':False}))
        self.assertNotIn('session', self.metrics(dict(quota=[self.week], plan_type='plus')))
        self.assertNotIn('session', self.metrics(dict(quota=[], plan_type='pro')))
        metrics = self.metrics(dict(quota=[self.session]))
        self.assertEqual(metrics['session'], ('5h —', None))
        self.assertEqual(metrics['clock'], ('—', None))

    def test_cache_status_uses_quota_error_and_previous_result_only(self):
        self.assertTrue(quota_is_cached(dict(quota=[self.week], quota_error='timeout')))
        self.assertTrue(quota_is_cached(dict(quota=[self.session], quota_error='timeout')))
        self.assertFalse(quota_is_cached(dict(quota=[self.week], error='catalog timeout')))
        self.assertFalse(quota_is_cached(dict(quota=[], quota_error='timeout')))
        self.assertFalse(quota_is_cached(dict(quota=[self.week], quota_error=None)))

    def test_daily_value_without_a_valid_week_is_unknown(self):
        for quota in ([], [self.session], [dict(self.week, resets_at=self.stamp)]):
            data = dict(quota=quota, daily_quota='3%', daily_observed_at=self.now.isoformat())
            result = effective_quota_data(data, self.stamp)
            self.assertEqual(result['daily_quota'], '—')
            self.assertIsNone(result['daily_observed_at'])


class DailyObservationTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 12, 14, tzinfo=timezone(timedelta(hours=8)))
        self.midnight = self.now.replace(hour=0).timestamp()
        self.reset = self.now.timestamp()+86400
        self.window = dict(remaining=70, resets_at=self.reset)

    def sample(self, seconds, used=20, reset=None):
        return dict(at=self.midnight+seconds, used=used, reset=self.reset if reset is None else reset)

    def test_first_valid_observation_skips_empty_and_future_samples(self):
        samples = [self.sample(-1), self.sample(10, None), self.sample(20, reset=0),
                   self.sample(16*3600), self.sample(12*3600, 25), self.sample(11*3600)]
        observed = daily_observed_at(samples, self.window, self.now)
        self.assertEqual(observed, self.now.replace(hour=11).isoformat())
        self.assertEqual(daily_quota_text(samples, self.window, self.now), '10%')

    def test_midnight_uses_only_the_new_local_day(self):
        samples = [self.sample(-1), self.sample(0), self.sample(1)]
        now = self.now.replace(hour=0)
        self.assertEqual(daily_observed_at(samples, self.window, now), now.isoformat())
        self.assertIsNone(daily_observed_at(samples[:1], self.window, now))
        self.assertIsNone(daily_observed_at(samples[2:], self.window, now))

    def test_current_window_must_match_last_valid_observation(self):
        samples = [self.sample(11*3600), self.sample(12*3600, reset=self.reset+30)]
        self.assertIsNone(daily_observed_at(samples, self.window, self.now))
        self.assertEqual(daily_quota_text(samples, self.window, self.now), '—')
        samples[-1]['reset'] = self.reset+2
        self.assertEqual(daily_observed_at(samples, self.window, self.now), self.now.replace(hour=11).isoformat())

    def test_observation_start_survives_resets_without_changing_delta_sum(self):
        old_reset = self.midnight+10*3600
        samples = [self.sample(30, 81, old_reset), self.sample(10*3600-30, 88, old_reset),
                   self.sample(10*3600+30, 1), self.sample(14*3600, 4)]
        window = dict(remaining=96, resets_at=self.reset)
        self.assertEqual(daily_observed_at(samples, window, self.now), self.now.replace(hour=0, second=30).isoformat())
        self.assertEqual(daily_quota_text(samples, window, self.now), '10%')

    def test_missing_baseline_or_window_is_not_a_full_day(self):
        for samples,window in (([], self.window), ([self.sample(1, None)], self.window),
                               ([self.sample(1)], None), ([self.sample(1)], {'remaining':80})):
            with self.subTest(samples=samples, window=window):
                self.assertIsNone(daily_observed_at(samples, window, self.now))
                self.assertEqual(daily_quota_text(samples, window, self.now), '—')


if __name__ == '__main__':unittest.main()
