import json,hashlib,tempfile,io,unittest,time
from pathlib import Path
from unittest.mock import patch
from preferences import read_settings,write_settings,migrate_legacy,DISPLAY_DEFAULTS
from usage import quota_windows,visible_metrics
from updates import release_candidate,download_installer
class ReleaseTests(unittest.TestCase):
    def test_actual_windows_and_display_switches(self):
        q=quota_windows({'rateLimits':{'primary':{'usedPercent':20,'windowDurationMins':300,'resetsAt':time.time()+18000},'secondary':{'usedPercent':35,'windowDurationMins':10080,'resetsAt':time.time()+604800}}})
        data={'quota':q,'daily_quota':'4%'}
        fields=visible_metrics(data,DISPLAY_DEFAULTS)
        self.assertEqual([x[0] for x in fields],['quota','session','spent','clock'])
        self.assertEqual(fields[0][1],'7d 65%');self.assertEqual(fields[1][1],'5h 80%')
        self.assertEqual(visible_metrics(data,dict.fromkeys(DISPLAY_DEFAULTS,False)),[])
        self.assertNotIn('spent',[x[0] for x in visible_metrics({'quota':q[:1]},DISPLAY_DEFAULTS)])
        self.assertNotIn('session',[x[0] for x in visible_metrics({'quota':q[1:]},DISPLAY_DEFAULTS)])
        self.assertEqual([(k,v) for k,v,f in visible_metrics({**data,'error':'task lookup failed'},DISPLAY_DEFAULTS)],[(k,v) for k,v,f in fields])
        self.assertEqual([(k,v) for k,v,f in visible_metrics({**data,'quota_error':'offline'},DISPLAY_DEFAULTS)],[(k,v) for k,v,f in fields])
    def test_settings_and_selective_migration(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);old=root/'old';new=root/'new';old.mkdir()
            write_settings(old/'ui_settings.json',{'show_week':False,'chart_unit':'100M'})
            (old/'quota_history.json').write_text('[]');(old/'private.png').write_text('private')
            migrate_legacy(old,new);settings=read_settings(new/'ui_settings.json')
            self.assertFalse(settings['show_week']);self.assertTrue(settings['show_session'])
            self.assertEqual(settings['chart_unit'],'100M');self.assertFalse((new/'private.png').exists())
            settings['show_week']=True;write_settings(new/'ui_settings.json',settings);migrate_legacy(old,new)
            self.assertTrue(read_settings(new/'ui_settings.json')['show_week'])
    def test_update_version_and_asset_origin(self):
        repo='owner/repo';tag='v0.2.0';name='CodexTaskbarCompanion-0.2.0-Setup-x64.exe'
        release={'tag_name':tag,'assets':[{'name':n,'browser_download_url':f'https://github.com/{repo}/releases/download/{tag}/{n}'} for n in [name,name+'.sha256']]}
        self.assertEqual(release_candidate(release,repo)['version'],'0.2.0')
        self.assertIsNone(release_candidate({**release,'prerelease':True},repo))
        self.assertIsNone(release_candidate({**release,'tag_name':'v0.0.9'},repo))
        release['assets'][0]['browser_download_url']='https://example.com/install.exe'
        with self.assertRaises(ValueError):release_candidate(release,repo)
    def test_download_rejects_corruption(self):
        with tempfile.TemporaryDirectory() as d:
            release={'name':'test.exe','checksum_url':'checksum','url':'installer'}
            with patch('updates.open_url',side_effect=[io.BytesIO(b'0'*64),io.BytesIO(b'bad installer')]):
                with self.assertRaises(ValueError):download_installer(release,Path(d))
            self.assertEqual(list(Path(d).iterdir()),[])
            payload=b'verified fixture';checksum=hashlib.sha256(payload).hexdigest().encode()
            with patch('updates.open_url',side_effect=[io.BytesIO(checksum),io.BytesIO(payload)]):
                path=download_installer(release,Path(d));self.assertEqual(path.read_bytes(),payload)

    def test_runtime_location_is_independent_of_packaged_localappdata(self):
        from preferences import runtime_dir
        with patch.dict('os.environ',{'LOCALAPPDATA':'C:/Users/test/AppData/Local'}):first=runtime_dir()
        with patch.dict('os.environ',{'LOCALAPPDATA':'C:/Users/test/AppData/Local/Packages/host/LocalCache/Local'}):second=runtime_dir()
        self.assertEqual(first,second)
        self.assertEqual(first,Path.home()/'.codex-taskbar-companion')

    def test_migration_merges_restart_history_and_keeps_the_day_baseline(self):
        from datetime import datetime,timedelta,timezone
        from preferences import write_json
        from usage import daily_quota_text
        midnight=datetime(2026,9,7,tzinfo=timezone(timedelta(hours=8))).timestamp()
        old_reset=midnight+10.5*3600;new_reset=old_reset+7*86400
        old=[{'at':midnight+24,'used':82,'reset':old_reset},
             {'at':old_reset-30,'used':91,'reset':old_reset},
             {'at':old_reset+30,'used':0,'reset':new_reset},
             {'at':midnight+20*3600,'used':36,'reset':new_reset}]
        recent=[old[-1],{'at':midnight+21*3600,'used':38,'reset':new_reset}]
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);before=root/'packaged';after=root/'normal';stable=root/'stable'
            write_json(before/'quota_history.json',old);write_json(after/'quota_history.json',recent)
            migrate_legacy(before,stable,[after])
            rows=json.loads((stable/'quota_history.json').read_text())
            self.assertEqual(len(rows),5)
            window={'remaining':62,'resets_at':new_reset}
            now=datetime.fromtimestamp(midnight+21*3600,timezone(timedelta(hours=8)))
            self.assertEqual(daily_quota_text(rows,window,now),'47%')
            for _ in range(2):
                migrate_legacy(after,stable,[before])
                rows=json.loads((stable/'quota_history.json').read_text())
                self.assertEqual(daily_quota_text(rows,window,now),'47%')
            with patch.object(Path,'replace',side_effect=PermissionError('locked')):
                with self.assertRaises(PermissionError):write_json(stable/'quota_history.json',[])
            self.assertEqual(json.loads((stable/'quota_history.json').read_text()),rows)

    def test_migration_can_see_another_launch_context_later(self):
        from preferences import write_json
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);host=root/'host';normal=root/'normal';stable=root/'stable'
            first={'at':100,'used':10,'reset':1000};second={'at':200,'used':20,'reset':1000}
            write_json(host/'quota_history.json',[first])
            migrate_legacy(host,stable)
            write_json(normal/'quota_history.json',[second])
            migrate_legacy(normal,stable,[host])
            self.assertEqual(json.loads((stable/'quota_history.json').read_text()),[first,second])
            stamp=(stable/'quota_history.json').stat().st_mtime_ns
            migrate_legacy(normal,stable,[host])
            self.assertEqual((stable/'quota_history.json').stat().st_mtime_ns,stamp)

    def test_quota_failure_keeps_valid_values_but_not_an_expired_window(self):
        import time
        now=time.time()
        data={'quota':[{'minutes':10080,'remaining':65,'starts_at':now-100,'resets_at':now+1000}], 'daily_quota':'12%'}
        normal=visible_metrics(data,DISPLAY_DEFAULTS)
        stale=visible_metrics({**data,'quota_error':'timeout'},DISPLAY_DEFAULTS)
        self.assertEqual([(k,v) for k,v,f in normal],[(k,v) for k,v,f in stale])
        for before,after in zip(normal,stale):self.assertAlmostEqual(before[2],after[2],places=4)
        expired={**data,'quota':[dict(data['quota'][0],resets_at=now-1)],'quota_error':'timeout'}
        self.assertTrue(all(fraction is None for kind,value,fraction in visible_metrics(expired,DISPLAY_DEFAULTS)))
