from contextlib import ExitStack
from unittest.mock import patch
import unittest
from PySide6.QtCore import QPointF,Qt,QEvent
from PySide6.QtGui import QKeyEvent,QHideEvent,QFontInfo
from codex_taskbar import app
from codex_taskbar.task_finder import TaskFinder
from tests import test_interactions as fixtures


class UIFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.application=app.QApplication.instance() or app.QApplication([])
    def setUp(self):
        fixtures.InteractionTests.setUp(self);self.stack=ExitStack();self.addCleanup(self.stack.close)
        for name,value in [('placement',(100,800,540,30,1,False)),('follow_taskbar',None),('floating_window',None)]:self.stack.enter_context(patch('codex_taskbar.app.windows.'+name,return_value=value))
        self.stack.enter_context(patch('codex_taskbar.app.windows.user32.IsWindow',return_value=True))
        self.stack.enter_context(patch.object(self.bar,'ensure_visible',return_value=False))
        self.stack.enter_context(patch.object(self.bar,'underMouse',return_value=False))
        self.save=self.stack.enter_context(patch('codex_taskbar.app.write_settings'))
        self.stack.enter_context(patch('codex_taskbar.settings_ui.startup.enabled',return_value=False))
        self.dialog=app.SettingsDialog(self.bar);self.bar.settings_dialog=self.dialog
        self.stack.enter_context(patch.object(self.dialog,'isVisible',return_value=True))
        self.bar.setGeometry(100,800,540,30);self.bar.position=(100,800,540,30)
    def tearDown(self):fixtures.InteractionTests.tearDown(self)

    def layout(self):self.dialog.grab();self.application.processEvents();self.dialog.grab()

    def test_every_settings_row_has_balanced_control_clearance(self):
        self.bar.set_placement('auto')
        for language in app.LANGUAGES:
            self.bar.set_language(language)
            for page,controls in ((0,[self.dialog.placement,self.dialog.display,self.dialog.topmost,self.dialog.capsule,self.dialog.transparency.parentWidget()]),(1,list(self.dialog.checks.values())),(2,[self.dialog.language,self.dialog.update_button,self.dialog.login])):
                self.dialog.navigation.setCurrentRow(page);self.layout()
                for control in controls:
                    row=control.parentWidget();top=control.y();bottom=row.height()-control.y()-control.height()
                    with self.subTest(language=language,control=control.accessibleName()):
                        self.assertGreaterEqual(top,8);self.assertGreaterEqual(bottom,8);self.assertLessEqual(abs(top-bottom),1)

    def test_settings_changes_resize_real_layout_without_closing_dialog(self):
        self.dialog.navigation.setCurrentRow(1);self.layout()
        for placement in ('taskbar','floating'):
            self.dialog.placement.setCurrentIndex(self.dialog.placement.findData(placement))
            for key in ('show_tasks','show_week','show_session','show_countdown','show_daily'):
                control=self.dialog.checks[key]
                for enabled in (False,True,False):
                    control.setChecked(enabled)
                    if any(self.bar.settings[k] for k in app.DISPLAY_DEFAULTS if k!='show_task_strip'):
                        self.assertEqual(self.bar.width(),self.bar.content_width(self.bar.content_limit),(placement,key,enabled))
            self.dialog.checks['show_daily'].setChecked(True)
            self.dialog.checks['show_countdown'].setChecked(True)
            for enabled in (True,False,True):
                self.dialog.rotation.setChecked(enabled)
                self.assertEqual(self.bar.width(),self.bar.content_width(self.bar.content_limit))
            self.bar.set_language('zh-CN');self.assertEqual(self.bar.width(),self.bar.content_width(self.bar.content_limit))
        self.assertTrue(self.dialog.isVisible());self.provider.stop.assert_not_called()

    def test_pinned_rows_have_no_separate_visibility_or_topmost_switch(self):
        self.bar.set_placement('taskbar');self.dialog.refresh()
        self.assertTrue(self.dialog.topmost.row.isHidden())
        self.assertTrue(self.dialog.display_row.isHidden())
        self.assertNotIn('show_task_strip',self.dialog.checks)

    def test_startup_failure_restores_actual_state_and_explains_failure(self):
        with patch('codex_taskbar.app.startup.set_enabled',side_effect=OSError('fixture')),patch('builtins.print'):
            self.dialog.login.setChecked(True)
        self.assertFalse(self.dialog.login.isChecked())
        self.assertFalse(self.dialog.feedback.isHidden());self.assertIn('startup',self.dialog.feedback.text().lower())

    def test_save_failure_remains_visible_when_status_refreshes(self):
        self.save.side_effect=OSError('fixture')
        with patch('builtins.print'):self.dialog.capsule.setCurrentIndex(self.dialog.capsule.findData('light'))
        self.dialog.navigation.setCurrentRow(2);self.dialog.refresh_status()
        self.assertFalse(self.dialog.feedback.isHidden());self.assertIn('save',self.dialog.feedback.text().lower())
        self.save.side_effect=None;self.dialog.capsule.setCurrentIndex(self.dialog.capsule.findData('dark'))
        self.assertTrue(self.dialog.feedback.isHidden())

    def test_search_filter_scroll_and_cross_view_units_are_immediate(self):
        self.data['catalog']=[{'id':str(i),'title':f'Task {i}','project':str(i%2),'updated_at':1000-i} for i in range(80)]
        self.data['task_statistics']={str(i):{'ready':True,'tokens':120000000,'seconds':200,'turns':3} for i in range(80)}
        finder=TaskFinder(self.bar);self.bar.task_finder=finder;finder.resize(900,300);finder.grab();self.application.processEvents()
        finder.view.verticalScrollBar().setValue(finder.view.verticalScrollBar().maximum());self.assertGreater(finder.view.verticalScrollBar().value(),0)
        finder.search.setText('Task');self.assertEqual(finder.view.verticalScrollBar().value(),0)
        finder.view.verticalScrollBar().setValue(10);finder.refresh(dict(self.data));self.assertEqual(finder.view.verticalScrollBar().value(),10)
        finder.projects.setCurrentIndex(1);self.assertEqual(finder.view.verticalScrollBar().value(),0)
        self.bar.set_chart_unit('100M')
        self.assertEqual(finder.units.currentText(),'100M');self.assertIn('100M',finder.model.index(0,4).data(Qt.ItemDataRole.AccessibleTextRole))

    def test_press_feedback_tracks_leaving_and_returning_to_target(self):
        self.bar.grab();hit=next(h for h in self.bar.hit_regions if h[0]=='daily');self.bar.begin_press(hit)
        self.bar.track_pointer(QPointF(-5,-5));self.assertFalse(self.bar.press_inside)
        self.bar.track_pointer(hit[1].center());self.assertTrue(self.bar.press_inside)
        self.bar.release_press();self.assertFalse(self.bar.press_inside)

    def test_segment_motion_survives_real_setting_refresh_and_hiding_settles(self):
        self.layout();choice=self.dialog.placement
        with patch.object(choice,'isVisible',return_value=True):
            choice.setCurrentIndex(choice.findData('floating'))
            self.assertTrue(choice.motion.timer.isActive())
            choice.motion.advance(.025);before=(choice.motion.value,choice.motion.velocity)
            self.dialog.refresh();self.assertEqual((choice.motion.value,choice.motion.velocity),before)
            choice.hideEvent(QHideEvent());self.assertFalse(choice.motion.timer.isActive())
            self.assertEqual(choice.position,choice.items[choice.currentIndex()][0].x())

    def test_rapid_navigation_retains_each_visible_weight(self):
        nav=self.dialog.navigation
        with patch.object(nav,'isVisible',return_value=True):
            nav.setCurrentRow(1)
            for motion in nav.motions:motion.advance(.035)
            before=[(motion.value,motion.velocity) for motion in nav.motions]
            nav.setCurrentRow(2)
            self.assertEqual([(motion.value,motion.velocity) for motion in nav.motions],before)
            for motion in nav.motions:motion.advance(1.)
            self.assertEqual(nav.weights,[0.,0.,1.])

    def test_keyboard_navigation_and_runtime_reduced_motion_leave_no_timers(self):
        nav=self.dialog.navigation
        with patch.object(nav,'isVisible',return_value=True):
            self.application.sendEvent(nav,QKeyEvent(QEvent.Type.KeyPress,Qt.Key.Key_Down,Qt.KeyboardModifier.NoModifier))
            self.assertEqual(nav.currentRow(),1);self.assertFalse(any(m.timer.isActive() for m in nav.motions));self.assertFalse(self.dialog.page_motion.timer.isActive())
            nav.setCurrentRow(2);self.assertTrue(self.dialog.page_motion.timer.isActive())
            with patch('codex_taskbar.app.windows.animations_enabled',return_value=False):self.bar.sync_motion()
            self.assertFalse(any(m.timer.isActive() for m in nav.motions));self.assertFalse(self.dialog.page_effect.isEnabled())

    def test_current_font_and_reopened_preferences_match_all_controls(self):
        self.layout()
        self.assertEqual(QFontInfo(self.dialog.placement_label.font()).family(),self.bar.font.family())
        self.dialog.checks['show_week'].setChecked(False);self.dialog.rotation.setChecked(True)
        self.dialog.capsule.setCurrentIndex(self.dialog.capsule.findData('light'));self.dialog.transparency.setValue(35)
        self.dialog.close();reopened=app.SettingsDialog(self.bar);self.bar.settings_dialog=reopened;reopened.grab()
        self.assertFalse(reopened.checks['show_week'].isChecked());self.assertTrue(reopened.rotation.isChecked())
        self.assertEqual(reopened.capsule.currentData(),'light');self.assertEqual(reopened.transparency.value(),35)

    def test_optional_notice_is_grouped_and_click_rechecks_current_state(self):
        self.dialog.notify_input.setChecked(True);task=self.data['tasks'][0];task['needs_input']=True;task['title']='private title'
        with patch('codex_taskbar.app.time.monotonic',return_value=100):self.bar.check_attention()
        self.bar.tray.showMessage.assert_not_called()
        with patch('codex_taskbar.app.time.monotonic',return_value=101):self.bar.check_attention()
        self.bar.tray.showMessage.assert_called_once();self.assertNotIn('private title',str(self.bar.tray.showMessage.call_args))
        with patch.object(self.bar,'open_task') as opened:self.bar.notification_clicked();opened.assert_called_once_with(task)
        task['needs_input']=False
        with patch.object(self.bar,'open_finder') as finder:self.bar.notification_clicked();finder.assert_called_once()
        self.bar.notification_kind='settings'
        with patch.object(self.bar,'open_settings') as settings:self.bar.notification_clicked();settings.assert_called_once()
        self.assertEqual(self.dialog.navigation.currentRow(),2)

    def test_navigation_failure_is_visible_and_never_closes_search(self):
        finder=TaskFinder(self.bar);self.bar.task_finder=finder
        with patch('codex_taskbar.app.os.startfile',side_effect=OSError('fixture')),patch('builtins.print'),patch.object(finder,'hide') as hide:
            finder.open_row(finder.rows[0]);hide.assert_not_called()
        self.assertFalse(finder.failure.isHidden());self.assertIn('try again',finder.failure.text())
        self.bar.tray.showMessage.assert_called_once();self.assertEqual(self.bar.notification_kind,'navigation')

    def test_independent_errors_clear_only_when_each_operation_recovers(self):
        self.save.side_effect=OSError('fixture')
        with patch('builtins.print'),patch('codex_taskbar.app.startup.set_enabled',side_effect=OSError('fixture')):
            self.bar.save_settings();self.bar.set_startup(True)
        self.assertEqual(len(self.bar.settings_errors),2)
        self.save.side_effect=None;self.bar.save_settings();self.assertEqual(len(self.bar.settings_errors),1)
        self.assertIn('startup',self.dialog.feedback.text())
        with patch('codex_taskbar.app.startup.set_enabled'):self.bar.set_startup(True)
        self.assertFalse(self.bar.settings_errors);self.assertTrue(self.dialog.feedback.isHidden())

    def test_copy_diagnostics_uses_fake_clipboard_and_confirms_completion(self):
        with patch('codex_taskbar.settings_ui.QApplication.clipboard') as clipboard:
            self.dialog.diagnostics_button.click()
        clipboard.return_value.setText.assert_called_once();self.assertIn('"window"',clipboard.return_value.setText.call_args.args[0])
        self.assertEqual(self.dialog.diagnostics_button.text(),'Copied');self.assertTrue(self.dialog.copy_timer.isActive())
        self.dialog.hideEvent(QHideEvent());self.assertFalse(self.dialog.copy_timer.isActive())
