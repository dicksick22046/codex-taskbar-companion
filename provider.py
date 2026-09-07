from datetime import datetime
import ctypes
import json
from pathlib import Path
import threading
import time

from codex_api import CodexApi, project_name
from usage import UsageCursor, FIELDS, quota_windows
from unread import UnreadState
from preferences import write_json


class Provider:
    def __init__(self, runtime_dir):
        self.runtime_dir = Path(runtime_dir)
        self.runtime_dir.mkdir(exist_ok=True)
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.refresh_event = threading.Event()
        self.quota_history_path = self.runtime_dir / "quota_history.json"
        try:
            self.quota_history = json.loads(self.quota_history_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.quota_history = []
        self.snapshot = {"tasks": [], "quota": [], "totals": None, "loading": True}
        self.unread_state = UnreadState()
        self.api = None
        ctypes.windll.kernel32.GetTickCount64.restype = ctypes.c_ulonglong
        self.boot_time = time.time() - ctypes.windll.kernel32.GetTickCount64() / 1000
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def get(self):
        with self.lock:
            return self.snapshot

    def refresh(self):
        self.refresh_event.set()

    def _publish(self, threads, projects, cursors, quota, quota_at, error, last_turns=None, quota_error=None):
        totals = {key: 0 for key in FIELDS}
        tasks = []
        recent = []
        daily = {}
        newest_usage = None
        unread_ids=self.unread_state.read()
        for thread in threads:
            cursor = cursors.get(thread["id"])
            if cursor is None or not cursor.initialized:
                continue
            for key in FIELDS:
                totals[key] += cursor.daily[key]
            for day, tokens in cursor.by_day.items():
                daily[day] = daily.get(day, 0) + tokens
            if cursor.usage_at and (not newest_usage or cursor.usage_at > newest_usage):
                newest_usage = cursor.usage_at
            # An unfinished event from before this boot cannot be a live process.
            started = datetime.fromisoformat(cursor.started_at).timestamp() if cursor.started_at else 0
            running = cursor.running and started >= self.boot_time
            turn=(last_turns or {}).get(thread['id']) or {}
            failed=turn.get('id')==cursor.turn and turn.get('status')=='failed' and bool(turn.get('error'))
            status='failed' if failed else 'running' if running else 'stopped' if cursor.completion_kind=='turn_aborted' else 'idle'
            if failed:running=False
            daily_seconds=cursor.elapsed_today(include_running=running)
            if failed and cursor.running:
                end=turn.get('completedAt')
                daily_seconds=cursor.elapsed_today(datetime.fromtimestamp(end).astimezone()) if end is not None else None
            task = {"id": thread["id"], "title": thread.get("name") or "未命名任务",
                              "project": project_name(thread, projects), "tokens": cursor.daily["total_tokens"],
                              "started_at": cursor.started_at, "usage_at": cursor.usage_at,
                              "ended_at": cursor.ended_at, "activity_at": cursor.activity_at,
                              "run_tokens": cursor.run_tokens, "running": running, "status": status,
                              "daily_seconds": daily_seconds,
                              "unread": (cursor.completion_kind == 'task_complete' and not running and not failed
                                         and thread['id'] in unread_ids) if unread_ids is not None else None}
            if running:
                tasks.append(task)
            elif cursor.activity_at and datetime.fromisoformat(cursor.activity_at).astimezone().date() == datetime.now().astimezone().date():
                recent.append(task)
        tasks.sort(key=lambda t: (t["project"], t["started_at"] or "", t["id"]))
        from usage import daily_quota_text
        week = next((w for w in quota if w["label"] == "周"), None)
        snapshot = {"tasks": tasks, "recent_tasks": recent, "quota": quota, "quota_updated_at": quota_at,
                    "unread_count": sum(task['unread'] is True for task in recent) if unread_ids is not None else None,
                    "history": daily, "daily_quota": daily_quota_text(self.quota_history, week),
                    "totals": totals, "usage_at": newest_usage, "loading": False,
                    "updated_at": datetime.now().astimezone().isoformat(), "error": error, "quota_error": quota_error,
                    "source": "本机 Codex 日志；Token 包含缓存输入，按模型步骤上报"}
        with self.lock:
            self.snapshot = snapshot
        temporary = self.runtime_dir / "snapshot.tmp"
        try:
            temporary.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
            temporary.replace(self.runtime_dir / "snapshot.json")
        except OSError:
            pass  # A diagnostic file reader must not interrupt the live display.

    def _run(self):
        api = None
        projects, threads, cursors, quota = [], [], {}, []
        last_turns,turn_signatures,last_turn_errors={},{},{}
        catalog_at = quota_at_mono = 0
        quota_at = None
        error = None;quota_error=None;catalog_error=None;stage='connection'
        try:
            while not self.stop_event.is_set():
                try:
                    if api is None:
                        stage='connection'
                        api = CodexApi()
                        self.api = api
                    now = time.monotonic()
                    refresh = self.refresh_event.is_set()
                    self.refresh_event.clear()
                    if refresh or now - quota_at_mono >= 30:
                        stage='quota';quota_at_mono=time.monotonic()
                        try:
                            received=quota_windows(api.call("account/rateLimits/read"))
                            if not received:raise ValueError('No quota windows returned')
                        except (RuntimeError,ValueError,TimeoutError) as exc:
                            message=f'{type(exc).__name__}: {exc}'
                            if message!=quota_error:print(f'{datetime.now().astimezone().isoformat()} quota: {message}',flush=True)
                            quota_error=message
                        else:
                            quota=received;quota_error=None
                            quota_at=datetime.now().astimezone().isoformat()
                            week=next((w for w in quota if w["label"]=="周"),None)
                            if week:
                                self.quota_history.append({"at":time.time(),"used":100-week["remaining"],"reset":week["resets_at"]})
                                self.quota_history=[s for s in self.quota_history if s["at"]>=time.time()-8*86400]
                                try:write_json(self.quota_history_path,self.quota_history)
                                except OSError:pass
                    catalog_due=refresh or now - catalog_at >= 5
                    if catalog_due:
                        stage='catalog';catalog_at=now
                        try:new_projects,new_threads=api.catalog()
                        except (RuntimeError,TimeoutError) as exc:
                            message=f'{type(exc).__name__}: {exc}'
                            if message!=catalog_error:print(f'{datetime.now().astimezone().isoformat()} catalog: {message}',flush=True)
                            catalog_error=message
                        else:
                            projects,threads=new_projects,new_threads;catalog_error=None
                            live_ids={t['id'] for t in threads}
                            cursors={k:v for k,v in cursors.items() if k in live_ids}
                    stage='local records'
                    for thread in threads:
                        path = thread.get("path")
                        if not path:
                            continue
                        try:
                            cursor = cursors.get(thread["id"])
                            week = next((w for w in quota if w["label"] == "周"), quota[0] if quota else None)
                            since = datetime.fromtimestamp(week["starts_at"]).astimezone() if week and week.get("starts_at") else datetime.now().astimezone().replace(hour=0,minute=0,second=0,microsecond=0)
                            if cursor is None or str(cursor.path) != path or cursor.since != since:
                                cursor = cursors[thread["id"]] = UsageCursor(path, since=since,
                                    created_after=thread.get("createdAt") if thread.get("forkedFromId") else None)
                            cursor.update()
                        except OSError:
                            cursors.pop(thread["id"], None)
                    if catalog_due and not catalog_error:
                        today=datetime.now().astimezone().date()
                        for thread in threads:
                            cursor=cursors.get(thread['id'])
                            if not cursor or not cursor.activity_at or datetime.fromisoformat(cursor.activity_at).astimezone().date()!=today:continue
                            signature=(cursor.turn,cursor.offset,thread.get('updatedAt'))
                            if turn_signatures.get(thread['id'])==signature:continue
                            stage='latest turn'
                            try:last_turns[thread['id']]=api.latest_turn(thread['id'])
                            except (RuntimeError,TimeoutError) as exc:
                                message=f'{type(exc).__name__}: {exc}'
                                if last_turn_errors.get(thread['id'])!=message:print(f'{datetime.now().astimezone().isoformat()} latest turn: {message}',flush=True)
                                last_turn_errors[thread['id']]=message
                                continue
                            last_turn_errors.pop(thread['id'],None)
                            turn_signatures[thread['id']]=signature
                    error = catalog_error
                    self._publish(threads, projects, cursors, quota, quota_at, error,last_turns,quota_error)
                except Exception as exc:
                    error = f"{type(exc).__name__}: {exc}"
                    print(f"{datetime.now().astimezone().isoformat()} {stage}: {error}",flush=True)
                    if stage=="quota":quota_error=error
                    if api:
                        api.close()
                        api = None
                        self.api = None
                    with self.lock:
                        self.snapshot = {**self.snapshot, "error": error, "quota_error": quota_error}
                    self.stop_event.wait(5)
                self.stop_event.wait(1)
        finally:
            if api:
                api.close()

    def stop(self):
        self.stop_event.set()
        if self.api:
            self.api.close()
        self.thread.join(timeout=2)
