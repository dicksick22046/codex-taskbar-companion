"""Background, event-driven synchronization with the official price table."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import threading
import urllib.request

from .pricing_catalog import PricingCatalog

SOURCE = 'https://developers.openai.com/api/docs/pricing.md'
HEADING = '### Standard pricing data'
HEADER = ('Model', 'Short context input', 'Short context cached input',
          'Short context cache writes', 'Short context output',
          'Long context input', 'Long context cached input',
          'Long context cache writes', 'Long context output')


def _cells(line):
    return tuple(cell.strip() for cell in line.strip().strip('|').split('|'))


def parse_standard_prices(markdown):
    sections = markdown.split(HEADING)
    if len(sections) != 2:
        raise ValueError('Official Standard pricing section changed')
    lines = sections[1].splitlines()
    start = next((i for i, line in enumerate(lines) if _cells(line) == HEADER), None)
    if start is None or start + 1 >= len(lines) or not all(cell == '---' for cell in _cells(lines[start + 1])):
        raise ValueError('Official Standard pricing columns changed')
    rows = {}
    for line in lines[start + 2:]:
        if not line.startswith('|'):
            break
        fields = _cells(line)
        if len(fields) != len(HEADER):
            raise ValueError('Official Standard pricing row changed')
        name = fields[0].removesuffix(' (<272K context length)')
        if not name or name in rows:
            raise ValueError('Official Standard model IDs are ambiguous')
        try:
            values = tuple(None if price == '-' else Decimal(price.removeprefix('$')) for price in fields[1:])
        except InvalidOperation as exc:
            raise ValueError(f'Official Standard price is invalid for {name}') from exc
        short = values[:4]; long = values[4:]
        if any(value is not None for value in long):
            expected = tuple(value * factor if value is not None else None
                             for value, factor in zip(short, (Decimal(2), Decimal(2), Decimal(2), Decimal('1.5'))))
            if long != expected:
                raise ValueError(f'Official Standard long-context rates changed for {name}')
        threshold = 272000 if long[0] is not None else None
        rows[name] = tuple(float(value) if value is not None else None for value in short) + (threshold,)
    return rows


def fetch_official_standard_prices():
    request = urllib.request.Request(SOURCE, headers={'Accept': 'text/markdown', 'User-Agent': 'CodexTaskbarCompanion-price-sync'})
    with urllib.request.urlopen(request, timeout=15) as response:
        raw = response.read(512001)
    if len(raw) > 512000:
        raise ValueError('Official pricing page exceeds the audit size limit')
    return parse_standard_prices(raw.decode('utf-8'))


class PricingSyncCoordinator:
    def __init__(self, catalog: PricingCatalog, on_complete=None):
        self.catalog = catalog
        self.on_complete = on_complete
        self._lock = threading.Lock()
        self._running = False
        self._requested_unknown = set()
        self._thread = None

    def _schedule(self, key, notify=True):
        with self._lock:
            if self._running:
                return False
            self._running = True
        def work():
            try:
                self.catalog.merge_official(fetch_official_standard_prices(), datetime.now(timezone.utc))
                if notify and self.on_complete:
                    self.on_complete()
            except Exception as exc:
                print(f'Pricing sync: {type(exc).__name__}: {exc}', flush=True)
            finally:
                with self._lock:
                    self._running = False
        self._thread = threading.Thread(target=work, name='pricing-sync', daemon=True)
        self._thread.start()
        return True

    def on_version_start(self):
        if self.catalog.needs_version_check():
            return self._schedule(('version', self.catalog.app_version), notify=False)
        return False

    def on_unknown_model(self, model):
        if not self.catalog.observe_unknown(model) or model in self._requested_unknown:
            return False
        self._requested_unknown.add(model)
        return self._schedule(('model', model))
