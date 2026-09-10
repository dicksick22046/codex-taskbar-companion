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
        with patch('codex_taskbar.app.read_settings',return_value={**app.DISPLAY_DEFAULTS,'chart_unit':'M'}), \
             patch('codex_taskbar.app.windows.ClickHook'),patch('codex_taskbar.app.windows.placement',return_value=None),patch('codex_taskbar.app.RELEASE_REPOSITORY',''),patch('codex_taskbar.app.QSystemTrayIcon'):
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
        cancel_label=self.bar.label('Cancel');confirm_label=self.bar.label('Confirm reset')
        class AutoDialog(app.QMessageBox):
            def show(self):pass
            def exec(self):
                assert self.defaultButton().text()==cancel_label
                frame=self.frameGeometry();allowance=max(2,frame.height()-self.height())
                assert abs(frame.center().y()-self.screen().availableGeometry().center().y())<=allowance
                text=confirm_label if confirm else cancel_label
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

    def hover_point(self,mode):
        rect=next(r for m,r,t in self.bar.hit_regions if m==mode)
        return self.bar.mapToGlobal(rect.center().toPoint())

    def test_hover_debounce_switches_panels_but_never_navigates_tasks(self):
        self.bar.settings['hover_panels']=True
        with patch.object(self.bar,'isVisible',return_value=True),patch.object(self.bar,'toggle_popup') as show,patch.object(self.bar,'open_task') as navigate:
            self.bar.update_hover_popup(self.hover_point('usage'),0)
            self.bar.update_hover_popup(self.hover_point('usage'),.3);show.assert_not_called()
            self.bar.update_hover_popup(self.hover_point('daily'),.31)
            self.bar.update_hover_popup(self.hover_point('daily'),.7);show.assert_called_once_with('daily')
            show.reset_mock()
            self.bar.update_hover_popup(self.hover_point('task'),1)
            self.bar.update_hover_popup(self.hover_point('task'),2)
            show.assert_not_called();navigate.assert_not_called()
            self.bar.settings['hover_panels']=False
            self.bar.update_hover_popup(self.hover_point('usage'),3)
            self.bar.update_hover_popup(self.hover_point('usage'),4);show.assert_not_called()
        self.provider.request_reset.assert_not_called()

    def test_hover_keeps_panel_accessible_across_gap_then_closes_on_leave(self):
        self.bar.move(40,700);self.bar.settings['hover_panels']=True
        panel=app.TaskPopup(self.bar);self.bar.popup=panel;panel.refresh(self.data)
        inside=panel.geometry().center();outside=self.bar.mapToGlobal(app.QPointF(1100,-600).toPoint())
        gap=panel.geometry().bottomLeft()+app.QPointF(20,4).toPoint()
        with patch.object(self.bar,'isVisible',return_value=True),patch.object(panel,'isVisible',return_value=True):
            self.bar.update_hover_popup(inside,0)
            self.bar.update_hover_popup(gap,.1)
            self.bar.update_hover_popup(inside,.3)
            self.assertEqual(panel.reveal_target,1.)
            self.bar.update_hover_popup(outside,1)
            self.bar.update_hover_popup(outside,1.3);self.assertEqual(panel.reveal_target,1.)
            self.bar.update_hover_popup(outside,1.5);self.assertEqual(panel.reveal_target,0.)

    def test_click_close_suppresses_hover_until_pointer_leaves(self):
        self.bar.move(40,700);self.bar.settings['hover_panels']=True
        panel=app.TaskPopup(self.bar);self.bar.popup=panel;panel.refresh(self.data);panel.reveal_to(1.)
        with patch.object(self.bar,'isVisible',return_value=True):
            self.bar.toggle_popup('usage')
            self.bar.update_hover_popup(self.hover_point('usage'),10)
            self.assertEqual(panel.reveal_target,0.)
            self.bar.hide_popup(immediate=True)
            self.bar.leaveEvent(None)
            self.assertIsNone(self.bar.hover_suppressed)
            with patch.object(self.bar,'toggle_popup') as show:
                self.bar.update_hover_popup(self.hover_point('usage'),12);show.assert_not_called()
                self.bar.update_hover_popup(self.hover_point('usage'),12.4);show.assert_called_once_with('usage')

    def test_hover_is_suspended_for_settings_and_reset_confirmation(self):
        self.bar.settings['hover_panels']=True
        with patch.object(self.bar,'isVisible',return_value=True),patch.object(self.bar,'toggle_popup') as show:
            self.bar.confirming_reset=True
            self.bar.update_hover_popup(self.hover_point('resets'),0)
            self.bar.update_hover_popup(self.hover_point('resets'),1);show.assert_not_called()
            self.bar.confirming_reset=False
            self.bar.settings_dialog=Mock();self.bar.settings_dialog.isVisible.return_value=True
            self.bar.update_hover_popup(self.hover_point('usage'),2)
            self.bar.update_hover_popup(self.hover_point('usage'),3);show.assert_not_called()
            self.bar.settings_dialog=None
        self.provider.request_reset.assert_not_called()

    def test_compact_reset_columns_fit_two_quota_windows(self):
        self.data['reset_events']=[{'kind':'scheduled','at':datetime.now().timestamp(),'tokens':2036647183,'windows':['300','10080']}]
        panel=app.ResetPopup(self.bar);panel.refresh(self.data)
        self.assertGreaterEqual(panel.width(),300)
        self.assertEqual(panel.button.geometry().width(),panel.width()-36)
        metrics=app.QFontMetricsF(app.face(8))
        number_left=panel.token_right-metrics.horizontalAdvance(panel.history_usage(self.data['reset_events'][0]))
        date_right=18+metrics.horizontalAdvance(datetime.now().strftime('%m.%d %H:%M'))
        self.assertGreaterEqual(number_left-date_right,12)
        panel.close();panel.deleteLater()

    def test_history_rows_identify_usage_and_units_and_use_blue_categories(self):
        self.data['reset_events']=[{'kind':'scheduled','at':datetime.now().timestamp(),'tokens':2036647183,'windows':['10080']}]
        for language,expected in [('en','Tokens 20.37 ×100M'),('zh-CN','用量 20.37 亿'),('ja','使用量 20.37 億'),('es','Tokens 20.37 ×100M')]:
            self.bar.settings['language']=language
            panel=app.ResetPopup(self.bar);panel.refresh(self.data)
            with patch('codex_taskbar.app.text',wraps=app.text) as draw:panel.grab()
            labels=[call.args[3] for call in draw.call_args_list]
            self.assertEqual(panel.history_usage(self.data['reset_events'][0]),expected)
            self.assertIn(self.bar.label('Tokens'),labels);self.assertIn(self.bar.label('History'),labels)
            self.assertNotIn('History · 100M',labels)
            category=next(call for call in draw.call_args_list if call.args[3]==panel.history_label(self.data['reset_events'][0]))
            self.assertEqual(category.args[5],app.BLUE)
            self.assertEqual(panel.history_usage({'tokens':None}),self.bar.label('Tokens')+' —')
            self.assertGreater(panel.history_divider,panel.token_right)
            panel.close();panel.deleteLater()

    def test_history_uses_100m_for_both_small_and_large_totals(self):
        panel=app.ResetPopup(self.bar)
        self.assertEqual(panel.history_usage({'tokens':521911499}),'Tokens 5.22 ×100M')
        self.assertEqual(panel.history_usage({'tokens':1_000_000_000}),'Tokens 10 ×100M')
        self.assertEqual(panel.history_usage({'tokens':0}),'Tokens 0 ×100M')
        panel.close();panel.deleteLater()

    def test_history_labels_numbers_and_units_have_separate_aligned_columns(self):
        self.data['reset_events']=[{'kind':'scheduled','at':datetime.now().timestamp()+i,'tokens':value,'windows':['10080']}
                                   for i,value in enumerate((2037000000,522000000,None))]
        for language in app.LANGUAGES:
            self.bar.settings['language']=language
            panel=app.ResetPopup(self.bar);panel.refresh(self.data)
            with patch('codex_taskbar.app.text',wraps=app.text) as draw:panel.grab()
            calls=draw.call_args_list
            labels=[c for c in calls if c.args[3]==self.bar.label('Tokens')]
            self.assertEqual(len(labels),3)
            self.assertEqual(len({c.args[1] for c in labels}),1)
            row_y={c.args[2] for c in labels}
            numbers=[c for c in calls if c.args[3] in ('20.37','5.22','—') and c.args[2] in row_y]
            self.assertEqual(len(numbers),3)
            for call in numbers:
                self.assertAlmostEqual(call.args[1]+app.QFontMetricsF(call.args[4]).horizontalAdvance(call.args[3]),panel.number_right)
            units=[c for c in calls if c.args[3] in ('×100M','亿','億')]
            self.assertEqual(len(units),2)
            self.assertEqual({c.args[1] for c in units},{panel.unit_left})
            panel.close();panel.deleteLater()

    def test_history_window_labels_depend_on_event_not_current_account_windows(self):
        panel=app.ResetPopup(self.bar)
        for quotas in ([],self.data['quota'][:1],self.data['quota']):
            panel.refresh({**self.data,'quota':quotas})
            self.assertEqual(panel.history_label({'kind':'official','windows':['10080']}),'Official · 7d')
            self.assertEqual(panel.history_label({'kind':'scheduled','windows':['300','10080']}),'Scheduled · 5h + 7d')
            self.assertEqual(panel.history_label({'kind':'manual','windows':[]}),'Manual')
        panel.close();panel.deleteLater()

    def test_context_menu_belongs_above_strip_and_opens_above_taskbar(self):
        self.assertIs(self.bar.menu.parentWidget(),self.bar)
        self.assertTrue(self.bar.menu.windowFlags() & app.Qt.WindowType.WindowStaysOnTopHint)
        menu_handle=int(self.bar.menu.winId())
        self.assertIs(self.bar.menu.windowHandle().transientParent(),self.bar.windowHandle())
        self.assertTrue(app.windows.user32.GetWindowLongPtrW(menu_handle,-20)&0x8)
        self.bar.move(12,700)
        with patch('codex_taskbar.app.QCursor.pos',return_value=app.QPointF(100,715).toPoint()),patch.object(self.bar.menu,'popup') as opened:
            self.bar.open_menu()
        point=opened.call_args.args[0];height=self.bar.menu.sizeHint().height()
        self.assertLessEqual(point.y()+height,self.bar.y()-app.TaskPopup.GAP)
        self.assertLessEqual(point.y()+height,self.bar.screen().availableGeometry().bottom()+1-app.TaskPopup.GAP)

    def test_capsule_background_alpha_does_not_dim_foreground_or_move_controls(self):
        self.bar.settings['rotate_quotas']=True;self.bar.quota_kind='spent'
        baseline=None
        for theme in ('dark','light'):
            foreground=[]
            for transparency in (0,50,100):
                self.bar.settings.update(capsule_theme=theme,capsule_transparency=transparency)
                with patch('codex_taskbar.app.text',wraps=app.text) as draw:pixmap=self.bar.grab()
                positions=[(mode,rect.x(),rect.width()) for mode,rect,target in self.bar.hit_regions]
                if baseline is None:baseline=positions
                self.assertEqual(positions,baseline)
                image=pixmap.toImage();ratio=image.devicePixelRatio()
                pixel=image.pixelColor(round((self.bar.width()-40)*ratio),round(self.bar.height()/2*ratio))
                self.assertLessEqual(abs(pixel.alpha()-round(255*(1-transparency/100))),1)
                if transparency==0:self.assertEqual(pixel.name(),app.CAPSULE_COLORS[theme]['background'])
                colors=[app.QColor(c.args[5]).name() for c in draw.call_args_list if c.args[3]=='12%']
                self.assertEqual(colors,[app.CAPSULE_COLORS[theme]['muted']]);foreground.append(colors)
                self.assertEqual(self.bar.windowOpacity(),1.)
                self.assertEqual(image.pixelColor(0,0).alpha(),0)
            self.assertEqual(foreground[0],foreground[1]);self.assertEqual(foreground[0],foreground[2])
        self.bar.settings.update(dict.fromkeys(app.DISPLAY_DEFAULTS,False));self.bar.grab()
        self.assertEqual(self.bar.grab().toImage().pixelColor(100,15).alpha(),0)

    def test_capsule_controls_preview_drag_and_save_on_release_and_keyboard(self):
        from codex_taskbar.settings_ui import SettingsDialog
        from PySide6.QtTest import QTest
        with patch('codex_taskbar.settings_ui.startup.enabled',return_value=False),patch('codex_taskbar.app.write_settings') as saved:
            dialog=SettingsDialog(self.bar);self.bar.settings_dialog=dialog
            dialog.capsule.setCurrentIndex(dialog.capsule.findData('light'))
            self.assertEqual(self.bar.settings['capsule_theme'],'light');saved.assert_called_once()
            saved.reset_mock();dialog.transparency.setSliderDown(True);dialog.transparency.setValue(37)
            self.assertEqual(self.bar.settings['capsule_transparency'],37);saved.assert_not_called()
            dialog.transparency.setSliderDown(False);saved.assert_called_once()
            saved.reset_mock();QTest.keyClick(dialog.transparency,app.Qt.Key.Key_Right)
            self.assertEqual(self.bar.settings['capsule_transparency'],38);saved.assert_called_once()
            for language in app.LANGUAGES:
                self.bar.set_language(language)
                self.assertEqual(dialog.capsule_label.text(),self.bar.label('Capsule'))
                self.assertEqual(dialog.capsule.currentText(),self.bar.label('Light'))
                self.assertEqual(dialog.transparency_label.text(),self.bar.label('Transparency'))

    def test_language_switch_updates_open_settings_menu_and_panel_without_side_effects(self):
        from codex_taskbar.settings_ui import SettingsDialog
        self.data['tasks'][0].update(project='',side_chat=True,title='原任务标题')
        panel=app.TaskListPopup(self.bar,'daily');self.bar.popup=panel;panel.refresh(self.data)
        with patch('codex_taskbar.settings_ui.startup.enabled',return_value=True),patch('codex_taskbar.app.write_settings') as save:
            dialog=SettingsDialog(self.bar);self.bar.settings_dialog=dialog
            before={key:self.bar.settings.get(key) for key in app.DISPLAY_DEFAULTS}
            rotated=self.bar.rotated_at
            for language,settings,no_project,side,category in [('zh-CN','设置…','无项目','侧聊','进行中'),('en','Settings…','No project','Side','Running'),
                    ('ja','設定…','未所属','サイド','実行中'),('es','Ajustes…','Sin proyecto','Lateral','En curso')]:
                dialog.language.setCurrentIndex(dialog.language.findData(language))
                self.assertEqual(self.bar.settings['language'],language)
                self.assertEqual(self.bar.settings_action.text(),settings)
                self.assertEqual(self.bar.menu.actions()[0].text(),self.bar.label('Find task…'))
                self.assertEqual(panel.sections[0][0],category)
                self.assertEqual(dialog.checks['show_session'].text(),self.bar.label('5-hour quota'))
                self.assertEqual(dialog.language_label.text(),self.bar.label('Language'))
                with patch('codex_taskbar.app.text',wraps=app.text) as draw:
                    self.bar.grab();panel.grab()
                labels=[c.args[3] for c in draw.call_args_list]
                self.assertIn(no_project,labels);self.assertIn(side,labels)
                self.assertIn('原任务标题',labels)
                self.assertEqual(before,{key:self.bar.settings.get(key) for key in app.DISPLAY_DEFAULTS})
                self.assertEqual(self.bar.rotated_at,rotated)
                self.assertEqual(save.call_args.args[1]['language'],language)
            self.provider.request_reset.assert_not_called()
            self.provider.refresh.assert_not_called()

    def test_both_languages_render_all_panels_and_cancel_reset(self):
        now=datetime.now().timestamp()
        self.data['reset_events']=[{'kind':kind,'at':now-i*86400,'tokens':2036647183,'windows':['300','10080']}
                                   for i,kind in enumerate(('scheduled','manual','official'))]
        self.data['reset_credits']=[credit()]
        for language in app.LANGUAGES:
            self.bar.settings['language']=language
            for kind,key in ((app.TaskPopup,'Cycle · Tokens'),(app.SessionPopup,'Reset {time}'),(app.ResetPopup,'History')):
                panel=kind(self.bar);panel.refresh(self.data)
                with patch('codex_taskbar.app.text',wraps=app.text) as draw:panel.grab()
                labels=[c.args[3] for c in draw.call_args_list]
                if kind is app.SessionPopup:
                    reset=datetime.fromtimestamp(self.data['quota'][1]['resets_at']).strftime('%H:%M')
                    self.assertIn(self.bar.label(key,time=reset),labels)
                else:self.assertIn(self.bar.label(key),labels)
                if kind is app.ResetPopup:
                    self.assertEqual(panel.button.text(),self.bar.label('Reset quota'))
                    date_right=18+app.QFontMetricsF(app.face(8)).horizontalAdvance(datetime.now().strftime('%m.%d %H:%M'))
                    self.assertGreaterEqual(panel.token_right-app.QFontMetricsF(app.face(8)).horizontalAdvance(panel.history_usage(self.data['reset_events'][0]))-date_right,12)
                panel.close();panel.deleteLater()
            self.dialog(False)
        self.provider.request_reset.assert_not_called()

    def test_update_messages_follow_language_including_available_version(self):
        from codex_taskbar.settings_ui import SettingsDialog
        with patch('codex_taskbar.settings_ui.startup.enabled',return_value=False):
            dialog=SettingsDialog(self.bar);self.bar.settings_dialog=dialog
            for language in app.LANGUAGES:
                self.bar.settings['language']=language
                for result in ({'release':None},{'unpublished':True},{'error':'fixture'}, {'release':{'version':'9.9.9'}}):
                    with patch.object(self.bar.updater,'changed'),patch('builtins.print'):
                        self.bar.updater.finish(result)
                    dialog.refresh()
                    expected=self.bar.label(self.bar.updater.message,version=(self.bar.updater.release or {}).get('version',''))
                    self.assertEqual(dialog.update_button.text(),expected)
                self.assertIn('9.9.9',dialog.update_button.text())

    def test_all_left_metrics_rotate_in_one_slot_and_task_positions_stay_fixed(self):
        self.bar.settings['rotate_quotas']=True
        with patch.object(self.bar,'isVisible',return_value=True):
            positions=[]
            for at,kind,mode,label in [(0,'quota','usage','Week 70%'),(8,'spent','daily','Today 12%'),(16,'session','session','5h 60%'),(24,'clock','resets','Reset 6d'),(32,'quota','usage','Week 70%')]:
                self.bar.advance_quota(at);self.bar.quota_tween.setCurrentTime(self.bar.quota_tween.duration());self.bar.grab()
                self.assertEqual(self.bar.quota_kind,kind)
                self.assertEqual(self.bar.displayed_metrics()[0][1],label)
                modes=[m for m,r,t in self.bar.hit_regions]
                self.assertEqual([m for m in modes if m in ('usage','daily','session','resets')],[mode])
                positions.append([r.x() for m,r,t in self.bar.hit_regions if m in ('running','task')])
            self.assertTrue(all(p==positions[0] for p in positions))

    def test_rotation_slot_stays_fixed_within_each_countdown_format(self):
        self.bar.settings['rotate_quotas']=True
        for language in app.LANGUAGES:
            self.bar.settings['language']=language
            for times in ((6*86400+23*3600,86400+3600),(23*3600+59*60,3600+60),(3500,60)):
                widths=set();positions=set()
                for seconds in times:
                    self.data['quota'][0]['resets_at']=datetime.now().timestamp()+seconds
                    for kind,value,fraction in self.bar.quota_choices():
                        width=self.bar.metric_text_width(kind,value);widths.add(width)
                        self.assertGreaterEqual(width,app.QFontMetricsF(app.face(8)).horizontalAdvance(value))
                        self.bar.quota_kind=kind;self.bar.grab()
                        positions.add(next(r.x() for m,r,t in self.bar.hit_regions if m=='task'))
                self.assertEqual(len(widths),1);self.assertEqual(len(positions),1)

    def test_current_day_countdown_has_compact_text_gap_and_stationary_ring(self):
        self.bar.settings.update(rotate_quotas=True,language='en')
        self.data['quota'][0]['resets_at']=datetime.now().timestamp()+5*86400+16*3600
        for kind,_,_ in self.bar.quota_choices():
            self.bar.quota_kind=kind
            with patch('codex_taskbar.app.text',wraps=app.text) as draw,patch('codex_taskbar.app.icon',wraps=app.icon) as icons:self.bar.grab()
            metric_icon=next(c for c in icons.call_args_list if c.args[1]==kind)
            self.assertEqual(metric_icon.args[2],app.CONTENT_X)
            if kind=='clock':
                label=next(c for c in draw.call_args_list if c.args[3]=='Reset')
                number=next(c for c in draw.call_args_list if c.args[3]=='5d 16h')
                label_end=label.args[1]+app.QFontMetricsF(label.args[4]).horizontalAdvance('Reset')
                self.assertGreaterEqual(number.args[1]-label_end,3.)
                self.assertLess(number.args[1]-label_end,7.)

    def test_reset_item_uses_same_pause_and_transition_rules(self):
        self.bar.settings['rotate_quotas']=True;self.bar.quota_kind='clock';self.bar.quota_rotated_at=0;self.bar.grab()
        with patch.object(self.bar,'isVisible',return_value=True):
            self.bar.track_pointer(self.bar.hit_regions[0][1].center());self.bar.advance_quota(6)
            self.bar.advance_quota(100);self.assertEqual(self.bar.quota_kind,'clock')
            self.bar.track_pointer(app.QPointF(-1,-1))
            self.bar.popup=app.ResetPopup(self.bar);self.bar.advance_quota(150)
            self.assertEqual(self.bar.quota_kind,'clock')
            self.bar.hide_popup(immediate=True);self.bar.advance_quota(150)
            self.bar.advance_quota(152);self.assertEqual(self.bar.quota_kind,'quota')
            self.bar.quota_tween.setCurrentTime(120);self.bar.grab()
            self.assertEqual(self.bar.hit_regions[0][0],'resets')
            self.bar.settle_quota('resets');self.bar.quota_tween.setCurrentTime(self.bar.quota_tween.duration())
            self.assertEqual(self.bar.quota_kind,'clock')

    def test_quota_hover_and_panel_pause_resume_without_restarting_or_catching_up(self):
        self.bar.settings['rotate_quotas']=True
        with patch.object(self.bar,'isVisible',return_value=True):
            self.bar.advance_quota(0);self.bar.grab()
            self.bar.track_pointer(self.bar.hit_regions[0][1].center());self.bar.advance_quota(6)
            self.bar.advance_quota(100);self.assertEqual(self.bar.quota_kind,'quota')
            self.bar.track_pointer(app.QPointF(-1,-1));self.bar.advance_quota(100)
            self.bar.advance_quota(101);self.assertEqual(self.bar.quota_kind,'quota')
            self.bar.advance_quota(102);self.assertEqual(self.bar.quota_kind,'spent')
            self.bar.popup=app.TaskListPopup(self.bar,'daily');self.bar.advance_quota(108)
            self.bar.advance_quota(200);self.assertEqual(self.bar.quota_kind,'spent')
            self.bar.hide_popup(immediate=True);self.bar.advance_quota(200)
            self.bar.advance_quota(202);self.assertEqual(self.bar.quota_kind,'session')

    def test_rotating_slot_dispatches_visible_panel_and_press_prevents_switch(self):
        self.bar.settings['rotate_quotas']=True
        with patch.object(self.bar,'isVisible',return_value=True),patch('codex_taskbar.app.windows.rect',return_value=(0,0,1200,30)), \
             patch('codex_taskbar.app.windows.user32.GetDpiForWindow',return_value=96),patch.object(self.bar,'toggle_popup') as opened, \
             patch('codex_taskbar.app.QTimer.singleShot',side_effect=lambda ms,fn:fn()):
            for kind,mode in [('quota','usage'),('spent','daily'),('session','session'),('clock','resets')]:
                self.bar.quota_kind=kind;self.bar.quota_rotated_at=0;self.bar.quota_paused_at=None;self.bar.grab()
                point=self.bar.hit_regions[0][1].center()
                self.bar.desktop_click(point.x(),point.y())
                self.bar.advance_quota(7.9);self.bar.advance_quota(20)
                self.assertEqual(self.bar.quota_kind,kind)
                self.bar.desktop_click(point.x(),point.y(),'left_up')
                self.assertEqual(opened.call_args.args[0],mode)

    def test_rotation_handles_missing_window_single_none_and_empty_values(self):
        self.bar.settings['rotate_quotas']=True
        self.data['quota']=self.data['quota'][:1]
        self.assertEqual([k for k,v,f in self.bar.quota_choices()],['quota','spent','clock'])
        with patch.object(self.bar,'isVisible',return_value=True):
            self.bar.settings.update(show_daily=False,show_countdown=False)
            self.bar.advance_quota(0);self.bar.advance_quota(100)
            self.assertEqual(self.bar.quota_kind,'quota')
            self.bar.settings['show_week']=False;self.bar.advance_quota(101)
            self.assertIsNone(self.bar.quota_kind)
            self.bar.settings['show_countdown']=True;self.bar.advance_quota(102)
            self.assertEqual([k for k,v,f in self.bar.displayed_metrics()],['clock'])
            self.bar.settings['show_countdown']=False
            self.assertEqual(self.bar.displayed_metrics(),[])
            self.bar.settings.update(show_week=True,show_daily=True);self.data['quota']=[];self.data['daily_quota']='—'
            self.assertEqual(self.bar.quota_choices(),[('quota','Week —',None),('spent','Today —',None)])
            self.bar.quota_kind='session';self.bar.advance_quota(102)
            self.assertEqual(self.bar.quota_kind,'quota')

    def test_rotation_setting_language_and_task_rotation_remain_independent(self):
        from codex_taskbar.settings_ui import SettingsDialog
        with patch('codex_taskbar.settings_ui.startup.enabled',return_value=False),patch('codex_taskbar.app.write_settings') as save,patch.object(self.bar,'tick'):
            dialog=SettingsDialog(self.bar);self.bar.settings_dialog=dialog
            dialog.rotation.setChecked(True)
            self.assertTrue(save.call_args.args[1]['rotate_quotas'])
            self.bar.quota_kind='spent';self.bar.quota_rotated_at=12
            self.bar.set_language('zh-CN')
            self.assertEqual(dialog.rotation.text(),'轮换左侧指标')
            self.assertEqual(self.bar.displayed_metrics()[0][1],'今日 12%')
            self.assertEqual(self.bar.quota_rotated_at,12)
            self.bar.current_id='a';self.bar.rotated_at=0;self.bar.quota_hover=True
            with patch('codex_taskbar.app.time.monotonic',return_value=8):
                self.assertEqual(self.bar.selected_task([{'id':'a'},{'id':'b'}])['id'],'b')
            dialog.rotation.setChecked(False)
            self.assertFalse(save.call_args.args[1]['rotate_quotas'])
            self.assertEqual([k for k,v,f in self.bar.displayed_metrics()],['quota','session','spent','clock'])

    def test_rotation_pauses_for_settings_menu_and_confirmation(self):
        self.bar.settings['rotate_quotas']=True
        with patch.object(self.bar,'isVisible',return_value=True):
            self.bar.advance_quota(0)
            with patch.object(self.bar.menu,'isVisible',return_value=True):
                self.bar.advance_quota(6);self.bar.advance_quota(50)
            self.bar.advance_quota(50);self.assertEqual(self.bar.quota_kind,'quota')
            self.bar.advance_quota(52);self.assertEqual(self.bar.quota_kind,'spent')
            self.bar.confirming_reset=True;self.bar.advance_quota(53);self.bar.advance_quota(90)
            self.assertEqual(self.bar.quota_kind,'spent')
            self.bar.confirming_reset=False;self.bar.advance_quota(90)
            self.bar.settings_dialog=Mock();self.bar.settings_dialog.isVisible.return_value=True
            self.bar.advance_quota(91);self.bar.advance_quota(200)
            self.assertEqual(self.bar.quota_kind,'spent')
            self.bar.settings_dialog=None;self.bar.advance_quota(200)
            self.bar.advance_quota(206);self.assertEqual(self.bar.quota_kind,'session')

    def test_quota_transition_keeps_old_frame_then_blends_text_and_ring(self):
        self.bar.settings['rotate_quotas']=True
        with patch.object(self.bar,'isVisible',return_value=True),patch('codex_taskbar.app.time.monotonic',return_value=0):
            self.bar.advance_quota(0);self.bar.grab()
            slot=self.bar.hit_regions[0][1].toRect()
            before=self.bar.grab(slot).toImage()
            self.bar.advance_quota(8);self.bar.quota_tween.setCurrentTime(0)
            self.assertEqual(before,self.bar.grab(slot).toImage())
            self.bar.quota_tween.setCurrentTime(230)
            labels=[]
            draw_text=app.text
            def record(p,x,y,value,font,color=app.MUTED):
                if value in ('70%','12%'):labels.append((value,p.opacity(),y))
                return draw_text(p,x,y,value,font,color)
            with patch('codex_taskbar.app.text',side_effect=record),patch('codex_taskbar.app.icon',wraps=app.icon) as icons:self.bar.grab()
            self.assertEqual([row[0] for row in labels],['70%','12%'])
            self.assertAlmostEqual(sum(row[1] for row in labels),1.)
            self.assertTrue(all(0<row[1]<1 for row in labels))
            ring=next(c for c in icons.call_args_list if c.args[1]=='spent')
            self.assertAlmostEqual(ring.kwargs['fraction'],.41)
            self.assertNotIn(ring.args[4].name(),('#45ba91','#a088d1'))
            self.bar.quota_tween.setCurrentTime(460)
            self.assertIsNone(self.bar.quota_previous)
            self.assertEqual(self.bar.quota_kind,'spent')

    def test_metric_labels_are_consistent_in_parallel_and_rotation_modes(self):
        for language,week,today,reset in [('en','Week','Today','Reset'),('zh-CN','本周','今日','重置')]:
            self.bar.settings.update(language=language,rotate_quotas=False)
            parallel={kind:value for kind,value,fraction in self.bar.displayed_metrics()}
            self.assertEqual(parallel['quota'],week+' 70%')
            self.assertEqual(parallel['spent'],today+' 12%')
            self.assertEqual(parallel['session'],'5h 60%')
            self.assertTrue(parallel['clock'].startswith(reset+' '))
            self.bar.settings['rotate_quotas']=True
            for kind in ('quota','spent','session','clock'):
                self.bar.quota_kind=kind
                rotated={key:value for key,value,fraction in self.bar.displayed_metrics()}
                self.assertEqual(rotated[kind],parallel[kind])
                self.assertEqual(len(rotated),1)

    def test_rotating_numbers_share_a_compact_left_aligned_column(self):
        self.bar.settings['rotate_quotas']=True
        for language in app.LANGUAGES:
            self.bar.settings['language']=language
            number_positions=set()
            for kind,value,fraction in self.bar.quota_choices():
                self.bar.quota_kind=kind
                with patch('codex_taskbar.app.text',wraps=app.text) as draw:self.bar.grab()
                label,_,number=value.partition(' ')
                label_draw=next(c for c in draw.call_args_list if c.args[3]==label)
                number_draw=next(c for c in draw.call_args_list if c.args[3]==number)
                metric=self.bar.hit_regions[0][1]
                pill=next(rect for mode,rect,task in self.bar.hit_regions if mode=='running')
                divider_x=metric.right()+2
                number_end=number_draw.args[1]+app.QFontMetricsF(number_draw.args[4]).horizontalAdvance(number)
                self.assertGreaterEqual(divider_x-number_end,7-1e-6)
                self.assertAlmostEqual(pill.left()+2-divider_x,7)
                label_end=label_draw.args[1]+app.QFontMetricsF(label_draw.args[4]).horizontalAdvance(label)
                self.assertGreaterEqual(number_draw.args[1]-label_end,3-1e-6)
                number_positions.add(number_draw.args[1])
                if language=='en' and kind=='spent':self.assertAlmostEqual(number_draw.args[1]-label_end,3)
            self.assertEqual(len(number_positions),1)

    def test_press_during_transition_returns_smoothly_to_visible_item(self):
        self.bar.settings['rotate_quotas']=True
        with patch.object(self.bar,'isVisible',return_value=True),patch('codex_taskbar.app.windows.rect',return_value=(0,0,1200,30)), \
             patch('codex_taskbar.app.windows.user32.GetDpiForWindow',return_value=96),patch.object(self.bar,'toggle_popup') as opened, \
             patch('codex_taskbar.app.QTimer.singleShot',side_effect=lambda ms,fn:fn()):
            self.bar.advance_quota(0);self.bar.advance_quota(8);self.bar.quota_tween.setCurrentTime(160);self.bar.grab()
            progress=self.bar.quota_progress
            self.assertEqual(self.bar.hit_regions[0][0],'usage')
            point=self.bar.hit_regions[0][1].center();self.bar.desktop_click(point.x(),point.y())
            self.assertAlmostEqual(self.bar.quota_progress,progress)
            self.assertEqual(self.bar.quota_target,0.)
            self.bar.quota_tween.setCurrentTime(self.bar.quota_tween.duration())
            self.assertEqual(self.bar.quota_kind,'quota')
            self.bar.desktop_click(point.x(),point.y(),'left_up')
            opened.assert_called_once_with('usage')
