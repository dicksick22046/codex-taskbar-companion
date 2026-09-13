import json
import unittest
from codex_taskbar.diagnostics import diagnostic_text


class DiagnosticsTests(unittest.TestCase):
    def test_only_allowlisted_support_state_is_exported(self):
        secret='private-value-must-not-be-copied'
        report=diagnostic_text({'placement':'floating','capsule_theme':'dark','pinned_statuses':['running'],'token':secret,'account':secret},
            {'loading':False,'quota':[{'account':secret}],'error':secret,'catalog':[{'title':secret}],'path':secret},
            {'visible':True,'native_visible':False,'exposed':False,'width':180,'height':30,'font':'test-font','startup':True,'path':secret})
        self.assertNotIn(secret,report);data=json.loads(report)
        self.assertTrue(data['data']['data_error']);self.assertTrue(data['data']['quota_available'])
        self.assertEqual(data['window']['width'],180);self.assertEqual(data['presentation']['placement'],'floating')
        self.assertEqual(data['presentation']['pinned_statuses'],['running'])
        self.assertTrue(data['window']['visible']);self.assertFalse(data['window']['native_visible']);self.assertFalse(data['window']['exposed'])
        self.assertNotIn('catalog',report);self.assertNotIn('account',report)
