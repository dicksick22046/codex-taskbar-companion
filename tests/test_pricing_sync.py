import unittest
from unittest.mock import patch
from pathlib import Path
import tempfile

from codex_taskbar.pricing_catalog import PricingCatalog
from codex_taskbar.pricing_sync import PricingSyncCoordinator


class PricingSyncTests(unittest.TestCase):
    def test_version_trigger_is_deduplicated(self):
        with tempfile.TemporaryDirectory() as folder, patch('codex_taskbar.pricing_sync.fetch_official_standard_prices', return_value={}):
            catalog = PricingCatalog(Path(folder), '1.0')
            sync = PricingSyncCoordinator(catalog)
            self.assertTrue(sync.on_version_start())
            self.assertFalse(sync.on_version_start())
            sync._thread.join(2)

    def test_unknown_model_trigger_is_deduplicated(self):
        with tempfile.TemporaryDirectory() as folder, patch('codex_taskbar.pricing_sync.fetch_official_standard_prices', return_value={}):
            catalog = PricingCatalog(Path(folder), '1.0')
            sync = PricingSyncCoordinator(catalog)
            self.assertTrue(sync.on_unknown_model('future-model'))
            self.assertFalse(sync.on_unknown_model('future-model'))
            sync._thread.join(2)


if __name__ == '__main__': unittest.main()
