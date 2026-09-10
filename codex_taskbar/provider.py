from datetime import datetime
import ctypes
import json
from pathlib import Path
import threading
import time
import sqlite3

from .codex_api import CodexApi, project_name
from .usage import UsageCursor, FIELDS, quota_windows
from .unread import UnreadState
from .preferences import write_json
from .resets import ResetLedger
from .side_chats import SideChats
from .task_statistics import TaskStatistics


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
        self.catalog_rows=None;self.project_names={}
        self.statistics_active=threading.Event()
        self.unread_state = UnreadState()
        self.side_reader=SideChats(cache_path=self.runtime_dir/'side_chat_links.json');self.side_rows=[]
        self.api = None
        self.reset_busy = False
        self.reset_request = None
        ctypes.windll.kernel32.GetTickCount64.restype = ctypes.c_ulonglong
        self.boot_time = time.time() - ctypes.windll.kernel32.GetTickCount64() / 1000
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def get(self):
        with self.lock:
            return self.snapshot

    def refresh(self):
        self.refresh_event.set()

    def set_statistics_active(self,active):
        if active:self.statistics_active.set()
        else:self.statistics_active.clear()

    def request_reset(self, account, credit_id):
        with self.lock:
            if self.reset_busy or not account or not credit_id:return False
            self.reset_busy = True
            self.reset_request = (account, credit_id)
            self.snapshot = {**self.snapshot, 'reset_busy': True}
        self.refresh_event.set()
        return True

    def _process_reset(self, api):
        with self.lock:
            request = self.reset_request
            self.reset_request = None
        if not request:return
        try:
            raw=api.call('account/rateLimits/read')
            if not quota_windows(raw):raise ValueError('Quota unavailable before reset')
            self.resets.observe(raw)
            params = self.resets.begin(*request)
            self._record_quota(quota_windows(raw))
            outcome = api.call('account/rateLimitResetCredit/consume', params).get('outcome')
            self.resets.finish(outcome)
        except Exception as exc:
            self.resets.failed()
            print(f'Reset: {type(exc).__name__}: {exc}', flush=True)
        finally:
            with self.lock:self.reset_busy = False
            self.refresh_event.set()

    def _record_quota(self,quota):
        week=next((w for w in quota if w['minutes']==10080),None)
        if week:
            self.quota_history.append({'at':time.time(),'used':100-week['remaining'],'reset':week['resets_at']})
            self.quota_history=[s for s in self.quota_history if s['at']>=time.time()-8*86400]
            try:write_json(self.quota_history_path,self.quota_history)
            except OSError:pass

    def _publish(self, threads, projects, cursors, quota, quota_at, error, last_turns=None, quota_error=None):
        totals = {key: 0 for key in FIELDS}
        tasks = []
        recent = []
        daily = {}
        newest_usage = None
        native_running=[]
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
            if running:native_running.append(thread['id'])
            daily_seconds=cursor.elapsed_today(include_running=running)
            ended_at = cursor.ended_at
            if failed and cursor.running:
                end=turn.get('completedAt')
                daily_seconds=cursor.elapsed_today(datetime.fromtimestamp(end).astimezone()) if end is not None else None
                ended_at=datetime.fromtimestamp(end).astimezone().isoformat() if end is not None else None
            round_seconds=None
            if cursor.duration_known and cursor.started_at and (running or ended_at):
                end_time=datetime.now().astimezone() if running else datetime.fromisoformat(ended_at)
                round_seconds=max(0, int((end_time-datetime.fromisoformat(cursor.started_at)).total_seconds()))
            names=getattr(self,'project_names',{})
            task = {"id": thread["id"], "title": thread.get("name") or "",
                              "project": names[thread['id']] if thread['id'] in names else project_name(thread, projects), "tokens": cursor.daily["total_tokens"],
                              "started_at": cursor.started_at, "usage_at": cursor.usage_at,
                              "ended_at": ended_at, "activity_at": cursor.activity_at,
                              "run_tokens": cursor.run_tokens, "running": running, "status": status,
                              "needs_input":bool(cursor.pending_input and running),
                              "daily_seconds": daily_seconds, "round_seconds": round_seconds,
                              "unread": (cursor.completion_kind == 'task_complete' and not running and not failed
                                         and thread['id'] in unread_ids) if unread_ids is not None else None}
            sides=[s for s in getattr(self,'side_rows',[]) if s['parent_id']==thread['id']]
            active=[s for s in sides if s['running']]
            unread_sides=[s for s in sides if s.get('completion_kind')=='task_complete'
                          and unread_ids is not None and s['id'] in unread_ids]
            if unread_sides:
                task['side_chat']=True
                latest=max(unread_sides,key=lambda s:s['activity_at'])
                primary_at=datetime.fromisoformat(task['activity_at']).timestamp() if task['activity_at'] else 0
                if not running and (latest['activity_at']>=primary_at or status=='idle'):
                    use_side_time=not task['unread'] or latest['activity_at']>=primary_at
                    task.update(unread=True,status='idle')
                    if use_side_time:
                        start,end=latest.get('started_at'),latest.get('ended_at')
                        task['started_at']=datetime.fromtimestamp(start).astimezone().isoformat() if start is not None else None
                        task['ended_at']=datetime.fromtimestamp(end).astimezone().isoformat() if end is not None else None
                        task['round_seconds']=max(0,int(end-start)) if start is not None and end is not None else None
            if sides:
                task['activity_at']=max([task['activity_at'] or '']+[datetime.fromtimestamp(s['activity_at']).astimezone().isoformat() for s in sides])
            if active:
                task.update(running=True,status='running',unread=False,side_chat=True)
                if not running:
                    start=min(s['started_at'] for s in active if s.get('started_at') is not None)
                    task['started_at']=datetime.fromtimestamp(start).astimezone().isoformat()
                    task['ended_at']=None;task['round_seconds']=max(0,int(time.time()-start))
            if task['running']:
                tasks.append(task)
            elif task['activity_at'] and datetime.fromisoformat(task['activity_at']).astimezone().date() == datetime.now().astimezone().date():
                recent.append(task)
        tasks.sort(key=lambda t: (t["project"], t["started_at"] or "", t["id"]))
        from .usage import daily_quota_text
        week = next((w for w in quota if w["label"] == "周"), None)
        snapshot = {"tasks": tasks, "recent_tasks": recent, "quota": quota, "quota_updated_at": quota_at,
                    "catalog":getattr(self,'catalog_rows',None),
                    "task_statistics":self.statistics.view(native_running) if hasattr(self,'statistics') else {},
                    "unread_count": sum(task['unread'] is True for task in recent) if unread_ids is not None else None,
                    "history": daily, "daily_quota": daily_quota_text(self.quota_history, week),
                    "totals": totals, "usage_at": newest_usage, "loading": False,
                    "updated_at": datetime.now().astimezone().isoformat(), "error": error, "quota_error": quota_error,
                    "source": "本机 Codex 日志；Token 包含缓存输入，按模型步骤上报"}
        with self.lock:
            if hasattr(self,'resets'):
                snapshot.update(self.resets.view())
                period_ids={period[0] for period in self.resets.periods()}
                known=[c for c in cursors.values() if c.initialized]
                for event in snapshot['reset_events']:
                    if event['id'] in period_ids and known:
                        event['tokens']=sum(getattr(c,'period_totals',{}).get(event['id'],0) for c in known)
            snapshot['reset_busy']=getattr(self,'reset_busy',False)
            self.snapshot = snapshot
        self._write_snapshot()

    def _write_snapshot(self,force=False):
        now=time.monotonic()
        if not force and now-getattr(self,'snapshot_written_at',float('-inf'))<30:return
        snapshot={key:value for key,value in self.get().items() if key!='catalog'}
        temporary = self.runtime_dir / "snapshot.tmp"
        try:
            temporary.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
            temporary.replace(self.runtime_dir / "snapshot.json")
            self.snapshot_written_at=now
        except OSError:
            pass  # A diagnostic file reader must not interrupt the live display.

    def _run(self):
        self.resets=ResetLedger(self.runtime_dir/'reset_history.json')
        self.statistics=TaskStatistics(self.runtime_dir/'task_statistics.json')
        self.reset_request=getattr(self,'reset_request',None)
        self.reset_busy=getattr(self,'reset_busy',False)
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
                    if self.reset_request:self._process_reset(api)
                    now = time.monotonic()
                    refresh = self.refresh_event.is_set()
                    self.refresh_event.clear()
                    if refresh or now - quota_at_mono >= 30:
                        stage='quota';quota_at_mono=time.monotonic()
                        try:
                            raw=api.call("account/rateLimits/read")
                            received=quota_windows(raw)
                            if not received:raise ValueError('No quota windows returned')
                        except (RuntimeError,ValueError,TimeoutError) as exc:
                            message=f'{type(exc).__name__}: {exc}'
                            if message!=quota_error:print(f'{datetime.now().astimezone().isoformat()} quota: {message}',flush=True)
                            quota_error=message
                        else:
                            quota=received;quota_error=None
                            try:self.resets.observe(raw)
                            except (OSError,ValueError,TypeError) as exc:print(f'Reset history: {exc}',flush=True)
                            quota_at=datetime.now().astimezone().isoformat()
                            self._record_quota(quota)
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
                            self.project_names={t['id']:project_name(t,projects) for t in threads}
                            self.catalog_rows=[{'id':t['id'],'title':t.get('name') or '',
                                               'project':self.project_names[t['id']],'updated_at':t.get('updatedAt') or t.get('createdAt') or 0} for t in threads]
                            self.statistics.sync(threads)
                            live_ids={t['id'] for t in threads}
                            cursors={k:v for k,v in cursors.items() if k in live_ids}
                        if hasattr(self,'side_reader'):
                            try:self.side_rows=self.side_reader.update(threads)
                            except (OSError,ValueError,sqlite3.Error):pass
                    stage='local records'
                    periods=self.resets.periods()
                    for thread in threads:
                        path = thread.get("path")
                        if not path:
                            continue
                        try:
                            cursor = cursors.get(thread["id"])
                            week = next((w for w in quota if w["label"] == "周"), quota[0] if quota else None)
                            since = datetime.fromtimestamp(week["starts_at"]).astimezone() if week and week.get("starts_at") else datetime.now().astimezone().replace(hour=0,minute=0,second=0,microsecond=0)
                            if cursor is None or str(cursor.path) != path or cursor.since != since or cursor.periods!=periods:
                                cursor = cursors[thread["id"]] = UsageCursor(path, since=since,
                                    created_after=thread.get("createdAt") if thread.get("forkedFromId") else None,periods=periods)
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
                    if getattr(self,'statistics_active',None) and self.statistics_active.is_set():self.statistics.step()
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
            self._write_snapshot(force=True)
            self.statistics.save(force=True)
            if api:
                api.close()

    def stop(self):
        self.stop_event.set()
        if self.api:
            self.api.close()
        self.thread.join(timeout=2)
