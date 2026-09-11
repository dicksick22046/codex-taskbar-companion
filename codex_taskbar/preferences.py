"""Small persistent preferences; install files never contain user data."""
import json
import os
from pathlib import Path
import math
from .i18n import LANGUAGES

DISPLAY_DEFAULTS = {
    'show_week': True, 'show_session': True, 'show_countdown': True,
    'show_daily': True, 'show_tasks': True,
}


def runtime_dir():
    return Path.home() / '.codex-taskbar-companion'


def legacy_runtime_dirs():
    local=Path(os.environ['LOCALAPPDATA'])
    return [local/'CodexTaskbar', *sorted((local/'Packages').glob('*/LocalCache/Local/CodexTaskbar'))]


def migrate_legacy(source, destination, additional_sources=()):
    destination.mkdir(parents=True, exist_ok=True)
    sources=list(dict.fromkeys([source, *additional_sources]))
    settings=[p/'ui_settings.json' for p in sources if (p/'ui_settings.json').is_file()]
    if settings and not (destination/'ui_settings.json').exists():
        for path in sorted(settings,key=lambda p:p.stat().st_mtime,reverse=True):
            try:
                value=json.loads(path.read_text(encoding='utf-8'))
                if not isinstance(value,dict):continue
                write_json(destination/'ui_settings.json',value);break
            except (OSError,ValueError):continue
    history_path=destination/'quota_history.json'
    try:existing=json.loads(history_path.read_text(encoding='utf-8'))
    except (OSError,ValueError):existing=None
    samples={}
    for source in [*sources,destination]:
        try:
            rows=json.loads((source/'quota_history.json').read_text(encoding='utf-8'))
        except (OSError,ValueError):continue
        if not isinstance(rows,list):continue
        for row in rows:
            if not isinstance(row,dict):continue
            if not all(isinstance(row.get(k),(int,float)) and not isinstance(row[k],bool) and math.isfinite(row[k]) for k in ('at','used','reset')):continue
            if row['at']<=0 or row['reset']<=0 or not 0<=row['used']<=100:continue
            samples[(row['at'],row['reset'])]={k:row[k] for k in ('at','used','reset')}
    merged=sorted(samples.values(),key=lambda r:r['at'])
    if samples and merged!=existing:write_json(history_path,merged)


def read_settings(path):
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(data, dict): data = {}
    except (OSError, ValueError): data = {}
    result = dict(data)
    for key, default in DISPLAY_DEFAULTS.items():
        result[key] = data[key] if isinstance(data.get(key), bool) else default
    result['chart_unit'] = data.get('chart_unit') if data.get('chart_unit') in ('M', '100M') else 'M'
    result['hover_panels'] = data.get('hover_panels') is True
    result['rotate_quotas'] = data.get('rotate_quotas') is True
    result['notify_input'] = data.get('notify_input') is True
    result['language'] = data.get('language') if data.get('language') in LANGUAGES else 'en'
    result['capsule_theme'] = data.get('capsule_theme') if data.get('capsule_theme') in ('dark','light') else 'dark'
    transparency=data.get('capsule_transparency',0)
    result['capsule_transparency']=max(0,min(100,transparency)) if type(transparency) is int else 0
    result['placement']=data.get('placement') if data.get('placement') in ('auto','taskbar','floating') else 'taskbar'
    result['floating_topmost']=data.get('floating_topmost') is not False
    position=data.get('floating_position')
    valid=isinstance(position,dict) and isinstance(position.get('screen'),str) and all(
        type(position.get(k)) in (int,float) and math.isfinite(position[k]) and 0<=position[k]<=1 for k in ('x','y'))
    result['floating_position']={k:position[k] for k in ('screen','x','y')} if valid else None
    if valid and type(position.get('width')) is int and 1<=position['width']<=540:
        result['floating_position']['width']=position['width']
    selected=data.get('floating_display',position.get('screen') if valid else None)
    result['floating_display']=selected if isinstance(selected,str) and 0<len(selected)<=128 else None
    return result


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary=path.with_suffix('.tmp')
    with temporary.open('w',encoding='utf-8') as stream:
        json.dump(value,stream,ensure_ascii=False,indent=2)
        stream.flush();os.fsync(stream.fileno())
    temporary.replace(path)


def write_settings(path, settings):
    write_json(path,settings)
