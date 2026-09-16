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
        self.data['reset_events']=[{'id':str(i),'kind':'manual','at':now+i*86400,'tokens':value,'before':{'10080':{'remaining':remaining}}}
                                   for i,(value,remaining) in enumerate(((2000000000,80),(1000000000,5),(0,100),(None,0)))]
        self.panel=app.ResetPopup(self.bar);self.panel.refresh(self.data)
    def tearDown(self):
        self.panel.close();self.panel.deleteLater();fixtures.InteractionTests.tearDown(self)

    def test_bars_compare_tokens_not_quota_and_keep_the_scale_while_scrolling(self):
        panel=self.panel;rows=self.data['reset_events']
        first=panel.history_bar_rect(rows[0],0);second=panel.history_bar_rect(rows[1],1)
        self.assertEqual(first.height(),second.height()*2)
        self.assertEqual(first.bottom(),second.bottom());self.assertLess(first.left(),second.left())
        panel.history_scroll.setValue(44);self.assertEqual(panel.history_bar_rect(rows[1],1).height(),second.height())
        rows[1].pop('before');panel.refresh(self.data)
        self.assertEqual(panel.history_bar_rect(rows[1],1).height(),second.height())

    def test_zero_missing_and_invalid_tokens_are_not_filled_bars(self):
        panel=self.panel
        for value in (None,-1,True,float('nan'),float('inf')):
            row={'tokens':value};self.assertEqual(panel.history_amount(row),'—');self.assertEqual(panel.history_bar_rect(row,0).height(),0)
        self.assertEqual(panel.history_amount({'tokens':0}),'0');self.assertEqual(panel.history_unit(),'100M')
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

    def test_history_remains_chronological_without_quota_percentages(self):
        start=self.data['reset_events'][0]['at']-4*86400
        self.data['reset_events'][0]['period_start']=start-86400
        for index,row in enumerate(self.data['reset_events']):row['at']=start+index*86400
        for language in app.LANGUAGES:
            self.bar.settings['language']=language;self.panel.refresh(self.data)
            labels=self.panel.boundary_labels
            dates=[datetime.fromtimestamp(start-86400).strftime('%m/%d')]+[datetime.fromtimestamp(row['at']).strftime('%m/%d') for row in self.data['reset_events']]
            self.assertEqual(labels,dates)
            self.assertNotIn('%',self.panel.accessibleDescription())
            self.assertIn(self.panel.history_interval(self.panel.rows[0]),self.panel.accessibleDescription())

    def test_horizontal_scroll_reaches_latest_preserves_offset_and_keeps_height(self):
        for language in app.LANGUAGES:
            self.bar.settings['language']=language;panel=self.panel;panel.refresh(self.data)
            height=panel.height();self.data['reset_events']*=2;panel.refresh(self.data)
            self.data['reset_events']=[dict(row,id=str(index)) for index,row in enumerate(self.data['reset_events'])];panel.refresh(self.data)
            self.assertLessEqual(panel.height()-height,14);self.assertGreater(panel.history_scroll.maximum(),0)
            panel.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress,Qt.Key.Key_End,Qt.KeyboardModifier.NoModifier))
            self.assertEqual(panel.history_scroll.value(),panel.history_scroll.maximum())
            point=QPointF(panel.width()-19,panel.DATE_Y+panel.forecast_height)
            self.assertEqual(panel.history_at(point),len(panel.rows)-1)
            offset=panel.history_scroll.value();panel.refresh(self.data);self.assertEqual(panel.history_scroll.value(),offset)
            panel.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress,Qt.Key.Key_Home,Qt.KeyboardModifier.NoModifier));self.assertEqual(panel.history_scroll.value(),0)
        self.data['reset_events']=self.data['reset_events'][:1];panel.refresh(self.data)
        self.assertEqual(panel.history_scroll.maximum(),0);self.assertTrue(panel.history_scroll.isHidden())

    def test_wheel_axes_scroll_without_changing_data(self):
        panel=self.panel;self.data['reset_events']*=4;panel.refresh(self.data)
        panel.history_scroll.setValue(0);rows=list(panel.rows)
        point=QPointF(50,150+panel.forecast_height)
        def wheel(pixel=QPoint(),angle=QPoint(),shift=False):
            event=QWheelEvent(point,point,pixel,angle,Qt.MouseButton.NoButton,Qt.KeyboardModifier.ShiftModifier if shift else Qt.KeyboardModifier.NoModifier,Qt.ScrollPhase.ScrollUpdate,False)
            panel.wheelEvent(event)
        wheel(pixel=QPoint(-37,0));self.assertEqual(panel.history_scroll.value(),37);self.assertEqual(panel.scroll,0)
        wheel(angle=QPoint(0,-120));self.assertEqual(panel.history_scroll.value(),37+panel.column_width)
        self.assertEqual(panel.rows,rows)
        with patch.object(panel,'scroll_limit',return_value=200):
            old=panel.history_scroll.value();wheel(angle=QPoint(0,-120));self.assertEqual(panel.history_scroll.value(),old);self.assertGreater(panel.scroll,0)
            wheel(angle=QPoint(0,-120),shift=True);self.assertGreater(panel.history_scroll.value(),old)
        self.provider.request_reset.assert_not_called()

    def chart_mouse(self,kind,point):
        held=Qt.MouseButton.LeftButton if kind!=QEvent.Type.MouseButtonRelease else Qt.MouseButton.NoButton
        button=Qt.MouseButton.NoButton if kind==QEvent.Type.MouseMove else Qt.MouseButton.LeftButton
        event=QMouseEvent(kind,point,QPointF(self.panel.mapToGlobal(point.toPoint())),button,held,Qt.KeyboardModifier.NoModifier)
        app.QApplication.sendEvent(self.panel,event)






    def test_scrolled_edges_never_show_partial_amount_or_boundary_labels(self):
        self.bar.settings['language']='en';panel=self.panel
        self.data['reset_events']=[dict(self.data['reset_events'][index%4],id=str(index)) for index in range(12)];panel.refresh(self.data)
        for offset in (0,panel.column_width//2,panel.history_scroll.maximum()):
            panel.history_scroll.setValue(offset)
            with patch('codex_taskbar.app.text',wraps=app.text) as draw:panel.grab()
            labels=[call.args for call in draw.call_args_list if call.args[3] in panel.boundary_labels and call.args[2]==panel.DATE_Y]
            self.assertTrue(labels)
            previous=18
            for _,x,y,value,font,*_ in labels:
                width=app.QFontMetricsF(font).horizontalAdvance(value)
                self.assertGreaterEqual(x,previous);self.assertLessEqual(x+width,panel.width()-18)
                previous=x+width
            amounts=[panel.history_amount(row) for row in panel.rows]
            for call in draw.call_args_list:
                _,x,y,value,font,*_=call.args
                if value not in amounts or not panel.CHART_TOP<=y<=panel.BASELINE:continue
                self.assertGreaterEqual(x,18)
                self.assertLessEqual(x+app.QFontMetricsF(font).horizontalAdvance(value),panel.width()-18)

    def test_period_bars_are_thinner_and_weekly_is_unchanged(self):
        self.bar.settings['language']='zh-CN';self.panel.refresh(self.data)
        weekly=app.TaskPopup(self.bar);weekly.refresh(self.data)
        try:
            with patch('codex_taskbar.app.paint_usage_column',wraps=app.paint_usage_column) as columns:
                weekly.grab();self.assertTrue(columns.called);columns.reset_mock()
                self.panel.grab();self.assertFalse(columns.called)
            first=self.panel.history_bar_rect(self.panel.rows[0],0);second=self.panel.history_bar_rect(self.panel.rows[1],1)
            self.assertEqual(first.height(),64);self.assertEqual(first.width(),second.width())
            self.assertEqual(first.width(),24)
            self.assertLess(first.width(),self.panel.column_width/2)
            self.data['reset_events']=self.data['reset_events'][:1];self.panel.refresh(self.data)
            axis=app.usage_date_rect(0,self.panel.BASELINE,1)
            self.assertTrue(self.panel.history_scroll.isHidden())
            self.assertEqual(self.panel.credits_top-14-axis.bottom(),8)
        finally:weekly.close();weekly.deleteLater()

    def test_start_metadata_and_boundary_labels_distinguish_same_day_resets(self):
        now=datetime(2026,9,15,10,0).timestamp()
        self.data['reset_events']=[dict(self.panel.rows[0],id=str(i),at=now+i*20,period_start=now-3600 if i==0 else now+(i-1)*20) for i in range(3)]
        self.panel.refresh(self.data)
        self.assertEqual(self.panel.history_start(self.panel.rows[0]),now-3600)
        self.assertEqual(len(set(self.panel.boundary_labels)),4)
        self.assertIn('10:00:20',self.panel.boundary_labels[2])
        self.assertIn('09:00',self.panel.history_interval(self.panel.rows[0]))
        for i in range(3):
            self.panel.rows[i].pop('period_start')
        self.panel.refresh(self.data)
        self.assertEqual(self.panel.boundary_labels[0],'—')
        self.assertTrue(self.panel.history_interval(self.panel.rows[0]).startswith('—'))
        self.assertEqual(self.panel.history_start(self.panel.rows[1]),now)

    def test_latest_same_day_period_draws_both_boundaries_without_overlap(self):
        now=datetime(2026,9,15,10,0).timestamp();panel=self.panel
        self.data['reset_events']=[dict(panel.rows[0],id=str(i),at=now+i*20,period_start=now+(i-1)*20) for i in range(8)]
        panel.refresh(self.data);panel.history_scroll.setValue(panel.history_scroll.maximum())
        self.assertEqual(panel.history_scroll.value(),panel.history_scroll.maximum())
        with patch('codex_taskbar.app.text',wraps=app.text) as draw:panel.grab()
        shown={call.args[3]:call.args[1] for call in draw.call_args_list if call.args[2]==panel.DATE_Y}
        left,right=panel.boundary_labels[-2:]
        self.assertIn(left,shown);self.assertIn(right,shown)
        self.assertLessEqual(shown[left]+app.QFontMetricsF(app.face(7)).horizontalAdvance(left)+6,shown[right])
        self.assertGreaterEqual(shown[left],18)
        self.assertLessEqual(shown[right]+app.QFontMetricsF(app.face(7)).horizontalAdvance(right),panel.width()-18)
        self.assertLess(panel.column_width,max(app.QFontMetricsF(app.face(7)).horizontalAdvance(label) for label in panel.boundary_labels)+10)

    def test_explicit_unknown_start_never_falls_back_and_equal_boundaries_are_unknown(self):
        panel=self.panel;row=panel.rows[1]
        row['period_start']=None;self.assertIsNone(panel.history_start(row))
        row['period_start']=row['at'];self.assertIsNone(panel.history_start(row))
        row.pop('period_start');row['at']=panel.rows[0]['at'];self.assertIsNone(panel.history_start(row))

    def test_known_zero_amount_sits_above_baseline_while_missing_stays_distinct(self):
        panel=self.panel;self.bar.settings['language']='en'
        self.data['reset_events']=self.data['reset_events'][2:];panel.refresh(self.data)
        with patch('codex_taskbar.app.text',wraps=app.text) as draw:panel.grab()
        zero=next(call.args for call in draw.call_args_list if call.args[3]=='0')
        self.assertLess(zero[2]+app.QFontMetricsF(zero[4]).height()/2,panel.BASELINE)
        missing=[call.args for call in draw.call_args_list if call.args[3]=='—' and call.args[2]==panel.BASELINE-1]
        self.assertTrue(missing)

    def test_attached_width_does_not_reserve_space_for_a_hidden_scrollbar(self):
        self.bar.setGeometry(30,700,560,30);self.bar.settings['placement']='floating';self.bar.motion_enabled=False
        host=self.bar.task_strip;panel=app.ResetPopup(self.bar,host);host.attach_detail(panel)
        try:
            panel.refresh(self.data)
            self.assertEqual(panel.width(),self.bar.width())
            self.assertEqual(panel.history_scroll.maximum(),0)
            self.assertTrue(panel.history_scroll.isHidden())
            axis_bottom=app.usage_date_rect(0,panel.BASELINE,panel.column_width).bottom()
            self.assertEqual(panel.history_height,axis_bottom+2-panel.HISTORY_START)
            self.assertEqual(panel.credits_top-14-axis_bottom,8)
        finally:host.detach_detail(restore=False);panel.close();panel.deleteLater()


    def test_hover_press_and_click_do_not_change_chart_or_create_selection(self):
        panel=self.panel;panel.history_scroll.setValue(0);before=panel.grab().toImage()
        point=QPointF(18+1.5*panel.column_width,130)
        for kind in (QEvent.Type.MouseMove,QEvent.Type.MouseButtonPress,QEvent.Type.MouseButtonRelease):
            self.chart_mouse(kind,point);self.assertEqual(panel.grab().toImage(),before)
        self.assertFalse(hasattr(panel,'history_selected'));self.assertFalse(hasattr(panel,'history_focus'))
        self.provider.request_reset.assert_not_called()

    def test_drag_browses_and_hidden_or_empty_data_cancels_gesture(self):
        panel=self.panel;original=self.data['reset_events']
        self.data['reset_events']=[dict(original[index%4],id=str(index)) for index in range(12)];panel.refresh(self.data);panel.history_scroll.setValue(0)
        point=QPointF(18+1.5*panel.column_width,130)
        self.chart_mouse(QEvent.Type.MouseButtonPress,point);self.chart_mouse(QEvent.Type.MouseMove,point-QPointF(65,0));self.chart_mouse(QEvent.Type.MouseButtonRelease,point-QPointF(65,0))
        self.assertEqual(panel.history_scroll.value(),65);self.assertIsNone(panel.history_press)
        self.chart_mouse(QEvent.Type.MouseButtonPress,QPointF(50,130));panel.hideEvent(QHideEvent());self.assertIsNone(panel.history_press)

    def test_latest_viewport_initializes_once_and_arrows_scroll_without_selection(self):
        original=self.panel.rows[0];self.data['reset_events']=[dict(original,id=str(index),at=original['at']+index*86400) for index in range(12)]
        panel=app.ResetPopup(self.bar)
        try:
            panel.refresh(self.data);self.assertEqual(panel.history_scroll.value(),panel.history_scroll.maximum())
            def key(value):panel.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress,value,Qt.KeyboardModifier.NoModifier))
            key(Qt.Key.Key_Home);self.assertEqual(panel.history_scroll.value(),0)
            key(Qt.Key.Key_Right);self.assertEqual(panel.history_scroll.value(),panel.column_width)
            key(Qt.Key.Key_Left);self.assertEqual(panel.history_scroll.value(),0)
            panel.history_scroll.setValue(35)
            self.data['reset_events'].append(dict(original,id='new',at=original['at']+12*86400));panel.refresh(self.data)
            self.assertEqual(panel.history_scroll.value(),35)
            key(Qt.Key.Key_End);self.assertEqual(panel.history_scroll.value(),panel.history_scroll.maximum())
        finally:panel.close();panel.deleteLater()

    def test_header_unit_and_three_fixed_type_colors_fit_one_row_in_every_language(self):
        for language in app.LANGUAGES:
            self.bar.settings['language']=language;panel=self.panel
            for index,row in enumerate(panel.rows):row['kind']=('scheduled','official','manual')[index%3]
            panel.refresh(self.data)
            with patch('codex_taskbar.app.text',wraps=app.text) as draw:panel.grab()
            header=[call.args for call in draw.call_args_list if call.args[2]==64]
            expected={'en':'Period usage (100M)','zh-CN':'周期用量（亿）','ja':'期間別使用量（億）','es':'Uso por período (100M)'}
            self.assertEqual(panel.history_heading(),expected[language])
            self.assertEqual(panel.history_choice.currentText(),expected[language])
            self.assertEqual([args[3] for args in header],[label for _,label in panel.history_legend()])
            right=panel.history_choice.geometry().right()
            for _,x,y,value,font,*_ in header:
                self.assertGreaterEqual(x,right);right=x+app.QFontMetricsF(font).horizontalAdvance(value)
            self.assertLessEqual(right,panel.width()-18)
            colors=app.popup_palette(self.bar)
            self.assertEqual([panel.history_color(kind) for kind,_ in panel.history_legend()],[colors['link'],colors['lilac'],colors['rings']['session']])
            self.assertEqual(panel.CHART_TOP,76)
            self.assertNotIn('%',panel.accessibleDescription())
