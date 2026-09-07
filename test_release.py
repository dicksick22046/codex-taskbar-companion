import json,hashlib,tempfile,io,unittest
from pathlib import Path
from unittest.mock import patch
from preferences import read_settings,write_settings,migrate_legacy,DISPLAY_DEFAULTS
from usage import quota_windows,visible_metrics
from updates import release_candidate,download_installer
class ReleaseTests(unittest.TestCase):
    def test_actual_windows_and_display_switches(self):
        q=quota_windows({'rateLimits':{'primary':{'usedPercent':20,'windowDurationMins':300,'resetsAt':20000},'secondary':{'usedPercent':35,'windowDurationMins':10080,'resetsAt':900000}}})
        data={'quota':q,'daily_quota':'4%'}
        fields=visible_metrics(data,DISPLAY_DEFAULTS)
        self.assertEqual([x[0] for x in fields],['quota','session','spent','clock'])
        self.assertEqual(fields[0][1],'7d 65%');self.assertEqual(fields[1][1],'5h 80%')
        self.assertEqual(visible_metrics(data,dict.fromkeys(DISPLAY_DEFAULTS,False)),[])
        self.assertNotIn('spent',[x[0] for x in visible_metrics({'quota':q[:1]},DISPLAY_DEFAULTS)])
        self.assertNotIn('session',[x[0] for x in visible_metrics({'quota':q[1:]},DISPLAY_DEFAULTS)])
        self.assertTrue(all(x[2] is None for x in visible_metrics({**data,'error':'offline'},DISPLAY_DEFAULTS)))
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
