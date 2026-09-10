import unittest
from unittest.mock import patch
from PySide6.QtCore import Qt,QEvent,QPoint,QPointF
from PySide6.QtGui import QKeyEvent,QMouseEvent,QWheelEvent,QFocusEvent
from codex_taskbar import app
from tests import test_interactions as fixtures


class SettingsLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.application=app.QApplication.instance() or app.QApplication([])
    def setUp(self):fixtures.InteractionTests.setUp(self)
    def tearDown(self):fixtures.InteractionTests.tearDown(self)

    def test_grouped_switch_supports_keyboard_and_preserves_other_preferences(self):
        with patch('codex_taskbar.settings_ui.startup.enabled',return_value=False),patch('codex_taskbar.app.write_settings') as save,patch.object(self.bar,'tick'):
            dialog=app.SettingsDialog(self.bar);self.bar.settings_dialog=dialog;dialog.navigation.setCurrentRow(1);dialog.grab()
            toggle=dialog.checks['show_week'];self.assertTrue(toggle.hitButton(toggle.rect().center()));self.assertFalse(toggle.hitButton(QPoint(100,20)))
            for kind in (QEvent.Type.KeyPress,QEvent.Type.KeyRelease):self.application.sendEvent(toggle,QKeyEvent(kind,Qt.Key.Key_Space,Qt.KeyboardModifier.NoModifier))
            self.assertFalse(toggle.isChecked());self.assertFalse(self.bar.settings['show_week']);self.assertTrue(self.bar.settings['show_daily']);save.assert_called()

    def test_language_updates_tabs_without_resetting_active_page(self):
        with patch('codex_taskbar.settings_ui.startup.enabled',return_value=False),patch('codex_taskbar.app.write_settings'):
            dialog=app.SettingsDialog(self.bar);self.bar.settings_dialog=dialog;dialog.navigation.setCurrentRow(2)
            dialog.language.setCurrentIndex(dialog.language.findData('zh-CN'))
            self.assertEqual(dialog.navigation.currentRow(),2)
            self.assertEqual([dialog.navigation.item(i).text() for i in range(3)],['外观','显示项','常规'])
            self.assertEqual(dialog.navigation.horizontalScrollBarPolicy(),Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def mouse(self,widget,kind,point):
        button=Qt.MouseButton.LeftButton
        held=Qt.MouseButton.NoButton if kind==QEvent.Type.MouseButtonRelease else button
        self.application.sendEvent(widget,QMouseEvent(kind,QPointF(point),QPointF(widget.mapToGlobal(point)),button,held,Qt.KeyboardModifier.NoModifier))

    def test_caption_and_row_space_never_toggle_or_save(self):
        with patch('codex_taskbar.settings_ui.startup.enabled',return_value=False),patch('codex_taskbar.app.write_settings') as save,patch.object(self.bar,'tick'):
            dialog=app.SettingsDialog(self.bar);self.bar.settings_dialog=dialog;dialog.navigation.setCurrentRow(1);dialog.grab()
            for toggle in [*dialog.checks.values(),dialog.rotation,dialog.hover,dialog.login,dialog.topmost]:
                before=toggle.isChecked()
                for widget,point in ((toggle.caption,toggle.caption.rect().center()),(toggle.row,QPoint(max(0,toggle.x()-8),20))):
                    self.mouse(widget,QEvent.Type.MouseButtonPress,point);self.mouse(widget,QEvent.Type.MouseButtonRelease,point)
                self.assertEqual(toggle.isChecked(),before);self.assertFalse(toggle.keyboard_focus)
            save.assert_not_called()

    def test_switch_commits_on_release_and_drag_out_cancels(self):
        with patch('codex_taskbar.settings_ui.startup.enabled',return_value=False),patch('codex_taskbar.app.write_settings') as save,patch.object(self.bar,'tick'):
            dialog=app.SettingsDialog(self.bar);self.bar.settings_dialog=dialog;dialog.navigation.setCurrentRow(1);dialog.grab()
            toggle=dialog.checks['show_week'];inside=toggle.rect().center();outside=QPoint(-20,16)
            self.mouse(toggle,QEvent.Type.MouseButtonPress,inside);self.assertTrue(toggle.isChecked());self.assertTrue(toggle.isDown());save.assert_not_called()
            self.mouse(toggle,QEvent.Type.MouseButtonRelease,outside);self.assertTrue(toggle.isChecked());save.assert_not_called()
            self.mouse(toggle,QEvent.Type.MouseButtonPress,outside);self.mouse(toggle,QEvent.Type.MouseButtonRelease,inside);self.assertTrue(toggle.isChecked());save.assert_not_called()
            self.mouse(toggle,QEvent.Type.MouseButtonPress,inside);self.mouse(toggle,QEvent.Type.MouseButtonRelease,inside)
            self.assertFalse(toggle.isChecked());self.assertFalse(toggle.keyboard_focus);self.assertEqual(save.call_count,1)

    def test_wheel_and_unfocused_enter_do_not_modify_controls(self):
        with patch('codex_taskbar.settings_ui.startup.enabled',return_value=False),patch('codex_taskbar.app.write_settings') as save,patch.object(self.bar,'update_clicked') as update:
            dialog=app.SettingsDialog(self.bar);self.bar.settings_dialog=dialog;dialog.grab()
            before=dict(self.bar.settings)
            for widget in (dialog.placement,dialog.capsule,dialog.language,dialog.transparency,dialog.navigation):
                self.application.sendEvent(widget,QWheelEvent(QPointF(10,10),QPointF(10,10),QPoint(),QPoint(0,-120),Qt.MouseButton.NoButton,Qt.KeyboardModifier.NoModifier,Qt.ScrollPhase.NoScrollPhase,False))
            self.application.sendEvent(dialog,QKeyEvent(QEvent.Type.KeyPress,Qt.Key.Key_Return,Qt.KeyboardModifier.NoModifier))
            self.assertEqual(self.bar.settings,before);self.assertEqual(dialog.navigation.currentRow(),0);save.assert_not_called();update.assert_not_called()

    def test_focus_cue_is_keyboard_only_and_switch_sized(self):
        from codex_taskbar.settings_ui import Toggle
        toggle=Toggle()
        toggle.focusInEvent(QFocusEvent(QEvent.Type.FocusIn,Qt.FocusReason.MouseFocusReason));self.assertFalse(toggle.keyboard_focus)
        toggle.focusInEvent(QFocusEvent(QEvent.Type.FocusIn,Qt.FocusReason.TabFocusReason));self.assertTrue(toggle.keyboard_focus)
        self.assertLessEqual(toggle.width(),48);self.assertLessEqual(toggle.switch_rect().width()+6,toggle.width())
        toggle.deleteLater()
