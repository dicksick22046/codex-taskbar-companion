import json
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

from codex_taskbar.pricing_catalog import PricingCatalog


class PricingCatalogTests(unittest.TestCase):
    def test_builtin_and_effective_cached_rates(self):
        with tempfile.TemporaryDirectory() as folder:
            catalog = PricingCatalog(Path(folder), '1.0')
            self.assertIsNotNone(catalog.rate_for('gpt-6.1-sol'))
            catalog.merge_official({'future-model': (1., .1, 1.25, 5., 272000)}, datetime(2026, 9, 30, tzinfo=timezone.utc))
            self.assertIsNone(catalog.rate_for('future-model', datetime(2026, 9, 29, tzinfo=timezone.utc)))
            self.assertEqual(catalog.rate_for('future-model', datetime(2026, 10, 1, tzinfo=timezone.utc))[0], 1.)

    def test_corrupt_cache_is_ignored(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'pricing_cache.json'; path.write_text('{bad', encoding='utf-8')
            self.assertIsNone(PricingCatalog(Path(folder), '1.0').rate_for('future-model'))


if __name__ == '__main__': unittest.main()
