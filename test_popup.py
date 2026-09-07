import unittest
from app import QApplication,QWidget,TaskPopup,TaskListPopup,StatusBar
from unittest.mock import patch


class PopupInitialFrameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application=QApplication.instance() or QApplication([])

    def test_both_panels_are_transparent_before_first_animation_tick(self):
        owner=QWidget();owner.popup=None
        for kind in (TaskPopup,TaskListPopup):
            with self.subTest(panel=kind.__name__):
                panel=kind(owner)
                self.assertEqual(panel.windowOpacity(),0.)
                self.assertEqual(panel.reveal,0.)
                self.assertIsNone(panel.reveal_target)
                self.assertFalse(panel.isVisible())
                panel.close();panel.deleteLater()
        owner.close();owner.deleteLater()

    def test_task_panel_adapts_to_names_and_caps_at_bar_width(self):
        owner=QWidget();owner.setGeometry(20,600,540,30);owner.popup=None
        panel=TaskListPopup(owner)
        data={'tasks':[{'id':'a','title':'Task','project':'Project','running':True}],
              'recent_tasks':[{'id':'b','title':'Earlier','project':'Project','running':False}]}
        panel.refresh(data)
        self.assertLess(panel.width(),owner.width())
        self.assertEqual([label for label,y in panel.sections],['Running','Recent'])
        data['tasks'][0]['title']='A very long task title '*30
        panel.refresh(data)
        self.assertEqual(panel.width(),owner.width())
        self.assertEqual(panel.x(),owner.x())
        panel.close();panel.deleteLater();owner.close();owner.deleteLater()

    def test_task_metrics_form_a_compact_group_separate_from_title(self):
        owner=QWidget();owner.setGeometry(20,600,540,30);owner.popup=None
        panel=TaskListPopup(owner)
        panel.refresh({'tasks':[{'id':'a','title':'Task','project':'Project','running':True,
                                'daily_seconds':17940,'tokens':142700000}]})
        from app import QFontMetricsF,face
        metrics=QFontMetricsF(face(8))
        self.assertAlmostEqual(panel.info_divider-(panel.TITLE_X+panel.TITLE_WIDTH),12)
        self.assertAlmostEqual(panel.token_right-metrics.horizontalAdvance('142.7M')-panel.time_right,12)
        self.assertGreaterEqual(panel.time_right-metrics.horizontalAdvance('4h 59m')-panel.info_divider,12)
        panel.close();panel.deleteLater();owner.close();owner.deleteLater()

    def test_task_hit_area_follows_visible_content(self):
        data={'tasks':[]}
        provider=type('Provider',(),{'get':lambda self:data,'stop':lambda self:None})()
        with patch('app.windows.ClickHook'),patch('app.windows.placement',return_value=None):
            bar=StatusBar(provider)
        bar.timer.stop();bar.animation.stop();bar.resize(810,30)
        task={'id':'a','project':'Project','title':'Short'}
        bar.task=task;bar.data={'tasks':[task]}
        bar.grab()
        self.assertLess(bar.task_area.right(),bar.width()-100)
        self.assertLess(bar.task_rect.width(),100)
        with patch.object(bar,'isVisible',return_value=True),patch('app.windows.rect',return_value=(0,0,810,30)), \
             patch('app.windows.user32.GetDpiForWindow',return_value=96),patch('app.QTimer.singleShot') as dispatch:
            self.assertFalse(bar.desktop_click(800,15))
            dispatch.assert_not_called()
            self.assertTrue(bar.desktop_click(round(bar.task_area.center().x()),15))
            dispatch.assert_called_once()
        task['title']='A long task title '*40
        bar.grab()
        self.assertEqual(bar.task_area.right(),bar.width())
        bar.task=None;bar.data={'tasks':[]};bar.grab()
        self.assertLess(bar.task_area.width(),100)
        bar.close();bar.deleteLater()


    def test_native_strip_is_layered_even_before_it_is_shown(self):
        import app
        provider=type('Provider',(),{'get':lambda self:{},'stop':lambda self:None})()
        with patch('app.windows.ClickHook'),patch('app.windows.placement',return_value=None):
            bar=StatusBar(provider)
        try:
            self.assertTrue(app.windows.user32.GetWindowLongPtrW(int(bar.winId()),-20)&0x80000)
        finally:bar.close();bar.deleteLater()
