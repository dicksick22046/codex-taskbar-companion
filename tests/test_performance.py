import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from codex_taskbar import app
from codex_taskbar.provider import Provider
from tests import test_interactions as fixtures


class RenderingBudgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.application=app.QApplication.instance() or app.QApplication([])

    def setUp(self):fixtures.InteractionTests.setUp(self)
    def tearDown(self):fixtures.InteractionTests.tearDown(self)

    def test_unchanged_ticks_keep_visibility_checks_without_redrawing(self):
        self.bar.settings['show_tasks']=False
        with patch('codex_taskbar.app.windows.placement',return_value=(0,900,1200,30,1,False)),patch.object(self.bar,'ensure_visible') as visible, \
             patch('codex_taskbar.app.windows.follow_taskbar'),patch.object(self.bar,'track_pointer'),patch.object(self.bar,'update') as draw:
            self.bar.tick();draw.reset_mock();visible.reset_mock()
            for _ in range(100):self.bar.tick()
            self.assertEqual(visible.call_count,100);draw.assert_not_called()
            self.data['daily_quota']='13%';self.bar.tick();draw.assert_called()

    def test_running_clock_paints_only_its_region_and_stops_without_activity(self):
        with patch.object(self.bar,'isVisible',return_value=True),patch.object(self.bar,'update') as draw:
            self.bar.animation.start(33)
            self.bar.animate()
            self.assertTrue(self.bar.animation.isActive());self.assertEqual(draw.call_count,1)
            rect=next(rect for mode,rect,task in self.bar.hit_regions if mode=='running')
            self.assertEqual(draw.call_args.args,(rect.toAlignedRect(),));draw.reset_mock()
            self.bar.settings['show_tasks']=False;self.bar.animate();draw.assert_not_called()
            self.assertFalse(self.bar.animation.isActive())
            self.bar.settings['show_tasks']=True;self.bar.motion_enabled=False;self.bar.animate();draw.assert_not_called()

    def test_settings_status_does_not_reread_startup_or_rebuild_controls(self):
        with patch('codex_taskbar.settings_ui.startup.enabled',return_value=False):dialog=app.SettingsDialog(self.bar)
        with patch('codex_taskbar.settings_ui.startup.enabled') as startup,patch.object(dialog.capsule,'setItemText') as text:
            for _ in range(100):dialog.refresh_status()
            self.data['error']='fixture';dialog.refresh_status()
            self.assertIn('Some data',dialog.connection.text())
            startup.assert_not_called();text.assert_not_called()
        dialog.close();dialog.deleteLater()


class DiagnosticWriteTests(unittest.TestCase):
    def test_memory_is_current_while_diagnostic_writes_are_bounded_and_flushable(self):
        with tempfile.TemporaryDirectory() as folder:
            provider=Provider.__new__(Provider);provider.runtime_dir=Path(folder);provider.lock=threading.Lock()
            provider.snapshot={'value':1}
            with patch('codex_taskbar.provider.time.monotonic',return_value=0):provider._write_snapshot()
            provider.snapshot={'value':2}
            with patch('codex_taskbar.provider.time.monotonic',return_value=29):provider._write_snapshot()
            path=Path(folder)/'snapshot.json'
            self.assertEqual(json.loads(path.read_text())['value'],1);self.assertEqual(provider.get()['value'],2)
            with patch('codex_taskbar.provider.time.monotonic',return_value=30):provider._write_snapshot()
            self.assertEqual(json.loads(path.read_text())['value'],2)
            provider.snapshot={'value':3}
            with patch('codex_taskbar.provider.time.monotonic',return_value=31):provider._write_snapshot(force=True)
            self.assertEqual(json.loads(path.read_text())['value'],3)
