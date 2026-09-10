import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QMenu
from codex_taskbar import app,windows


class Probe(app.QWidget):
    ensure_visible=app.StatusBar.ensure_visible

    def __init__(self):
        super().__init__(None,app.FLAGS)
        self.menu=QMenu(self);self.confirming_reset=False
        self.surface_loss_since=None;self.surface_repaired=False
        self.setAttribute(app.Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowOpacity(0);self.resize(10,10)


class NativeVisibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.qt=app.QApplication.instance() or app.QApplication([])

    def setUp(self):
        self.bar=Probe();self.bar.show()
        for _ in range(5):self.qt.processEvents()

    def tearDown(self):self.bar.close();self.bar.deleteLater();self.qt.processEvents()

    def test_recovers_native_hide_even_when_qt_still_reports_visible(self):
        hwnd=int(self.bar.winId());windows.user32.ShowWindow(hwnd,0);self.qt.processEvents()
        self.assertTrue(self.bar.isVisible())
        self.assertFalse(windows.user32.IsWindowVisible(hwnd))
        with patch('builtins.print'):
            self.assertFalse(self.bar.ensure_visible(0))
            self.assertFalse(self.bar.ensure_visible(.2))
            self.assertTrue(self.bar.ensure_visible(.31))
        for _ in range(5):self.qt.processEvents()
        self.assertTrue(windows.user32.IsWindowVisible(int(self.bar.winId())))
        self.assertTrue(self.bar.windowHandle().isExposed())
        self.assertFalse(self.bar.ensure_visible(.5))
        self.assertFalse(self.bar.surface_repaired)

    def test_does_not_keep_recreating_a_surface_that_cannot_be_exposed(self):
        with patch.object(self.bar.windowHandle(),'isExposed',return_value=False),patch('builtins.print'):
            self.assertFalse(self.bar.ensure_visible(0))
            self.assertTrue(self.bar.ensure_visible(.31))
            self.assertFalse(self.bar.ensure_visible(1))
            self.assertFalse(self.bar.ensure_visible(30))
        self.qt.processEvents();self.bar.ensure_visible(31)
        self.assertFalse(self.bar.surface_repaired)

    def test_recovers_native_minimization(self):
        windows.user32.ShowWindow(int(self.bar.winId()),7)  # SW_SHOWMINNOACTIVE
        self.qt.processEvents()
        self.assertTrue(windows.user32.IsIconic(int(self.bar.winId())))
        with patch('builtins.print'):
            self.bar.ensure_visible(0);self.bar.ensure_visible(.31)
        for _ in range(5):self.qt.processEvents()
        self.assertFalse(windows.user32.IsIconic(int(self.bar.winId())))
        self.assertTrue(windows.user32.IsWindowVisible(int(self.bar.winId())))

    def test_short_exposure_loss_and_open_menu_do_not_recreate_the_window(self):
        hwnd=int(self.bar.winId())
        with patch.object(self.bar.windowHandle(),'isExposed',return_value=False):
            self.assertFalse(self.bar.ensure_visible(0))
        self.bar.ensure_visible(.1)
        self.assertIsNone(self.bar.surface_loss_since)
        with patch.object(self.bar.windowHandle(),'isExposed',return_value=False),patch.object(self.bar.menu,'isVisible',return_value=True):
            self.assertFalse(self.bar.ensure_visible(2))
            self.assertFalse(self.bar.ensure_visible(4))
        self.assertEqual(int(self.bar.winId()),hwnd)
