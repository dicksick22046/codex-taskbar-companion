import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from codex_taskbar.preferences import read_settings,write_settings
from codex_taskbar.presentation import floating_rect,remember_position
from PySide6.QtCore import QRect
from codex_taskbar.tasks import category_counts
from tests import test_interactions as fixtures


class PresentationPreferenceTests(unittest.TestCase):
    def test_fresh_settings_keep_counts_and_make_running_strip_optional(self):
        with tempfile.TemporaryDirectory() as folder:
            data=read_settings(Path(folder)/'settings.json')
            self.assertTrue(data['show_tasks']);self.assertEqual(data['pinned_statuses'],[])
            self.assertFalse(data['show_task_statistics'])
            self.assertEqual(data['placement'],'auto')

    def test_legacy_display_is_preserved_without_resetting_position(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'settings.json';position={'screen':'Display','x':.3,'y':.6,'width':420}
            for shown in (False,True):
                path.write_text(json.dumps({'show_tasks':shown,'task_strip_position':position}),encoding='utf-8')
                data=read_settings(path)
                self.assertEqual(data['pinned_statuses'],['running'] if shown else []);self.assertNotIn('task_strip_position',data)
                data.update(show_tasks=not shown,show_task_statistics=True,placement='taskbar')
                write_settings(path,data);self.assertEqual(read_settings(path),data)

    def test_explicit_independent_choice_wins_and_invalid_values_use_defaults(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'settings.json'
            for counts,strip in ((True,False),(False,True)):
                path.write_text(json.dumps({'show_tasks':counts,'show_task_strip':strip}),encoding='utf-8')
                data=read_settings(path);self.assertEqual(data['show_tasks'],counts);self.assertEqual(data['pinned_statuses'],['running'] if strip else [])
            path.write_text(json.dumps({'show_tasks':True,'show_task_strip':'yes','show_task_statistics':1}),encoding='utf-8')
            data=read_settings(path);self.assertEqual(data['pinned_statuses'],[]);self.assertFalse(data['show_task_statistics'])

    def test_wide_labelled_content_restores_its_anchor_and_clamps_on_smaller_screen(self):
        bounds=QRect(-1600,0,1600,900);box=floating_rect(bounds,width=891)
        self.assertEqual(box.width(),891)
        saved=remember_position(box,bounds,'Left')
        self.assertEqual(floating_rect(bounds,saved,891),box)
        self.assertEqual(floating_rect(bounds,saved,500).left(),box.left())
        smaller=QRect(0,0,800,600);restored=floating_rect(smaller,saved,891)
        self.assertEqual(restored.width(),768);self.assertTrue(smaller.contains(restored))


class IndependentControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixtures.InteractionTests.setUpClass.__func__(cls)
    def setUp(self):fixtures.InteractionTests.setUp(self)
    def tearDown(self):fixtures.InteractionTests.tearDown(self)

    def test_unpin_keeps_status_counts_and_hiding_bar_hides_attached_rows(self):
        before=category_counts(self.data)
        with patch.object(self.bar,'save_settings'):
            self.bar.set_status_pinned('running',False);self.bar.grab()
            self.assertTrue(self.strip.hidden);self.assertIn('running',[mode for mode,rect,task in self.bar.hit_regions])
            self.bar.set_status_pinned('running',True);self.bar.set_display('show_tasks',False);self.bar.grab()
            self.assertTrue(self.strip.hidden);self.assertNotIn('running',[mode for mode,rect,task in self.bar.hit_regions])
            self.assertEqual(self.strip.task['id'],'running');self.assertEqual(category_counts(self.data),before)


if __name__=='__main__':unittest.main()
