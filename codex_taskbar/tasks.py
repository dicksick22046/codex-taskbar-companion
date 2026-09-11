"""Task-list ordering and labels, independent of the window implementation."""
from uuid import UUID
from datetime import datetime
from .usage import human_tokens

CATEGORIES = ('waiting','running', 'unread', 'failed', 'stopped', 'recent')
STATUS_CATEGORIES=CATEGORIES[:-1]
CATEGORY_LABELS = dict(zip(CATEGORIES, ('Needs input','Running', 'Unread', 'Failed', 'Stopped', 'Recent')))


def task_role_label(task):
    return 'Side' if task.get('side_chat') else 'Main' if task.get('task_role')=='main' else None


def task_category(task):
    if task.get('needs_input') and task.get('running'):return 'waiting'
    if task.get('running'):return 'running'
    if task.get('status') in ('failed', 'stopped'):return task['status']
    if task.get('unread'):return 'unread'
    return 'recent'


def panel_rows(data, mode='daily'):
    rows = task_rows(data)
    if mode != 'daily':return [t for t in rows if task_category(t) == mode]
    return sorted(rows, key=lambda t: (CATEGORIES.index(task_category(t)), -(t.get('tokens') or 0)))


def category_counts(data):
    rows = task_rows(data)
    return {kind: sum(task_category(t) == kind for t in rows) for kind in CATEGORIES}


def duration_text(elapsed):
    if elapsed is None:return '—'
    elapsed = max(0, int(elapsed))
    if elapsed < 60:return f'{elapsed}s'
    if elapsed < 3600:return f'{elapsed // 60}m'
    return f'{elapsed // 3600}h {elapsed % 3600 // 60}m'


def task_rows(data):
    tasks = []
    seen = set()
    for key in ("tasks", "recent_tasks"):
        for task in data.get(key, []):
            if task["id"] not in seen:
                tasks.append(task)
                seen.add(task["id"])
    def order(task):
        at=task.get('activity_at') or task.get('started_at')
        return bool(task.get('running')),datetime.fromisoformat(at).timestamp() if at else 0
    tasks.sort(key=order, reverse=True)
    return tasks


def task_metrics(task):
    return duration_text(task.get('daily_seconds')), human_tokens(task.get('tokens'))


def thread_url(thread_id):
    return f"codex://threads/{UUID(thread_id)}"
