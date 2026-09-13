import copy
from datetime import datetime
import unittest
from unittest.mock import patch,Mock

from codex_taskbar import app
from tests import test_interactions as fixtures


class QuotaPresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.application=app.QApplication.instance() or app.QApplication([])
    def setUp(self):fixtures.InteractionTests.setUp(self)
    def tearDown(self):fixtures.InteractionTests.tearDown(self)

    def rendered_labels(self,panel):
        with patch('codex_taskbar.app.text',wraps=app.text) as draw:panel.grab()
        return [call.args[3] for call in draw.call_args_list]

    def test_open_session_expires_to_unknown_with_or_without_read_failure(self):
        for error in (None,'read failed'):
            self.data['quota_error']=error
            panel=app.SessionPopup(self.bar);panel.refresh(self.data)
            try:
                self.assertIn('60% remaining',self.rendered_labels(panel))
                self.data['quota'][1]['resets_at']=datetime.now().timestamp()-1
                before=copy.deepcopy(self.data)
                panel.refresh(self.data)
                labels=self.rendered_labels(panel)
                self.assertNotIn('60% remaining',labels);self.assertIn('—',labels)
                self.assertEqual(self.data,before)
                metrics=dict((kind,value) for kind,value,fraction in self.bar.quota_choices())
                self.assertEqual(metrics['session'],'5h left —')
            finally:
                panel.close();panel.deleteLater()
                self.data['quota'][1]['resets_at']=datetime.now().timestamp()+3600

    def test_expired_week_keeps_historical_bounds_but_no_current_reset(self):
        reset=datetime.now().timestamp()-1
        self.data.update(quota=[dict(self.data['quota'][0],resets_at=reset)],quota_error='failed')
        chart=app.TaskPopup(self.bar);resets=app.ResetPopup(self.bar)
        try:
            chart.refresh(self.data);resets.refresh(self.data)
            self.assertTrue(chart.window_known);self.assertEqual(chart.end.timestamp(),reset)
            self.assertIn('Account quota · Week left — · Cached',chart.toolTip())
            self.assertNotIn('Account quota · Week left — · Cached',self.rendered_labels(chart))
            labels=self.rendered_labels(resets)
            self.assertNotIn(datetime.fromtimestamp(reset).strftime('%m.%d %H:%M'),labels)
            self.assertIn('—',labels)
        finally:
            chart.close();chart.deleteLater();resets.close();resets.deleteLater()

    def test_cache_marker_and_quota_tooltip_only_follow_quota_read_errors(self):
        stamp=datetime.now().astimezone().replace(hour=9,minute=12).isoformat()
        self.data.update(quota_updated_at=stamp,error='catalog failed',daily_observed_at=stamp)
        self.assertEqual(self.bar.cached_width(),0)
        self.data['quota_error']='read failed'
        self.assertGreater(self.bar.cached_width(),0)
        labels=self.rendered_labels(self.bar);self.assertIn('Cached',labels)
        quota=next(rect for mode,rect,target in self.bar.hit_regions if mode=='usage')
        self.bar.track_pointer(quota.center())
        self.assertIn('Account quota',self.bar.toolTip());self.assertIn('09:12',self.bar.toolTip())
        daily=next(rect for mode,rect,target in self.bar.hit_regions if mode=='daily')
        self.bar.track_pointer(daily.center());self.assertIn('Observed since 09:12',self.bar.toolTip())
        self.data.pop('quota_updated_at');self.bar.track_pointer(quota.center())
        self.assertIn('Update time unknown',self.bar.toolTip())

    def test_local_panel_headers_fit_all_languages_and_large_totals(self):
        stamp=datetime.now().astimezone().replace(hour=9,minute=12).isoformat()
        usage_stamp=datetime.now().astimezone().replace(hour=8,minute=34).isoformat()
        self.data.update(quota_updated_at=stamp,usage_at=usage_stamp,daily_observed_at=stamp,quota_error='failed',totals={'total_tokens':987654321123})
        self.bar.setGeometry(20,700,540,30)
        for language in app.LANGUAGES:
            self.bar.settings['language']=language
            for mode in ('usage','daily'):
                panel=app.TaskPopup(self.bar) if mode=='usage' else app.TaskListPopup(self.bar,mode)
                try:
                    panel.refresh(self.data)
                    with patch('codex_taskbar.app.text',wraps=app.text) as draw:panel.grab()
                    calls=draw.call_args_list
                    title=self.bar.label('Today · Tokens' if mode=='daily' else 'Cycle · Tokens')
                    title_call=next(call for call in calls if call.args[3]==title)
                    title_right=title_call.args[1]+app.QFontMetricsF(title_call.args[4]).horizontalAdvance(title)
                    self.assertLess(title_right,min(rect.left() for rect in panel.unit_rects().values())-6)
                    for context in app.quota_context_lines(self.bar,self.data,mode):
                        self.assertNotIn(context,[c.args[3] for c in calls]);self.assertIn(context,panel.toolTip())
                    updated=self.bar.label('Updated {time}',time='08:34')
                    update_call=next(c for c in calls if c.args[3]==updated)
                    self.assertEqual(update_call.args[2],title_call.args[2])
                    self.assertLessEqual(update_call.args[1]+app.QFontMetricsF(update_call.args[4]).horizontalAdvance(updated),min(r.left() for r in panel.unit_rects().values())-6)
                    total_call=next(call for call in calls if call.args[3].startswith('Σ '))
                    date_call=next(call for call in calls if call.args[1]==39 and call.args[2]==total_call.args[2])
                    self.assertLessEqual(date_call.args[1]+app.QFontMetricsF(date_call.args[4]).horizontalAdvance(date_call.args[3])+12,total_call.args[1]+1)
                    if mode=='daily':
                        self.assertIn(self.bar.label('Observed since {time}',time='09:12'),app.quota_context_lines(self.bar,self.data,mode)[1])
                        self.assertGreater(panel.row_positions[0]+8,32+panel.TITLE_HEIGHT)
                finally:panel.close();panel.deleteLater()

    def test_missing_observation_is_not_claimed_as_full_day_and_recovery_is_inferred(self):
        self.assertIn('Observation start unknown',app.quota_context_lines(self.bar,self.data,'daily')[1])
        self.assertEqual(app.usage_update_label(self.bar,{'quota_updated_at':datetime.now().isoformat()}),'Update time unknown')
        panel=app.ResetPopup(self.bar);panel.refresh(self.data)
        try:
            self.assertEqual(panel.history_label({'kind':'official','windows':['10080']}),'Official · 7d')
            self.assertIn('inferred',panel.toolTip())
        finally:panel.close();panel.deleteLater()

    def test_waiting_has_a_visible_name_and_menu_categories_dispatch_existing_panels(self):
        self.data['tasks'].append(dict(self.data['tasks'][0],id='waiting',needs_input=True))
        self.bar.grab();self.bar.refresh_accessibility();self.bar.refresh_status_menu()
        self.assertIn('Needs input 1',self.rendered_labels(self.bar))
        self.assertIn('Needs input 1',self.bar.accessibleName())
        self.assertIn('tray menu',self.bar.accessibleDescription())
        self.assertEqual(self.bar.menu.actions()[1].menu(),self.bar.status_menu)
        with patch.object(self.bar,'toggle_popup') as opened,patch('codex_taskbar.app.QTimer.singleShot',side_effect=lambda delay,callback:callback()):
            for action in self.bar.status_menu.actions():
                action.trigger();self.assertEqual(opened.call_args.args,(action.data(),))
        self.data.update(tasks=[],recent_tasks=[]);self.bar.refresh_status_menu()
        self.assertEqual(len(self.bar.status_menu.actions()),1)
        self.assertFalse(self.bar.status_menu.actions()[0].isEnabled())

    def test_running_list_animation_requires_visible_hover_overflow(self):
        panel=app.TaskListPopup(self.bar,'running');panel.refresh(self.data)
        try:
            with patch.object(panel,'isVisible',return_value=True):
                panel.sync_animation();self.assertFalse(panel.animation.isActive())
                panel.hovered='running';panel.sync_animation();self.assertFalse(panel.animation.isActive())
                self.data['tasks'][0]['title']='Long task title '*60
                panel.refresh(self.data);panel.hovered='running';panel.sync_animation();self.assertTrue(panel.animation.isActive())
                self.bar.motion_enabled=False;panel.sync_animation();self.assertFalse(panel.animation.isActive())
                self.bar.motion_enabled=True;panel.hovered=None;panel.sync_animation();self.assertFalse(panel.animation.isActive())
        finally:panel.close();panel.deleteLater()

    def test_all_metrics_cached_and_all_states_fit_by_measured_content_in_every_language(self):
        self.data['tasks'].append(dict(self.data['tasks'][0],id='waiting',needs_input=True))
        self.data['quota_error']='cached';self.bar.settings.update(placement='floating',rotate_quotas=False)
        screen=Mock();screen.availableGeometry.return_value=app.QRect(0,0,1600,900)
        with patch.object(self.bar,'floating_screen',return_value=screen),patch.object(self.bar,'ensure_visible',return_value=False),patch('codex_taskbar.app.windows.floating_window'),patch('codex_taskbar.app.windows.foreground_fullscreen',return_value=False):
            for language in app.LANGUAGES:
                self.bar.settings['language']=language;self.bar.tick(resize=True);self.bar.grab()
                required=self.bar.content_width(float('inf'))
                self.assertGreater(required,540);self.assertEqual(self.bar.width(),required)
                self.assertTrue(screen.availableGeometry().contains(self.bar.geometry()))
                self.assertFalse(self.bar.settings['rotate_quotas'])
                for mode,rect,target in self.bar.hit_regions:self.assertLessEqual(rect.right(),self.bar.width()-8,(language,mode))
                self.assertIn('waiting',[mode for mode,rect,target in self.bar.hit_regions])

    def test_docked_placement_receives_the_full_width_without_540_cap(self):
        self.data['tasks'].append(dict(self.data['tasks'][0],id='waiting',needs_input=True))
        self.data['quota_error']='cached';self.bar.settings.update(placement='taskbar',rotate_quotas=False)
        with patch('codex_taskbar.app.windows.placement',return_value=None) as place,patch('codex_taskbar.app.windows.foreground_fullscreen',return_value=False):
            self.bar.tick(resize=True)
        self.assertEqual(place.call_args.kwargs['minimum_width'],self.bar.content_width(float('inf')))
        self.assertGreater(place.call_args.kwargs['minimum_width'],540)

    def test_no_room_keeps_tray_category_readable_from_an_unplaced_owner(self):
        self.bar.settings.update(placement='floating',language='es',rotate_quotas=False)
        self.data['tasks']=[dict(self.data['tasks'][0],id=str(i)) for i in range(20)]
        self.bar.position=None;self.bar.move(0,0)
        screen=Mock();screen.availableGeometry.return_value=app.QRect(0,0,450,600)
        with patch.object(self.bar,'floating_screen',return_value=screen),patch('codex_taskbar.app.windows.foreground_fullscreen',return_value=False),patch.object(self.bar,'ensure_visible') as show:
            self.bar.tick(resize=True);self.assertTrue(self.bar.placement_unavailable);show.assert_not_called()
            panel=app.TaskListPopup(self.bar,'running');self.bar.popup=panel;panel.refresh(self.data)
            self.bar.tick()
            self.assertIs(self.bar.popup,panel)
            self.assertTrue(screen.availableGeometry().contains(panel.geometry()))
            self.assertGreater(panel.height(),100)
            self.assertFalse(self.bar.settings['rotate_quotas'])
        with patch('codex_taskbar.app.windows.foreground_fullscreen',return_value=True):self.bar.tick()
        self.assertIsNone(self.bar.popup)
