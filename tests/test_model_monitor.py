import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from codex_taskbar.model_monitor import ModelMonitor, parse_trace_metadata


class ModelTraceTests(unittest.TestCase):
    def test_projects_only_server_model_metadata(self):
        text = (
            'turn{thread_id=thr-123}:run_turn{model=gpt-6-astra} '
            'SSE event: {"type":"response.created","response":{'
            '"id":"resp_123","model":"gpt-5.6-luna","output":[]}}'
        )
        rows = parse_trace_metadata(text, '2026-09-29T01:02:03+00:00')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].requested_model, 'gpt-6-astra')
        self.assertEqual(rows[0].server_model, 'gpt-5.6-luna')
        self.assertTrue(rows[0].mismatch)
        self.assertEqual(rows[0].response_id, 'resp_123')

    def test_escaped_trace_and_completed_update(self):
        text = r'payload=\{"type":"response.completed","response":\{"model":"gpt-6-astra","id":"resp_1"\}\}'
        rows = parse_trace_metadata(text)
        self.assertEqual([(row.response_id, row.status) for row in rows], [('resp_1', 'completed')])

    def test_monitor_persists_sanitized_records_only(self):
        with tempfile.TemporaryDirectory() as folder:
            monitor = ModelMonitor(Path(folder))
            monitor.enabled = True
            db = Path(folder) / 'logs_2.sqlite'
            import sqlite3
            connection = sqlite3.connect(db)
            try:
                connection.execute('create table logs (id integer, ts integer, target text, feedback_log_body text)')
                body = 'model=gpt-6-astra ' + (
                    '{"type":"response.completed","response":{'
                    '"id":"resp_1","model":"gpt-6-astra","input":"secret"}}')
                connection.execute('insert into logs values (1, 1, ?, ?)', ('codex_api::endpoint::responses_websocket', body))
                connection.commit()
            finally:
                connection.close()
            monitor.logs_path = db
            monitor.poll()
            saved = json.loads((Path(folder) / 'model_monitor.json').read_text(encoding='utf-8'))
            self.assertEqual(saved['records'][0]['server_model'], 'gpt-6-astra')
            self.assertNotIn('secret', json.dumps(saved))

    def test_missing_model_is_not_fabricated(self):
        self.assertEqual(parse_trace_metadata(
            'model=gpt-6-astra {"type":"response.completed","response":{"id":"resp_2"}}'), [])

    def test_proxy_model_is_sanitized_without_a_log_database(self):
        with tempfile.TemporaryDirectory() as folder:
            monitor = ModelMonitor(Path(folder));monitor.enabled=True;monitor.logs_path=Path(folder)/'missing.sqlite'
            monitor._proxy_models.put(('gpt-6.1-sol','2026-09-30T01:02:03+00:00'))
            monitor.poll()
            self.assertEqual(monitor.records[0]['server_model'],'gpt-6.1-sol')
            self.assertEqual(monitor.records[0]['status'],'observed')

    def test_manual_handoff_honors_explicit_restart_even_with_active_tasks(self):
        with tempfile.TemporaryDirectory() as folder, patch('codex_taskbar.model_monitor.CodexLauncher') as launcher, patch('codex_taskbar.model_monitor.ModelProxy') as proxy:
            proxy.return_value.start.return_value=proxy.return_value
            monitor=ModelMonitor(Path(folder));monitor.set_enabled(True)
            self.assertTrue(monitor.manual_handoff(['running-task']))
            launcher.return_value.graceful_restart.assert_called_once_with(proxy=proxy.return_value)

    def test_manual_handoff_reports_codex_close_timeout_clearly(self):
        with tempfile.TemporaryDirectory() as folder, patch('codex_taskbar.model_monitor.CodexLauncher') as launcher:
            launcher.return_value.graceful_restart.side_effect=RuntimeError('still open')
            monitor=ModelMonitor(Path(folder));monitor.set_enabled(True)
            self.assertFalse(monitor.manual_handoff([]))
            self.assertEqual(monitor.error,'codex_busy')


if __name__ == '__main__':
    unittest.main()
