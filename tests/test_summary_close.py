import unittest
from unittest.mock import patch
from PySide6.QtCore import Qt,QEvent,QPointF,QRectF,QAbstractAnimation
from PySide6.QtGui import QEnterEvent,QFocusEvent,QMouseEvent,QKeyEvent
from codex_taskbar import app
from tests import test_interactions as fixtures


class SummaryCloseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixtures.InteractionTests.setUpClass.__func__(cls)
    def setUp(self):
        fixtures.InteractionTests.setUp(self);self.button=self.strip.close_button
    def tearDown(self):fixtures.InteractionTests.tearDown(self)

    def test_close_target_stays_small_and_only_reveals_on_row_hover_or_keyboard_focus(self):
        self.bar.motion_enabled=False
        self.assertEqual((self.button.width(),self.button.height()),(26,26))
        self.assertEqual(self.button.glyph_rect().size().toSize().toTuple(),(12,12))
        self.assertEqual(self.button.glyph_rect().center(),QRectF(self.button.rect()).center())
        self.assertTrue(app.close_renderer('#99a6b5').isValid())
        for theme,color in (('dark','#8795a5'),('light','#667588')):
            self.bar.settings['capsule_theme']=theme;self.button.sync();self.strip.track_pointer(QPointF(-1,-1))
            with patch.object(self.button,'underMouse',return_value=False),patch('codex_taskbar.app.close_renderer',wraps=app.close_renderer) as rendered:
                self.button.grab();rendered.assert_not_called()
                self.strip.track_pointer(QPointF(45,15));self.button.grab();self.assertEqual(rendered.call_args.args[0],color)
                self.strip.track_pointer(QPointF(-1,-1))
                self.button.focusInEvent(QFocusEvent(QEvent.Type.FocusIn,Qt.FocusReason.TabFocusReason));self.button.grab()
                self.assertEqual(rendered.call_args.args[0],'#2169ad' if theme=='light' else app.BLUE)
                self.button.focusOutEvent(QFocusEvent(QEvent.Type.FocusOut))

    def test_press_release_cancel_and_keyboard_activation_do_not_navigate(self):
        def mouse(kind,point):
            held=Qt.MouseButton.LeftButton if kind==QEvent.Type.MouseButtonPress else Qt.MouseButton.NoButton
            self.application.sendEvent(self.button,QMouseEvent(kind,point,QPointF(self.button.mapToGlobal(point.toPoint())),Qt.MouseButton.LeftButton,held,Qt.KeyboardModifier.NoModifier))
        with patch.object(self.bar,'dismiss_status') as close,patch.object(self.bar,'open_task') as opened:
            mouse(QEvent.Type.MouseButtonPress,QPointF(13,13));mouse(QEvent.Type.MouseButtonRelease,QPointF(-3,-3));close.assert_not_called()
            mouse(QEvent.Type.MouseButtonPress,QPointF(13,13));mouse(QEvent.Type.MouseButtonRelease,QPointF(13,13));close.assert_called_once_with('running')
            close.reset_mock();self.button.focusInEvent(QFocusEvent(QEvent.Type.FocusIn,Qt.FocusReason.TabFocusReason))
            for kind in (QEvent.Type.KeyPress,QEvent.Type.KeyRelease):self.application.sendEvent(self.button,QKeyEvent(kind,Qt.Key.Key_Space,Qt.KeyboardModifier.NoModifier))
            close.assert_called_once_with('running')
            opened.assert_not_called()
        for language in app.LANGUAGES:
            self.bar.settings['language']=language;self.button.sync()
            self.assertIn(self.bar.label('Running'),self.button.accessibleName())
        self.assertFalse(self.button.isCheckable())

    def test_reveal_reverses_and_reduced_motion_settles(self):
        self.bar.motion_enabled=True;self.button.set_revealed(True);self.button.hover_tween.setCurrentTime(70)
        value=self.button.hover_value;self.assertGreater(value,0);self.assertLess(value,1)
        self.button.set_revealed(False);self.assertEqual(self.button.hover_tween.startValue(),value)
        self.bar.motion_enabled=False;self.button.sync()
        self.assertEqual(self.button.hover_value,0);self.assertEqual(self.button.hover_tween.state(),QAbstractAnimation.State.Stopped)
