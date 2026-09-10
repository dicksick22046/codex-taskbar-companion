import unittest
from codex_taskbar.attention_notices import AttentionNotices


def waiting(*ids):return [{'id':i,'running':True,'needs_input':True} for i in ids]


class NoticeRulesTests(unittest.TestCase):
    def test_startup_disabled_and_loading_do_not_send_old_work(self):
        notices=AttentionNotices()
        self.assertEqual(notices.update([],True,0,ready=False),[])
        self.assertEqual(notices.update(waiting('old'),True,1),[])
        self.assertEqual(notices.update(waiting('old'),True,20),[])
        self.assertEqual(notices.update(waiting('old','second'),False,30),[])
        self.assertEqual(notices.update(waiting('old','second'),True,40),[])
    def test_batches_new_tasks_once_and_drops_already_answered(self):
        notices=AttentionNotices();notices.update([],True,0)
        self.assertEqual(notices.update(waiting('a','b'),True,1),[])
        self.assertEqual(notices.update(waiting('a','b','c'),True,1.5),[])
        self.assertEqual(notices.update(waiting('b','c'),True,2),['b','c'])
        self.assertEqual(notices.update(waiting('b','c'),True,20),[])
        notices.update(waiting('c'),True,21);notices.update(waiting('b','c'),True,22)
        self.assertEqual(notices.update(waiting('b','c'),True,23),['b'])
    def test_disabled_or_cancelled_interval_clears_pending_batch(self):
        notices=AttentionNotices();notices.update([],True,0);notices.update(waiting('a'),True,1)
        notices.update(waiting('a'),False,1.5);self.assertEqual(notices.update(waiting('a'),True,2),[])
        notices.update([],True,3);notices.update(waiting('b'),True,4)
        self.assertEqual(notices.update([],True,5),[])
        self.assertEqual(notices.update([{'id':'b','needs_input':True}],True,6),[])
