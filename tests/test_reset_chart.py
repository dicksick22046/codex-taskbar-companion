from datetime import datetime
import unittest
from unittest.mock import Mock,patch
from PySide6.QtCore import QPoint,QPointF,Qt
from PySide6.QtGui import QWheelEvent,QKeyEvent,QMouseEvent
from PySide6.QtCore import QEvent
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
        first=panel.history_bar_rect(rows[0],0);second=panel.history_bar_rect(rows[1],1)
        self.assertEqual(first.height(),second.height()*2)
        self.assertEqual(panel.history_percent(rows[0]),'20%');self.assertEqual(panel.history_percent(rows[1]),'95%')
        self.assertEqual(first.bottom(),second.bottom());self.assertLess(first.left(),second.left())
        panel.history_scroll.setValue(44);self.assertEqual(panel.history_bar_rect(rows[1],1).height(),second.height())
        rows[1].pop('before');panel.refresh(self.data)
        self.assertEqual(panel.history_percent(rows[1]),'—');self.assertEqual(panel.history_bar_rect(rows[1],1).height(),second.height())

    def test_zero_missing_and_invalid_tokens_are_not_filled_bars(self):
        panel=self.panel
        for value in (None,-1,True,float('nan'),float('inf')):
            row={'tokens':value};self.assertEqual(panel.history_parts(row),('—',''));self.assertEqual(panel.history_bar_rect(row,0).height(),0)
        self.assertEqual(panel.history_parts({'tokens':0}),('0','×100M'))
        self.assertEqual(panel.history_bar_rect({'tokens':0},0).height(),0)
        self.data['reset_events']=[dict(self.data['reset_events'][0],tokens=0)]
        panel.refresh(self.data);self.assertEqual(panel.history_max,0);self.assertEqual(panel.history_bar_rect(self.data['reset_events'][0],0).height(),0)

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
            panel.scroll=panel.scroll_limit();panel.layout_history_scroll();after=panel.grab().toImage()
            header_height=round(48*panel.devicePixelRatioF())
            self.assertEqual(before.copy(0,0,before.width(),header_height),after.copy(0,0,after.width(),header_height))
            self.assertEqual(panel.button.geometry(),button)
            last_credit_y=panel.forecast_height+panel.credits_top+26*max(1,len(panel.credits))-panel.scroll
            self.assertLess(last_credit_y+8,button.top())
        self.provider.request_reset.assert_not_called()

    def test_native_horizontal_thumb_can_be_dragged_without_moving_the_mouse(self):
        from PySide6.QtWidgets import QStyleOptionSlider,QStyle
        self.data['reset_events']*=4;self.panel.refresh(self.data);slider=self.panel.history_scroll
        option=QStyleOptionSlider();slider.initStyleOption(option)
        handle=slider.style().subControlRect(QStyle.ComplexControl.CC_ScrollBar,option,QStyle.SubControl.SC_ScrollBarSlider,slider)
        start=QPointF(handle.center());end=QPointF(slider.width()-30,start.y())
        for kind,point,button,held in ((QEvent.Type.MouseButtonPress,start,Qt.MouseButton.LeftButton,Qt.MouseButton.LeftButton),(QEvent.Type.MouseMove,end,Qt.MouseButton.NoButton,Qt.MouseButton.LeftButton),(QEvent.Type.MouseButtonRelease,end,Qt.MouseButton.LeftButton,Qt.MouseButton.NoButton)):
            event=QMouseEvent(kind,point,QPointF(slider.mapToGlobal(point.toPoint())),button,held,Qt.KeyboardModifier.NoModifier)
            app.QApplication.sendEvent(slider,event)
        self.assertGreater(slider.value(),0);self.assertFalse(slider.isSliderDown())

    def test_history_remains_chronological_and_quota_is_described_separately(self):
        for language in app.LANGUAGES:
            self.bar.settings['language']=language;self.panel.refresh(self.data)
            with patch('codex_taskbar.app.text',wraps=app.text) as draw:self.panel.grab()
            labels=[call.args[3] for call in draw.call_args_list]
            dates=[datetime.fromtimestamp(row['at']).strftime('%m.%d') for row in self.data['reset_events']]
            shown=[call.args[3] for call in draw.call_args_list if call.args[2]==190]
            self.assertEqual(shown,dates[:len(shown)])
            self.assertIn(self.bar.label('Quota used')+' 20%',self.panel.accessibleDescription())

    def test_horizontal_scroll_reaches_latest_preserves_offset_and_keeps_height(self):
        for language in app.LANGUAGES:
            self.bar.settings['language']=language;panel=self.panel;panel.refresh(self.data)
            height=panel.height();self.data['reset_events']*=2;panel.refresh(self.data)
            self.assertEqual(panel.height(),height);self.assertGreater(panel.history_scroll.maximum(),0)
            panel.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress,Qt.Key.Key_End,Qt.KeyboardModifier.NoModifier))
            self.assertEqual(panel.history_scroll.value(),panel.history_scroll.maximum())
            point=QPointF(panel.width()-19,190+panel.forecast_height)
            self.assertEqual(panel.history_at(point),len(panel.rows)-1)
            offset=panel.history_scroll.value();panel.refresh(self.data);self.assertEqual(panel.history_scroll.value(),offset)
            panel.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress,Qt.Key.Key_Home,Qt.KeyboardModifier.NoModifier));self.assertEqual(panel.history_scroll.value(),0)
        self.data['reset_events']=self.data['reset_events'][:1];panel.refresh(self.data)
        self.assertEqual(panel.history_scroll.maximum(),0);self.assertTrue(panel.history_scroll.isHidden())

    def test_wheel_axes_and_hover_time_follow_the_visible_period(self):
        panel=self.panel;self.data['reset_events']*=4;panel.refresh(self.data)
        point=QPointF(50,150+panel.forecast_height)
        def wheel(pixel=QPoint(),angle=QPoint(),shift=False):
            event=QWheelEvent(point,point,pixel,angle,Qt.MouseButton.NoButton,Qt.KeyboardModifier.ShiftModifier if shift else Qt.KeyboardModifier.NoModifier,Qt.ScrollPhase.ScrollUpdate,False)
            panel.wheelEvent(event)
        wheel(pixel=QPoint(-37,0));self.assertEqual(panel.history_scroll.value(),37);self.assertEqual(panel.scroll,0)
        wheel(angle=QPoint(0,-120));self.assertEqual(panel.history_scroll.value(),37+panel.column_width)
        panel.history_point=point;panel.update_history_tooltip();index=panel.history_at(point)
        self.assertIn(datetime.fromtimestamp(panel.rows[index]['at']).strftime('%Y.%m.%d %H:%M'),panel.toolTip())
        with patch.object(panel,'scroll_limit',return_value=200):
            old=panel.history_scroll.value();wheel(angle=QPoint(0,-120));self.assertEqual(panel.history_scroll.value(),old);self.assertGreater(panel.scroll,0)
            wheel(angle=QPoint(0,-120),shift=True);self.assertGreater(panel.history_scroll.value(),old)
        self.provider.request_reset.assert_not_called()
