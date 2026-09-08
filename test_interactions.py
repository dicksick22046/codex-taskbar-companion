from datetime import datetime,timedelta
from unittest.mock import patch,Mock
import unittest

import app
from tasks import panel_rows,category_counts
from test_resets import credit


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
        with patch('app.windows.ClickHook'),patch('app.windows.placement',return_value=None),patch('app.RELEASE_REPOSITORY',''):
            self.bar=app.StatusBar(self.provider)
        self.bar.timer.stop();self.bar.animation.stop();self.bar.update_timer.stop();self.bar.tray.hide()
        self.bar.resize(1200,30);self.bar.data=self.data;self.bar.task=self.data['tasks'][0]
        self.bar.settings=dict(app.DISPLAY_DEFAULTS);self.bar.grab()

    def tearDown(self):self.bar.close();self.bar.deleteLater()

    def test_categories_are_exclusive_and_daily_keeps_all_tasks(self):
        self.assertEqual(category_counts(self.data),dict.fromkeys(['running','unread','failed','stopped','recent'],1))
        self.assertEqual(len(panel_rows(self.data,'daily')),5)
        for category in ['running','unread','failed','stopped','recent']:
            self.assertEqual([t['id'] for t in panel_rows(self.data,category)],[category])

    def test_daily_has_only_tokens_and_category_has_only_current_round_time(self):
        daily=app.TaskListPopup(self.bar,'daily');daily.refresh(self.data)
        self.assertEqual(daily.values['running'],'500')
        self.assertEqual([s for s,y in daily.sections],['Today · Tokens','Running','Unread','Failed','Stopped','Recent'])
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
        with patch.object(self.bar,'isVisible',return_value=True),patch('app.windows.rect',return_value=(0,0,1200,30)), \
             patch('app.windows.user32.GetDpiForWindow',return_value=96),patch.object(self.bar,'open_task') as navigate, \
             patch('app.QTimer.singleShot',side_effect=lambda ms,fn:fn()):
            self.bar.desktop_click(point.x(),point.y())
            self.bar.task={'id':'replacement','project':'Other','title':'Another task'};self.bar.grab()
            self.bar.desktop_click(point.x(),point.y(),'left_up')
            self.assertEqual(navigate.call_args.args[0]['id'],'running')
            navigate.reset_mock()
            point=self.bar.task_area.center();self.bar.desktop_click(point.x(),point.y())
            self.bar.desktop_click(1199,100,'left_up');navigate.assert_not_called()

    def test_popup_regions_dispatch_their_own_mode(self):
        with patch.object(self.bar,'isVisible',return_value=True),patch('app.windows.rect',return_value=(0,0,1200,30)), \
             patch('app.windows.user32.GetDpiForWindow',return_value=96),patch.object(self.bar,'toggle_popup') as toggle, \
             patch('app.QTimer.singleShot',side_effect=lambda ms,fn:fn()):
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
        with patch('app.QMessageBox',AutoDialog),patch('app.windows.user32.ShowWindow'):
            self.bar.confirm_reset()

    def test_cancel_never_queues_a_reset(self):
        self.dialog(False);self.provider.request_reset.assert_not_called()

    def test_explicit_confirmation_queues_only_the_displayed_fake_credit(self):
        self.dialog(True)
        self.provider.request_reset.assert_called_once_with('fixture-account','new')

    def test_busy_reset_does_not_open_another_confirmation(self):
        self.data['reset_busy']=True
        with patch('app.QMessageBox') as dialog:self.bar.confirm_reset();dialog.assert_not_called()
        self.provider.request_reset.assert_not_called()

    def test_reset_panel_has_one_action_without_credit_selector(self):
        panel=app.ResetPopup(self.bar);panel.refresh(self.data)
        self.assertEqual(len(panel.findChildren(app.QPushButton)),1)
        self.assertTrue(panel.button.isEnabled());panel.close();panel.deleteLater()
