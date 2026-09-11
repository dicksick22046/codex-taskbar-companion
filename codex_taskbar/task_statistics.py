"""Bounded, resumable lifetime aggregates; canonical logs remain read-only."""
import hashlib
import json
import math
import re
from pathlib import Path
import time
from collections import deque
from .preferences import write_json
from .usage import event_from_line,LIFECYCLE


_HEADER=re.compile(rb'^\s*\{\s*"timestamp"\s*:\s*"[^"\\]*"\s*,\s*"type"\s*:\s*"([a-z_]+)"\s*,')
_PAYLOAD=re.compile(rb'\s*"payload"\s*:\s*\{\s*"type"\s*:\s*"([a-z_]+)"\s*[,}]')
_KINDS={kind.encode() for kind in LIFECYCLE}|{b'token_count'}


def irrelevant_record(line):
    """Fast path for canonical Codex envelopes; unknown layouts use the parser."""
    header=_HEADER.match(line)
    if not header:return False
    if header[1]!=b'event_msg':return True
    payload=_PAYLOAD.match(line,header.end())
    return bool(payload and payload[1] not in _KINDS)


class TaskStatistics:
    VERSION=2
    CHUNK=1024*1024

    def __init__(self,path):
        self.path=Path(path);self.entries={};self.sources={};self.missing=set();self.cursor=0;self.dirty=False;self.saved_at=time.monotonic()
        try:
            data=json.loads(self.path.read_text(encoding='utf-8'))
            if data.get('version')==self.VERSION and isinstance(data.get('entries'),dict):self.entries=data['entries']
        except (OSError,ValueError,AttributeError):pass
        for key,entry in list(self.entries.items()):
            required=('path','created','identity','offset','prefix_size','prefix','mtime','last','tokens','tokens_partial','seconds','seen','starts','start','turn','incomplete','ready')
            valid=isinstance(entry,dict) and all(k in entry for k in required)
            valid=valid and all(type(entry[k]) is int and entry[k]>=0 for k in ('offset','prefix_size','mtime','tokens'))
            valid=valid and entry['prefix_size']<=256 and isinstance(entry['path'],str) and isinstance(entry['prefix'],str) and len(entry['prefix'])==64
            valid=valid and type(entry['seconds']) in (float,int) and math.isfinite(entry['seconds']) and entry['seconds']>=0
            valid=valid and all(isinstance(entry[k],list) and all(isinstance(v,str) for v in entry[k]) for k in ('seen','starts'))
            valid=valid and all(entry[k] is None or type(entry[k]) in (int,float) and math.isfinite(entry[k]) for k in ('last','start','created'))
            valid=valid and type(entry.get('discarding',False)) is bool
            if not valid:del self.entries[key];continue
            entry['pending']=b'';entry['seen']=set(entry['seen']);entry['starts']=set(entry['starts']);entry['checked']=False
            entry.setdefault('discarding',False)

    def sync(self,threads):
        self.sources={t['id']:(t.get('path'),t.get('createdAt') if t.get('forkedFromId') else None) for t in threads if t.get('path')}

    def _entry(self,key):
        name,created=self.sources[key];path=Path(name);stat=path.stat()
        entry=self.entries.get(key)
        reset=(not entry or entry.get('path')!=str(path) or entry.get('created')!=created or entry.get('identity')!=[stat.st_dev,stat.st_ino]
               or stat.st_size<entry.get('offset',0) or stat.st_size==entry.get('offset') and stat.st_mtime_ns!=entry.get('mtime'))
        if not reset and not entry.get('checked'):
            with path.open('rb') as stream:prefix=stream.read(entry['prefix_size'])
            reset=hashlib.sha256(prefix).hexdigest()!=entry['prefix']
        if reset:
            with path.open('rb') as stream:prefix=stream.read(min(256,stat.st_size))
            entry={'path':str(path),'created':created,'identity':[stat.st_dev,stat.st_ino],
                   'offset':0,'prefix_size':len(prefix),'prefix':hashlib.sha256(prefix).hexdigest(),
                   'mtime':stat.st_mtime_ns,'last':None,'tokens':0,'tokens_partial':False,'seconds':0.,'seen':set(),'starts':set(),
                   'start':None,'turn':None,'incomplete':False,'ready':False,'pending':b'','discarding':False}
            self.entries[key]=entry;self.dirty=True
        entry['checked']=True;entry['missing']=False;entry['size']=stat.st_size;self.missing.discard(key)
        return path,stat,entry

    @staticmethod
    def apply(entry,event):
        if not event:return
        at=event['at'].timestamp();original=entry['created'] is None or at>=entry['created'];kind=event['kind'];turn=event['turn']
        if kind=='token_count':
            value=(event.get('usage') or {}).get('total_tokens')
            if type(value) is int and value>=0:
                previous=entry['last']
                if original:
                    if previous is None and entry['created'] is not None:entry['tokens_partial']=True
                    else:entry['tokens']+=value if previous is None or value<previous else value-previous
                entry['last']=value
        elif kind=='task_started' and original:
            identifier=turn or '@'+event['at'].isoformat()
            start_id=identifier+'@'+event['at'].isoformat()
            if start_id not in entry['starts']:
                if entry['start'] is not None:entry['incomplete']=True
                entry['starts'].add(start_id);entry['seen'].add(identifier);entry['start']=at;entry['turn']=turn
        elif kind in ('task_complete','turn_aborted') and original:
            if entry['start'] is not None and at>=entry['start'] and (not turn or not entry['turn'] or turn==entry['turn']):
                entry['seconds']+=max(0,at-entry['start']);entry['start']=None
            elif not entry['seen']:entry['incomplete']=True

    def step(self,budget=.06):
        keys=list(self.sources)
        if not keys:return
        deadline=time.monotonic()+budget
        start=self.cursor%len(keys);queue=deque(keys[start:]+keys[:start]);checked={}
        while queue and time.monotonic()<deadline:
            key=queue.popleft();self.cursor+=1
            try:
                if key not in checked:checked[key]=self._entry(key)
                path,stat,entry=checked[key]
                if stat.st_size>entry['offset']:
                    with path.open('rb') as stream:
                        stream.seek(entry['offset']);chunk=stream.read(min(self.CHUNK,stat.st_size-entry['offset']))
                    self.consume(entry,chunk)
                    entry['offset']+=len(chunk);entry['mtime']=stat.st_mtime_ns;self.dirty=True
                entry['ready']=entry['offset']>=stat.st_size
                if not entry['ready']:queue.append(key)
            except (OSError,ValueError,KeyError,TypeError):
                self.missing.add(key)
                if key in self.entries:self.entries[key]['missing']=True
        self.save()

    def consume(self,entry,chunk):
        data=entry['pending']+chunk;entry['pending']=b''
        if entry.get('discarding'):
            end=data.find(b'\n')
            if end<0:return
            data=data[end+1:];entry['discarding']=False
        lines=data.split(b'\n');tail=lines.pop()
        for line in lines:
            if not irrelevant_record(line):self.apply(entry,event_from_line(line))
        if irrelevant_record(tail):entry['discarding']=True
        else:entry['pending']=tail

    def view(self,running=(),now=None):
        now=time.time() if now is None else now;running=set(running);result={}
        for key in self.sources:
            entry=self.entries.get(key)
            if key in self.missing:result[key]={'ready':False,'missing':True};continue
            if not entry or not entry.get('checked') or entry.get('missing'):
                result[key]={'ready':False};continue
            ready=bool(entry.get('ready'));elapsed=entry['seconds'];partial=entry['incomplete'] or not ready
            if entry['start'] is not None:
                if ready and key in running:elapsed+=max(0,now-entry['start'])
                else:partial=True
            result[key]={'ready':ready,'tokens':entry['tokens'],'seconds':int(elapsed) if entry['seen'] else None,
                         'turns':len(entry['seen']) if entry['seen'] else None,'partial':partial,'tokens_partial':entry['tokens_partial'] or not ready,
                         'turns_partial':not ready,'indexed_bytes':max(0,entry['offset']-len(entry['pending'])),'total_bytes':entry.get('size',entry['offset'])}
        return result

    def save(self,force=False):
        if not self.dirty or not force and time.monotonic()-self.saved_at<30:return
        entries={}
        for key,entry in self.entries.items():
            value={k:v for k,v in entry.items() if k not in ('pending','checked','missing')}
            # Resume before an unfinished line instead of persisting its contents.
            value['offset']-=len(entry['pending']);value['seen']=sorted(entry['seen']);value['starts']=sorted(entry['starts']);entries[key]=value
        try:write_json(self.path,{'version':self.VERSION,'entries':entries})
        except OSError:return
        self.saved_at=time.monotonic();self.dirty=False
