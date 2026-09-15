import unittest
from unittest.mock import patch
from codex_taskbar import app
from tests import test_interactions as fixtures


class NavigationPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixtures.InteractionTests.setUpClass()
    def setUp(self):
        fixtures.InteractionTests.setUp(self)
        self.bar.motion_enabled=False;self.bar.setGeometry(160,700,450,30);self.bar.position=self.bar.geometry().getRect()
    def tearDown(self):fixtures.InteractionTests.tearDown(self)

    def test_every_panel_keeps_left_anchor_and_pinned_rows_during_switch_and_refresh(self):
        group=self.bar.task_strip;pins=list(self.bar.settings['pinned_statuses'])
        with patch.object(self.bar,'isVisible',return_value=True),patch.object(group,'isVisible',return_value=True):
            group.refresh(self.data);active=list(group.active)
            for mode,kind in [('usage',app.TaskPopup),('daily',app.TaskListPopup),('session',app.SessionPopup),('resets',app.ResetPopup),('running',app.TaskListPopup)]:
                panel=kind(self.bar,mode) if kind is app.TaskListPopup else kind(self.bar)
                self.bar.popup=panel
                try:
                    panel.refresh(self.data);panel.reveal_to(1.);self.bar.grab();before=panel.geometry()
                    self.assertEqual(panel.x(),self.bar.x())
                    self.assertLessEqual(panel.geometry().bottom()+panel.GAP,group.geometry().top())
                    group.refresh(self.data);panel.refresh(self.data)
                    self.assertEqual(group.active,active);self.assertEqual(self.bar.settings['pinned_statuses'],pins)
                    self.assertEqual(panel.geometry(),before)
                    for progress in (0.,.5,1.):panel.set_reveal(progress);self.assertEqual(panel.geometry(),before)
                finally:self.bar.popup=None;panel.close();panel.deleteLater()

    def test_button_selection_is_stronger_than_hover_and_closing_restores_it(self):
        self.bar.settings['capsule_theme']='dark';self.bar.track_pointer(app.QPointF(-1,-1));base=self.bar.grab().toImage()
        rect=self.bar.feedback_regions['usage'];ratio=base.devicePixelRatio();x=round(rect.center().x()*ratio);y=round(5*ratio)
        self.bar.track_pointer(rect.center());hover=self.bar.grab().toImage()
        self.assertIsNone(self.bar.popup)
        panel=app.TaskPopup(self.bar);self.bar.popup=panel;panel.refresh(self.data);panel.reveal_to(1.)
        selected=self.bar.grab().toImage()
        self.assertGreater(hover.pixelColor(x,y).lightness(),base.pixelColor(x,y).lightness())
        self.assertGreater(selected.pixelColor(x,y).lightness(),hover.pixelColor(x,y).lightness())
        self.bar.hide_popup(immediate=True);self.bar.track_pointer(app.QPointF(-1,-1))
        self.assertEqual(self.bar.grab().toImage().pixelColor(x,y),base.pixelColor(x,y))

    def test_multiple_projects_stay_attached_to_each_task(self):
        self.data['tasks']=[dict(self.data['tasks'][0],id=str(i),project=project,title='Task '+str(i)) for i,project in enumerate(('Alpha','Beta','Alpha'))]
        panel=app.TaskListPopup(self.bar,'running');panel.refresh(self.data)
        try:
            with patch('codex_taskbar.app.project_tag',wraps=app.project_tag) as labels:panel.grab()
            self.assertEqual([c.args[3] for c in labels.call_args_list],[t['project'] for t in panel.rows])
            self.assertEqual(len(panel.rows),3);self.assertEqual(len(panel.sections),1)
        finally:panel.close();panel.deleteLater()
