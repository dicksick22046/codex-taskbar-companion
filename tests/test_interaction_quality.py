import unittest
from unittest.mock import patch,Mock
from PySide6.QtCore import Qt,QEvent,QPoint,QPointF,QAbstractAnimation
from PySide6.QtGui import QMouseEvent,QKeyEvent,QWheelEvent
from codex_taskbar import app
from codex_taskbar.motion import Spring,critical_step
from tests import test_interactions as fixtures


class InteractionQualityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.application=app.QApplication.instance() or app.QApplication([])
    def setUp(self):fixtures.InteractionTests.setUp(self)
    def tearDown(self):fixtures.InteractionTests.tearDown(self)

    def mouse(self,widget,kind,point):
        held=Qt.MouseButton.NoButton if kind==QEvent.Type.MouseButtonRelease else Qt.MouseButton.LeftButton
        self.application.sendEvent(widget,QMouseEvent(kind,QPointF(point),QPointF(widget.mapToGlobal(point)),Qt.MouseButton.LeftButton,held,Qt.KeyboardModifier.NoModifier))

    def wheel(self,widget,pixels=0,angle=-120):
        self.application.sendEvent(widget,QWheelEvent(QPointF(12,12),QPointF(12,12),QPoint(0,pixels),QPoint(0,angle),Qt.MouseButton.NoButton,Qt.KeyboardModifier.NoModifier,Qt.ScrollPhase.ScrollUpdate,False))

    def panel(self,mode='daily'):
        panel=app.TaskListPopup(self.bar,mode);self.bar.popup=panel;panel.refresh(self.data);panel.grab();return panel

    def test_unit_press_cancels_outside_and_commits_once_on_release(self):
        panel=self.panel();button=panel.unit_buttons['100M'];point=button.rect().center()
        with patch('codex_taskbar.app.write_settings') as save:
            self.mouse(button,QEvent.Type.MouseButtonPress,point)
            self.assertTrue(button.isDown());self.assertEqual(self.bar.chart_unit,'M');save.assert_not_called()
            self.mouse(button,QEvent.Type.MouseButtonRelease,QPoint(-10,12))
            self.assertEqual(self.bar.chart_unit,'M');save.assert_not_called()
            self.mouse(button,QEvent.Type.MouseButtonPress,point);self.mouse(button,QEvent.Type.MouseButtonRelease,point)
            self.assertEqual(self.bar.chart_unit,'100M');self.assertEqual(save.call_count,1)
            button.click();self.assertEqual(save.call_count,1)
        panel.scroll=200
        for rect in panel.unit_rects().values():self.assertIsNone(panel.task_at(rect.center()))

    def test_keyboard_navigation_keeps_target_visible_and_escape_closes(self):
        self.data['tasks']=[dict(self.data['tasks'][0],id=str(i),title=f'Task {i}') for i in range(30)]
        panel=self.panel('running');panel.resize(panel.width(),180)
        def key(code):self.application.sendEvent(panel,QKeyEvent(QEvent.Type.KeyPress,code,Qt.KeyboardModifier.NoModifier))
        with patch.object(panel,'focusWidget',return_value=panel),patch.object(self.bar,'open_task') as opened,patch.object(self.bar,'hide_popup') as closed:
            key(Qt.Key.Key_End);self.assertEqual(panel.keyboard_task,panel.rows[-1]['id']);self.assertGreater(panel.scroll,0)
            y=panel.row_positions[-1]+8-panel.scroll
            self.assertLessEqual(y+panel.ROW_HEIGHT,panel.height()-8)
            key(Qt.Key.Key_Return);self.assertEqual(opened.call_args.args[0]['id'],panel.rows[-1]['id'])
            key(Qt.Key.Key_Home);self.assertEqual(panel.keyboard_task,panel.rows[0]['id']);self.assertEqual(panel.scroll,0)
            key(Qt.Key.Key_Escape);closed.assert_called_once()

    def test_pixel_scrolling_and_scroll_cancels_a_pending_row_click(self):
        self.data['tasks']=[dict(self.data['tasks'][0],id=str(i)) for i in range(30)]
        panel=self.panel('running');panel.resize(panel.width(),180);panel.pressed_task=panel.rows[0]['id']
        self.wheel(panel,pixels=-13)
        self.assertEqual(panel.scroll,13);self.assertIsNone(panel.pressed_task)
        self.wheel(panel);self.assertEqual(panel.scroll,13+panel.ROW_HEIGHT)

    def test_covered_strip_does_not_intercept_and_context_menu_commits_on_release(self):
        point=self.bar.hit_regions[0][1].center()
        with patch.object(self.bar,'isVisible',return_value=True),patch('codex_taskbar.app.windows.rect',return_value=(0,0,1200,30)),patch('codex_taskbar.app.windows.user32.GetDpiForWindow',return_value=96),patch('codex_taskbar.app.QTimer.singleShot',side_effect=lambda ms,fn:fn()),patch.object(self.bar,'open_menu') as menu:
            with patch('codex_taskbar.app.windows.pointer_over',return_value=False):
                self.assertFalse(self.bar.desktop_click(point.x(),point.y()));self.assertIsNone(self.bar.pressed)
                self.assertFalse(self.bar.desktop_click(point.x(),point.y(),'right'))
            self.bar.desktop_click(point.x(),point.y(),'right');menu.assert_not_called()
            self.bar.desktop_click(-10,-10,'right_up');menu.assert_not_called()
            self.bar.desktop_click(point.x(),point.y(),'right');self.bar.desktop_click(point.x(),point.y(),'right_up');menu.assert_called_once()

    def test_holding_task_freezes_provider_snapshot_and_animation(self):
        hit=next(h for h in self.bar.hit_regions if h[0]=='task')
        self.bar.task_tween.setStartValue(0.);self.bar.task_tween.setEndValue(1.);self.bar.task_tween.start();self.bar.task_tween.setCurrentTime(100)
        self.bar.begin_press(hit);value=self.bar.task_blend
        self.assertEqual(self.bar.task_tween.state(),QAbstractAnimation.State.Paused)
        self.provider.get.reset_mock()
        with patch('codex_taskbar.app.windows.placement',return_value=None):self.bar.tick()
        self.provider.get.assert_not_called();self.assertEqual(self.bar.task_blend,value)
        self.assertTrue(self.bar.press_inside);self.bar.release_press();self.assertFalse(self.bar.press_inside)
        self.assertEqual(self.bar.task_tween.state(),QAbstractAnimation.State.Running)

    def test_hover_open_never_activates_but_explicit_open_accepts_keyboard(self):
        panel=Mock();panel.mode='usage';panel.reveal_target=1.;panel.winId.return_value=1
        with patch('codex_taskbar.app.TaskPopup',return_value=panel),patch('codex_taskbar.app.windows.popup_glass'):
            self.bar.toggle_popup('usage',activate=False);panel.activateWindow.assert_not_called();panel.setFocus.assert_not_called()
            self.bar.popup=None;self.bar.toggle_popup('usage');panel.activateWindow.assert_called_once();panel.setFocus.assert_called_once()
        self.bar.popup=None

    def test_empty_cycle_does_not_fabricate_a_period(self):
        panel=app.TaskPopup(self.bar);self.bar.popup=panel;panel.refresh({})
        with patch.object(panel,'usage_header',wraps=panel.usage_header) as header:
            panel.grab();self.assertEqual(header.call_args.args[1:],('—',None))

    def test_finder_wheel_does_not_change_filter_or_units_and_cancels_pending_click(self):
        from codex_taskbar.task_finder import TaskFinder
        self.data['catalog']=[dict(self.data['tasks'][0],id=str(i),project=str(i%2)) for i in range(30)]
        finder=TaskFinder(self.bar);self.bar.task_finder=finder;finder.grab()
        project=finder.projects.currentData();unit=finder.units.currentText()
        with patch('codex_taskbar.app.write_settings') as save:
            self.wheel(finder.projects);self.wheel(finder.units)
            self.assertEqual(finder.projects.currentData(),project);self.assertEqual(finder.units.currentText(),unit);save.assert_not_called()
        finder.pressed_id='1';self.wheel(finder.view.viewport());self.assertIsNone(finder.pressed_id)
        finder.pressed_id='1';self.mouse(finder.view.viewport(),QEvent.Type.MouseButtonRelease,QPoint(-5,-5));self.assertIsNone(finder.pressed_id)

    def test_reduced_motion_snaps_controls_and_stops_panel_loops(self):
        with patch('codex_taskbar.settings_ui.startup.enabled',return_value=False):self.bar.settings_dialog=app.SettingsDialog(self.bar)
        toggle=self.bar.settings_dialog.checks['show_week'];toggle.motion.snap(0);toggle.motion.retarget(1)
        panel=self.panel('running');panel.reveal_to(1);panel.fade.advance(.025);self.assertLess(panel.reveal,1)
        with patch('codex_taskbar.app.windows.animations_enabled',return_value=False):self.bar.sync_motion()
        self.assertEqual(panel.reveal,1);self.assertFalse(panel.fade.timer.isActive());self.assertEqual(toggle.progress,1);self.assertFalse(toggle.motion.timer.isActive())
        panel.sync_animation();self.assertFalse(panel.animation.isActive());self.assertFalse(self.bar.animation.isActive())

    def test_spring_reversal_preserves_velocity_and_settles_without_a_loop(self):
        spring=Spring();spring.retarget(1);spring.advance(.035)
        before=(spring.value,spring.velocity);spring.retarget(0)
        self.assertEqual((spring.value,spring.velocity),before)
        spring.advance(.001);self.assertLess(abs(spring.value-before[0]),.03)
        finished=Mock();spring.finished.connect(finished)
        for _ in range(120):
            if not spring.timer.isActive():break
            spring.advance(1/60)
        self.assertEqual(spring.value,0);self.assertFalse(spring.timer.isActive());finished.assert_called_once()
        values=[];value=velocity=0.
        for _ in range(120):
            value,velocity=critical_step(value,velocity,1,1/60);values.append(value)
        self.assertEqual(values,sorted(values));self.assertTrue(all(0<=x<=1 for x in values))

    def test_metric_feedback_has_optical_padding_and_distinct_complete_targets(self):
        for rotated in (False,True):
            self.bar.settings['rotate_quotas']=rotated
            for language in app.LANGUAGES:
                self.bar.settings['language']=language
                for kind,_,_ in self.bar.quota_choices():
                    self.bar.quota_kind=kind
                    with patch('codex_taskbar.app.icon',wraps=app.icon) as icons:self.bar.grab()
                    metrics=[c for c in icons.call_args_list if c.args[1] in ('quota','session','spent','clock')]
                    for call in metrics:
                        name,x=call.args[1:3];mode={'quota':'usage','session':'session','spent':'daily','clock':'resets'}[name]
                        box=self.bar.feedback_regions[mode];target=next(r for m,r,t in self.bar.hit_regions if m==mode)
                        self.assertGreaterEqual(x-6.2-box.left(),4.5)
                        self.assertGreaterEqual(self.bar.height()/2-6.2-box.top(),4.5)
                        self.assertTrue(target.contains(box));self.assertGreaterEqual(box.left(),5)
                    for i,(_,rect,_) in enumerate(self.bar.hit_regions):
                        for _,other,_ in self.bar.hit_regions[i+1:]:self.assertFalse(rect.intersects(other))

    def test_count_selection_uses_its_own_pill_and_does_not_shift_content(self):
        self.bar.grab();before=[(m,app.QRectF(r)) for m,r,t in self.bar.hit_regions]
        panel=self.panel('running');panel.reveal_target=1.
        with patch('codex_taskbar.app.activity_count',wraps=app.activity_count) as counts:self.bar.grab()
        self.assertEqual([(m,r) for m,r,t in self.bar.hit_regions],before)
        self.assertNotIn('running',self.bar.feedback_regions)
        self.assertEqual(counts.call_args_list[0].kwargs['emphasis'],1)
        hit=next(h for h in self.bar.hit_regions if h[0]=='running');self.bar.begin_press(hit)
        with patch('codex_taskbar.app.activity_count',wraps=app.activity_count) as counts:self.bar.grab()
        self.assertEqual(counts.call_args_list[0].kwargs['emphasis'],2)
        self.bar.track_pointer(app.QPointF(-1,-1));self.assertFalse(self.bar.press_inside)
