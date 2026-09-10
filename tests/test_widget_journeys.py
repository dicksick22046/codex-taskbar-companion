"""Run with QT_QPA_PLATFORM=offscreen: visible Qt windows, no desktop input."""
import unittest
from unittest.mock import patch
from PySide6.QtCore import Qt,QEvent,QPointF,QPoint
from PySide6.QtGui import QMouseEvent,QKeyEvent
from codex_taskbar import app
from tests import test_ui_flows as flows


class WidgetJourneyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application=app.QApplication.instance() or app.QApplication([])
        if cls.application.platformName()!='offscreen':raise unittest.SkipTest('Separate offscreen journey run required')
    def setUp(self):
        flows.UIFlowTests.setUp(self);self.foreground=app.windows.user32.GetForegroundWindow()
        self.dialog.show();self.dialog.activateWindow();self.application.processEvents()
    def tearDown(self):
        self.assertEqual(app.windows.user32.GetForegroundWindow(),self.foreground)
        flows.UIFlowTests.tearDown(self)
    def mouse(self,widget,kind,point):
        held=Qt.MouseButton.NoButton if kind==QEvent.Type.MouseButtonRelease else Qt.MouseButton.LeftButton
        self.application.sendEvent(widget,QMouseEvent(kind,QPointF(point),QPointF(widget.mapToGlobal(point)),Qt.MouseButton.LeftButton,held,Qt.KeyboardModifier.NoModifier));self.application.processEvents()
    def click(self,widget,point=None):
        point=point or widget.rect().center()
        self.mouse(widget,QEvent.Type.MouseButtonPress,point);self.mouse(widget,QEvent.Type.MouseButtonRelease,point)
    def page(self,index):
        nav=self.dialog.navigation;self.click(nav.viewport(),nav.visualItemRect(nav.item(index)).center());self.assertEqual(self.dialog.stack.currentIndex(),index)
    def key(self,widget,key):
        for kind in (QEvent.Type.KeyPress,QEvent.Type.KeyRelease):self.application.sendEvent(widget,QKeyEvent(kind,key,Qt.KeyboardModifier.NoModifier))
        self.application.processEvents()

    def test_settings_pointer_keyboard_cancel_and_reopen_journey(self):
        self.page(1);toggle=self.dialog.checks['show_tasks'];before=dict(self.bar.settings)
        self.click(toggle.caption);self.assertEqual(self.bar.settings,before)
        self.mouse(toggle,QEvent.Type.MouseButtonPress,toggle.rect().center());self.assertTrue(toggle.isChecked())
        self.mouse(toggle,QEvent.Type.MouseButtonRelease,QPoint(-10,10));self.assertTrue(toggle.isChecked())
        self.click(toggle);self.assertFalse(self.bar.settings['show_tasks']);self.assertEqual(self.bar.width(),self.bar.content_width(self.bar.content_limit))
        self.page(0);self.click(self.dialog.placement.items[1][0]);self.assertTrue(self.bar.floating);self.assertFalse(self.dialog.topmost.row.isHidden())
        self.click(self.dialog.capsule.items[1][0]);self.assertEqual(self.bar.settings['capsule_theme'],'light')
        slider=self.dialog.transparency;slider.setFocus();value=slider.value();self.key(slider,Qt.Key.Key_Right)
        self.assertGreater(slider.value(),value);self.assertEqual(slider.value(),self.bar.settings['capsule_transparency'])
        self.page(2);combo=self.dialog.language;combo.showPopup();self.application.processEvents()
        combo.view().setCurrentIndex(combo.model().index(combo.findData('zh-CN'),0));self.key(combo.view(),Qt.Key.Key_Return)
        self.assertEqual(self.bar.language,'zh-CN');self.assertEqual(self.dialog.headings[2].text(),'常规')
        self.dialog.close();self.dialog.show();self.application.processEvents()
        self.assertEqual(self.dialog.capsule.currentData(),'light');self.assertFalse(self.dialog.checks['show_tasks'].isChecked())
        self.provider.request_reset.assert_not_called()

    def test_keyboard_navigation_keeps_hidden_controls_reachable_in_short_window(self):
        self.dialog.resize(620,300);self.page(1)
        self.dialog.checks['show_week'].setFocus();self.application.processEvents()
        for _ in range(8):self.key(self.dialog.focusWidget(),Qt.Key.Key_Tab)
        focused=self.dialog.focusWidget();self.assertIsNotNone(focused)
        self.assertGreater(self.dialog.scroll_area.verticalScrollBar().value(),0)
        self.assertTrue(self.dialog.scroll_area.viewport().rect().intersects(focused.rect().translated(focused.mapTo(self.dialog.scroll_area.viewport(),QPoint()))))
