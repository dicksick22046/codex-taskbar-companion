from datetime import datetime,timedelta
from unittest.mock import patch,Mock
import unittest

from codex_taskbar import app
from codex_taskbar.tasks import panel_rows,category_counts
from tests.test_resets import credit


class InteractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.application=app.QApplication.instance() or app.QApplication([])

    def setUp(self):
        now=datetime.now().astimezone().timestamp()
        self.data={'tasks':[{'id':'running','project':'Demo','title':'Running task','running':True,'tokens':500,'daily_seconds':7200,'round_seconds':42}],
            'recent_tasks':[{'id':k,'project':'Demo','title':k,'status':k,'unread':k=='unread','tokens':1000,'daily_seconds':3600,'round_seconds':25}
                            for k in ['unread','failed','stopped','recent']],
            'quota':[{'minutes':10080,'remaining':70,'starts_at':now-86400,'resets_at':now+6*86400},
                     {'minutes':300,'remaining':60,'starts_at':now-3600,'resets_at':now+4*3600}],
            'daily_quota':'12%','reset_account':'fixture-account','reset_selected':credit(),'reset_available':3}
        self.provider=Mock();self.provider.get.side_effect=lambda:self.data
        with patch('codex_taskbar.app.windows.ClickHook'),patch('codex_taskbar.app.windows.placement',return_value=None),patch('codex_taskbar.app.RELEASE_REPOSITORY',''):
            self.bar=app.StatusBar(self.provider)
        self.bar.timer.stop();self.bar.animation.stop();self.bar.update_timer.stop();self.bar.tray.hide()
        self.bar.resize(1200,30);self.bar.data=self.data;self.bar.task=self.data['tasks'][0]
        self.bar.settings=dict(app.DISPLAY_DEFAULTS);self.bar.chart_unit='M';self.bar.grab()

    def tearDown(self):self.bar.close();self.bar.deleteLater()

    def test_categories_are_exclusive_and_daily_keeps_all_tasks(self):
        self.assertEqual(category_counts(self.data),dict.fromkeys(['running','unread','failed','stopped','recent'],1))
        self.assertEqual(len(panel_rows(self.data,'daily')),5)
        for category in ['running','unread','failed','stopped','recent']:
            self.assertEqual([t['id'] for t in panel_rows(self.data,category)],[category])

    def test_daily_has_only_tokens_and_category_has_only_current_round_time(self):
        daily=app.TaskListPopup(self.bar,'daily');daily.refresh(self.data)
        self.assertEqual(daily.values['running'],'<0.1')
        self.assertEqual([s for s,y in daily.sections],['Running','Unread','Failed','Stopped','Recent'])
        running=app.TaskListPopup(self.bar,'running');running.refresh(self.data)
        self.assertEqual(running.values,{'running':'42s'})
        self.assertEqual([s for s,y in running.sections],['Running'])
        daily.close();running.close();daily.deleteLater();running.deleteLater()

    def test_metric_and_status_regions_are_distinct(self):
        self.assertEqual([m for m,r,t in self.bar.hit_regions],['usage','session','daily','resets','running','unread','failed','stopped','task'])
        for i,(_,a,_) in enumerate(self.bar.hit_regions):
            for _,b,_ in self.bar.hit_regions[i+1:]:self.assertFalse(a.intersects(b))

    def test_task_target_is_frozen_at_press_and_dragging_out_cancels(self):
        region=next(r for m,r,t in self.bar.hit_regions if m=='task');point=region.center()
        with patch.object(self.bar,'isVisible',return_value=True),patch('codex_taskbar.app.windows.rect',return_value=(0,0,1200,30)), \
             patch('codex_taskbar.app.windows.user32.GetDpiForWindow',return_value=96),patch.object(self.bar,'open_task') as navigate, \
             patch('codex_taskbar.app.QTimer.singleShot',side_effect=lambda ms,fn:fn()):
            self.bar.desktop_click(point.x(),point.y())
            self.bar.task={'id':'replacement','project':'Other','title':'Another task'};self.bar.grab()
            self.bar.desktop_click(point.x(),point.y(),'left_up')
            self.assertEqual(navigate.call_args.args[0]['id'],'running')
            navigate.reset_mock()
            point=self.bar.task_area.center();self.bar.desktop_click(point.x(),point.y())
            self.bar.desktop_click(1199,100,'left_up');navigate.assert_not_called()

    def test_popup_regions_dispatch_their_own_mode(self):
        with patch.object(self.bar,'isVisible',return_value=True),patch('codex_taskbar.app.windows.rect',return_value=(0,0,1200,30)), \
             patch('codex_taskbar.app.windows.user32.GetDpiForWindow',return_value=96),patch.object(self.bar,'toggle_popup') as toggle, \
             patch('codex_taskbar.app.QTimer.singleShot',side_effect=lambda ms,fn:fn()):
            for mode,region,payload in self.bar.hit_regions[:-1]:
                point=region.center();self.bar.desktop_click(point.x(),point.y())
                self.bar.desktop_click(point.x(),point.y(),'left_up')
                self.assertEqual(toggle.call_args.args[0],mode)

    def dialog(self, confirm):
        class AutoDialog(app.QMessageBox):
            def show(self):pass
            def exec(self):
                assert self.defaultButton().text()=='取消'
                frame=self.frameGeometry();allowance=max(2,frame.height()-self.height())
                assert abs(frame.center().y()-self.screen().availableGeometry().center().y())<=allowance
                text='确认重置' if confirm else '取消'
                next(b for b in self.buttons() if b.text()==text).click()
                return 0
        with patch('codex_taskbar.app.QMessageBox',AutoDialog),patch('codex_taskbar.app.windows.user32.ShowWindow'):
            self.bar.confirm_reset()

    def test_cancel_never_queues_a_reset(self):
        self.dialog(False);self.provider.request_reset.assert_not_called()

    def test_explicit_confirmation_queues_only_the_displayed_fake_credit(self):
        self.dialog(True)
        self.provider.request_reset.assert_called_once_with('fixture-account','new')

    def test_busy_reset_does_not_open_another_confirmation(self):
        self.data['reset_busy']=True
        with patch('codex_taskbar.app.QMessageBox') as dialog:self.bar.confirm_reset();dialog.assert_not_called()
        self.provider.request_reset.assert_not_called()

    def test_reset_panel_has_one_action_without_credit_selector(self):
        panel=app.ResetPopup(self.bar);panel.refresh(self.data)
        self.assertEqual(len(panel.findChildren(app.QPushButton)),1)
        self.assertTrue(panel.button.isEnabled());panel.close();panel.deleteLater()

    def test_only_weekly_chart_handles_unit_controls(self):
        event=Mock();event.button.return_value=app.Qt.MouseButton.LeftButton;event.position.return_value=app.QPointF(290,43)
        with patch.object(self.bar,'set_chart_unit') as change:
            for kind in (app.SessionPopup,app.ResetPopup):
                panel=kind(self.bar);panel.refresh(self.data)
                panel.mousePressEvent(event);panel.mouseMoveEvent(event)
                change.assert_not_called()
                self.assertEqual(panel.cursor().shape(),app.Qt.CursorShape.ArrowCursor)
                panel.close();panel.deleteLater()
            panel=app.TaskPopup(self.bar);panel.refresh(self.data);panel.mousePressEvent(event)
            change.assert_called_once_with('M');panel.close();panel.deleteLater()

    def test_daily_units_refresh_rows_and_total_without_navigation(self):
        self.data['tasks'][0]['tokens']=142700000
        self.data['totals']={'total_tokens':142704000}
        panel=app.TaskListPopup(self.bar,'daily');self.bar.popup=panel;panel.refresh(self.data)
        event=Mock();event.button.return_value=app.Qt.MouseButton.LeftButton
        event.position.return_value=panel.unit_rects()['100M'].center()
        with patch('codex_taskbar.app.write_settings'),patch.object(self.bar,'open_task') as navigate:
            panel.mousePressEvent(event);panel.mouseReleaseEvent(event)
            self.assertEqual(panel.values['running'],'1.43')
            with patch.object(panel,'usage_header') as header:panel.grab()
            self.assertEqual(header.call_args.args[2],142704000)
            navigate.assert_not_called()

    def test_unit_hover_and_refresh_keep_cursor_without_changing_selection(self):
        panel=app.TaskListPopup(self.bar,'daily');panel.refresh(self.data)
        point=panel.unit_rects()['100M'].center()
        event=Mock();event.position.return_value=point
        with patch.object(self.bar,'set_chart_unit') as select,patch.object(panel,'mapFromGlobal',return_value=point):
            panel.mouseMoveEvent(event)
            self.assertEqual(panel.cursor().shape(),app.Qt.CursorShape.PointingHandCursor)
            panel.refresh(self.data)
            self.assertEqual(panel.cursor().shape(),app.Qt.CursorShape.PointingHandCursor)
            self.assertEqual(self.bar.chart_unit,'M');select.assert_not_called()
        panel.close();panel.deleteLater()

    def test_all_credit_expiries_are_visible_but_only_one_reset_action(self):
        now=datetime.now().timestamp()
        self.data['reset_events']=[{'kind':'unknown','at':now-100,'windows':['10080']},
                                   {'kind':'scheduled','at':now-86400,'windows':['10080']}]
        self.data['reset_credits']=[credit(str(i),now-i*100,now+(i+1)*86400) for i in range(3)]
        self.data['reset_selected']=self.data['reset_credits'][0]
        panel=app.ResetPopup(self.bar);panel.refresh(self.data)
        with patch('codex_taskbar.app.text',wraps=app.text) as draw:panel.grab()
        labels=[c.args[3] for c in draw.call_args_list]
        for item in self.data['reset_credits']:
            self.assertIn(datetime.fromtimestamp(item['expiresAt']).strftime('%m.%d %H:%M'),labels)
        self.assertEqual(labels.count('Default'),1)
        self.assertIn('3 available',labels)
        self.assertNotIn('Unknown',labels)
        self.assertNotIn('来源未确认',labels)
        self.assertIn(datetime.fromtimestamp(now-100).strftime('%m.%d %H:%M'),labels)
        self.assertTrue(any(label.startswith('Scheduled') for label in labels))
        self.assertGreater(panel.button.y(),panel.credits_top+26+2*26+8)
        self.assertEqual(len(panel.findChildren(app.QPushButton)),1)
        self.provider.request_reset.assert_not_called()
        panel.close();panel.deleteLater()

    def test_popups_do_not_freeze_rotation_and_hover_still_pauses(self):
        tasks=[{'id':'a'},{'id':'b'},{'id':'c'}]
        self.bar.current_id='a';self.bar.rotated_at=0
        panel=app.ResetPopup(self.bar);self.bar.popup=panel
        with patch('codex_taskbar.app.time.monotonic',return_value=10):
            self.assertEqual(self.bar.selected_task(tasks)['id'],'b')
        self.bar.task_hover=True
        with patch('codex_taskbar.app.time.monotonic',return_value=20):
            self.assertEqual(self.bar.selected_task(tasks)['id'],'b')
        self.bar.task_hover=False
        with patch('codex_taskbar.app.time.monotonic',return_value=21):
            self.assertEqual(self.bar.selected_task(tasks)['id'],'c')

    def test_hover_and_popup_close_preserve_rotation_progress(self):
        self.bar.current_id='running';self.bar.rotated_at=0
        point=self.bar.task_area.center()
        with patch('codex_taskbar.app.time.monotonic',return_value=6):self.bar.track_pointer(point)
        with patch('codex_taskbar.app.time.monotonic',return_value=16):self.bar.track_pointer(app.QPointF(-1,-1))
        self.assertEqual(self.bar.rotated_at,10)
        self.bar.popup=app.TaskPopup(self.bar)
        with patch('codex_taskbar.app.time.monotonic',return_value=17):self.bar.hide_popup(immediate=True)
        self.assertEqual(self.bar.rotated_at,10)
        tasks=[self.bar.task,{'id':'next'}]
        with patch('codex_taskbar.app.time.monotonic',return_value=18):
            self.assertEqual(self.bar.selected_task(tasks)['id'],'next')

    def test_replacement_task_does_not_inherit_previous_hover_wait(self):
        self.bar.current_id='finished';self.bar.task_hover=True;self.bar.title_hover_started=0
        with patch('codex_taskbar.app.time.monotonic',return_value=10):self.bar.selected_task([{'id':'next'}])
        with patch('codex_taskbar.app.time.monotonic',return_value=16):self.bar.track_pointer(app.QPointF(-1,-1))
        self.assertEqual(self.bar.rotated_at,16)

    def test_entire_interactive_regions_have_native_hit_pixels(self):
        self.bar.resize(1500,30)
        img=self.bar.grab().toImage();ratio=img.devicePixelRatio()
        for mode,rect,target in self.bar.hit_regions:
            for dx in (3,rect.width()/2,rect.width()-3):
                for dy in (3,rect.height()-3):
                    self.assertGreater(img.pixelColor(round((rect.left()+dx)*ratio),round(dy*ratio)).alpha(),0,mode)
        self.assertEqual(img.pixelColor(img.width()-3,3).alpha(),0)
