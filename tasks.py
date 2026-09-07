"""Task-list ordering and labels, independent of the window implementation."""
from uuid import UUID
from usage import human_tokens


def task_rows(data):
    tasks = []
    seen = set()
    for key in ("tasks", "recent_tasks"):
        for task in data.get(key, []):
            if task["id"] not in seen:
                tasks.append(task)
                seen.add(task["id"])
    tasks.sort(key=lambda t: (bool(t.get('running')),t.get("activity_at") or t.get("started_at") or ""), reverse=True)
    return tasks


def task_metrics(task):
    elapsed = task.get('daily_seconds')
    if elapsed is None:
        duration = "—"
    elif elapsed < 60:
        duration = f"{elapsed}s"
    elif elapsed < 3600:
        duration = f"{elapsed // 60}m"
    else:
        duration = f"{elapsed // 3600}h {elapsed % 3600 // 60}m"
    return duration, human_tokens(task.get('tokens'))


def thread_url(thread_id):
    return f"codex://threads/{UUID(thread_id)}"
