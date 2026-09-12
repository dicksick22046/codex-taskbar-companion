import unittest
from codex_taskbar.app import QApplication,QWidget,TaskPopup,TaskListPopup,StatusBar,SessionPopup,ResetPopup,DISPLAY_DEFAULTS
from unittest.mock import patch
from codex_taskbar.i18n import translate
from PySide6.QtCore import QEvent,QPointF,Qt
from PySide6.QtGui import QMouseEvent
from tests import test_interactions as fixtures


class Owner(QWidget):
    floating=False
    language='en'

    def label(self,key,**values):return translate(self.language,key,**values)


class PopupInitialFrameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application=QApplication.instance() or QApplication([])

    def test_both_panels_are_transparent_before_first_animation_tick(self):
        owner=Owner();owner.popup=None;owner.chart_unit="M"
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
        owner=Owner();owner.setGeometry(20,600,540,30);owner.popup=None;owner.chart_unit="M"
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
        owner=Owner();owner.setGeometry(20,600,540,30);owner.popup=None;owner.chart_unit="M"
        panel=TaskListPopup(owner)
        panel.refresh({'tasks':[{'id':'a','title':'Task','project':'Project','running':True,
                                'daily_seconds':17940,'tokens':142700000}]})
        from codex_taskbar.app import QFontMetricsF,face
        metrics=QFontMetricsF(face(8))
        self.assertAlmostEqual(panel.info_divider-(panel.TITLE_X+panel.TITLE_WIDTH),12)
        self.assertEqual(panel.values['a'],'142.7')
        self.assertAlmostEqual(panel.value_right-metrics.horizontalAdvance('142.7')-panel.info_divider,12)
        panel.close();panel.deleteLater();owner.close();owner.deleteLater()

    def test_both_panels_leave_space_above_taskbar_not_inside_it(self):
        owner=Owner();owner.setGeometry(20,610,540,30);owner.popup=None;owner.chart_unit="M"
        owner.settings=DISPLAY_DEFAULTS;owner.confirm_reset=lambda:None
        with patch('codex_taskbar.app.windows.user32.FindWindowW',return_value=1), \
             patch('codex_taskbar.app.windows.rect',return_value=(0,900,1600,972)), \
             patch.object(owner,'devicePixelRatioF',return_value=1.5):
            for kind in (TaskPopup,TaskListPopup,SessionPopup,ResetPopup):
                panel=kind(owner)
                panel.refresh({'tasks':[]})
                self.assertEqual(panel.y()+panel.height(),600-8)
                panel.close();panel.deleteLater()
        owner.close();owner.deleteLater()

    def test_task_hit_area_follows_visible_content(self):
        fixtures.InteractionTests.setUp(self);self.addCleanup(fixtures.InteractionTests.tearDown,self)
        bar=self.bar;strip=self.strip
        task={'id':'a','project':'Project','title':'Short','running':True}
        bar.data={'tasks':[task]};strip.refresh(bar.data);strip.task_tween.setCurrentTime(strip.task_tween.duration());strip.grab()
        self.assertLess(strip.task_area.right(),strip.width()-100)
        self.assertLess(strip.task_rect.width(),100)
        def send(kind,point):
            held=Qt.MouseButton.NoButton if kind==QEvent.Type.MouseButtonRelease else Qt.MouseButton.LeftButton
            self.application.sendEvent(strip,QMouseEvent(kind,point,QPointF(strip.mapToGlobal(point.toPoint())),Qt.MouseButton.LeftButton,held,Qt.KeyboardModifier.NoModifier))
        with patch.object(bar,'open_task') as opened:
            blank=QPointF(strip.width()-10,15)
            send(QEvent.Type.MouseButtonPress,blank);send(QEvent.Type.MouseButtonRelease,blank);opened.assert_not_called()
            point=strip.task_area.center();send(QEvent.Type.MouseButtonPress,point);opened.assert_not_called()
            send(QEvent.Type.MouseButtonRelease,point);opened.assert_called_once_with(task)
        task['title']='A long task title '*40
        strip.refresh(bar.data);strip.grab()
        self.assertLessEqual(strip.task_area.right(),strip.width()-5)
        self.assertEqual(strip.task_area.right()-strip.task_rect.right(),6)
        bar.data={'tasks':[]};strip.refresh(bar.data);strip.grab();bar.grab()
        self.assertTrue(strip.task_area.isEmpty())
        self.assertEqual(sum(mode=='daily' for mode,rect,target in bar.hit_regions),1)


    def test_native_strip_is_layered_even_before_it_is_shown(self):
        from codex_taskbar import app
        provider=type('Provider',(),{'get':lambda self:{},'stop':lambda self:None})()
        with patch('codex_taskbar.app.read_settings',return_value={**DISPLAY_DEFAULTS,'chart_unit':'M'}),patch('codex_taskbar.app.RELEASE_REPOSITORY',''), \
             patch('codex_taskbar.app.windows.ClickHook'),patch('codex_taskbar.app.windows.placement',return_value=None),patch('codex_taskbar.app.QSystemTrayIcon'), \
             patch('codex_taskbar.task_strip.TaskStrip.ensure_visible',new=lambda self:False):
            bar=StatusBar(provider)
        try:
            self.assertTrue(app.windows.user32.GetWindowLongPtrW(int(bar.winId()),-20)&0x80000)
        finally:bar.close();bar.deleteLater()
