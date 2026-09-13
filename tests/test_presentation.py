import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtCore import QRect,QPointF,QEvent
from PySide6.QtGui import QMouseEvent
from codex_taskbar import app,windows
from codex_taskbar.preferences import read_settings,write_settings
from codex_taskbar.presentation import floating_rect,remember_position,clamp_rect,panel_rect
from tests import test_interactions as fixtures


class GeometryTests(unittest.TestCase):
    def test_position_roundtrip_and_resolution_change(self):
        bounds=QRect(-1920,-200,1920,1040);box=QRect(-1500,500,540,30)
        saved=remember_position(box,bounds,'secondary')
        self.assertEqual(floating_rect(bounds,saved),box)
        smaller=QRect(0,0,800,600);self.assertTrue(smaller.contains(floating_rect(smaller,saved)))
        self.assertEqual(floating_rect(smaller,saved).width(),540)
        self.assertTrue(QRect(0,0,400,300).contains(floating_rect(QRect(0,0,400,300),saved)))

    def test_panels_open_below_top_and_above_bottom_with_gap(self):
        bounds=QRect(-1920,0,1920,1040)
        top=QRect(-100,10,80,30);bottom=QRect(-100,990,80,30)
        a=panel_rect(top,bounds,360,220);b=panel_rect(bottom,bounds,360,220)
        self.assertEqual(a.top()-top.bottom()-1,8);self.assertEqual(bottom.top()-b.bottom()-1,8)
        self.assertTrue(bounds.contains(a));self.assertTrue(bounds.contains(b))
        tall=panel_rect(QRect(-1000,500,540,30),bounds,360,2000)
        self.assertTrue(bounds.contains(tall));self.assertLess(tall.height(),2000)

    def test_preferences_validate_position_and_preserve_existing_options(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'settings.json';settings=read_settings(path)
            self.assertEqual(settings['placement'],'auto');self.assertTrue(settings['floating_topmost'])
            settings.update(placement='floating',floating_topmost=False,floating_position={'screen':'B','x':.3,'y':.7})
            write_settings(path,settings);self.assertEqual(read_settings(path),settings)
            for bad in (None,[],{'screen':'B','x':True,'y':0},{'screen':'B','x':float('nan'),'y':0}):
                path.write_text(json.dumps({'floating_position':bad}));self.assertIsNone(read_settings(path)['floating_position'])


class FloatingInteractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.application=app.QApplication.instance() or app.QApplication([])

    def setUp(self):
        fixtures.InteractionTests.setUp(self)
        self.bar.settings.update(placement='floating',floating_topmost=False,rotate_quotas=True)
        self.bar.setGeometry(200,300,540,30);self.bar.grab()

    def tearDown(self):fixtures.InteractionTests.tearDown(self)

    def send(self,kind,local,global_point=None,widget=None):
        widget=widget or self.bar
        button=app.Qt.MouseButton.NoButton if kind==QEvent.Type.MouseMove else app.Qt.MouseButton.LeftButton
        held=app.Qt.MouseButton.NoButton if kind==QEvent.Type.MouseButtonRelease else app.Qt.MouseButton.LeftButton
        event=QMouseEvent(kind,local,global_point or QPointF(widget.mapToGlobal(local.toPoint())),button,held,app.Qt.KeyboardModifier.NoModifier)
        self.application.sendEvent(widget,event)

    def test_click_retains_task_target_and_does_not_save_position(self):
        point=self.strip.task_area.center()
        with patch.object(self.bar,'open_task') as opened,patch.object(self.bar,'save_settings') as saved:
            self.send(QEvent.Type.MouseButtonPress,point,widget=self.strip)
            self.strip.task={'id':'replacement','title':'Replacement','project':'P'};self.strip.grab()
            self.send(QEvent.Type.MouseButtonRelease,point,widget=self.strip)
            self.assertEqual(opened.call_args.args[0]['id'],'running');saved.assert_not_called()

    def test_drag_from_metric_moves_without_opening_panel_and_saves_once(self):
        point=self.bar.hit_regions[0][1].center();start=QPointF(self.bar.mapToGlobal(point.toPoint()))
        with patch.object(self.bar,'toggle_popup') as opened,patch.object(self.bar,'open_task') as task,patch.object(self.bar,'save_settings') as saved:
            self.send(QEvent.Type.MouseButtonPress,point,start)
            self.send(QEvent.Type.MouseMove,point+QPointF(1,0),start+QPointF(1,0));self.assertFalse(self.bar.dragging)
            self.send(QEvent.Type.MouseMove,point+QPointF(80,0),start+QPointF(80,0));self.assertTrue(self.bar.dragging)
            self.send(QEvent.Type.MouseButtonRelease,point,start+QPointF(80,0))
            self.assertEqual(self.bar.x(),280);opened.assert_not_called();task.assert_not_called();saved.assert_called_once()
            self.assertIn('screen',self.bar.settings['floating_position'])

    def test_floating_hook_never_steals_clicks_from_a_covering_window(self):
        self.assertFalse(self.bar.desktop_click(220,315));self.assertFalse(self.bar.desktop_click(220,315,'left_up'))
        self.assertIsNone(self.bar.pressed)

    def test_floating_does_not_query_taskbar_and_mode_switch_reuses_provider(self):
        with patch.object(self.bar,'ensure_visible',return_value=False),patch('codex_taskbar.app.windows.placement',return_value=None) as placement, \
             patch('codex_taskbar.app.windows.floating_window') as floating,patch('codex_taskbar.app.windows.follow_taskbar') as follow,patch.object(self.bar,'save_settings'):
            self.bar.tick();self.bar.tick();placement.assert_not_called();follow.assert_not_called();floating.assert_called_once()
            self.bar.set_placement('taskbar');placement.assert_called_once();self.assertIs(self.bar.provider,self.provider)
            self.provider.stop.assert_not_called()

    def test_removed_screen_uses_primary_and_all_panels_stay_on_screen(self):
        self.bar.settings['floating_position']={'screen':'removed screen','x':1.,'y':1.}
        self.assertEqual(self.bar.floating_screen(),self.application.primaryScreen())
        screen=self.bar.screen();bounds=screen.availableGeometry()
        for y in (bounds.top()+10,bounds.center().y(),bounds.bottom()-50):
            self.bar.setGeometry(bounds.right()-550,y,540,30)
            for cls in (app.TaskPopup,app.SessionPopup,app.ResetPopup,app.TaskListPopup):
                panel=cls(self.bar);panel.refresh(self.data)
                self.assertTrue(bounds.contains(panel.geometry()),(cls.__name__,panel.geometry(),bounds))
                self.assertFalse(self.bar.geometry().intersects(panel.geometry()))
                panel.grab();panel.close();panel.deleteLater()

    def test_reset_long_body_scrolls_but_button_stays_visible(self):
        self.data['reset_credits']=[{'id':str(i),'expiresAt':1900000000+i} for i in range(100)]
        panel=app.ResetPopup(self.bar);panel.refresh(self.data)
        self.assertGreater(panel.scroll_limit(),0);self.assertTrue(panel.rect().contains(panel.button.geometry()))
        panel.scroll=panel.scroll_limit();panel.grab();panel.close();panel.deleteLater()

    def test_settings_scroll_on_short_windows_and_translate_placement(self):
        with patch('codex_taskbar.settings_ui.startup.enabled',return_value=False):dialog=app.SettingsDialog(self.bar)
        self.bar.settings['language']='es';dialog.refresh();dialog.navigation.setCurrentRow(1);dialog.resize(dialog.width(),300);dialog.grab()
        self.assertGreater(dialog.scroll_area.verticalScrollBar().maximum(),0)
        self.assertEqual(dialog.placement.currentText(),'Flotante')
        self.assertEqual(dialog.capsule.currentText(),'Oscuro')
        self.assertEqual([data for _,data in dialog.capsule.items],['dark','light'])
        dialog.close();dialog.deleteLater()


class FloatingNativeTests(unittest.TestCase):
    def test_floating_detaches_owner_and_changes_topmost_without_activation(self):
        with patch.object(windows.user32,'GetWindowLongPtrW',return_value=20),patch.object(windows.user32,'SetWindowLongPtrW') as owner, \
             patch.object(windows.user32,'SetWindowPos') as move:
            windows.floating_window(10,False);owner.assert_called_once_with(10,-8,0)
            self.assertEqual(move.call_args.args[1].value,windows.w.HWND(-2).value)
            self.assertTrue(move.call_args.args[-1]&0x10)
