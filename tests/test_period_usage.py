from datetime import datetime,timedelta
from pathlib import Path
import tempfile
import unittest

from codex_taskbar.usage import UsageCursor
from tests.test_usage import record


class PeriodUsageTests(unittest.TestCase):
    def test_history_ranges_keep_daily_and_current_cycle_boundaries(self):
        now=datetime.now().astimezone().replace(hour=0,minute=0,second=0,microsecond=0)
        first=now-timedelta(days=2);boundary=now-timedelta(days=1)
        periods=(('old',first.timestamp(),boundary.timestamp()),('recent',boundary.timestamp(),now.timestamp()))
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'usage.jsonl'
            path.write_bytes(record('token_count',first-timedelta(seconds=1),100)+record('token_count',first,150)+
                             record('token_count',boundary,190)+record('token_count',now,220))
            cursor=UsageCursor(path,since=now,periods=periods);cursor.update()
            self.assertEqual(cursor.period_totals,{'old':50,'recent':40})
            self.assertEqual(cursor.daily['total_tokens'],30)
            self.assertEqual(cursor.by_day,{now.date().isoformat():30})
            cursor.update();self.assertEqual(cursor.period_totals,{'old':50,'recent':40})

    def test_forked_inheritance_does_not_count_toward_history(self):
        now=datetime.now().astimezone();start=now-timedelta(hours=1)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'fork.jsonl'
            path.write_bytes(record('token_count',start,500)+record('token_count',now,530))
            periods=(('phase',start.timestamp(),(now+timedelta(seconds=1)).timestamp()),)
            cursor=UsageCursor(path,created_after=now.timestamp(),periods=periods);cursor.update()
            self.assertEqual(cursor.period_totals,{'phase':30})
