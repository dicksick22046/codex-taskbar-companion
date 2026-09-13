import tempfile,unittest
from pathlib import Path
from unittest.mock import patch,Mock
from codex_taskbar import app
from codex_taskbar.preferences import read_settings,write_settings
from tests import test_interactions as fixtures


class PinnedPreferenceTests(unittest.TestCase):
    def test_migration_preserves_choice_and_drops_independent_position(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'settings.json'
            for data,expected in [({},[]),({'show_task_strip':True},['running']),({'show_tasks':True},['running']),
                ({'show_tasks':True,'show_task_strip':False},[]),({'show_task_strip':True,'pinned_statuses':[]},[]),
                ({'pinned_statuses':['unread','running','unread','invalid']},['running','unread'])]:
                with self.subTest(data=data):
                    write_settings(path,{**data,'task_strip_position':{'screen':'old','x':.4,'y':.4},'chart_unit':'100M'})
                    result=read_settings(path);self.assertEqual(result['pinned_statuses'],expected)
                    self.assertNotIn('show_task_strip',result);self.assertNotIn('task_strip_position',result)
                    self.assertEqual(result['chart_unit'],'100M')
                    write_settings(path,result);self.assertEqual(read_settings(path)['pinned_statuses'],expected)


class PinnedPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.application=app.QApplication.instance() or app.QApplication([])
    def setUp(self):
        fixtures.InteractionTests.setUp(self);self.group=self.bar.task_strip
        self.bar.settings.update(pinned_statuses=['running','unread']);self.bar.motion_enabled=False
        self.bar.setGeometry(100,500,300,30)
        self.visible=patch.object(self.bar,'isVisible',return_value=True);self.visible.start();self.addCleanup(self.visible.stop)
    def tearDown(self):fixtures.InteractionTests.tearDown(self)

    def test_rows_attach_and_empty_categories_keep_preferences(self):
        self.group.refresh(self.data);self.assertEqual(self.group.active,['running','unread'])
        self.assertEqual(self.group.width(),self.bar.width());self.assertEqual(self.group.geometry().bottom(),self.bar.y())
        self.assertEqual(self.group.joined_edge,'top');self.assertEqual(self.group.rows['unread'].y(),30)
        self.data['recent_tasks']=[];self.group.refresh(self.data)
        self.assertEqual(self.group.active,['running']);self.assertEqual(self.bar.settings['pinned_statuses'],['running','unread'])
        self.group.refresh(self.data,hidden=True);self.assertIsNone(self.group.joined_edge)
        self.assertFalse(self.group.needs_animation)
        self.bar.move(100,0);self.group.refresh(self.data)
        self.assertEqual(self.group.joined_edge,'bottom');self.assertEqual(self.group.y(),self.bar.geometry().bottom())

    def test_taskbar_inset_does_not_leave_a_gap_at_work_area_boundary(self):
        screen=Mock();screen.availableGeometry.return_value=app.QRect(0,0,1200,800);screen.geometry.return_value=app.QRect(0,0,1200,840)
        self.bar.settings['placement']='taskbar';self.bar.setGeometry(100,808,300,30)
        with patch.object(self.bar,'screen',return_value=screen):self.group.refresh(self.data)
        self.assertEqual(self.group.geometry().bottom(),808)

    def test_pin_from_popover_and_unpin_row_do_not_open_task(self):
        self.bar.settings['pinned_statuses']=[]
        panel=app.TaskListPopup(self.bar,'running');panel.refresh(self.data)
        with patch.object(self.bar,'tick'),patch.object(self.bar,'save_settings') as saved,patch.object(self.bar,'open_task') as opened:
            panel.pin_button.click();self.assertEqual(self.bar.settings['pinned_statuses'],['running']);saved.assert_called_once()
            self.group.rows['running'].pin_button.click();self.assertEqual(self.bar.settings['pinned_statuses'],[]);opened.assert_not_called()
        panel.close();panel.deleteLater()

    def test_hover_and_rotation_are_independent_and_small_bar_has_room(self):
        self.data['tasks'].append(dict(self.data['tasks'][0],id='run2',title='Another running task'))
        self.data['recent_tasks'].append(dict(self.data['recent_tasks'][0],id='unread2'))
        with patch('codex_taskbar.task_strip.time.monotonic',return_value=0):self.group.refresh(self.data)
        first=self.group.rows['running'];second=self.group.rows['unread'];first.grab()
        with patch('codex_taskbar.task_strip.time.monotonic',return_value=6):first.track_pointer(first.task_area.center())
        with patch('codex_taskbar.task_strip.time.monotonic',return_value=9):self.group.refresh(self.data)
        self.assertEqual(first.task['id'],'running');self.assertEqual(second.task['id'],'unread2')
        for key in ('show_week','show_session','show_daily','show_countdown'):self.bar.settings[key]=False
        self.assertGreaterEqual(self.bar.content_width(float('inf')),240)

    def test_height_motion_reverses_and_hidden_state_stops_it(self):
        self.bar.motion_enabled=True;self.group.refresh(self.data)
        self.group.size_motion.advance(.02);height=self.group.size_motion.value
        self.assertGreater(height,0);self.assertLess(height,61)
        self.bar.settings['pinned_statuses']=[];self.group.refresh(self.data)
        self.assertEqual(self.group.size_motion.value,height);self.assertEqual(self.group.size_motion.target,0)
        self.group.refresh(self.data,hidden=True);self.assertFalse(self.group.size_motion.timer.isActive())

    def test_joined_surface_is_solid_and_hover_is_visible(self):
        for edge in ('top','bottom'):
            shape=app.connected_surface(app.QRectF(1,1,298,30),edge)
            self.assertTrue(shape.contains(app.QPointF(150,4)));self.assertTrue(shape.contains(app.QPointF(150,27)))
        self.group.refresh(self.data);row=self.group.rows['running'];row.track_pointer(app.QPointF(-1,-1))
        before=row.grab().toImage();row.track_pointer(app.QPointF(55,15));after=row.grab().toImage()
        self.assertNotEqual(before,after);self.assertTrue(row.task_hover)
