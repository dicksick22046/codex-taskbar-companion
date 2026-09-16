"""Details expand in the existing pinned viewport, without duplicate summaries."""
import unittest
from unittest.mock import patch
from PySide6.QtCore import QPoint,QRect,Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtCore import QEvent
from codex_taskbar import app
from tests import test_interactions as fixtures


class AttachedPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixtures.InteractionTests.setUpClass()
    def setUp(self):
        fixtures.InteractionTests.setUp(self)
        visible=patch.object(self.bar,'isVisible',return_value=True);visible.start();self.addCleanup(visible.stop)
        self.bar.setGeometry(30,700,330,30);self.bar.settings['placement']='floating';self.bar.motion_enabled=False
        self.host=self.bar.task_strip;self.host.refresh(self.data)
    def tearDown(self):fixtures.InteractionTests.tearDown(self)
    def open(self,mode='running'):
        self.bar.toggle_popup(mode,activate=False)
        return self.bar.popup

    def test_detail_is_child_and_replaces_all_pins_without_changing_settings(self):
        self.bar.settings['pinned_statuses']=['running','unread'];self.host.refresh(self.data)
        panel=self.open('unread')
        self.assertIs(panel.parentWidget(),self.host);self.assertFalse(panel.isWindow())
        self.assertEqual(self.host.active,[])
        self.assertTrue(all(row.isHidden() for row in self.host.rows.values()))
        self.assertEqual(self.bar.settings['pinned_statuses'],['running','unread'])
        self.bar.hide_popup()
        self.assertIsNone(self.bar.popup);self.assertIsNone(self.host.detail)
        self.assertEqual(self.host.active,['running','unread']);self.assertEqual(self.host.size_motion.target,61)
        self.assertFalse(self.host.rows['running'].isHidden())

    def test_quota_detail_available_with_tasks_disabled_and_no_native_child_setup(self):
        self.bar.settings['show_tasks']=False
        with patch('codex_taskbar.app.windows.popup_glass') as glass:
            panel=self.open('usage')
        glass.assert_not_called();self.assertIs(self.host.detail,panel)
        self.assertGreater(self.host.height(),100)
        self.bar.hide_popup();self.assertEqual(self.host.size_motion.target,0)

    def test_stable_left_edge_readable_width_and_above_below_attachment(self):
        panel=self.open('usage')
        self.assertEqual(self.host.x(),self.bar.x())
        self.assertGreaterEqual(self.host.width(),self.bar.width())
        self.assertEqual(self.host.geometry().bottom(),self.bar.y())
        self.assertEqual(panel.size(),self.host.detail_box.size())
        self.bar.move(30,5);panel.reposition()
        self.assertEqual(self.host.y(),self.bar.geometry().bottom())
        self.assertEqual(panel.pos(),QPoint(0,0))
        self.bar.move(self.bar.screen().availableGeometry().right()-80,5);panel.reposition()
        self.assertLessEqual(self.host.geometry().right(),self.bar.screen().availableGeometry().right())

    def test_close_targets_summary_height_and_reverse_preserves_live_motion(self):
        self.open('usage');self.bar.motion_enabled=True
        self.bar.hide_popup();self.assertEqual(self.host.size_motion.target,31)
        self.host.size_motion.advance(.025);closing_value=self.host.size_motion.value;closing_velocity=self.host.size_motion.velocity
        self.bar.toggle_popup('usage',activate=False)
        self.assertEqual(self.host.size_motion.value,closing_value);self.assertEqual(self.host.size_motion.velocity,closing_velocity)
        self.assertGreater(self.host.size_motion.target,31)
        self.bar.hide_popup();values=[]
        self.host.size_motion.changed.connect(values.append)
        for _ in range(80):self.host.size_motion.advance(.016)
        self.assertIsNone(self.bar.popup);self.assertEqual(self.host.active,['running'])
        self.assertGreaterEqual(min(values),30.99);self.assertEqual(self.host.size_motion.target,31)

    def test_switch_preserves_height_and_velocity_without_summary_flash(self):
        self.bar.motion_enabled=True;self.open('usage');self.host.size_motion.advance(.025)
        height=self.host.size_motion.value;velocity=self.host.size_motion.velocity
        with patch.object(self.host.rows['running'],'show') as summary:
            panel=self.open('resets')
        summary.assert_not_called();self.assertEqual(self.host.size_motion.value,height);self.assertEqual(self.host.size_motion.velocity,velocity)
        self.assertIs(self.host.detail,panel);self.assertEqual(self.host.active,[])

    def test_global_hit_region_is_only_visible_clipped_child(self):
        panel=self.open('usage');self.host.layout_rows(50)
        self.assertEqual(panel.global_geometry(),self.host.geometry())
        self.assertEqual(panel.y(),0);self.assertEqual(panel.height(),self.host.detail_box.height())
        self.assertFalse(panel.global_geometry().contains(self.host.geometry().topLeft()-QPoint(0,1)))

    def test_static_detail_refresh_does_not_restart_height_motion_or_reposition_recursively(self):
        panel=self.open('usage')
        with patch.object(self.host.size_motion,'retarget') as retarget,patch.object(panel,'reposition',wraps=panel.reposition) as reposition:
            self.host.refresh(self.data)
        retarget.assert_not_called();reposition.assert_not_called()
        event=QKeyEvent(QEvent.Type.KeyPress,Qt.Key.Key_Escape,Qt.KeyboardModifier.NoModifier)
        panel.keyPressEvent(event);self.assertIsNone(self.bar.popup)

    def test_narrow_footer_expands_with_readable_status_detail_and_restores(self):
        self.bar.resize(200,30);self.bar.content_limit=200
        self.data['tasks'][0]['title']='A task title that needs a readable column'
        panel=self.open('running')
        self.assertEqual(self.bar.navigation_width,200);self.assertGreaterEqual(panel.width(),260)
        self.assertEqual(self.bar.width(),panel.width());self.assertEqual(self.host.width(),panel.width())
        self.assertGreater(panel.TITLE_WIDTH,80)
        self.bar.hide_popup(immediate=True);self.assertEqual(self.bar.width(),200)

    def test_usd_values_expand_one_shared_surface_without_width_feedback(self):
        from datetime import datetime
        self.bar.settings['language']='zh-CN';self.bar.chart_unit='USD'
        self.data['quota']=[dict(minutes=10080,remaining=0,
            starts_at=datetime(2026,9,12,16,9).astimezone().timestamp(),resets_at=datetime(2026,9,19,16,9).astimezone().timestamp())]
        self.data['history_usd']={f'2026-09-{i}':value for i,value in zip(range(12,17),[180.45,219.88,515.01,982.5,211.01])}
        self.data['history']={day:100 for day in self.data['history_usd']}
        panel=self.open('usage')
        self.assertGreater(panel.width(),330)
        for _ in range(3):
            panel.refresh(self.data)
            self.assertEqual(self.host.geometry().left(),self.bar.geometry().left())
            self.assertEqual(self.host.geometry().right(),self.bar.geometry().right())
            self.assertEqual(self.bar.navigation_width,330)
        self.open('running')
        self.assertEqual(self.bar.width(),330);self.assertEqual(self.host.width(),330)
        self.bar.hide_popup(immediate=True);self.assertEqual(self.bar.width(),330)

    def test_taskbar_shared_width_stays_inside_reserved_slot(self):
        self.bar.settings['placement']='taskbar';self.bar.content_limit=340
        self.open('usage');self.host.place_detail(600,180)
        self.assertEqual(self.host.width(),340);self.assertEqual(self.bar.width(),340)
        self.assertEqual(self.host.x(),30);self.assertEqual(self.bar.x(),30)
        self.assertEqual(self.host.detail_width_for(600),340)
        self.bar.hide_popup(immediate=True);self.assertEqual(self.bar.width(),330)

    def test_expansion_at_screen_edge_keeps_original_left_anchor(self):
        bounds=self.bar.screen().availableGeometry();left=bounds.right()-349
        self.bar.move(left,700);self.open('usage');self.host.place_detail(600,180)
        self.assertEqual(self.bar.x(),left);self.assertEqual(self.host.x(),left)
        self.assertEqual(self.bar.width(),350);self.assertEqual(self.host.width(),350)
        self.assertEqual(self.host.geometry().right(),bounds.right())

    def test_open_surface_tracks_compact_layout_changes_and_restores_latest_width(self):
        self.open('usage')
        for width in (420,280):
            compact=QRect(30,700,width,30);footer=self.host.footer_geometry(compact)
            self.bar.setGeometry(footer);self.bar.position=footer.getRect();self.bar.popup.refresh(self.data)
            self.assertEqual(self.bar.navigation_width,width)
            self.assertEqual(self.host.geometry().right(),self.bar.geometry().right())
        self.bar.hide_popup(immediate=True)
        self.assertEqual(self.bar.width(),280)
        with patch.object(self.bar,'content_width',return_value=250),patch.object(self.bar,'underMouse',return_value=False):
            self.assertEqual(self.bar.fitted_width(500),250)

    def test_rotation_buttons_stay_at_compact_content_position_when_expanded(self):
        self.bar.settings['rotate_quotas']=True;self.bar.grab()
        before={mode:rect for mode,rect,_ in self.bar.hit_regions}
        self.open('usage');self.bar.grab()
        after={mode:rect for mode,rect,_ in self.bar.hit_regions}
        for mode in ('running','unread','failed','stopped'):self.assertEqual(before[mode],after[mode])

    def test_switch_and_close_animation_frames_keep_common_edges(self):
        self.bar.motion_enabled=True;self.open('usage')
        self.assertEqual(self.host.geometry().right(),self.bar.geometry().right())
        for mode in ('resets','running','usage'):
            self.open(mode)
            self.assertEqual(self.host.geometry().right(),self.bar.geometry().right())
            for _ in range(12):
                self.host.size_motion.advance(.016)
                self.assertEqual(self.host.geometry().left(),self.bar.geometry().left())
                self.assertEqual(self.host.geometry().right(),self.bar.geometry().right())
        self.bar.hide_popup()
        for _ in range(80):
            self.host.size_motion.advance(.016)
            if self.host.isVisible():
                self.assertEqual(self.host.geometry().left(),self.bar.geometry().left())
                self.assertEqual(self.host.geometry().right(),self.bar.geometry().right())
        self.assertIsNone(self.bar.popup);self.assertEqual(self.bar.width(),330)

    def test_immediate_detach_syncs_remaining_host_before_animation_tick(self):
        self.open('usage');self.bar.motion_enabled=True
        self.bar.hide_popup(immediate=True)
        self.assertEqual(self.bar.width(),330)
        self.assertEqual(self.host.width(),330)
        self.assertEqual(self.host.geometry().right(),self.bar.geometry().right())

    def test_status_scroll_keeps_header_fixed_and_noninteractive(self):
        self.data['tasks']=[dict(self.data['tasks'][0],id=str(i),title='Task '+str(i)) for i in range(24)]
        panel=self.open('running');panel.scroll=0
        before=panel.grab().toImage();ratio=before.devicePixelRatio()
        panel.scroll=panel.ROW_HEIGHT
        after=panel.grab().toImage()
        header=QRect(0,0,round(panel.width()*ratio),round(32*ratio))
        self.assertEqual(before.copy(header),after.copy(header))
        self.assertIsNone(panel.task_at(QPoint(60,18)))
        self.assertEqual(panel.task_at(QPoint(60,40))['id'],'1')
        panel.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress,Qt.Key.Key_Home,Qt.KeyboardModifier.NoModifier))
        self.assertEqual(panel.scroll,0);self.assertEqual(panel.keyboard_task,'0')

    def test_hidden_detail_pauses_and_resumes_opening_or_closing_in_place(self):
        self.bar.motion_enabled=True
        for closing in (False,True):
            with self.subTest(closing=closing):
                self.open('usage')
                if closing:
                    self.host.size_motion.snap(self.host.size_motion.target)
                    self.bar.hide_popup()
                self.host.size_motion.advance(.025)
                value=self.host.size_motion.value;target=self.host.size_motion.target
                self.host.refresh(self.data,hidden=True)
                self.assertFalse(self.host.size_motion.timer.isActive())
                self.assertEqual(self.host.size_motion.value,value)
                with patch.object(self.host,'ensure_visible') as visible:
                    self.bar.popup.refresh(self.data)
                    self.host.layout_rows(value)
                visible.assert_not_called()
                self.assertFalse(self.host.size_motion.timer.isActive())
                self.host.refresh(self.data,hidden=False)
                self.assertTrue(self.host.size_motion.timer.isActive())
                self.assertEqual(self.host.size_motion.value,value)
                self.assertEqual(self.host.size_motion.target,target)
                self.bar.hide_popup(immediate=True)

    def test_hosted_details_restore_parent_background_on_content_repaint(self):
        for mode in ('running','usage','resets'):
            panel=self.open(mode)
            self.assertFalse(panel.testAttribute(Qt.WidgetAttribute.WA_NoSystemBackground))
            self.assertFalse(panel.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground))
        standalone=app.TaskPopup(self.bar)
        self.addCleanup(standalone.deleteLater)
        self.assertTrue(standalone.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground))

    def test_width_only_host_change_invalidates_footer_shared_outline(self):
        panel=self.open('usage')
        previous=self.host.geometry()
        self.host.detail_box.setWidth(previous.width()+20)
        with patch.object(self.bar,'update') as footer:
            self.host.layout_rows(self.host.size_motion.value)
        self.assertEqual(self.host.height(),previous.height())
        self.assertNotEqual(self.host.width(),previous.width());footer.assert_called_once()
        with patch.object(self.bar,'update') as unchanged:
            self.host.layout_rows(self.host.size_motion.value)
        unchanged.assert_not_called()

    def test_status_width_tracks_footer_not_task_title_length(self):
        self.bar.resize(340,30);self.bar.content_limit=600
        panel=self.open('running');before=self.host.geometry()
        self.assertEqual(self.host.width(),self.bar.width())
        self.data['tasks'][0]['title']='A much longer task title '*12
        panel.refresh(self.data)
        self.assertEqual(self.host.geometry(),before)
        self.data['tasks'][0]['title']='Short'
        panel.refresh(self.data)
        self.assertEqual(self.host.geometry(),before)

    def test_detail_header_stays_in_view_through_height_transition(self):
        self.open('running');self.bar.motion_enabled=True
        panel=self.open('daily')
        for seconds in (0,.016,.016,.032,.064):
            if seconds:self.host.size_motion.advance(seconds)
            self.assertEqual(panel.y(),0)
            self.assertEqual(panel.mapToGlobal(QPoint(0,0)),self.host.geometry().topLeft())
            self.assertLess(panel.TITLE_HEIGHT,self.host.height())
        self.assertEqual(self.host.size_motion.response,.28)
        self.bar.hide_popup(immediate=True);self.assertEqual(self.host.size_motion.response,.18)

    def test_daily_and_session_fit_measured_header_without_fixed_360_width(self):
        from datetime import datetime
        self.bar.resize(334,30);self.bar.settings['language']='zh-CN';self.bar.content_limit=600
        self.data['usage_at']=self.data['quota_updated_at']=datetime.now().astimezone().isoformat()
        for mode in ('daily','session'):
            panel=self.open(mode)
            width=self.host.width()
            self.assertGreaterEqual(width,334);self.assertLess(width,360)
            self.data['tasks'][0]['title']='Long task title '*40
            panel.refresh(self.data)
            self.assertEqual(self.host.width(),width)

    def test_narrow_weekly_chart_reserves_measured_date_and_amount_slots(self):
        from datetime import datetime
        self.bar.resize(180,30);self.data['usage_at']=datetime.now().astimezone().isoformat()
        self.data['history']={datetime.now().astimezone().date().isoformat():1234567890000}
        panel=self.open('usage');metrics=app.QFontMetricsF(app.face(7))
        values,_=app.chart_values(panel.days,self.data['history'],datetime.now().astimezone().date())
        labels=[f'{day.month}/{day.day}' for day in panel.days]+[app.chart_number(value,self.bar.chart_unit) for value in values]
        self.assertGreaterEqual((panel.width()-36)/len(panel.days),max(metrics.horizontalAdvance(label) for label in labels)+8)

    def test_new_content_fades_without_retaining_previous_child(self):
        old=self.open('running');height=self.host.height();self.bar.motion_enabled=True
        panel=self.open('unread')
        self.assertTrue(old.isHidden());self.assertIs(self.host.detail,panel)
        self.assertEqual(self.host.height(),height)
        self.assertEqual(panel.reveal,0.);self.assertTrue(panel.content_opacity.isEnabled())
        panel.fade.advance(.03)
        self.assertGreater(panel.reveal,0.);self.assertLess(panel.reveal,1.)
        value=panel.reveal;velocity=panel.fade.velocity
        self.bar.hide_popup()
        self.assertEqual(panel.reveal,value);self.assertEqual(panel.fade.velocity,velocity)
        self.bar.toggle_popup('unread',activate=False)
        self.assertEqual(panel.reveal,value);self.assertEqual(panel.fade.velocity,velocity)
        for _ in range(60):panel.fade.advance(.016)
        self.assertEqual(panel.reveal,1.);self.assertFalse(panel.content_opacity.isEnabled())

    def test_reduced_motion_content_is_immediately_opaque_without_effect(self):
        panel=self.open('usage')
        self.assertEqual(panel.reveal,1.)
        self.assertFalse(panel.content_opacity.isEnabled())
        self.assertFalse(panel.fade.timer.isActive())

    def test_close_restores_summary_on_first_final_pixel_frame(self):
        panel=self.open('daily');self.bar.motion_enabled=True
        self.bar.hide_popup();target=round(self.host.size_motion.target)
        reached=False
        for _ in range(120):
            self.host.size_motion.advance(.016)
            if round(self.host.size_motion.value)==target:
                reached=True
                self.assertIsNone(self.bar.popup)
                self.assertEqual(self.host.active,['running'])
                self.assertEqual(self.host.size_motion.value,target)
                self.assertFalse(self.host.size_motion.timer.isActive())
                break
            self.assertIs(self.bar.popup,panel)
        self.assertTrue(reached)

    def test_hover_reentering_different_button_keeps_detail_during_switch_dwell(self):
        self.bar.resize(800,30);self.bar.settings.update(placement='taskbar',hover_panels=True)
        self.bar.grab();panel=self.open('resets');self.bar.motion_enabled=True
        self.bar.hide_popup();self.host.size_motion.advance(.06);panel.fade.advance(.06)
        self.assertEqual(panel.reveal_target,0.)
        point=self.bar.mapToGlobal(next(rect for mode,rect,_ in self.bar.hit_regions if mode=='unread').center().toPoint())
        self.bar.update_hover_popup(point,10.)
        self.assertIs(self.bar.popup,panel);self.assertEqual(panel.reveal_target,1.)
        for tick in range(1,22):
            self.host.size_motion.advance(.016);panel.fade.advance(.016)
            self.bar.update_hover_popup(point,10.+tick*.016)
            app.QApplication.instance().processEvents()
            self.assertIs(self.bar.popup,panel)
            self.assertGreater(self.host.size_motion.target,31)
            self.assertEqual(self.bar.hover_target,'unread')
        self.bar.update_hover_popup(point,10.36)
        self.assertEqual(self.bar.popup.mode,'unread');self.assertIsNot(self.bar.popup,panel)
        self.assertGreater(self.host.size_motion.target,0)


if __name__=='__main__':unittest.main()
