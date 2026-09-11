"""Read ephemeral side-chat lifecycle metadata from the current desktop logs."""
import ctypes
from contextlib import closing
from ctypes import wintypes as w
from datetime import datetime
from pathlib import Path
import json
import re
import sqlite3
from .preferences import write_json


def process_alive(pid):
    kernel=ctypes.windll.kernel32
    kernel.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD];kernel.OpenProcess.restype=w.HANDLE
    kernel.GetExitCodeProcess.argtypes=[w.HANDLE,ctypes.POINTER(w.DWORD)]
    kernel.CloseHandle.argtypes=[w.HANDLE]
    handle=kernel.OpenProcess(0x1000,False,pid)
    if not handle:return False
    try:
        code=w.DWORD()
        return bool(kernel.GetExitCodeProcess(handle,ctypes.byref(code))) and code.value==259
    finally:kernel.CloseHandle(handle)


class SideChats:
    def __init__(self,logs=None,core_db=None,state_db=None,cache_path=None):
        home=Path.home()
        self.log_roots=[Path(logs)] if logs else [home/'AppData/Local/Codex/Logs',
            *(home/'AppData/Local/Packages').glob('OpenAI.Codex_*/LocalCache/Local/Codex/Logs')]
        self.core_db=Path(core_db or home/'.codex/logs_2.sqlite')
        self.state_db=Path(state_db or home/'.codex/state_5.sqlite')
        self.cache_path=Path(cache_path) if cache_path else None
        self.saved_parents={}
        self.session=None;self.offsets={};self.pending={};self.forks={};self.parents={};self.states={}

    def restore_parents(self):
        if not self.cache_path:return
        try:cached=json.loads(self.cache_path.read_text(encoding='utf-8'))
        except (OSError,ValueError):return
        if not isinstance(cached,dict) or cached.get('session')!=self.session:return
        parents=cached.get('parents')
        if isinstance(parents,dict):
            self.parents={child:parent for child,parent in parents.items() if isinstance(child,str) and isinstance(parent,str) and child and parent and child!=parent}
            self.saved_parents=dict(self.parents)

    def update(self,threads):
        groups=[list(root.rglob('codex-desktop-*-t0-*.log')) for root in self.log_roots]
        groups=[files for files in groups if files]
        if not groups:return []
        files=max(groups,key=lambda items:max(p.stat().st_mtime for p in items))
        latest=max(files,key=lambda p:p.stat().st_mtime)
        session=latest.name.split('-t0-')[0]
        pid=int(session.rsplit('-',1)[1])
        if session!=self.session or not process_alive(pid):
            self.session=session;self.offsets.clear();self.pending.clear();self.forks.clear();self.parents.clear();self.states.clear()
            self.saved_parents={}
            if not process_alive(pid):return []
            self.restore_parents()
        events=[]
        for path in sorted((p for p in files if p.name.startswith(session+'-t0-')),key=lambda p:p.stat().st_mtime):
            size=path.stat().st_size;offset=self.offsets.get(path,0)
            if size==offset:continue
            if size<offset:offset=0;self.pending.pop(path,None)
            with path.open('rb') as stream:
                stream.seek(offset);data=self.pending.get(path,b'')+stream.read();self.offsets[path]=stream.tell()
            lines=data.split(b'\n');self.pending[path]=lines.pop()
            for raw in lines:
                line=raw.decode('utf-8',errors='replace')
                response=bool(re.match(r'^\S+ info \[AppServerConnection\] response_routed ',line))
                completed=bool(re.match(r'^\S+ info \[electron-message-handler\] \[desktop-notifications\] show turn-complete ',line))
                idle=bool(re.match(r'^\S+ info \[browser-session-registry\] IAB_LIFECYCLE ended browser use session activity ',line))
                if not response and not completed and not idle:continue
                values=dict(re.findall(r'([A-Za-z]+)=([^\s]+)',line))
                if response and (values.get('errorCode')!='null' or values.get('method') not in ('thread/fork','turn/start','turn/interrupt')):continue
                at=datetime.fromisoformat(line.split(' ',1)[0].replace('Z','+00:00')).timestamp()
                events.append((at,'complete' if completed else 'idle' if idle else values['method'],values))
        for at,kind,values in sorted(events,key=lambda e:e[0]):
            thread=values.get('conversationId')
            if not thread or thread=='null':continue
            if kind=='thread/fork':
                self.forks[values['requestId']]={'parent':thread,'at':at,'duration':float(values.get('durationMs',0))/1000}
            else:
                previous=self.states.get(thread)
                if previous and previous['activity_at']>=at:continue
                # Cleanup confirms inactivity but cannot replace a known terminal reason.
                if kind=='idle' and previous and not previous['running']:continue
                self.states[thread]={'id':thread,'running':kind=='turn/start',
                    'completion_kind':'task_complete' if kind=='complete' else 'turn_aborted' if kind=='turn/interrupt' else 'session_idle' if kind=='idle' else None,
                    'started_at':at if kind=='turn/start' else (previous or {}).get('started_at'),
                    'ended_at':None if kind=='turn/start' else at,'activity_at':at}
        if self.forks and self.core_db.exists() and self.state_db.exists():
            with closing(sqlite3.connect(self.core_db.as_uri()+'?mode=ro',uri=True)) as core,closing(sqlite3.connect(self.state_db.as_uri()+'?mode=ro',uri=True)) as state:
                known={t['id'] for t in threads}
                for request,fork in list(self.forks.items()):
                    if fork['parent'] not in known:continue
                    rows=core.execute('select distinct thread_id from logs where ts between ? and ? and thread_id is not null and feedback_log_body like ?',
                        (int(fork['at']-fork['duration'])-1,int(fork['at'])+2,'app_server.request{%rpc.request_id='+request+'%')).fetchall()
                    children={row[0] for row in rows if row[0]!=fork['parent']}
                    if len(children)!=1:continue
                    child=children.pop()
                    if not state.execute('select 1 from threads where id=?',(child,)).fetchone():self.parents[child]=fork['parent']
                    del self.forks[request]
        if self.cache_path and self.parents!=self.saved_parents:
            try:write_json(self.cache_path,{'session':self.session,'parents':self.parents})
            except OSError:pass
            else:self.saved_parents=dict(self.parents)
        return [{**self.states[child],'parent_id':parent} for child,parent in self.parents.items() if child in self.states]
