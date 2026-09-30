"""Controlled Qt model-check views; no Codex process or desktop interaction."""
from datetime import datetime, timezone
import unittest
from unittest.mock import patch
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from codex_taskbar import app
from tests import test_interactions as fixtures


class ModelMonitorUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixtures.InteractionTests.setUpClass()
    def setUp(self):
        fixtures.InteractionTests.setUp(self)
        self.application=fixtures.InteractionTests.application
    def tearDown(self):fixtures.InteractionTests.tearDown(self)

    def record(self,number=0,requested='gpt-6-astra',server='gpt-6-astra'):
        return dict(response_id=f'resp_fixture_{number}',requested_model=requested,
                    server_model=server,at=datetime(2026,9,30,1,42,tzinfo=timezone.utc).isoformat(),
                    status='completed',mismatch=bool(requested and server and requested!=server))

    def test_empty_settings_has_no_disabled_full_width_action(self):
        self.data['model_monitor']=dict(enabled=True,phase='waiting',records=[])
        with patch('codex_taskbar.settings_ui.startup.enabled',return_value=False):
            dialog=app.SettingsDialog(self.bar);self.bar.settings_dialog=dialog
            dialog.navigation.setCurrentRow(2);dialog.grab()
            self.assertTrue(dialog.model_monitor_button.isHidden())
            self.assertFalse(dialog.model_monitor_restart_button.isHidden())
        self.assertIn(self.bar.label('Enabled; restart Codex manually to begin monitoring.'),dialog.model_monitor_status.text())

    def test_settings_secondary_action_has_clearance_in_four_languages(self):
        self.data['model_monitor']=dict(enabled=True,phase='monitoring',records=[self.record()])
        with patch('codex_taskbar.settings_ui.startup.enabled',return_value=False):
            dialog=app.SettingsDialog(self.bar);self.bar.settings_dialog=dialog;dialog.resize(620,300)
            dialog.navigation.setCurrentRow(2)
            for language in app.LANGUAGES:
                self.bar.settings['language']=language;dialog.refresh();dialog.grab();self.application.processEvents();dialog.grab()
                button=dialog.model_monitor_button;card=dialog.model_monitor.row.parentWidget()
                box=button.rect().translated(button.mapTo(card,QPoint()))
                with self.subTest(language=language):
                    self.assertFalse(button.isHidden());self.assertTrue(button.isEnabled())
                    self.assertGreaterEqual(card.width()-box.right()-1,14)
                    self.assertGreaterEqual(card.height()-box.bottom()-1,14)
                    self.assertLess(button.width(),card.width()/2)
                    self.assertGreaterEqual(button.width(),button.fontMetrics().horizontalAdvance(button.text())+24)

    def test_popup_uses_shared_panel_contract_and_retains_all_recent_records(self):
        popup=app.ModelMonitorPopup(self.bar)
        self.addCleanup(popup.deleteLater);self.addCleanup(popup.close)
        self.assertIsInstance(popup,app.TaskPopup)
        self.data['model_monitor']=dict(enabled=True,phase='monitoring',records=[self.record(n) for n in range(100)])
        popup.refresh(self.data);popup.sync_units();popup.reposition()
        self.assertEqual(len(popup.rows),100)
        self.assertEqual(popup.rows[0]['response_id'],'resp_fixture_99')
        self.assertGreater(popup.full_height,popup.height())
        self.application.sendEvent(popup,QWheelEvent(QPointF(10,90),QPointF(10,90),QPoint(),QPoint(0,-120),Qt.MouseButton.NoButton,Qt.KeyboardModifier.NoModifier,Qt.ScrollPhase.NoScrollPhase,False))
        self.assertGreater(popup.scroll,0)
        scrolled=popup.scroll;popup.refresh(self.data);self.assertEqual(popup.scroll,scrolled)

    def test_popup_shows_time_response_and_unknown_request_without_claiming_match(self):
        popup=app.ModelMonitorPopup(self.bar)
        self.addCleanup(popup.deleteLater);self.addCleanup(popup.close)
        self.data['model_monitor']=dict(enabled=True,phase='monitoring',records=[self.record(requested=None)])
        popup.refresh(self.data)
        with patch('codex_taskbar.app.text',wraps=app.text) as drawn:popup.grab()
        labels=[call.args[3] for call in drawn.call_args_list]
        self.assertTrue(any(self.bar.label('Not verified') in value for value in labels))
        self.assertFalse(any(self.bar.label('Model matches') in value for value in labels))
        self.assertTrue(any('09.30' in value and ':' in value for value in labels))
        self.assertTrue(any('resp_fixture_0' in value for value in labels))
