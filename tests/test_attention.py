import unittest
from unittest.mock import patch
from codex_taskbar import app
from codex_taskbar.tasks import category_counts,panel_rows
from tests import test_interactions as fixtures


class AttentionUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.application=app.QApplication.instance() or app.QApplication([])
    def setUp(self):fixtures.InteractionTests.setUp(self)
    def tearDown(self):fixtures.InteractionTests.tearDown(self)
    def test_waiting_is_exclusive_and_gets_its_own_panel(self):
        self.data['tasks'][0]['needs_input']=True;self.bar.grab()
        counts=category_counts(self.data);self.assertEqual(counts['waiting'],1);self.assertEqual(counts['running'],0)
        self.assertEqual(panel_rows(self.data,'running'),[]);self.assertEqual(len(panel_rows(self.data,'waiting')),1)
        self.assertIn('waiting',[mode for mode,rect,task in self.bar.hit_regions])
        with patch('codex_taskbar.app.text',wraps=app.text) as draw:
            self.bar.grab();self.assertIn('Needs input 1',[call.args[3] for call in draw.call_args_list])
        self.strip.refresh(self.data);self.assertIsNone(self.strip.task);self.assertFalse(self.strip.needs_animation)
        panel=app.TaskListPopup(self.bar,'waiting');panel.refresh(self.data);self.assertEqual(panel.sections[0][0],'Needs input');panel.close();panel.deleteLater()
