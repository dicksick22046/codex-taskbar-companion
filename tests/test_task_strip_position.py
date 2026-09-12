import json
from pathlib import Path
import tempfile
import unittest

from PySide6.QtCore import QRect
from codex_taskbar.preferences import read_settings,write_settings
from codex_taskbar.presentation import floating_rect,remember_position,task_strip_rect


class TaskStripPositionTests(unittest.TestCase):
    def test_default_above_anchor_has_fixed_size_and_gap(self):
        bounds=QRect(0,0,1600,900);anchor=QRect(100,800,260,30)
        rect=task_strip_rect(bounds,anchor)
        self.assertEqual(rect,QRect(100,762,420,30))
        self.assertEqual(anchor.top()-rect.bottom()-1,8)

    def test_above_insufficient_uses_below_with_same_gap(self):
        bounds=QRect(0,0,1600,900);anchor=QRect(100,30,260,30)
        rect=task_strip_rect(bounds,anchor)
        self.assertEqual(rect,QRect(100,68,420,30))
        self.assertEqual(rect.top()-anchor.bottom()-1,8)

    def test_no_valid_anchor_uses_existing_lower_left_default(self):
        bounds=QRect(-1600,-200,1600,900)
        for anchor in (None,QRect()):
            with self.subTest(anchor=anchor):
                self.assertEqual(task_strip_rect(bounds,anchor),floating_rect(bounds,width=420))

    def test_saved_negative_screen_position_roundtrips_and_overrides_anchor(self):
        bounds=QRect(-1920,-200,1920,1040);rect=QRect(-1500,500,420,30)
        saved=remember_position(rect,bounds,'secondary')
        self.assertEqual(task_strip_rect(bounds,position=saved),rect)
        self.assertEqual(task_strip_rect(bounds,QRect(-1000,200,200,30),saved),rect)
        smaller=QRect(0,0,800,600)
        self.assertTrue(smaller.contains(task_strip_rect(smaller,position=saved)))

    def test_narrow_screen_and_edge_anchor_keep_whole_strip_inside(self):
        bounds=QRect(-400,-200,400,300);anchor=QRect(-50,-80,50,30)
        rect=task_strip_rect(bounds,anchor)
        self.assertEqual(rect.width(),368);self.assertEqual(rect.height(),30)
        self.assertTrue(bounds.contains(rect))
        saved={'screen':'removed','x':1.,'y':1.,'width':420}
        restored=task_strip_rect(bounds,position=saved)
        self.assertEqual(restored.width(),368);self.assertTrue(bounds.contains(restored))
        tiny=QRect(0,0,20,20)
        self.assertTrue(tiny.contains(task_strip_rect(tiny,QRect(0,0,10,10))))

    def test_settings_roundtrip_preserves_independent_positions(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'settings.json';settings=read_settings(path)
            self.assertIsNone(settings['task_strip_position'])
            original={'screen':'original','x':.2,'y':.7,'width':250}
            task={'screen':'task','x':.5,'y':.4,'width':420}
            settings.update(floating_position=original,task_strip_position=task,chart_unit='100M')
            write_settings(path,settings);loaded=read_settings(path)
            self.assertEqual(loaded,settings)
            loaded['task_strip_position']=dict(task,x=.8)
            write_settings(path,loaded);restored=read_settings(path)
            self.assertEqual(restored['floating_position'],original)
            self.assertEqual(restored['task_strip_position'],dict(task,x=.8))
            self.assertEqual(restored['chart_unit'],'100M')

    def test_task_position_does_not_replace_existing_display_fallback(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'settings.json'
            task={'screen':'task','x':.5,'y':.4}
            original={'screen':'original','x':.2,'y':.7}
            for value,expected in (({'task_strip_position':task},None),
                                   ({'floating_position':original,'task_strip_position':task},'original')):
                path.write_text(json.dumps(value))
                self.assertEqual(read_settings(path)['floating_display'],expected)

    def test_invalid_task_positions_do_not_affect_original_position(self):
        original={'screen':'original','x':.2,'y':.7,'width':250}
        invalid=(None,[],{}, {'screen':3,'x':0,'y':0},
                 {'screen':'task','x':True,'y':0}, {'screen':'task','x':0,'y':False},
                 {'screen':'task','x':float('nan'),'y':0},
                 {'screen':'task','x':0,'y':float('inf')},
                 {'screen':'task','x':-.1,'y':0}, {'screen':'task','x':0,'y':1.1})
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'settings.json'
            for value in invalid:
                with self.subTest(value=value):
                    path.write_text(json.dumps({'floating_position':original,'task_strip_position':value}))
                    loaded=read_settings(path)
                    self.assertIsNone(loaded['task_strip_position'])
                    self.assertEqual(loaded['floating_position'],original)
                    self.assertEqual(loaded['floating_display'],'original')

    def test_optional_reference_width_must_be_a_positive_integer(self):
        task={'screen':'task','x':.5,'y':.4}
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'settings.json'
            for width in (None,True,0,-1,420.,'420'):
                with self.subTest(width=width):
                    path.write_text(json.dumps({'task_strip_position':dict(task,width=width)}))
                    self.assertEqual(read_settings(path)['task_strip_position'],task)
            for width in (1,420,540,891,10000):
                with self.subTest(width=width):
                    path.write_text(json.dumps({'task_strip_position':dict(task,width=width)}))
                    self.assertEqual(read_settings(path)['task_strip_position'],dict(task,width=width))


if __name__=='__main__':unittest.main()
