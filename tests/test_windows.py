import unittest
import ctypes
from unittest.mock import patch

from codex_taskbar import windows


class TaskbarOrderTests(unittest.TestCase):
    def test_placement_uses_actual_space_and_rejects_an_incomplete_content_width(self):
        def child(parent,after,name,title):return 2 if name=='ReBarWindow32' else 3
        boxes={1:(0,1040,1920,1080),2:(1000,1040,1400,1080),3:(1000,1040,1040,1080)}
        with patch.object(windows.user32,'FindWindowW',return_value=1),patch.object(windows.user32,'GetDpiForWindow',return_value=96), \
             patch.object(windows.user32,'FindWindowExW',side_effect=child),patch.object(windows,'rect',side_effect=boxes.get), \
             patch.object(windows.user32,'GetSystemMetrics',return_value=1080),patch.object(windows.user32,'GetForegroundWindow',return_value=0):
            placed=windows.placement(minimum_width=700)
            self.assertIsNotNone(placed);self.assertEqual(placed[2],984)
            self.assertIsNone(windows.placement(minimum_width=1000))

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
        self.assertEqual(owners[0].args,(10,-8,20));self.assertEqual(tops,[])
        self.assertEqual(moves[0].args,(10,0,0,0,0,0,0x0213))

    def test_rebind_does_not_raise_above_a_menu_already_above_taskbar(self):
        owners,moves,tops=self.follow({20:30},owner=0)
        self.assertEqual(tops,[])
        self.assertEqual(moves[0].args,(10,30,0,0,0,0,0x0213))

    def test_missing_taskbar_or_changing_order_does_not_loop_or_force_topmost(self):
        self.assertEqual(self.follow({},tray=0)[1],[])
        self.assertEqual(self.follow({10:30,30:40,40:30})[1],[])


class OwnedWindowOrderTests(unittest.TestCase):
    def test_z_order_messages_ignore_plain_move_resize_and_unrelated_messages(self):
        position=windows.WindowPos();message=windows.w.MSG();message.message=0x0047;message.lParam=ctypes.addressof(position)
        self.assertTrue(windows.z_order_changed(message))
        position.flags=0x0004;self.assertFalse(windows.z_order_changed(message))
        position.flags=0;message.message=0x001A;self.assertFalse(windows.z_order_changed(message))
        message.message=0x0047;message.lParam=0;self.assertFalse(windows.z_order_changed(message))

    def test_taskbar_click_requires_actual_shell_target(self):
        with patch.object(windows.user32,'FindWindowW',return_value=20),patch.object(windows.user32,'WindowFromPoint',return_value=21),patch.object(windows.user32,'GetAncestor',return_value=20):
            self.assertTrue(windows.taskbar_at_point(100,900))
        with patch.object(windows.user32,'FindWindowW',return_value=20),patch.object(windows.user32,'WindowFromPoint',return_value=10),patch.object(windows.user32,'GetAncestor',return_value=10):
            self.assertFalse(windows.taskbar_at_point(100,900))

    def follow(self,order,owner=20,topmost=True,keep=True):
        with patch.object(windows.user32,'GetWindowLongPtrW',side_effect=lambda h,index:owner if index==-8 else 8 if topmost else 0), \
             patch.object(windows.user32,'SetWindowLongPtrW') as set_owner, \
             patch.object(windows.user32,'GetWindow',side_effect=lambda h,relation:order.get(h,0)), \
             patch.object(windows.user32,'SetWindowPos') as move:
            windows.follow_owner(10,20,keep)
            return set_owner.call_args_list,move.call_args_list

    def test_already_ordered_group_does_not_keep_raising(self):
        self.assertEqual(self.follow({20:10,10:30,30:0}),( [],[]))

    def test_owner_and_occlusion_are_repaired_without_activation(self):
        owners,moves=self.follow({10:15,15:20,20:30,30:0},owner=0)
        self.assertEqual(owners[0].args,(10,-8,20))
        self.assertEqual(moves[0].args,(10,30,0,0,0,0,0x0213))

    def test_non_topmost_floating_preference_is_retained(self):
        owners,moves=self.follow({20:10,10:0},keep=False)
        self.assertEqual(owners,[]);self.assertEqual(len(moves),1)
        self.assertEqual(moves[0].args[1].value,windows.w.HWND(-2).value)
        self.assertEqual(moves[0].args[-1],0x0213)
