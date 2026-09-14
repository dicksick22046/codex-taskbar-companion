import unittest
from unittest.mock import patch
from PySide6.QtCore import Qt,QEvent,QPointF,QRectF,QAbstractAnimation
from PySide6.QtGui import QEnterEvent,QFocusEvent,QMouseEvent
from codex_taskbar import app
from tests import test_interactions as fixtures


class PinControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.application=app.QApplication.instance() or app.QApplication([])
    def setUp(self):
        fixtures.InteractionTests.setUp(self);self.bar.settings['pinned_statuses']=[]
        self.panel=app.TaskListPopup(self.bar,'running');self.panel.refresh(self.data);self.button=self.panel.pin_button
    def tearDown(self):
        self.panel.close();self.panel.deleteLater();fixtures.InteractionTests.tearDown(self)

    def test_standard_icon_is_small_centered_and_aligned_with_heading(self):
        self.assertEqual((self.button.width(),self.button.height()),(26,26))
        self.assertEqual(self.button.glyph_rect().size().toSize().toTuple(),(12,12))
        self.assertEqual(self.button.glyph_rect().center(),QRectF(self.button.rect()).center())
        self.assertTrue(app.pin_renderer('#99a6b5').isValid())
        with patch('codex_taskbar.app.text',wraps=app.text) as draw:self.panel.grab()
        heading=next(c for c in draw.call_args_list if c.args[3]==self.bar.label('Running'))
        self.assertEqual(QRectF(self.button.geometry()).center().y(),heading.args[2])

    def test_dark_popup_does_not_inherit_light_capsule_icon_color(self):
        self.bar.settings['capsule_theme']='light';self.button.sync(False)
        with patch('codex_taskbar.app.pin_renderer',wraps=app.pin_renderer) as render:self.button.grab()
        self.assertEqual(render.call_args.args[0],'#99a6b5')
        row=self.bar.task_strip.rows['running'];row.pin_button.sync(True)
        with patch('codex_taskbar.app.pin_renderer',wraps=app.pin_renderer) as render:row.pin_button.grab()
        self.assertEqual(render.call_args.args[0],'#667588')
        row.pin_button.set_hover_value(1.)
        with patch('codex_taskbar.app.pin_renderer',wraps=app.pin_renderer) as render:row.pin_button.grab()
        self.assertEqual(render.call_args.args[0],'#2169ad')

    def test_drag_out_cancels_and_pointer_focus_is_not_keyboard_focus(self):
        def mouse(kind,point):
            held=Qt.MouseButton.LeftButton if kind==QEvent.Type.MouseButtonPress else Qt.MouseButton.NoButton
            event=QMouseEvent(kind,point,QPointF(self.button.mapToGlobal(point.toPoint())),Qt.MouseButton.LeftButton,held,Qt.KeyboardModifier.NoModifier)
            self.application.sendEvent(self.button,event)
        with patch.object(self.bar,'set_status_pinned') as pin:
            mouse(QEvent.Type.MouseButtonPress,QPointF(13,13));self.assertTrue(self.button.isDown());pin.assert_not_called()
            mouse(QEvent.Type.MouseButtonRelease,QPointF(-3,-3));pin.assert_not_called()
            mouse(QEvent.Type.MouseButtonPress,QPointF(13,13));mouse(QEvent.Type.MouseButtonRelease,QPointF(13,13));pin.assert_called_once_with('running',True)
        self.button.focusInEvent(QFocusEvent(QEvent.Type.FocusIn,Qt.FocusReason.MouseFocusReason));self.assertFalse(self.button.keyboard_focus)
        self.button.focusInEvent(QFocusEvent(QEvent.Type.FocusIn,Qt.FocusReason.TabFocusReason));self.assertTrue(self.button.keyboard_focus)

    def test_hover_can_reverse_and_reduced_motion_settles_it(self):
        self.bar.motion_enabled=True
        self.button.enterEvent(QEnterEvent(QPointF(),QPointF(),QPointF()));self.button.hover_tween.setCurrentTime(70)
        value=self.button.hover_value;self.assertGreater(value,0);self.assertLess(value,1)
        self.button.leaveEvent(QEvent(QEvent.Type.Leave));self.assertEqual(self.button.hover_tween.startValue(),value)
        self.bar.motion_enabled=False;self.button.sync(False)
        self.assertEqual(self.button.hover_value,0);self.assertEqual(self.button.hover_tween.state(),QAbstractAnimation.State.Stopped)
