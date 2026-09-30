"""Local, metadata-only model routing monitor for future Codex sessions."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import time
import queue
from typing import Iterable

from .preferences import write_json
from . import windows
from .model_proxy import ModelProxy


_EVENT_RE = re.compile(
    r'"type"\s*:\s*"response\.(created|completed)".*?'
    r'"response"\s*:\s*\{(?P<body>.*?)\}', re.S)
_ID_RE = re.compile(r'"id"\s*:\s*"([^"]+)"')
_MODEL_RE = re.compile(r'"model"\s*:\s*"([^"]+)"')
_REQUEST_MODEL_RE = re.compile(r'\bmodel=([A-Za-z0-9._-]+)')
_THREAD_RE = re.compile(r'\bthread_id=([0-9a-f-]{20,})')
_TURN_RE = re.compile(r'\bturn_id=([0-9a-f-]{20,})')


@dataclass(frozen=True)
class ModelObservation:
    response_id: str
    requested_model: str | None
    server_model: str | None
    thread_id: str | None
    turn_id: str | None
    at: str
    status: str

    @property
    def mismatch(self):
        return bool(self.requested_model and self.server_model
                    and self.requested_model.lower() != self.server_model.lower())


def parse_trace_metadata(text: str, at: str | None = None) -> list[ModelObservation]:
    """Project response model metadata from one trace record; never return body text."""
    if not isinstance(text, str) or 'response.' not in text:
        return []
    # JSON in tracing records may be escaped once by the log formatter.
    normalized = text.replace(r'\"', '"').replace(r'\{', '{').replace(r'\}', '}')
    requested = _REQUEST_MODEL_RE.search(normalized)
    thread = _THREAD_RE.search(normalized)
    turn = _TURN_RE.search(normalized)
    stamp = at or datetime.now(timezone.utc).isoformat()
    result = []
    for match in _EVENT_RE.finditer(normalized):
        body = match.group('body')
        response_id = _ID_RE.search(body)
        server_model = _MODEL_RE.search(body)
        if not response_id or not server_model:
            continue
        result.append(ModelObservation(
            response_id=response_id.group(1),
            requested_model=requested.group(1) if requested else None,
            server_model=server_model.group(1),
            thread_id=thread.group(1) if thread else None,
            turn_id=turn.group(1) if turn else None,
            at=stamp,
            status=match.group(1),
        ))
    return result


class CodexLauncher:
    """Launch a monitored Desktop Codex child without touching system proxy settings."""

    TRACE_LOG = 'tungstenite::protocol=trace,tungstenite::protocol::frame=off'

    def __init__(self):
        self.process = None

    @staticmethod
    def executable():
        roots = []
        windows_apps = Path(os.environ.get('ProgramW6432', r'C:\Program Files')) / 'WindowsApps'
        try:
            roots = sorted(windows_apps.glob('OpenAI.Codex_*/*/ChatGPT.exe'),
                           key=lambda p: p.stat().st_mtime, reverse=True)
        except OSError:
            roots = []
        return roots[0] if roots else None

    def launch(self, proxy=None):
        executable = self.executable()
        if executable is None:
            raise FileNotFoundError('Codex Desktop executable not found')
        environment = os.environ.copy()
        environment['RUST_LOG'] = self.TRACE_LOG
        args = [str(executable)]
        if proxy is not None:
            args.extend(proxy.launch_args())
            environment.update(proxy.environment())
        self.process = subprocess.Popen(args, env=environment,
                                        cwd=str(executable.parent),
                                        creationflags=0x08000000)
        return self.process.pid

    @staticmethod
    def _process_ids():
        ids=[]
        for name in ('ChatGPT.exe','Codex.exe'):
            try:
                output=subprocess.check_output(['tasklist','/FI',f'IMAGENAME eq {name}','/FO','CSV','/NH'],
                                               text=True,encoding='mbcs',errors='replace',creationflags=0x08000000)
            except (OSError,subprocess.SubprocessError):
                continue
            for line in output.splitlines():
                fields=[part.strip('"') for part in line.split('","')]
                if len(fields)>=2 and fields[0].lower()==name.lower():
                    try:ids.append(int(fields[1]))
                    except ValueError:pass
        return sorted(set(ids))

    def graceful_restart(self, proxy=None, force=False):
        """Restart Desktop; force is reserved for the explicit manual action."""
        old=windows.process_window_ids(self._process_ids())
        windows.request_close_process_windows(old)
        deadline=time.monotonic()+20
        while old and time.monotonic()<deadline:
            time.sleep(.25)
            if not set(old).intersection(self._process_ids()):break
        remaining=set(old).intersection(self._process_ids())
        if remaining and force:
            for pid in remaining:
                subprocess.run(['taskkill','/PID',str(pid),'/T','/F'],capture_output=True,creationflags=0x08000000)
            deadline=time.monotonic()+5
            while remaining and time.monotonic()<deadline:
                time.sleep(.25);remaining=set(old).intersection(self._process_ids())
        if remaining:
            raise RuntimeError('Codex Desktop did not close for monitoring handoff')
        return self.launch(proxy=proxy)


class ModelMonitor:
    """Read-only SQLite tailer and sanitized local observation ledger."""

    LIMIT = 100

    def __init__(self, runtime_dir):
        self.runtime_dir = Path(runtime_dir)
        self.path = self.runtime_dir / 'model_monitor.json'
        self.logs_path = Path.home() / '.codex' / 'logs_2.sqlite'
        self.enabled = False
        self.phase = 'off'
        self.last_id = 0
        self.error = None
        self.records: list[dict] = []
        self._proxy_models = queue.Queue()
        self.proxy = None
        self._load()

    def _load(self):
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            data = {}
        if not isinstance(data, dict):
            return
        self.last_id = data.get('last_id') if type(data.get('last_id')) is int else 0
        self.phase = data.get('phase') if data.get('phase') in ('off','waiting','restarting','waiting_response','monitoring','error') else 'off'
        self.error = data.get('error') if isinstance(data.get('error'), str) else None
        rows = data.get('records')
        if isinstance(rows, list):
            self.records = [row for row in rows[-self.LIMIT:] if self._valid(row)]

    @staticmethod
    def _valid(row):
        return isinstance(row, dict) and isinstance(row.get('response_id'), str) and \
            row.get('status') in ('created', 'completed', 'observed') and \
            isinstance(row.get('at'), str)

    def _save(self):
        try:
            write_json(self.path, {'last_id': self.last_id, 'phase': self.phase, 'error': self.error,
                                   'records': self.records[-self.LIMIT:]})
        except OSError:
            pass

    def set_enabled(self, enabled, active=False):
        self.enabled = bool(enabled)
        if not self.enabled:
            self.phase = 'off'
            if self.proxy:
                self.proxy.close();self.proxy=None
        elif self.proxy is None and self.phase in ('restarting','waiting_response','monitoring'):
            self.phase = 'waiting'
        elif active:
            self.phase = 'waiting'
        elif not self.records or self.phase in ('off', 'error'):
            self.phase = 'waiting'
        self._save()

    def poll(self):
        if not self.enabled:
            return
        try:
            changed = self._drain_proxy_models()
            rows = []
            if self.logs_path.exists():
                db = sqlite3.connect(self.logs_path.as_uri() + '?mode=ro', uri=True, timeout=0.2)
                try:
                    rows = db.execute(
                        "SELECT id, ts, feedback_log_body FROM logs "
                        "WHERE id>? AND target IN (?,?) AND feedback_log_body LIKE ? "
                        "ORDER BY id LIMIT 500",
                        (self.last_id, 'codex_api::endpoint::responses_websocket',
                         'codex_api::sse::responses', '%response.%')).fetchall()
                finally:
                    db.close()
            for ident, timestamp, body in rows:
                self.last_id = max(self.last_id, int(ident))
                for observation in parse_trace_metadata(body or '',
                                                        datetime.fromtimestamp(timestamp, timezone.utc).isoformat()):
                    item = asdict(observation)
                    item['mismatch'] = observation.mismatch
                    self.records = [row for row in self.records
                                    if row.get('response_id') != observation.response_id]
                    self.records.append(item)
                    changed = True
            if changed:
                self.phase = 'monitoring'
            if changed or rows:
                self._save()
            self.error = None
        except (OSError, sqlite3.Error, ValueError) as exc:
            self.phase = 'error'
            self.error = type(exc).__name__

    def close(self):
        if self.proxy:
            self.proxy.close();self.proxy=None
        self._save()

    def _drain_proxy_models(self):
        changed = False
        while True:
            try:
                server_model, stamp = self._proxy_models.get_nowait()
            except queue.Empty:
                break
            requested = self._latest_requested_model()
            item = {'response_id': '',
                    'requested_model': requested, 'server_model': server_model,
                    'thread_id': None, 'turn_id': None, 'at': stamp,
                    'status': 'observed',
                    'mismatch': bool(requested and requested.lower()!=server_model.lower())}
            self.records = [row for row in self.records if row.get('response_id') != item['response_id']]
            self.records.append(item);changed=True
        return changed

    def _latest_requested_model(self):
        try:
            db=sqlite3.connect(self.logs_path.as_uri()+'?mode=ro',uri=True,timeout=.2)
            try:
                rows=db.execute("SELECT feedback_log_body FROM logs WHERE target IN (?,?) AND feedback_log_body LIKE '%model=%' ORDER BY id DESC LIMIT 1",
                                ('codex_api::endpoint::responses_websocket','codex_api::sse::responses')).fetchall()
            finally:db.close()
            match=_REQUEST_MODEL_RE.search(rows[0][0]) if rows else None
            return match.group(1) if match else None
        except (OSError,sqlite3.Error):
            return None

    def view(self):
        latest = self.records[-1] if self.records else None
        mismatch_count = sum(row.get('mismatch') is True for row in self.records)
        return {'enabled': self.enabled, 'phase': self.phase, 'error': self.error,
                'latest': dict(latest) if latest else None,
                'mismatch_count': mismatch_count,
                'records': [dict(row) for row in self.records[-self.LIMIT:]]}

    def manual_handoff(self, active_tasks):
        """Restart Codex after an explicit user action, regardless of task state."""
        if not self.enabled or self.phase in ('restarting','waiting_response'):
            return False
        self.phase='restarting';self.error=None;self._save()
        try:
            if self.proxy is None:
                self.proxy=ModelProxy(lambda model,at:self._proxy_models.put((model,at))).start()
            CodexLauncher().graceful_restart(proxy=self.proxy,force=True)
            self.phase='waiting_response'
            result=True
        except (OSError,RuntimeError,subprocess.SubprocessError) as exc:
            if self.proxy:
                self.proxy.close();self.proxy=None
            self.phase='error';self.error='codex_busy' if isinstance(exc,RuntimeError) else type(exc).__name__
            result=False
        self._save()
        return result
