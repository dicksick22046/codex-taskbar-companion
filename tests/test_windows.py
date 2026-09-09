import unittest
from unittest.mock import patch

from codex_taskbar import windows


class TaskbarOrderTests(unittest.TestCase):
    def follow(self,order,owner=20,tray=20):
        with patch.object(windows.user32,'FindWindowW',return_value=tray), \
             patch.object(windows.user32,'GetWindowLongPtrW',return_value=owner), \
             patch.object(windows.user32,'SetWindowLongPtrW') as set_owner, \
             patch.object(windows.user32,'GetWindow',side_effect=lambda h,relation:order.get(h,0)), \
             patch.object(windows.user32,'SetWindowPos') as move,patch.object(windows,'topmost') as top:
            windows.follow_taskbar(10)
            return set_owner.call_args_list,move.call_args_list,top.call_args_list

    def test_repairs_taskbar_occlusion_without_activation_or_owner_reordering(self):
        owners,moves,tops=self.follow({10:15,15:20,20:30,30:0})
        self.assertEqual(owners,[]);self.assertEqual(tops,[])
        self.assertEqual(moves[0].args,(10,30,0,0,0,0,0x0213))

    def test_does_not_raise_when_already_above_taskbar(self):
        self.assertEqual(self.follow({20:10,10:30,30:0})[1],[])

    def test_rebinds_a_recreated_taskbar_once(self):
        owners,moves,tops=self.follow({},owner=99)
        self.assertEqual(owners[0].args,(10,-8,20));self.assertEqual(tops[0].args,(10,))

    def test_missing_taskbar_or_changing_order_does_not_loop_or_force_topmost(self):
        self.assertEqual(self.follow({},tray=0)[1],[])
        self.assertEqual(self.follow({10:30,30:40,40:30})[1],[])
