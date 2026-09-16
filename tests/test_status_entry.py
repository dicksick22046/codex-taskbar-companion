import unittest
from unittest.mock import patch
from PySide6.QtCore import QEvent,QPointF
from PySide6.QtGui import QMouseEvent
from codex_taskbar import app
from tests import test_interactions as fixtures


class StatusEntryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixtures.InteractionTests.setUpClass()

    def setUp(self):
        self.fixture=fixtures.InteractionTests();self.fixture.setUp()
        self.bar=self.fixture.bar;self.data=self.fixture.data

    def tearDown(self):self.fixture.tearDown();self.fixture.doCleanups()

    def mouse(self,kind,point):
        held=app.Qt.MouseButton.NoButton if kind==QEvent.Type.MouseButtonRelease else app.Qt.MouseButton.LeftButton
        event=QMouseEvent(kind,QPointF(point),QPointF(self.bar.mapToGlobal(point.toPoint())),app.Qt.MouseButton.LeftButton,held,app.Qt.KeyboardModifier.NoModifier)
        self.fixture.application.sendEvent(self.bar,event)

    def test_single_status_click_navigates_in_both_placements_and_all_statuses(self):
        with patch.object(self.bar,'open_task',return_value=True) as opened,patch.object(self.bar,'toggle_popup') as popup, \
             patch.object(self.bar,'isVisible',return_value=True),patch('codex_taskbar.app.windows.rect',return_value=(0,0,1200,30)), \
             patch('codex_taskbar.app.windows.user32.GetDpiForWindow',return_value=96), \
             patch('codex_taskbar.app.QTimer.singleShot',side_effect=lambda ms,fn:fn()):
            for placement in ('taskbar','floating'):
                self.bar.settings['placement']=placement
                for category in app.STATUS_CATEGORIES:
                    task=dict(id=category,title='Single',project='',running=category in ('waiting','running'),
                              needs_input=category=='waiting',unread=category=='unread',status=category)
                    self.data.update(tasks=[task],recent_tasks=[]);self.bar.grab()
                    region=next(rect for mode,rect,_ in self.bar.hit_regions if mode==category);point=region.center()
                    opened.reset_mock();popup.reset_mock()
                    if placement=='floating':
                        self.mouse(QEvent.Type.MouseButtonPress,point);self.mouse(QEvent.Type.MouseButtonRelease,point)
                    else:
                        self.bar.desktop_click(point.x(),point.y());self.bar.desktop_click(point.x(),point.y(),'left_up')
                    opened.assert_called_once_with(task);popup.assert_not_called()
                    self.assertEqual(self.bar.hover_suppressed,category)

    def test_multiple_tasks_and_hover_keep_the_status_panel(self):
        self.data.update(tasks=[dict(id=str(i),title='Task',project='',running=True) for i in range(2)],recent_tasks=[])
        hit=('running',app.QRectF(0,0,50,30),None)
        self.bar.begin_press(hit);pressed=self.bar.release_press()
        with patch.object(self.bar,'toggle_popup') as popup,patch.object(self.bar,'open_task') as opened:
            self.bar.activate_status_entry(pressed[0],pressed[2]);popup.assert_called_once_with('running');opened.assert_not_called()
            popup.reset_mock();self.data['tasks']=self.data['tasks'][:1]
            self.bar.settings.update(placement='taskbar',hover_panels=True);self.bar.grab()
            point=self.bar.mapToGlobal(next(rect for mode,rect,_ in self.bar.hit_regions if mode=='running').center().toPoint())
            with patch.object(self.bar,'isVisible',return_value=True):
                self.bar.update_hover_popup(point,now=0);self.bar.update_hover_popup(point,now=.4)
            popup.assert_called_once_with('running',activate=False);opened.assert_not_called()

    def test_refresh_does_not_retarget_click_or_promote_a_list_click_to_navigation(self):
        original=dict(id='original',title='Task',project='',running=True)
        replacement=dict(original,id='replacement')
        hit=('running',app.QRectF(0,0,50,30),None)
        with patch.object(self.bar,'toggle_popup') as popup,patch.object(self.bar,'open_task',return_value=True) as opened:
            self.data.update(tasks=[original],recent_tasks=[]);self.bar.begin_press(hit);pressed=self.bar.release_press()
            self.data['tasks']=[replacement];self.bar.activate_status_entry(pressed[0],pressed[2])
            opened.assert_not_called();popup.assert_called_once_with('running')
            popup.reset_mock();self.data['tasks']=[original,replacement];self.bar.begin_press(hit);pressed=self.bar.release_press()
            self.data['tasks']=[original];self.bar.activate_status_entry(pressed[0],pressed[2])
            opened.assert_not_called();popup.assert_called_once_with('running')

    def test_floating_drag_and_release_outside_cancel_navigation(self):
        self.bar.settings['placement']='floating';self.bar.grab()
        point=next(rect for mode,rect,_ in self.bar.hit_regions if mode=='running').center()
        with patch.object(self.bar,'open_task') as opened,patch.object(self.bar,'toggle_popup') as popup,patch.object(self.bar,'save_settings'):
            self.mouse(QEvent.Type.MouseButtonPress,point);self.mouse(QEvent.Type.MouseButtonRelease,point+QPointF(0,80))
            self.mouse(QEvent.Type.MouseButtonPress,point);self.bar.dragging=True;self.mouse(QEvent.Type.MouseButtonRelease,point)
            opened.assert_not_called();popup.assert_not_called()

    def test_single_side_uses_existing_parent_navigation(self):
        parent='00000000-0000-4000-8000-000000000001'
        side=dict(id='00000000-0000-4000-8000-000000000002',navigation_id=parent,side_chat=True,running=True,title='Side',project='')
        self.data.update(tasks=[side],recent_tasks=[])
        self.bar.begin_press(('running',app.QRectF(0,0,50,30),None));pressed=self.bar.release_press()
        with patch('codex_taskbar.app.os.startfile') as opened:
            self.bar.activate_status_entry(pressed[0],pressed[2]);opened.assert_called_once_with('codex://threads/'+parent)
