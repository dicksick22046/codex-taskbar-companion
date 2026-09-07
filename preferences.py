"""Small persistent preferences; install files never contain user data."""
import json
import os
from pathlib import Path
import shutil

DISPLAY_DEFAULTS = {
    'show_week': True, 'show_session': True, 'show_countdown': True,
    'show_daily': True, 'show_tasks': True,
}


def runtime_dir():
    return Path(os.environ['LOCALAPPDATA']) / 'CodexTaskbar'


def migrate_legacy(source, destination):
    destination.mkdir(parents=True, exist_ok=True)
    for name in ('ui_settings.json', 'quota_history.json'):
        old, new = source / name, destination / name
        if old.is_file() and not new.exists():
            shutil.copy2(old, new)


def read_settings(path):
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(data, dict): data = {}
    except (OSError, ValueError): data = {}
    result = dict(data)
    for key, default in DISPLAY_DEFAULTS.items():
        result[key] = data[key] if isinstance(data.get(key), bool) else default
    result['chart_unit'] = data.get('chart_unit') if data.get('chart_unit') in ('M', '100M') else 'M'
    return result


def write_settings(path, settings):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)
