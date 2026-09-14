"""Popovers follow capsule colors without recoloring data or other windows."""
from datetime import datetime
import unittest
from unittest.mock import patch
from codex_taskbar import app
from tests import test_interactions as fixtures


class PopupThemeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixtures.InteractionTests.setUpClass()
    def setUp(self):
        fixtures.InteractionTests.setUp(self)
        now=datetime.now().astimezone()
        self.data['history']={now.date().isoformat():5000000}
        self.data['reset_events']=[{'id':'one','kind':'official','at':now.timestamp(),'tokens':200000000,'before':{'10080':{'remaining':9}}}]
        self.panels=[app.TaskPopup(self.bar),app.SessionPopup(self.bar),app.ResetPopup(self.bar),app.TaskListPopup(self.bar),app.TaskListPopup(self.bar,'running')]
        for panel in self.panels:panel.refresh(self.data)
    def tearDown(self):
        self.bar.popup=None
        for panel in self.panels:panel.close();panel.deleteLater()
        fixtures.InteractionTests.tearDown(self)

    def test_every_panel_shares_opaque_capsule_material_in_both_themes(self):
        global_palette=app.QApplication.palette()
        for theme in ('dark','light'):
            self.bar.settings['capsule_theme']=theme;self.bar.settings['capsule_transparency']=100
            for panel in self.panels:
                with self.subTest(theme=theme,mode=panel.mode):
                    panel.sync_theme()
                    image=panel.grab().toImage();ratio=image.devicePixelRatio()
                    pixel=image.pixelColor(round(5*ratio),round(panel.height()/2*ratio))
                    self.assertEqual(pixel.alpha(),255)
                    self.assertGreater(pixel.lightness(),200) if theme=='light' else self.assertLess(pixel.lightness(),80)
                    with patch('codex_taskbar.app.capsule_surface',wraps=app.capsule_surface) as material:panel.grab()
                    self.assertEqual(material.call_args.args[2:4],(theme,0))
        self.assertEqual(app.QApplication.palette(),global_palette)

    def test_switch_updates_existing_controls_without_losing_values_or_selection(self):
        for panel in self.panels:
            with self.subTest(mode=panel.mode):
                self.bar.popup=panel
                rows=list(panel.rows);geometry=panel.geometry()
                before=panel.grab().toImage()
                with patch.object(self.bar,'save_settings'):
                    self.bar.set_capsule_theme('light')
                after=panel.grab().toImage()
                self.assertNotEqual(before,after)
                self.assertEqual(panel.rows,rows);self.assertEqual(panel.geometry(),geometry)
                for unit,button in panel.unit_buttons.items():
                    self.assertIn(app.popup_palette(self.bar)['title'],button.styleSheet())
                    self.assertEqual(button.isChecked(),unit==self.bar.chart_unit)
                if isinstance(panel,app.ResetPopup):
                    self.assertEqual(panel.history_selected,'one');self.assertEqual(panel.history_percent(panel.rows[0]),'91%')
                    self.assertIn(app.popup_palette(self.bar)['button'],panel.button.styleSheet())
                    self.assertIn(app.popup_palette(self.bar)['link'],panel.history_scroll.styleSheet())
                if getattr(panel,'pin_button',None):self.assertTrue(panel.pin_button.light_surface)
                self.bar.settings['capsule_theme']='dark';panel.sync_theme()
        self.provider.request_reset.assert_not_called()

    def test_chart_geometry_values_and_semantic_roles_survive_theme_change(self):
        chart=self.panels[0]
        calls=[]
        for theme in ('dark','light'):
            self.bar.settings['capsule_theme']=theme
            with patch('codex_taskbar.app.paint_usage_column',wraps=app.paint_usage_column) as draw:chart.grab()
            calls.append([call.args[1:8] for call in draw.call_args_list])
            colors=[call.args[8] for call in draw.call_args_list]
            self.assertIn(app.popup_palette(self.bar)['green'],colors)
        self.assertEqual(calls[0],calls[1])
