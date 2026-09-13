from datetime import datetime
import unittest
from unittest.mock import Mock,patch
from codex_taskbar import app
from tests import test_interactions as fixtures


class ResetChartTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixtures.InteractionTests.setUpClass()
    def setUp(self):
        fixtures.InteractionTests.setUp(self)
        now=datetime.now().timestamp()
        self.data['reset_events']=[{'kind':'manual','at':now+i,'tokens':value,'before':{'10080':{'remaining':remaining}}}
                                   for i,(value,remaining) in enumerate(((2000000000,80),(1000000000,5),(0,100),(None,0)))]
        self.panel=app.ResetPopup(self.bar);self.panel.refresh(self.data)
    def tearDown(self):
        self.panel.close();self.panel.deleteLater();fixtures.InteractionTests.tearDown(self)

    def test_bars_compare_tokens_not_quota_and_keep_the_scale_while_scrolling(self):
        panel=self.panel;rows=self.data['reset_events']
        first=panel.history_bar_rect(rows[0],89);second=panel.history_bar_rect(rows[1],133)
        self.assertEqual(first.width(),second.width()*2)
        self.assertEqual(panel.history_percent(rows[0]),'20%');self.assertEqual(panel.history_percent(rows[1]),'95%')
        self.assertEqual(first.left(),second.left());self.assertLess(first.right(),panel.token_left)
        panel.scroll=44;self.assertEqual(panel.history_bar_rect(rows[1],89).width(),second.width())
        rows[1].pop('before');panel.refresh(self.data)
        self.assertEqual(panel.history_percent(rows[1]),'—');self.assertEqual(panel.history_bar_rect(rows[1],89).width(),second.width())

    def test_zero_missing_and_invalid_tokens_are_not_filled_bars(self):
        panel=self.panel
        for value in (None,-1,True,float('nan'),float('inf')):
            row={'tokens':value};self.assertEqual(panel.history_parts(row),('—',''));self.assertEqual(panel.history_bar_rect(row,89).width(),0)
        self.assertEqual(panel.history_parts({'tokens':0}),('0','×100M'))
        self.assertEqual(panel.history_bar_rect({'tokens':0},89).width(),0)
        self.data['reset_events']=[dict(self.data['reset_events'][0],tokens=0)]
        panel.refresh(self.data);self.assertEqual(panel.history_max,0);self.assertEqual(panel.history_bar_rect(self.data['reset_events'][0],89).width(),0)

    def test_constrained_height_scrolls_content_above_fixed_button_in_both_modes(self):
        panel=self.panel;screen=Mock();screen.availableGeometry.return_value=app.QRect(0,0,500,280)
        self.data['reset_events']*=4
        for placement in ('taskbar','floating'):
            self.bar.settings['placement']=placement;self.bar.position=(0,260,350,30);self.bar.setGeometry(*self.bar.position)
            with patch.object(self.bar,'screen',return_value=screen),patch.object(self.bar,'floating_screen',return_value=screen):panel.refresh(self.data)
            self.assertTrue(panel.scroll_body);self.assertGreater(panel.scroll_limit(),0)
            self.assertTrue(screen.availableGeometry().contains(panel.geometry()))
            button=panel.button.geometry();self.assertEqual(button.bottom(),panel.height()-17)
            panel.scroll=0;before=panel.grab().toImage()
            panel.scroll=panel.scroll_limit();after=panel.grab().toImage()
            header_height=round(48*panel.devicePixelRatioF())
            self.assertEqual(before.copy(0,0,before.width(),header_height),after.copy(0,0,after.width(),header_height))
            self.assertEqual(panel.button.geometry(),button)
            last_credit_y=panel.forecast_height+panel.credits_top+26*max(1,len(panel.credits))-panel.scroll
            self.assertLess(last_credit_y+8,button.top())
        self.provider.request_reset.assert_not_called()

    def test_history_remains_chronological_and_percentages_have_a_separate_heading(self):
        for language in app.LANGUAGES:
            self.bar.settings['language']=language;self.panel.refresh(self.data)
            with patch('codex_taskbar.app.text',wraps=app.text) as draw:self.panel.grab()
            labels=[call.args[3] for call in draw.call_args_list]
            self.assertEqual(labels.count(self.bar.label('Quota used')),1)
            dates=[datetime.fromtimestamp(row['at']).strftime('%m.%d %H:%M') for row in self.data['reset_events']]
            self.assertEqual([call.args[3] for call in draw.call_args_list if call.args[1]==18 and call.args[2] in {89+i*self.panel.ROW_HEIGHT for i in range(4)}],dates)
            self.assertIn(self.bar.label('Quota used')+' 20%',self.panel.accessibleDescription())

    def test_each_period_is_one_aligned_row_with_separate_columns(self):
        for language in app.LANGUAGES:
            self.bar.settings['language']=language;panel=self.panel;panel.refresh(self.data)
            with patch('codex_taskbar.app.text',wraps=app.text) as draw:panel.grab()
            for index,row in enumerate(self.data['reset_events']):
                y=89+index*panel.ROW_HEIGHT;bar=panel.history_bar_rect(row,y)
                self.assertEqual(bar.center().y(),y)
                numbers=[call for call in draw.call_args_list if call.args[3]==panel.history_parts(row)[0] and call.args[2]==y and call.args[1]<panel.number_right]
                self.assertEqual(len(numbers),1)
                self.assertLessEqual(bar.right()+8,panel.token_left)
                self.assertLess(panel.token_right,panel.percent_right)
                self.assertLess(panel.percent_right,panel.history_divider)
            self.assertLessEqual(panel.ROW_HEIGHT,28)
