"""Transient, grouped input notices over already-verified task metadata."""


class AttentionNotices:
    def __init__(self):self.seen=None;self.pending=set();self.since=None
    def update(self,tasks,enabled,now,ready=True):
        if not ready:return []
        current={task['id'] for task in tasks if task.get('running') and task.get('needs_input')}
        new=current-self.seen if self.seen is not None else set();self.seen=current
        if not enabled:self.pending.clear();self.since=None;return []
        self.pending.intersection_update(current)
        if new:
            if not self.pending:self.since=now
            self.pending.update(new)
        if not self.pending:self.since=None;return []
        if now-self.since<1.:return []
        result=sorted(self.pending);self.pending.clear();self.since=None;return result
