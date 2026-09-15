from contextlib import ExitStack
from unittest.mock import Mock,patch
import unittest

from PySide6.QtCore import Qt,QEvent,QPoint,QPointF,QRect,QRectF,QTimer,QAbstractAnimation
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication,QWidget

from codex_taskbar import app
from codex_taskbar.task_strip import TaskStrip
from codex_taskbar.tasks import category_counts


def task(identifier,title=None,**fields):
    return {'id':identifier,'project':'Fixture','title':title or identifier,'running':True,**fields}


class TaskStripTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.application=QApplication.instance() or QApplication([])

    def setUp(self):
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        self.visible=Mock(return_value=False);self.show=Mock()
        self.stack.enter_context(patch.object(TaskStrip,'show',new=lambda strip:self.show()))
        self.owner=QWidget();self.owner.settings={'show_tasks':True,'pinned_statuses':['running'],'language':'en','floating_position':{'screen':'unchanged','x':.2,'y':.8,'width':300}}
        self.owner.language='en';self.owner.font=app.face();self.owner.motion_enabled=False
        self.owner.label=lambda key,**values:app.translate(self.owner.language,key,**values)
        self.owner.menu=Mock();self.owner.menu.isVisible.return_value=False
        self.owner.settings_dialog=None;self.owner.confirming_reset=False
        self.owner.open_task=Mock();self.owner.save_settings=Mock();self.owner.hide_popup=Mock()
        self.parent=QWidget();self.addCleanup(self.parent.deleteLater)
        self.owner.set_status_pinned=Mock()
        self.strip=TaskStrip(self.owner,parent=self.parent)
        self.addCleanup(self.strip.deleteLater);self.addCleanup(self.owner.deleteLater);self.addCleanup(self.strip.shutdown)

    def refresh(self,tasks,now=0,**kwargs):
        with patch('codex_taskbar.task_strip.time.monotonic',return_value=now):
            self.strip.refresh({'tasks':tasks},**kwargs)
        self.strip.grab()

    def event(self,kind,point,global_point=None,button=Qt.MouseButton.LeftButton):
        return QMouseEvent(kind,QPointF(point),QPointF(global_point or self.strip.mapToGlobal(QPointF(point).toPoint())),
                           button,Qt.MouseButton.NoButton if kind==QEvent.Type.MouseButtonRelease else button,Qt.KeyboardModifier.NoModifier)

    def press(self,point=None):
        point=point or self.strip.task_area.center()
        self.strip.mousePressEvent(self.event(QEvent.Type.MouseButtonPress,point));return point

    def release(self,point):self.strip.mouseReleaseEvent(self.event(QEvent.Type.MouseButtonRelease,point))

    def test_constructor_has_transparency_before_native_handle_and_no_new_clock(self):
        self.assertTrue(self.strip.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground))
        self.assertTrue(self.strip.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating))
        self.assertFalse(self.strip.testAttribute(Qt.WidgetAttribute.WA_WState_Created))
        self.assertEqual(self.strip.findChildren(QTimer),[]);self.show.assert_not_called()

    def test_candidates_match_running_count_and_keep_main_side_identity(self):
        items=[task('main',task_role='main'),task('side',side_chat=True,parent_id='main'),task('waiting',needs_input=True),task('done',running=False)]
        self.refresh(items)
        self.assertEqual([item['id'] for item in self.strip.candidates],['main','side'])
        self.assertEqual(len(self.strip.candidates),category_counts({'tasks':items})['running'])
        self.assertEqual(self.strip.task['task_role'],'main')

    def test_zero_one_many_rotation_and_stable_width(self):
        self.refresh([]);self.visible.assert_not_called();self.assertIsNone(self.strip.task)
        self.refresh([task('a')]);width=self.strip.width()
        self.refresh([task('a')],now=80);self.assertEqual(self.strip.current_id,'a')
        self.refresh([task('a'),task('b','A substantially longer second task')],now=88)
        self.assertEqual(self.strip.current_id,'b');self.assertEqual(self.strip.width(),width)
        self.refresh([],now=89);self.assertIsNone(self.strip.task);self.assertEqual(self.strip.task_area,QRectF())

    def test_hover_resumes_remaining_rotation_time(self):
        items=[task('a'),task('b')];self.refresh(items)
        with patch('codex_taskbar.task_strip.time.monotonic',return_value=6):self.strip.track_pointer(self.strip.task_area.center())
        self.refresh(items,now=30);self.assertEqual(self.strip.current_id,'a')
        with patch('codex_taskbar.task_strip.time.monotonic',return_value=30):self.strip.track_pointer(QPointF(-1,-1))
        self.refresh(items,now=31);self.assertEqual(self.strip.current_id,'a')
        self.refresh(items,now=32);self.assertEqual(self.strip.current_id,'b')

    def test_single_task_new_candidate_does_not_accumulate_multiple_rotations(self):
        self.refresh([task('a')]);self.refresh([task('a')],now=100)
        self.refresh([task('a'),task('b'),task('c')],now=101)
        self.assertEqual(self.strip.current_id,'b')
        self.refresh([task('a'),task('b'),task('c')],now=102);self.assertEqual(self.strip.current_id,'b')

    def test_press_pins_task_but_refreshes_eligibility(self):
        self.refresh([task('a'),task('b')]);point=self.press()
        self.refresh([task('b')],now=10)
        self.assertEqual(self.strip.task['id'],'a');self.assertEqual(self.strip.candidates[0]['id'],'b')
        self.release(point);self.owner.open_task.assert_not_called()
        self.refresh([task('b')],now=11);self.assertEqual(self.strip.task['id'],'b')

    def test_press_survives_refresh_and_preserves_side_parent(self):
        item=task('side',side_chat=True,parent_id='parent');self.refresh([item]);point=self.press()
        self.refresh([{**item,'title':'updated after press'}],now=10);self.release(point)
        self.owner.open_task.assert_called_once_with(item)

    def test_release_outside_task_or_click_on_pin_does_not_open(self):
        self.refresh([task('a')]);self.press();self.release(QPointF(-2,-2))
        self.press(QPointF(self.strip.width()-20,15));self.release(QPointF(self.strip.width()-20,15))
        self.owner.open_task.assert_not_called()

    def test_visible_row_padding_opens_task_but_corners_and_pin_do_not(self):
        item=task('a','Short',project='Demo');self.refresh([item])
        points=(QPointF(2,15),QPointF(self.strip.pin_button.x()-3,15),QPointF(self.strip.width()-3,15))
        for point in points:
            with self.subTest(point=point):
                self.owner.open_task.reset_mock();self.assertTrue(self.strip.task_at_point(point))
                self.press(point);self.release(point);self.owner.open_task.assert_called_once_with(item)
        self.owner.open_task.reset_mock()
        for point in (QPointF(1,1),QPointF(self.strip.width()-1,1),QPointF(self.strip.pin_button.geometry().center())):
            self.assertFalse(self.strip.task_at_point(point));self.press(point);self.release(point)
        self.strip.pin_button.click()
        self.owner.open_task.assert_not_called();self.owner.set_status_pinned.assert_called_once_with('running',False)

    def test_project_tag_and_title_share_handoff_and_keep_marquee_out_of_tag_and_pin(self):
        self.owner.motion_enabled=True;items=[task('a','First title '*30,project='Alpha'),task('b','Second title '*30,project='Beta')]
        self.refresh(items);self.refresh(items,now=8);self.strip.task_tween.setCurrentTime(180)
        with patch('codex_taskbar.app.project_tag',wraps=app.project_tag) as tags,patch('codex_taskbar.app.running_title',wraps=app.running_title) as titles:
            self.strip.grab()
        self.assertEqual([call.args[3] for call in tags.call_args_list],['Alpha','Beta'])
        for tag,title in zip(tags.call_args_list,titles.call_args_list):
            self.assertEqual(tag.args[2],title.args[2])
            self.assertGreater(title.args[1],tag.args[1]);self.assertEqual(title.args[1],title.args[5])
            self.assertLessEqual(title.args[5]+title.args[6],self.strip.pin_button.x()-8)
        self.strip.task_tween.setCurrentTime(450);self.strip.task_hover=True
        with patch('codex_taskbar.app.marquee_offset',wraps=app.marquee_offset) as marquee,patch('codex_taskbar.app.project_tag',wraps=app.project_tag) as tags:
            self.strip.grab()
        self.assertEqual(tags.call_args.args[1],30)
        available=self.strip.width()-40-self.strip.task_rect.x()
        self.assertAlmostEqual(marquee.call_args.args[1],app.QFontMetricsF(self.owner.font).horizontalAdvance(items[1]['title'])-available)

    def test_long_and_missing_projects_are_localized_and_elided(self):
        for language in ('en','zh-CN','ja','es'):
            self.owner.language=language
            for project in ('','A very long project name '*8):
                self.refresh([task('a','Title',project=project)])
                with patch('codex_taskbar.app.text',wraps=app.text) as draw:self.strip.grab()
                project_draw=next(call.args for call in draw.call_args_list if call.args[1]==36)
                rendered=project_draw[3]
                self.assertTrue(rendered)
                self.assertLessEqual(app.QFontMetricsF(project_draw[4]).horizontalAdvance(rendered)+12,90)
                if not project:self.assertEqual(rendered,app.project_label('',language))
                else:self.assertIn('…',rendered)
                self.assertGreater(self.strip.task_rect.x(),36)

    def test_transition_click_uses_visible_item_and_freezes_both_labels(self):
        self.owner.motion_enabled=True;items=[task('a','First',project='Alpha'),task('b','Second',project='Beta')]
        self.refresh(items);self.refresh(items,now=8)
        self.strip.task_tween.setCurrentTime(100);self.strip.grab()
        self.assertEqual(self.strip.displayed_task()['id'],'a')
        point=self.press();blend=self.strip.task_blend
        self.assertEqual(self.strip.task_tween.state(),QAbstractAnimation.State.Paused)
        self.refresh(items,now=9);self.assertEqual(self.strip.task_blend,blend)
        self.release(point);self.owner.open_task.assert_called_once_with(items[0])

    def test_title_marquee_waits_until_handoff_finishes(self):
        self.owner.motion_enabled=True;self.refresh([task('a','Long first title '*20),task('b','Long second title '*20)])
        self.refresh([task('a','Long first title '*20),task('b','Long second title '*20)],now=8)
        self.strip.task_tween.setCurrentTime(100);self.strip.task_hover=True
        with patch('codex_taskbar.app.marquee_offset',wraps=app.marquee_offset) as marquee:
            self.strip.grab();marquee.assert_not_called()
            self.strip.task_tween.setCurrentTime(450);self.strip.grab();marquee.assert_called_once()

    def test_drag_cancels_click_without_moving_attached_row(self):
        self.refresh([task('a')]);original=dict(self.owner.settings['floating_position'])
        point=self.press();start=self.strip.mapToGlobal(point.toPoint());threshold=QApplication.startDragDistance()
        self.strip.mouseMoveEvent(self.event(QEvent.Type.MouseMove,point+QPointF(threshold-1,0),start+QPoint(threshold-1,0)))
        self.assertFalse(self.strip.dragging)
        self.strip.mouseMoveEvent(self.event(QEvent.Type.MouseMove,point+QPointF(threshold,0),start+QPoint(threshold,0)))
        self.assertTrue(self.strip.dragging);self.assertIsNone(self.strip.pressed)
        self.release(point);self.owner.open_task.assert_not_called();self.owner.save_settings.assert_not_called()
        self.assertEqual(self.owner.settings['floating_position'],original)
        self.assertNotIn('task_strip_position',self.owner.settings)

    def test_hidden_or_disabled_strip_cancels_press_and_stops_paint_clock(self):
        self.refresh([task('a')]);self.press()
        self.refresh([task('a')],now=3,hidden=True)
        self.assertIsNone(self.strip.pressed);self.assertIsNone(self.strip.drag_origin);self.assertFalse(self.strip.needs_animation)
        self.refresh([task('a')],now=4,hidden=True);self.assertTrue(self.strip.hidden)

    def test_fullscreen_restore_preserves_pause_progress(self):
        items=[task('a'),task('b')];self.refresh(items)
        self.refresh(items,now=6,hidden=True);self.refresh(items,now=60)
        self.assertEqual(self.strip.current_id,'a')
        self.refresh(items,now=62);self.assertEqual(self.strip.current_id,'b')

    def test_languages_keep_content_and_finite_title_space_without_resizing(self):
        item=task('side','A long unchanged task title '*15,project='',side_chat=True,parent_id='parent')
        self.refresh([item]);initial=self.strip.geometry()
        for language in ('en','zh-CN','ja','es'):
            self.owner.language=language
            with patch('codex_taskbar.app.side_tag',wraps=app.side_tag) as label:self.strip.grab()
            label.assert_not_called();self.assertGreater(self.strip.task_rect.width(),200)
            self.assertEqual(self.strip.geometry(),initial);self.assertEqual(self.strip.task['title'],item['title'])

    def test_reduced_motion_finishes_transition_and_shared_clock_only_paints_visible(self):
        self.owner.motion_enabled=True;self.refresh([task('a'),task('b')]);self.refresh([task('a'),task('b')],now=8)
        self.owner.motion_enabled=False;self.strip.sync_motion()
        self.assertEqual(self.strip.task_blend,1.);self.assertIsNone(self.strip.previous_task)
        self.assertEqual(self.strip.task_tween.state(),QAbstractAnimation.State.Stopped)
        with patch.object(self.strip,'update') as update:self.strip.animate();update.assert_not_called()
        self.owner.motion_enabled=True
        with patch.object(self.strip,'isVisible',return_value=True),patch.object(self.strip,'update') as update:
            self.strip.animate();update.assert_called_once()

    def test_only_deliberate_long_title_hover_needs_a_paint_clock(self):
        self.owner.motion_enabled=True;self.strip.category='unread';self.refresh([task('a',running=False,unread=True)])
        with patch.object(self.strip,'isVisible',return_value=True):
            self.assertFalse(self.strip.needs_animation)
            self.strip.track_pointer(self.strip.task_area.center());self.assertFalse(self.strip.needs_animation)
            self.refresh([task('a','Long task title '*40,running=False,unread=True)])
            self.strip.track_pointer(self.strip.task_area.center());self.assertTrue(self.strip.needs_animation)
            with patch.object(self.strip,'update') as update:self.strip.animate();update.assert_called_once()
            self.strip.track_pointer(QPointF(-1,-1));self.assertFalse(self.strip.needs_animation)

    def test_shutdown_cleans_interaction_and_future_refresh_is_noop(self):
        self.refresh([task('a')]);self.press();self.strip.shutdown();self.visible.reset_mock()
        self.assertIsNone(self.strip.pressed);self.assertIsNone(self.strip.drag_origin)
        self.assertEqual(self.strip.task_tween.state(),QAbstractAnimation.State.Stopped)
        self.refresh([task('b')],now=8);self.visible.assert_not_called()

    def test_running_dot_and_highlight_move_without_moving_targets(self):
        self.owner.motion_enabled=True;self.refresh([task('a','Working')])
        with patch('codex_taskbar.task_strip.time.monotonic',return_value=0):first=self.strip.grab().toImage()
        area=QRectF(self.strip.task_area)
        with patch('codex_taskbar.task_strip.time.monotonic',return_value=1.4):second=self.strip.grab().toImage()
        self.assertNotEqual(first,second);self.assertEqual(self.strip.task_area,area)
        self.owner.motion_enabled=False
        with patch('codex_taskbar.task_strip.time.monotonic',return_value=0):first=self.strip.grab().toImage()
        with patch('codex_taskbar.task_strip.time.monotonic',return_value=1.4):second=self.strip.grab().toImage()
        self.assertEqual(first,second)
        with patch.object(self.strip,'isVisible',return_value=False):self.assertFalse(self.strip.needs_animation)

    def test_codex_cadence_waits_then_sweeps_without_loop_seams(self):
        self.owner.motion_enabled=True;self.refresh([task('a','Tracing the import')]);self.strip.shimmer_started=0
        area=QRectF(self.strip.task_rect);hits=QRectF(self.strip.task_area)
        def frame(at):
            with patch('codex_taskbar.app.time.monotonic',return_value=at):
                image=self.strip.grab().toImage();scale=image.devicePixelRatio()
                return image.copy(QRect(round(area.x()*scale),0,round(area.width()*scale),image.height()))
        app.running_text_raster.cache_clear()
        first=frame(.2);swept=frame(1.0)
        self.assertNotEqual(first,swept);self.assertEqual(first,frame(2.5));self.assertEqual(first,frame(2.6));self.assertEqual(swept,frame(3.0))
        self.assertEqual(app.running_text_raster.cache_info().misses,1)
        self.assertEqual(self.strip.task_area,hits);self.assertEqual(self.strip.task_rect,area)
        self.owner.motion_enabled=False
        self.assertEqual(first,frame(.9))

    def test_fitting_title_hover_keeps_sweep_and_reading_overflow_uses_plain_text(self):
        self.owner.motion_enabled=True;self.refresh([task('a','Working')]);self.strip.track_pointer(self.strip.task_area.center())
        with patch('codex_taskbar.app.running_title',wraps=app.running_title) as light:self.strip.grab();light.assert_called_once()
        self.refresh([task('a','Long running task title '*40)]);self.strip.track_pointer(self.strip.task_area.center())
        with patch('codex_taskbar.app.running_title',wraps=app.running_title) as light:self.strip.grab();light.assert_not_called()

    def test_handoff_uses_cached_ink_with_parent_opacity_and_hidden_rows_reset_cadence(self):
        self.owner.motion_enabled=True;tasks=[task('a','First task'),task('b','Second task')]
        self.refresh(tasks,now=0);self.assertEqual(self.strip.shimmer_started,0)
        self.refresh(tasks,now=8);self.assertEqual(self.strip.shimmer_started,0);self.strip.set_task_blend(.5)
        with patch('codex_taskbar.app.running_title',wraps=app.running_title) as light:self.strip.grab();self.assertEqual(light.call_count,2)
        self.refresh(tasks,now=9,hidden=True);self.assertIsNone(self.strip.shimmer_started)
        self.refresh(tasks,now=12);self.assertEqual(self.strip.shimmer_started,12)

    def test_mask_is_composed_before_parent_fade_opacity(self):
        def render(opacity):
            image=app.QImage(220,40,app.QImage.Format.Format_ARGB32_Premultiplied);image.fill(Qt.GlobalColor.transparent)
            painter=app.QPainter(image);painter.setOpacity(opacity)
            app.running_title(painter,12,20,'Thinking',self.owner.font,12,app.QFontMetricsF(self.owner.font).horizontalAdvance('Thinking'),app.MUTED,elapsed=.9)
            painter.end();return image
        full=render(1);half=render(.5);visible=0
        for y in range(full.height()):
            for x in range(full.width()):
                alpha=full.pixelColor(x,y).alpha()
                if alpha:
                    visible+=1;self.assertLessEqual(abs(half.pixelColor(x,y).alpha()-alpha*.5),1)
        self.assertGreater(visible,50)

    def test_cached_ink_matches_normal_text_at_fractional_pixel_scales(self):
        for scale in (1.,1.25,1.5,2.):
            images=[]
            for masked in (False,True):
                image=app.QImage(round(240*scale),round(44*scale),app.QImage.Format.Format_ARGB32_Premultiplied);image.setDevicePixelRatio(scale);image.fill(Qt.GlobalColor.transparent)
                painter=app.QPainter(image);painter.setRenderHint(app.QPainter.RenderHint.TextAntialiasing)
                if masked:app.running_title(painter,12.3,18.7,'任务状态 · Thinking',self.owner.font,12.3,210,app.MUTED,elapsed=.2)
                else:app.text(painter,12.3,18.7,'任务状态 · Thinking',self.owner.font,app.MUTED)
                painter.end();images.append(image)
            self.assertEqual(images[0],images[1],scale)


if __name__=='__main__':unittest.main()
