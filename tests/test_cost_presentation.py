from datetime import datetime,timedelta
import unittest
from unittest.mock import patch

from PySide6.QtCore import Qt,QEvent,QPointF,QPoint
from PySide6.QtGui import QKeyEvent,QWheelEvent
from PySide6.QtWidgets import QStyleOptionComboBox,QStyle
from codex_taskbar import app
from codex_taskbar.preferences import read_settings
from codex_taskbar.task_finder import cell_text
from tests import test_interactions as fixtures


class CostPresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixtures.InteractionTests.setUpClass()

    def setUp(self):
        self.fixture=fixtures.InteractionTests();self.fixture.setUp()
        self.bar=self.fixture.bar;self.data=self.fixture.data
        self.bar.setGeometry(20,700,360,30);self.bar.motion_enabled=False
        now=datetime.now().astimezone();today=now.date().isoformat()
        self.data.update(history={today:100000000},history_usd={today:.25},daily_usd=.25,usage_at=now.isoformat(),
            reset_events=[dict(id=str(i),kind=kind,at=(now-timedelta(days=2-i)).timestamp(),
                period_start=(now-timedelta(days=3-i)).timestamp(),tokens=100000000,usd=value)
                for i,(kind,value) in enumerate((('scheduled',2.5),('official',None),('manual',0)))])
        for task in self.data['tasks']+self.data['recent_tasks']:task['usd']=.05
        self.bar.data=self.data

    def tearDown(self):self.fixture.tearDown();self.fixture.doCleanups()

    def test_usd_switch_preserves_token_unit_search_and_persists(self):
        self.bar.set_chart_unit('100M');self.bar.set_chart_unit('USD')
        self.assertEqual(self.bar.chart_unit,'100M');self.assertEqual(self.bar.selected_chart_unit,'USD')
        saved=read_settings(app.RUNTIME/'ui_settings.json')
        self.assertEqual(saved['chart_metric'],'usd');self.assertEqual(saved['chart_unit'],'100M')
        self.assertEqual(cell_text({'total_tokens':100000000,'tokens_partial':False},4,self.bar.chart_unit),'1 ×100M')
        self.bar.set_chart_unit('M')
        self.assertEqual(self.bar.selected_chart_unit,'M');self.assertEqual(self.bar.settings['chart_metric'],'tokens')

    def test_click_and_keyboard_use_cost_data_and_restore_tokens(self):
        self.bar.toggle_popup('daily',activate=False);panel=self.bar.popup
        panel.unit_buttons['USD'].click()
        self.assertTrue(panel.unit_buttons['USD'].isChecked())
        self.assertEqual(set(panel.values.values()),{'0.05'})
        self.assertEqual(panel.usage_title(),'Estimated cost (USD)')
        panel.unit_buttons['M'].setFocus(Qt.FocusReason.TabFocusReason)
        event=QKeyEvent(QEvent.Type.KeyPress,Qt.Key.Key_Return,Qt.KeyboardModifier.NoModifier)
        self.fixture.application.sendEvent(panel.unit_buttons['M'],event)
        self.assertEqual(self.bar.selected_chart_unit,'M')
        self.assertEqual(panel.values['running'],'<0.1')

    def test_history_choice_changes_metric_without_chart_selection_or_wheel_accidents(self):
        self.bar.toggle_popup('resets',activate=False);panel=self.bar.popup
        panel.history_choice.setCurrentIndex(1);panel.history_choice.activated.emit(1)
        self.assertEqual([panel.history_amount(row) for row in panel.rows],['2.5','—','0'])
        self.assertAlmostEqual(panel.history_bar_rect(panel.rows[0],0).height(),app.USAGE_COLUMN_HEIGHT)
        self.assertEqual(panel.history_bar_rect(panel.rows[1],1).height(),0)
        self.assertEqual(panel.history_choice.currentText(),'Estimated cost (USD)')
        point=panel.history_choice.rect().center()
        wheel=QWheelEvent(QPointF(point),QPointF(point),QPoint(),QPoint(0,120),Qt.MouseButton.NoButton,
                         Qt.KeyboardModifier.NoModifier,Qt.ScrollPhase.NoScrollPhase,False)
        self.fixture.application.sendEvent(panel.history_choice,wheel)
        self.assertEqual(panel.history_choice.currentData(),'usd')
        self.bar.hide_popup(immediate=True);self.bar.toggle_popup('resets',activate=False)
        self.assertEqual(self.bar.popup.history_choice.currentData(),'usd')

    def test_cycle_sum_does_not_hide_unknown_cost(self):
        self.bar.set_chart_unit('USD');panel=app.TaskPopup(self.bar)
        try:
            today=datetime.now().astimezone().date()
            panel.days=[today-timedelta(days=1),today,today+timedelta(days=1)]
            panel.data={'history':{day.isoformat():100 for day in panel.days[:2]},
                        'history_usd':{today.isoformat():.25}}
            values,_=panel.usage_values();self.assertIsNone(panel.usage_total(values))
            panel.data['history_usd'][(today-timedelta(days=1)).isoformat()]=.75
            values,_=panel.usage_values();self.assertEqual(panel.usage_total(values),1.)
            self.assertEqual(app.chart_number(.001,'USD'),'<0.01')
        finally:panel.close();panel.deleteLater()

    def test_four_language_headers_and_controls_fit_without_changing_anchor(self):
        for language in app.LANGUAGES:
            self.bar.settings['language']=language
            for theme in ('dark','light'):
                self.bar.settings['capsule_theme']=theme
                for mode in ('usage','daily','resets'):
                    self.bar.toggle_popup(mode,activate=False);panel=self.bar.popup
                    before=(self.bar.x(),self.bar.task_strip.x())
                    for unit in ('100M','USD'):
                        self.bar.set_chart_unit(unit);panel.refresh(self.data)
                        with patch('codex_taskbar.app.text',wraps=app.text) as drawn:panel.grab()
                        if mode=='resets':
                            option=QStyleOptionComboBox();panel.history_choice.initStyleOption(option)
                            edit=panel.history_choice.style().subControlRect(QStyle.ComplexControl.CC_ComboBox,option,QStyle.SubControl.SC_ComboBoxEditField,panel.history_choice)
                            self.assertGreaterEqual(edit.width(),app.QFontMetricsF(panel.history_choice.font()).horizontalAdvance(panel.history_choice.currentText()))
                            right=panel.history_choice.geometry().right()
                            legend=[call.args for call in drawn.call_args_list if call.args[2]==64]
                            for _,x,y,label,font,*_ in legend:
                                self.assertGreater(x,right);right=x+app.QFontMetricsF(font).horizontalAdvance(label)
                            self.assertLessEqual(right,panel.width()-18)
                            self.assertEqual(panel.history_choice.currentText(),panel.history_heading())
                        else:
                            update=next(call.args for call in drawn.call_args_list if call.args[3]==app.usage_update_label(self.bar,self.data))
                            self.assertLess(update[1]+app.QFontMetricsF(update[4]).horizontalAdvance(update[3]),min(r.left() for r in panel.unit_rects().values())-5)
                            for button in panel.unit_buttons.values():self.assertTrue(panel.rect().contains(button.geometry()))
                        self.assertEqual((self.bar.x(),self.bar.task_strip.x()),before)
                        self.assertEqual(panel.toolTip(),'')
                    self.bar.hide_popup(immediate=True)

    def test_unit_dropdown_does_not_close_the_host_during_choice(self):
        self.bar.toggle_popup('resets',activate=False);panel=self.bar.popup
        self.bar.settings['hover_panels']=True
        with patch.object(app.QApplication,'activePopupWidget',return_value=panel.history_choice.view().window()),patch.object(self.bar,'hide_popup') as hidden:
            self.bar.update_hover_popup(QPoint(-9000,-9000),now=100)
            self.bar.desktop_click(-9000,-9000,'left')
            hidden.assert_not_called()
        self.fixture.provider.request_reset.assert_not_called()
