from datetime import datetime,timezone
import unittest
from unittest.mock import patch,Mock
from PySide6.QtWidgets import QApplication
from codex_taskbar.forecast import parse_forecast,ResetForecast


def sample(now=100000):
    iso=lambda t:datetime.fromtimestamp(t,timezone.utc).isoformat()
    return {'data':{'provider':'codex','freshness':{'state':'fresh'},'next_reset_estimate':{
        'chance_percent':3,'confidence':'low','generated_at':iso(now),'forecast_window_ends_at':iso(now+48*3600)}}}


class ForecastTests(unittest.TestCase):
    def test_null_invalid_stale_and_wrong_provider_are_not_probabilities(self):
        self.assertIsNone(parse_forecast({'probability_24h':None},100000))
        for value in (None,True,-1,101,float('nan')):
            data=sample();data['data']['next_reset_estimate']['chance_percent']=value
            self.assertIsNone(parse_forecast(data,100000))
        self.assertIsNone(parse_forecast(sample(),100000+21601))
        data=sample();data['data']['provider']='grok';self.assertIsNone(parse_forecast(data,100000))
        data=sample();data['data']['freshness']['state']='stale';self.assertIsNone(parse_forecast(data,100000))
        self.assertEqual(parse_forecast(sample(),100000)['chance'],3)
        data=sample();data['data']['next_reset_estimate']['chance_percent']=0
        self.assertEqual(parse_forecast(data,100000)['chance'],0)

    def test_requests_are_on_demand_bounded_and_throttled(self):
        core=QApplication.instance() or QApplication([]);controller=ResetForecast()
        with patch('codex_taskbar.forecast.time.monotonic',return_value=100),patch('codex_taskbar.forecast.threading.Thread') as thread:
            controller.request();controller.request();thread.assert_called_once();self.assertTrue(controller.pending)
            controller.finished(None);controller.request();thread.assert_called_once()
        response=Mock();response.read.return_value=b'{}'
        with patch('codex_taskbar.forecast.urllib.request.urlopen') as opened:
            opened.return_value.__enter__.return_value=response;controller.fetch()
            request=opened.call_args.args[0];self.assertEqual(opened.call_args.kwargs['timeout'],4)
            self.assertNotIn('Authorization',request.headers);self.assertNotIn('account',request.full_url)
            response.read.assert_called_once_with(512001)
        controller.deleteLater()
