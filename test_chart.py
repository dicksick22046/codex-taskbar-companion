from datetime import date, timedelta
import unittest
from app import chart_values, chart_number, chart_total, marquee_offset


class ChartTests(unittest.TestCase):
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
