"""Reviewed and event-synchronized Standard pricing catalog."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile

from .pricing import RATES


def _stamp(value):
    try:
        return datetime.fromisoformat(value).astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


class PricingCatalog:
    def __init__(self, runtime_dir, app_version):
        self.path = Path(runtime_dir) / 'pricing_cache.json'
        self.app_version = str(app_version)
        self.checked_app_version = None
        self.entries = {}
        self._unknown = set()
        self._load()

    def _load(self):
        try:
            data = json.loads(self.path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return
        if not isinstance(data, dict):
            return
        self.checked_app_version = data.get('checked_app_version') if isinstance(data.get('checked_app_version'), str) else None
        entries = data.get('entries')
        if not isinstance(entries, dict):
            return
        for model, entry in entries.items():
            if not isinstance(model, str) or not isinstance(entry, dict):
                continue
            rates = entry.get('rates')
            if not isinstance(rates, list) or len(rates) != 5:
                continue
            if not all(value is None or isinstance(value, (int, float)) for value in rates):
                continue
            stamp = _stamp(entry.get('effective_at'))
            if stamp is None:
                continue
            self.entries[model] = {'rates': tuple(rates), 'effective_at': stamp.isoformat()}

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {'checked_app_version': self.checked_app_version, 'entries': self.entries}
        temporary = self.path.with_suffix('.tmp')
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        temporary.replace(self.path)

    def needs_version_check(self):
        return self.checked_app_version != self.app_version

    def mark_version_checked(self):
        self.checked_app_version = self.app_version
        self._save()

    def rate_for(self, model, at=None):
        if not isinstance(model, str):
            return None
        if model in RATES:
            return RATES[model]
        entry = self.entries.get(model)
        if not entry:
            return None
        effective = _stamp(entry.get('effective_at'))
        if effective and at is not None and at.astimezone(timezone.utc) < effective:
            return None
        return entry['rates']

    def observe_unknown(self, model):
        if not isinstance(model, str) or self.rate_for(model) is not None or model in self._unknown:
            return False
        self._unknown.add(model)
        return True

    def merge_official(self, rows, fetched_at=None):
        fetched_at = fetched_at or datetime.now(timezone.utc)
        stamp = fetched_at.astimezone(timezone.utc).isoformat()
        for model, rates in rows.items():
            if model in RATES or not isinstance(rates, tuple) or len(rates) != 5:
                continue
            self.entries[model] = {'rates': list(rates), 'effective_at': stamp}
        self.checked_app_version = self.app_version
        self._save()
