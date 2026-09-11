import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import QRect
from codex_taskbar import app,windows
from codex_taskbar.presentation import AutoPlacement
from codex_taskbar.preferences import read_settings
from tests import test_ui_flows as flows


class Screen:
    def __init__(self,name,bounds):self._name=name;self.bounds=bounds
    def name(self):return self._name
    def availableGeometry(self):return self.bounds
    def size(self):return self.bounds.size()
    def devicePixelRatio(self):return 1.


class PlacementPolicyTests(unittest.TestCase):
    def test_chatter_is_ignored_and_locked_switch_waits(self):
        policy=AutoPlacement();self.assertFalse(policy.resolve(True,0))
        self.assertFalse(policy.resolve(False,1));self.assertFalse(policy.resolve(True,1.5))
        self.assertFalse(policy.resolve(False,2));self.assertFalse(policy.resolve(False,3,locked=True))
        self.assertTrue(policy.resolve(False,3.1));self.assertTrue(policy.resolve(True,4))
        self.assertFalse(policy.resolve(True,5));self.assertTrue(policy.resolve(False,5.1,immediate=True))

    def test_legacy_screen_and_explicit_primary_preferences(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'settings.json';base={'placement':'auto','floating_position':{'screen':'B','x':.3,'y':.6}}
            path.write_text(json.dumps(base));value=read_settings(path)
            self.assertEqual(value['placement'],'auto');self.assertEqual(value['floating_display'],'B')
            path.write_text(json.dumps({**base,'floating_display':None}));self.assertIsNone(read_settings(path)['floating_display'])
            path.write_text(json.dumps({**base,'floating_display':[]}));self.assertIsNone(read_settings(path)['floating_display'])

    def test_fullscreen_uses_monitor_bounds_including_negative_origins(self):
        def info(monitor,result):
            result._obj.monitor=windows.w.RECT(-1920,0,0,1080);return 1
        with patch.object(windows.user32,'GetForegroundWindow',return_value=100),patch.object(windows.user32,'GetDesktopWindow',return_value=1),patch.object(windows.user32,'GetShellWindow',return_value=2),patch.object(windows.user32,'GetClassNameW'),patch.object(windows.user32,'MonitorFromWindow',return_value=3),patch.object(windows.user32,'GetMonitorInfoW',side_effect=info),patch('codex_taskbar.windows.rect',return_value=(-1920,0,0,1080)):
            self.assertTrue(windows.foreground_fullscreen())
            with patch('codex_taskbar.windows.rect',return_value=(-1920,0,0,1040)):self.assertFalse(windows.foreground_fullscreen())


class AdaptivePlacementFlows(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.application=app.QApplication.instance() or app.QApplication([])
    def setUp(self):
        flows.UIFlowTests.setUp(self)
        self.stack.enter_context(patch('codex_taskbar.app.windows.foreground_fullscreen',return_value=False))
    def tearDown(self):flows.UIFlowTests.tearDown(self)

    def test_auto_fallback_recovers_without_rewriting_user_mode(self):
        self.bar.set_placement('auto');self.assertFalse(self.bar.floating);self.save.reset_mock()
        with patch('codex_taskbar.app.windows.placement',return_value=None):
            for at,expected in ((100,False),(100.5,False),(101,True)):
                with patch('codex_taskbar.app.time.monotonic',return_value=at):self.bar.tick()
                self.assertEqual(self.bar.floating,expected)
        self.assertEqual(self.bar.settings['placement'],'auto');self.save.assert_not_called()
        self.dialog.refresh_status();self.assertIn('Using floating',self.dialog.connection.text())
        for at,expected in ((102,True),(103,False)):
            with patch('codex_taskbar.app.time.monotonic',return_value=at):self.bar.tick()
            self.assertEqual(self.bar.floating,expected)
        self.assertEqual(self.bar.settings['placement'],'auto')

    def test_auto_controls_fit_compact_layout_in_every_language(self):
        self.bar.set_placement('auto');self.dialog.resize(620,540)
        for language in app.LANGUAGES:
            self.bar.set_language(language);self.dialog.navigation.setCurrentRow(0);self.dialog.grab();self.application.processEvents();self.dialog.grab()
            self.assertLessEqual(self.dialog.body.width(),self.dialog.scroll_area.viewport().width(),language)
            label=self.dialog.display_label;control=self.dialog.display
            self.assertGreaterEqual(control.x()-label.geometry().right(),6,language)
            self.assertLessEqual(app.QFontMetricsF(control.font()).horizontalAdvance(control.currentText()),control.width()-42,language)

    def test_hidden_taskbar_and_fullscreen_do_not_create_overlay(self):
        with patch('codex_taskbar.app.windows.placement',return_value=(0,1000,540,30,1,True)),patch.object(self.bar,'hide') as hide:
            self.bar.set_placement('auto');self.assertFalse(self.bar.floating);hide.assert_called()
        with patch('codex_taskbar.app.windows.placement',return_value=None),patch('codex_taskbar.app.windows.foreground_fullscreen',return_value=True),patch.object(self.bar,'ensure_visible') as visible:
            self.bar.tick(resize=True);self.assertTrue(self.bar.floating);visible.assert_not_called()

    def test_open_panel_defers_automatic_return_and_reuses_its_screen(self):
        with patch('codex_taskbar.app.windows.placement',return_value=None):self.bar.set_placement('auto')
        panel=app.TaskListPopup(self.bar);self.bar.popup=panel;panel.refresh(self.data)
        for at in (100,102):
            with patch('codex_taskbar.app.time.monotonic',return_value=at):self.bar.tick()
            self.assertTrue(self.bar.floating);self.assertIs(self.bar.popup,panel)
        self.bar.hide_popup(immediate=True)
        with patch('codex_taskbar.app.time.monotonic',return_value=103):self.bar.tick()
        self.assertFalse(self.bar.floating)

    def test_disconnected_display_falls_back_and_returns_without_losing_position(self):
        a=Screen('A',QRect(0,0,1920,1040));b=Screen('B',QRect(-1600,0,1600,900));screens=[a,b]
        saved={'screen':'B','x':.3,'y':.6,'width':300}
        self.bar.settings.update(placement='floating',floating_display='B',floating_position=dict(saved))
        with patch.object(app.QApplication,'screens',side_effect=lambda:screens),patch.object(app.QApplication,'primaryScreen',return_value=a):
            self.bar.tick(resize=True);before=self.bar.geometry();self.assertTrue(b.bounds.contains(before))
            panel=app.TaskListPopup(self.bar);panel.refresh(self.data);self.assertTrue(b.bounds.contains(panel.geometry()));panel.close();panel.deleteLater()
            from codex_taskbar.task_finder import TaskFinder
            finder=TaskFinder(self.bar);self.assertTrue(b.bounds.contains(finder.geometry()));finder.close();finder.deleteLater()
            settings=app.SettingsDialog(self.bar);self.assertTrue(b.bounds.contains(settings.geometry()));settings.close();settings.deleteLater()
            with patch.object(self.bar.menu,'popup') as menu:
                self.bar.open_menu();self.assertTrue(b.bounds.contains(menu.call_args.args[0]))
            screens[:]=[a];self.bar.tick(resize=True);self.dialog.refresh_displays()
            self.assertTrue(a.bounds.contains(self.bar.geometry()));self.assertEqual(self.dialog.display.currentData(),'B')
            self.assertFalse(self.dialog.display.model().item(self.dialog.display.currentIndex()).isEnabled())
            screens[:]=[a,b];self.bar.tick(resize=True);self.dialog.refresh_displays()
            self.assertEqual(self.bar.geometry(),before);self.assertEqual(self.bar.settings['floating_position'],saved)
            self.assertEqual(self.bar.settings['floating_display'],'B')
        self.save.assert_not_called()

    def test_display_choice_preserves_relative_position_and_primary_can_follow(self):
        a=Screen('A',QRect(0,0,1920,1040));b=Screen('B',QRect(-1600,0,1600,900))
        self.bar.settings.update(placement='floating',floating_display='A',floating_position={'screen':'A','x':.2,'y':.7,'width':300})
        with patch.object(app.QApplication,'screens',return_value=[a,b]),patch.object(app.QApplication,'primaryScreen',return_value=a):
            self.dialog.refresh_displays();self.dialog.display.setCurrentIndex(self.dialog.display.findData('B'))
            self.assertEqual(self.bar.settings['floating_display'],'B');self.assertEqual(self.bar.settings['floating_position']['x'],.2)
            self.assertTrue(b.bounds.contains(self.bar.geometry()))
            self.dialog.display.setCurrentIndex(0);self.assertIsNone(self.bar.settings['floating_display'])
            with patch.object(app.QApplication,'primaryScreen',return_value=b):self.bar.tick(resize=True);self.assertTrue(b.bounds.contains(self.bar.geometry()))
