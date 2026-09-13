from datetime import datetime
import unittest
from unittest.mock import Mock,patch
from PySide6.QtCore import QPoint,QPointF,Qt
from PySide6.QtGui import QWheelEvent,QKeyEvent,QMouseEvent,QHideEvent
from PySide6.QtCore import QEvent
from codex_taskbar import app
from tests import test_interactions as fixtures


class ResetChartTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixtures.InteractionTests.setUpClass()
    def setUp(self):
        fixtures.InteractionTests.setUp(self)
        now=datetime.now().timestamp()
        self.data['reset_events']=[{'id':str(i),'kind':'manual','at':now+i,'tokens':value,'before':{'10080':{'remaining':remaining}}}
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
        self.data['reset_events']*=4;self.panel.refresh(self.data);slider=self.panel.history_scroll;slider.setValue(0)
        option=QStyleOptionSlider();slider.initStyleOption(option)
        handle=slider.style().subControlRect(QStyle.ComplexControl.CC_ScrollBar,option,QStyle.SubControl.SC_ScrollBarSlider,slider)
        start=QPointF(handle.center());end=QPointF(slider.width()-30,start.y())
        for kind,point,button,held in ((QEvent.Type.MouseButtonPress,start,Qt.MouseButton.LeftButton,Qt.MouseButton.LeftButton),(QEvent.Type.MouseMove,end,Qt.MouseButton.NoButton,Qt.MouseButton.LeftButton),(QEvent.Type.MouseButtonRelease,end,Qt.MouseButton.LeftButton,Qt.MouseButton.NoButton)):
            event=QMouseEvent(kind,point,QPointF(slider.mapToGlobal(point.toPoint())),button,held,Qt.KeyboardModifier.NoModifier)
            app.QApplication.sendEvent(slider,event)
        self.assertGreater(slider.value(),0);self.assertFalse(slider.isSliderDown())

    def test_history_remains_chronological_and_quota_is_described_separately(self):
        start=self.data['reset_events'][0]['at']-4*86400
        for index,row in enumerate(self.data['reset_events']):row['at']=start+index*86400
        for language in app.LANGUAGES:
            self.bar.settings['language']=language;self.panel.refresh(self.data)
            with patch('codex_taskbar.app.paint_usage_column',wraps=app.paint_usage_column) as draw:self.panel.grab()
            dates=[f'{datetime.fromtimestamp(row["at"]).month}/{datetime.fromtimestamp(row["at"]).day}' for row in self.data['reset_events']]
            shown=[call.args[7] for call in draw.call_args_list]
            self.assertTrue(shown)
            order=[dates.index(value) for value in shown];self.assertEqual(order,sorted(order))
            self.assertIn(self.bar.label('Quota used')+' 20%',self.panel.accessibleDescription())

    def test_horizontal_scroll_reaches_latest_preserves_offset_and_keeps_height(self):
        for language in app.LANGUAGES:
            self.bar.settings['language']=language;panel=self.panel;panel.refresh(self.data)
            height=panel.height();self.data['reset_events']*=2;panel.refresh(self.data)
            self.data['reset_events']=[dict(row,id=str(index)) for index,row in enumerate(self.data['reset_events'])];panel.refresh(self.data)
            self.assertLessEqual(panel.height()-height,14);self.assertGreater(panel.history_scroll.maximum(),0)
            panel.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress,Qt.Key.Key_End,Qt.KeyboardModifier.NoModifier))
            self.assertEqual(panel.history_scroll.value(),panel.history_scroll.maximum())
            self.assertEqual(panel.selected_history_index(),len(panel.rows)-1)
            point=QPointF(panel.width()-19,190+panel.forecast_height)
            self.assertEqual(panel.history_at(point),len(panel.rows)-1)
            offset=panel.history_scroll.value();panel.refresh(self.data);self.assertEqual(panel.history_scroll.value(),offset)
            panel.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress,Qt.Key.Key_Home,Qt.KeyboardModifier.NoModifier));self.assertEqual(panel.history_scroll.value(),0)
        self.data['reset_events']=self.data['reset_events'][:1];panel.refresh(self.data)
        self.assertEqual(panel.history_scroll.maximum(),0);self.assertTrue(panel.history_scroll.isHidden())

    def test_wheel_axes_scroll_without_changing_selection(self):
        panel=self.panel;self.data['reset_events']*=4;panel.refresh(self.data)
        panel.history_scroll.setValue(0);selected=panel.history_selected
        point=QPointF(50,150+panel.forecast_height)
        def wheel(pixel=QPoint(),angle=QPoint(),shift=False):
            event=QWheelEvent(point,point,pixel,angle,Qt.MouseButton.NoButton,Qt.KeyboardModifier.ShiftModifier if shift else Qt.KeyboardModifier.NoModifier,Qt.ScrollPhase.ScrollUpdate,False)
            panel.wheelEvent(event)
        wheel(pixel=QPoint(-37,0));self.assertEqual(panel.history_scroll.value(),37);self.assertEqual(panel.scroll,0)
        wheel(angle=QPoint(0,-120));self.assertEqual(panel.history_scroll.value(),37+panel.column_width)
        self.assertEqual(panel.history_selected,selected)
        with patch.object(panel,'scroll_limit',return_value=200):
            old=panel.history_scroll.value();wheel(angle=QPoint(0,-120));self.assertEqual(panel.history_scroll.value(),old);self.assertGreater(panel.scroll,0)
            wheel(angle=QPoint(0,-120),shift=True);self.assertGreater(panel.history_scroll.value(),old)
        self.provider.request_reset.assert_not_called()

    def chart_mouse(self,kind,point):
        held=Qt.MouseButton.LeftButton if kind!=QEvent.Type.MouseButtonRelease else Qt.MouseButton.NoButton
        button=Qt.MouseButton.NoButton if kind==QEvent.Type.MouseMove else Qt.MouseButton.LeftButton
        event=QMouseEvent(kind,point,QPointF(self.panel.mapToGlobal(point.toPoint())),button,held,Qt.KeyboardModifier.NoModifier)
        app.QApplication.sendEvent(self.panel,event)

    def test_hover_is_inert_and_only_click_changes_selection(self):
        panel=self.panel;self.bar.motion_enabled=False;panel.history_scroll.setValue(0)
        point=QPointF(18+1.5*panel.column_width,150)
        self.chart_mouse(QEvent.Type.MouseMove,point)
        self.assertEqual(panel.active_history_index(),3);self.assertEqual(panel.selected_history_index(),3)
        self.chart_mouse(QEvent.Type.MouseButtonPress,point);self.chart_mouse(QEvent.Type.MouseButtonRelease,point)
        self.assertEqual(panel.selected_history_index(),1)
        self.chart_mouse(QEvent.Type.MouseMove,QPointF(18+2.5*panel.column_width,150));self.assertEqual(panel.active_history_index(),1)
        panel.leaveEvent(QEvent(QEvent.Type.Leave));self.assertEqual(panel.active_history_index(),1)
        self.assertFalse(panel.history_focus.timer.isActive());self.provider.request_reset.assert_not_called()

    def test_drag_and_changed_data_cancel_click_selection(self):
        panel=self.panel;original=self.data['reset_events']
        self.data['reset_events']=[dict(original[index%4],id=str(index)) for index in range(12)];panel.refresh(self.data);panel.history_scroll.setValue(0)
        selected=panel.history_selected
        point=QPointF(18+1.5*panel.column_width,150);pressed=panel.history_key(panel.rows[1])
        self.chart_mouse(QEvent.Type.MouseButtonPress,point);self.chart_mouse(QEvent.Type.MouseMove,point-QPointF(65,0));self.chart_mouse(QEvent.Type.MouseButtonRelease,point-QPointF(65,0))
        self.assertGreater(panel.history_scroll.value(),0);self.assertNotEqual(panel.history_selected,pressed)
        self.assertEqual(panel.history_selected,selected)
        panel.select_history(1);key=panel.history_selected
        self.data['reset_events'].insert(0,dict(original[0],id='earlier',at=original[0]['at']-1));panel.refresh(self.data)
        self.assertEqual(panel.history_selected,key)
        self.chart_mouse(QEvent.Type.MouseButtonPress,QPointF(50,150))
        self.data['reset_events']=[];panel.refresh(self.data);self.chart_mouse(QEvent.Type.MouseButtonRelease,QPointF(50,150))
        self.assertIsNone(panel.history_selected);self.assertIsNone(panel.history_press)

    def test_selection_motion_reverses_and_stops_when_hidden(self):
        panel=self.panel;self.bar.motion_enabled=True
        with patch.object(panel,'isVisible',return_value=True):
            panel.select_history(1);panel.history_focus.advance(.025);value=panel.history_focus.value
            panel.select_history(0);self.assertEqual(panel.history_focus.value,value)
            self.assertNotEqual(panel.history_focus.value,panel.history_focus.target)
        panel.hideEvent(QHideEvent());self.assertFalse(panel.history_focus.timer.isActive())

    def test_pointer_down_feedback_does_not_commit_and_drag_out_cancels(self):
        panel=self.panel;self.bar.motion_enabled=False;panel.history_scroll.setValue(0);point=QPointF(18+1.5*panel.column_width,150)
        before=panel.grab().toImage()
        self.chart_mouse(QEvent.Type.MouseButtonPress,point)
        self.assertEqual(panel.active_history_index(),3);self.assertNotEqual(panel.grab().toImage(),before)
        self.chart_mouse(QEvent.Type.MouseButtonRelease,QPointF(-5,150))
        self.assertEqual(panel.active_history_index(),3);self.assertIsNone(panel.history_press)

    def test_system_reduced_motion_settles_the_selection(self):
        self.bar.motion_enabled=True;self.bar.popup=self.panel
        try:
            with patch.object(self.panel,'isVisible',return_value=True):self.panel.select_history(1)
            self.assertTrue(self.panel.history_focus.timer.isActive())
            with patch('codex_taskbar.app.windows.animations_enabled',return_value=False):self.bar.sync_motion()
            self.assertFalse(self.panel.history_focus.timer.isActive());self.assertEqual(self.panel.history_focus.value,self.panel.history_focus.target)
        finally:self.bar.popup=None

    def test_scrolled_edges_never_show_partial_amount_labels(self):
        self.bar.settings['language']='en';panel=self.panel
        self.data['reset_events']=[dict(self.data['reset_events'][index%4],id=str(index)) for index in range(12)];panel.refresh(self.data)
        panel.history_scroll.setValue(panel.column_width//2)
        with patch('codex_taskbar.app.paint_usage_column',wraps=app.paint_usage_column) as draw:panel.grab()
        self.assertTrue(draw.call_args_list)
        for call in draw.call_args_list:self.assertEqual(call.kwargs['label_bounds'].getRect(),(18.,0.,panel.width()-36.,float(panel.height())))
        painter=Mock();bounds=app.QRectF(18,0,264,200)
        app.paint_usage_column(painter,18,100,80,1,1,'20.37 ×100M','9/14',app.BLUE,label_bounds=bounds)
        painter.drawText.assert_not_called()
        app.paint_usage_column(painter,100,100,80,1,1,'20.37 ×100M','9/14',app.BLUE,label_bounds=bounds)
        self.assertEqual(painter.drawText.call_count,2)

    def test_weekly_and_history_share_columns_and_do_not_reserve_hidden_scroll_space(self):
        self.bar.settings['language']='zh-CN';self.panel.refresh(self.data)
        weekly=app.TaskPopup(self.bar);weekly.refresh(self.data)
        try:
            with patch('codex_taskbar.app.paint_usage_column',wraps=app.paint_usage_column) as columns:
                weekly.grab();self.assertTrue(columns.called);columns.reset_mock()
                self.panel.grab();self.assertTrue(columns.called)
            highest=self.panel.history_bar_rect(self.data['reset_events'][0],0)
            self.assertEqual(highest.height(),64)
            axis=app.usage_date_rect(highest.center().x(),highest.bottom(),self.panel.column_width)
            self.assertEqual(axis.top()-highest.bottom(),9)
            self.assertTrue(self.panel.history_scroll.isHidden())
            self.assertEqual(self.panel.credits_top-14-axis.bottom(),8)
            self.assertLessEqual(self.panel.history_column_rect(highest.center().x()).height(),18)
        finally:weekly.close();weekly.deleteLater()

    def test_latest_is_the_default_but_refresh_keeps_an_explicit_choice(self):
        panel=self.panel;self.assertEqual(panel.selected_history_index(),3)
        original=panel.rows[0]
        self.data['reset_events']=[dict(original,id=str(index),at=original['at']+index) for index in range(12)]
        panel.history_selected=None;panel.refresh(self.data)
        self.assertEqual(panel.selected_history_index(),11);self.assertEqual(panel.history_scroll.value(),panel.history_scroll.maximum())
        panel.select_history(2)
        self.data['reset_events'].append(dict(original,id='new',at=original['at']+12));panel.refresh(self.data)
        self.assertEqual(panel.history_selected,'2')
        self.data['reset_events']=[row for row in self.data['reset_events'] if row['id']!='2'];panel.refresh(self.data)
        self.assertEqual(panel.history_selected,'new')
