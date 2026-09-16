from datetime import datetime,timedelta
import unittest
from unittest.mock import patch,Mock
from PySide6.QtCore import QRect
from codex_taskbar import app
from tests import test_interactions as fixtures


class SharedWidthContentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixtures.InteractionTests.setUpClass()

    def setUp(self):
        self.case=fixtures.InteractionTests();self.case.setUp();self.bar=self.case.bar;self.data=self.case.data
        self.bar.settings.update(placement='taskbar',language='zh-CN',show_session=False)
        self.bar.motion_enabled=False;self.bar.setGeometry(30,700,200,30);self.bar.position=self.bar.geometry().getRect()
        self.bar.content_limit=220
        self.visible=patch.object(self.bar,'isVisible',return_value=True);self.visible.start()
        self.screen=Mock();self.screen.geometry.return_value=QRect(0,0,1200,900);self.screen.availableGeometry.return_value=QRect(0,0,1200,850)
        self.screen_patch=patch.object(self.bar,'screen',return_value=self.screen);self.screen_patch.start()
        now=datetime.now().astimezone();start=now.replace(hour=0,minute=0,second=0,microsecond=0)-timedelta(days=4)
        self.data['quota'][0].update(starts_at=start.timestamp(),resets_at=(start+timedelta(days=7)).timestamp())
        self.data.update(history_usd={(start+timedelta(days=i)).date().isoformat():value for i,value in enumerate((180.45,219.88,515.01,982.5,211.01))},usage_at=now.isoformat())
        self.bar.set_chart_unit('USD')

    def tearDown(self):
        self.case.tearDown();self.case.doCleanups();self.screen_patch.stop();self.visible.stop()

    def test_narrow_cycle_keeps_units_clear_and_chart_labels_do_not_collide(self):
        self.bar.toggle_popup('usage',activate=False);panel=self.bar.popup
        self.assertEqual(self.bar.width(),panel.width());self.assertEqual(panel.width(),220)
        for language in app.LANGUAGES:
            self.bar.settings['language']=language;panel.refresh(self.data)
            with patch('codex_taskbar.app.text',wraps=app.text) as texts,patch('codex_taskbar.app.paint_usage_column',wraps=app.paint_usage_column) as columns:panel.grab()
            for call in texts.call_args_list:
                _,x,y,label,font,*_=call.args
                if y==21:self.assertLessEqual(x+app.QFontMetricsF(font).horizontalAdvance(label),min(r.left() for r in panel.unit_rects().values())-6)
            for field in (6,7):
                end=12
                for call in columns.call_args_list:
                    label=call.args[field]
                    if not label:continue
                    x=call.kwargs.get('amount_x' if field==6 else 'date_x',call.args[1]);width=app.QFontMetricsF(app.face(7)).horizontalAdvance(label)
                    self.assertGreaterEqual(x-width/2,end+6);self.assertLessEqual(x+width/2,panel.width()-18);end=x+width/2
            for button in panel.unit_buttons.values():self.assertTrue(panel.rect().contains(button.geometry()))

    def test_reset_scrollbar_is_sized_from_actual_common_viewport(self):
        now=datetime.now().timestamp()
        self.data['reset_events']=[dict(id=str(i),at=now-(3-i)*86400,period_start=now-(4-i)*86400,kind='official',tokens=100000000,usd=10+i) for i in range(4)]
        self.bar.toggle_popup('resets',activate=False);panel=self.bar.popup
        self.assertEqual(panel.width(),220);self.assertGreater(panel.requested_size[0],panel.width())
        self.assertEqual(panel.history_scroll.maximum(),panel.history_width-(panel.width()-36))
        self.assertFalse(panel.history_scroll.isHidden())
        self.assertGreaterEqual(panel.credits_top,panel.history_scroll.geometry().bottom()+14)
        self.assertLessEqual(panel.history_choice.geometry().right(),panel.width()-72)
        panel.history_scroll.setValue(0);self.assertEqual(panel.history_scroll.value(),0)

    def test_task_columns_fit_after_host_caps_requested_width(self):
        self.bar.toggle_popup('running',activate=False);panel=self.bar.popup
        self.assertEqual(panel.width(),220);self.assertEqual(self.bar.width(),220)
        self.assertLess(33+panel.project_width,panel.TITLE_X)
        self.assertLess(panel.TITLE_X,panel.info_divider)
        self.assertGreater(panel.TITLE_WIDTH,0)
        self.assertLessEqual(panel.TITLE_X+panel.TITLE_WIDTH+12,panel.info_divider)
