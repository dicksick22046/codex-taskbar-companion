"""Allowlisted support report; no logs, task metadata, credentials or paths."""
import json
import platform
from .build_info import APP_NAME,VERSION


def diagnostic_text(settings,data,window):
    return json.dumps({
        'app':APP_NAME,'version':VERSION,'platform':platform.platform(),
        'presentation':{key:settings.get(key) for key in ('placement','capsule_theme','capsule_transparency','language','rotate_quotas','show_week','show_session','show_daily','show_countdown','show_tasks','hover_panels','notify_input')},
        'window':{key:window.get(key) for key in ('visible','native_visible','minimized','exposed','width','height','placement_available','effective_placement','animations','font','startup')},
        'data':{'loading':bool(data.get('loading')),'quota_available':bool(data.get('quota')),'quota_error':bool(data.get('quota_error')),'data_error':bool(data.get('error'))},
    },ensure_ascii=False,indent=2)
