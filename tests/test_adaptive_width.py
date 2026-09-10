import unittest
from unittest.mock import patch
from PySide6.QtCore import QRect
from codex_taskbar import app
from codex_taskbar.presentation import floating_rect,remember_position
from tests import test_interactions as fixtures


class AdaptiveWidthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.application=app.QApplication.instance() or app.QApplication([])

    def setUp(self):
        fixtures.InteractionTests.setUp(self)
        self.bar.settings['rotate_quotas']=True;self.bar.content_limit=540
        self.data['recent_tasks']=[];self.data['tasks'][0].update(title='Short task',project='App')

    def tearDown(self):fixtures.InteractionTests.tearDown(self)

    def test_short_content_fits_and_long_content_retains_original_cap(self):
        width=self.bar.content_width(540);self.assertLess(width,400)
        self.bar.resize(width,30);self.bar.grab()
        self.assertAlmostEqual(self.bar.task_rect.right(),width-12,delta=1)
        self.data['tasks'][0]['title']='Long task title '*30
        self.assertEqual(self.bar.content_width(540),540)
        self.assertEqual(self.bar.content_width(400),400)

    def test_rotation_uses_longest_task_regardless_of_order_or_selection(self):
        self.data['tasks'].append({**self.data['tasks'][0],'id':'second','title':'A slightly longer task'})
        width=self.bar.content_width(540)
        self.bar.task=self.data['tasks'][1];self.data['tasks'].reverse()
        self.assertEqual(self.bar.content_width(540),width)
        self.data['tasks']=[self.data['tasks'][-1]]
        self.assertLess(self.bar.content_width(540),width)

    def test_metrics_only_capsule_does_not_reserve_task_space(self):
        with_task=self.bar.content_width(540);self.data['tasks']=[]
        metrics_only=self.bar.content_width(540)
        self.assertLess(metrics_only,with_task)
        self.bar.settings['show_tasks']=False
        self.assertEqual(self.bar.content_width(540),metrics_only)

    def test_shrink_is_deferred_while_interacting_but_respects_available_space(self):
        self.bar.setGeometry(100,100,400,30);self.bar.position=(100,100,400,30)
        with patch.object(self.bar,'underMouse',return_value=True):
            self.assertEqual(self.bar.fitted_width(540),400)
            self.assertEqual(self.bar.fitted_width(350),350)
        with patch.object(self.bar,'underMouse',return_value=False):self.assertLess(self.bar.fitted_width(540),400)

    def test_panels_keep_readable_width_when_capsule_is_short(self):
        self.bar.resize(150,30);panel=app.TaskListPopup(self.bar);panel.refresh(self.data)
        self.assertGreaterEqual(panel.width(),360);self.assertLessEqual(panel.width(),540)
        panel.close();panel.deleteLater()

    def test_floating_left_anchor_does_not_move_when_width_changes(self):
        bounds=QRect(0,0,1600,900);old={'screen':'screen','x':.5,'y':.7}
        full=floating_rect(bounds,old);short=floating_rect(bounds,old,250)
        self.assertEqual(full.x(),short.x());self.assertEqual(full.y(),short.y())
        saved=remember_position(short,bounds,'screen')
        self.assertEqual(floating_rect(bounds,saved,250),short)
        self.assertEqual(floating_rect(bounds,saved,350).x(),short.x())

    def test_growing_near_screen_edge_clamps_whole_capsule(self):
        bounds=QRect(-1600,0,1600,900);short=QRect(-250,300,250,30)
        saved=remember_position(short,bounds,'screen')
        self.assertEqual(floating_rect(bounds,saved,250),short)
        self.assertTrue(bounds.contains(floating_rect(bounds,saved,540)))
