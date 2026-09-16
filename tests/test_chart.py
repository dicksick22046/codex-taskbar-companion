from datetime import date, datetime, timedelta
import unittest
from codex_taskbar.app import chart_values, chart_number, chart_total, marquee_offset, calendar_day_spans, fit_chart_labels


class ChartTests(unittest.TestCase):
    def test_partial_day_labels_keep_all_amounts_without_overlapping(self):
        centers=[39.9,68.5,110,151,192];widths=[31,31,31,25,31]
        placed=fit_chart_labels(centers,widths,18,337)
        self.assertTrue(all(center is not None for center in placed))
        right=12
        for center,width in zip(placed,widths):
            self.assertGreaterEqual(center-width/2,right+6)
            self.assertLessEqual(center+width/2,337);right=center+width/2
        self.assertEqual(centers,[39.9,68.5,110,151,192])
        self.assertEqual(fit_chart_labels([20],[100],18,40),[None])

    def test_non_midnight_week_has_eight_dates_but_exactly_seven_days_of_width(self):
        start=datetime(2026,9,16,14,53);end=start+timedelta(days=7)
        spans=calendar_day_spans(start,end)
        self.assertEqual(len(spans),8)
        seconds=[(b-a)*(end.timestamp()-start.timestamp()) for _,a,b in spans]
        self.assertAlmostEqual(seconds[0],9*3600+7*60)
        self.assertAlmostEqual(seconds[-1],14*3600+53*60)
        for duration in seconds[1:-1]:self.assertAlmostEqual(duration,86400)
        self.assertAlmostEqual(sum(seconds),168*3600)
        self.assertEqual(spans[0][1],0);self.assertEqual(spans[-1][2],1)
        for previous,current in zip(spans,spans[1:]):self.assertEqual(previous[2],current[1])

    def test_midnight_end_excludes_empty_eighth_date_and_short_windows_stay_exact(self):
        start=datetime(2026,9,16)
        spans=calendar_day_spans(start,start+timedelta(days=7))
        self.assertEqual(len(spans),7);self.assertEqual(spans[-1][0],date(2026,9,22))
        self.assertEqual(calendar_day_spans(start,start+timedelta(hours=5)),[(start.date(),0.,1.)])
        self.assertEqual(calendar_day_spans(start,start),[])
        self.assertEqual(calendar_day_spans(start,start-timedelta(seconds=1)),[])

    def test_tiny_partial_day_is_not_inflated_into_a_full_day(self):
        start=datetime(2026,9,16,23,59,59);end=start+timedelta(days=7)
        spans=calendar_day_spans(start,end)
        self.assertAlmostEqual(spans[0][2]-spans[0][1],1/(168*3600))
        self.assertAlmostEqual((spans[0][2]-spans[0][1])+(spans[-1][2]-spans[-1][1]),1/7)

    def test_long_title_scrolls_only_when_there_is_overflow(self):
        self.assertEqual(marquee_offset(5,0),0)
        self.assertEqual(marquee_offset(.4,64),0)
        self.assertAlmostEqual(marquee_offset(1.8,64),32)
        self.assertAlmostEqual(marquee_offset(3,64),64)
        self.assertAlmostEqual(marquee_offset(4.6,64),32)

    def test_units_use_millions_and_hundred_millions(self):
        self.assertEqual(chart_number(572_200_000,'M'),'572.2')
        self.assertEqual(chart_number(572_200_000,'100M'),'5.72')
        self.assertEqual(chart_number(100_000_000,'100M'),'1')

    def test_unknown_and_small_values_do_not_become_false_zero(self):
        self.assertEqual(chart_number(None,'M'),'—')
        self.assertEqual(chart_number(0,'100M'),'0')
        self.assertEqual(chart_number(1000,'100M'),'<0.01')

    def test_period_total_uses_displayed_data_and_same_unit(self):
        values,_=chart_values(self.days,{d.isoformat():n for d,n in zip(self.days,[100_000_000,200_000_000,None,0,0,0,999_000_000])},self.today)
        self.assertEqual(chart_total(values),300_000_000)
        self.assertEqual(chart_number(chart_total(values),'M'),'300')
        self.assertEqual(chart_number(chart_total(values),'100M'),'3')
        self.assertIsNone(chart_total([None,None]))
        self.assertEqual(chart_total([None,0]),0)

    def setUp(self):
        self.days=[date(2026,9,1)+timedelta(days=i) for i in range(7)]
        self.today=self.days[5]

    def test_only_finished_valid_days_participate_in_extremes(self):
        history={d.isoformat():v for d,v in zip(self.days,[10,30,20,None,15,100,999]) if v is not None}
        values,extremes=chart_values(self.days,history,self.today)
        self.assertEqual(extremes,{self.days[0],self.days[1]})
        self.assertIsNone(values[3])
        self.assertIsNone(values[6])
        self.assertEqual(values[5],100)

    def test_recorded_zero_is_valid_and_distinct_from_missing(self):
        values,extremes=chart_values(self.days,{self.days[0].isoformat():0,self.days[1].isoformat():20},self.today)
        self.assertEqual(values[0],0)
        self.assertIsNone(values[2])
        self.assertEqual(extremes,{self.days[0],self.days[1]})

    def test_equal_values_do_not_highlight_every_bar(self):
        history={d.isoformat():10 for d in self.days}
        self.assertEqual(chart_values(self.days,history,self.today)[1],set())


if __name__=='__main__':unittest.main()
