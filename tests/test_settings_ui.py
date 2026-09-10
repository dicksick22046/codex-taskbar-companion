import unittest
from unittest.mock import patch
from PySide6.QtCore import Qt,QEvent,QPoint
from PySide6.QtGui import QKeyEvent
from codex_taskbar import app
from tests import test_interactions as fixtures


class SettingsLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.application=app.QApplication.instance() or app.QApplication([])
    def setUp(self):fixtures.InteractionTests.setUp(self)
    def tearDown(self):fixtures.InteractionTests.tearDown(self)

    def test_grouped_switch_supports_keyboard_and_preserves_other_preferences(self):
        with patch('codex_taskbar.settings_ui.startup.enabled',return_value=False),patch('codex_taskbar.app.write_settings') as save,patch.object(self.bar,'tick'):
            dialog=app.SettingsDialog(self.bar);self.bar.settings_dialog=dialog;dialog.tabs.setCurrentIndex(1);dialog.grab()
            toggle=dialog.checks['show_week'];self.assertTrue(toggle.hitButton(QPoint(4,20)))
            for kind in (QEvent.Type.KeyPress,QEvent.Type.KeyRelease):self.application.sendEvent(toggle,QKeyEvent(kind,Qt.Key.Key_Space,Qt.KeyboardModifier.NoModifier))
            self.assertFalse(toggle.isChecked());self.assertFalse(self.bar.settings['show_week']);self.assertTrue(self.bar.settings['show_daily']);save.assert_called()

    def test_language_updates_tabs_without_resetting_active_page(self):
        with patch('codex_taskbar.settings_ui.startup.enabled',return_value=False),patch('codex_taskbar.app.write_settings'):
            dialog=app.SettingsDialog(self.bar);self.bar.settings_dialog=dialog;dialog.tabs.setCurrentIndex(2)
            dialog.language.setCurrentIndex(dialog.language.findData('zh-CN'))
            self.assertEqual(dialog.tabs.currentIndex(),2)
            self.assertEqual([dialog.tabs.tabText(i) for i in range(3)],['外观','显示项','常规'])
            self.assertFalse(dialog.tabs.tabBar().usesScrollButtons())
