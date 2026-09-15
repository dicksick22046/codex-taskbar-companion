import unittest
from unittest.mock import patch
from PySide6.QtCore import QPoint,Qt,QEvent
from PySide6.QtGui import QFocusEvent,QKeyEvent
from codex_taskbar import app
from tests import test_interactions as fixtures


class TaskListFeedbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixtures.InteractionTests.setUpClass()
    def setUp(self):
        fixtures.InteractionTests.setUp(self)
        visible=patch.object(self.bar,'isVisible',return_value=True);visible.start();self.addCleanup(visible.stop)
        self.bar.setGeometry(30,700,340,30);self.bar.motion_enabled=False
    def tearDown(self):fixtures.InteractionTests.tearDown(self)

    def test_opening_daily_does_not_hover_rows_below_expanding_viewport(self):
        self.bar.toggle_popup('running',activate=False);self.bar.motion_enabled=True
        point=self.bar.mapToGlobal(QPoint(80,15))
        with patch('codex_taskbar.app.QCursor.pos',return_value=point):
            self.bar.toggle_popup('daily',activate=False);panel=self.bar.popup
            self.assertIsNone(panel.hovered)
            for step in (.016,.032,.064):
                self.bar.task_strip.size_motion.advance(step);panel.refresh(self.data)
                self.assertIsNone(panel.hovered)
        self.assertIsNone(panel.task_at(panel.mapFromGlobal(point)))

    def test_mouse_focus_does_not_paint_default_keyboard_selection(self):
        self.bar.toggle_popup('daily',activate=False);panel=self.bar.popup
        panel.hovered=None;row=panel.row_positions[0]+8+panel.ROW_HEIGHT/2
        def pixel():
            image=panel.grab().toImage();ratio=image.devicePixelRatio()
            return image.pixelColor(round(15*ratio),round(row*ratio))
        with patch.object(panel,'hasFocus',return_value=False):baseline=pixel()
        panel.focusInEvent(QFocusEvent(QEvent.Type.FocusIn,Qt.FocusReason.MouseFocusReason))
        with patch.object(panel,'hasFocus',return_value=True):self.assertEqual(pixel(),baseline)
        panel.focusInEvent(QFocusEvent(QEvent.Type.FocusIn,Qt.FocusReason.TabFocusReason))
        with patch.object(panel,'hasFocus',return_value=True):self.assertNotEqual(pixel(),baseline)

    def test_clipped_task_row_cannot_be_hovered_until_it_is_visible(self):
        self.bar.toggle_popup('daily',activate=False);panel=self.bar.popup
        point=QPoint(80,round(panel.row_positions[0]+8+panel.ROW_HEIGHT/2))
        self.bar.task_strip.layout_rows(50);panel.track_hover(point)
        self.assertIsNone(panel.hovered)
        self.bar.task_strip.layout_rows(self.bar.task_strip.size_motion.target);panel.track_hover(point)
        self.assertEqual(panel.hovered,panel.rows[0]['id'])

    def test_arrow_navigation_still_selects_after_mouse_open(self):
        self.bar.toggle_popup('daily',activate=False);panel=self.bar.popup
        panel.focusInEvent(QFocusEvent(QEvent.Type.FocusIn,Qt.FocusReason.MouseFocusReason))
        panel.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress,Qt.Key.Key_Down,Qt.KeyboardModifier.NoModifier))
        self.assertTrue(panel.keyboard_navigation)
        self.assertEqual(panel.keyboard_task,panel.rows[1]['id'])
