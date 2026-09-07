"""Incremental lifecycle and token metrics from the locally observed JSONL format."""
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path

FIELDS = ("total_tokens", "input_tokens", "cached_input_tokens", "output_tokens")
LIFECYCLE = {"task_started", "task_complete", "turn_aborted"}


def event_from_line(line):
    try:
        item = json.loads(line)
        if item.get("type") != "event_msg":
            return None
        payload = item.get("payload", {})
        kind = payload.get("type")
        if kind not in LIFECYCLE and kind != "token_count":
            return None
        at = datetime.fromisoformat(item["timestamp"].replace("Z", "+00:00"))
        # Retain no prompt, tool output, reasoning text, or assistant message.
        return {"kind": kind, "at": at, "turn": payload.get("turn_id"),
                "usage": (payload.get("info") or {}).get("total_token_usage")}
    except (ValueError, TypeError, KeyError):
        return None


class UsageCursor:
    def __init__(self, path, today=None, since=None, created_after=None):
        self.path = Path(path)
        self.day = today or datetime.now().astimezone().date()
        self.since = since or datetime.combine(self.day, datetime.min.time()).astimezone()
        self.created_after = created_after
        self.by_day = {}
        self.offset = 0
        self.pending = b""
        self.last = None
        self.daily = {key: 0 for key in FIELDS}
        self.running = False
        self.turn = None
        self.started_at = None
        self.usage_at = None
        self.ended_at = None
        self.completion_kind = None
        self.activity_at = None
        self.run_tokens = None
        self.initialized = False
        self.daily_seconds = 0.
        self.duration_known = False
        self.duration_start = None

    def apply(self, event):
        if event is None:
            return
        kind = event["kind"]
        original = self.created_after is None or event["at"].timestamp() >= self.created_after
        if original:
            self.activity_at = event["at"].isoformat()
        if kind == "task_started":
            if not self.running or self.turn != event["turn"] or self.duration_start is None:
                self.duration_start = event["at"] if original else None
            if original:self.duration_known = True
            self.running = True
            self.turn = event["turn"]
            self.started_at = event["at"].isoformat()
            self.ended_at = None
            self.completion_kind = None
            self.run_tokens = 0
        elif kind in ("task_complete", "turn_aborted"):
            if not self.turn or not event["turn"] or event["turn"] == self.turn:
                if self.running and self.duration_start is not None:
                    self.daily_seconds += self.seconds_today(self.duration_start,event["at"])
                self.duration_start = None
                self.running = False
                self.ended_at = event["at"].isoformat()
                self.completion_kind = kind
        elif kind == "token_count" and isinstance(event["usage"], dict):
            current = event["usage"]
            local_day = event["at"].astimezone().date()
            original = self.created_after is None or event["at"].timestamp() >= self.created_after
            for key in FIELDS:
                value = current.get(key)
                previous = (self.last or {}).get(key)
                if isinstance(value, int):
                    delta = value if previous is None or value < previous else value - previous
                    if original and key == "total_tokens" and self.running and self.run_tokens is not None:
                        self.run_tokens += delta
                    if original and local_day == self.day:
                        self.daily[key] += delta
                    if original and key == "total_tokens" and event["at"] >= self.since:
                        name = local_day.isoformat()
                        self.by_day[name] = self.by_day.get(name, 0) + delta
            self.last = current
            self.usage_at = event["at"].isoformat()

    def seconds_today(self,start,end):
        midnight=datetime.combine(self.day,datetime.min.time()).astimezone()
        return max(0.,(min(end,midnight+timedelta(days=1))-max(start,midnight)).total_seconds())

    def elapsed_today(self,now=None,include_running=True):
        if not self.duration_known:return None
        elapsed=self.daily_seconds
        if include_running and self.running and self.duration_start is not None:
            elapsed+=self.seconds_today(self.duration_start,now or datetime.now().astimezone())
        return int(elapsed)

    def bootstrap(self):
        size = self.path.stat().st_size
        window = min(size, 1024 * 1024)
        events = []
        boundary=min(self.since,datetime.combine(self.day,datetime.min.time()).astimezone())
        with self.path.open("rb") as stream:
            while True:
                start = max(0, size - window)
                stream.seek(start)
                raw = stream.read(size - start)
                parts = raw.split(b"\n")
                complete = parts[:-1]
                if start:
                    complete = complete[1:]  # Initial fragment may start mid-line.
                events = [event for line in complete if (event := event_from_line(line))]
                baseline = any(e["kind"] == "token_count" and e["at"] < boundary for e in events)
                lifecycle = any(e["kind"] in LIFECYCLE and e["at"] < boundary for e in events)
                if not start or (baseline and lifecycle):
                    self.pending = parts[-1]
                    break
                window = min(size, max(window * 2, 1))
        # A tail always contains a token baseline from before today's boundary.
        for event in events:
            self.apply(event)
        self.offset = size
        self.initialized = True

    def update(self):
        today = datetime.now().astimezone().date()
        size = self.path.stat().st_size
        if not self.initialized:
            self.bootstrap()
        elif size < self.offset or today != self.day:
            self.__init__(self.path, today, self.since, self.created_after)
            self.bootstrap()
        elif size > self.offset:
            with self.path.open("rb") as stream:
                stream.seek(self.offset)
                data = self.pending + stream.read()
                self.offset = stream.tell()
            parts = data.split(b"\n")
            self.pending = parts.pop()
            for line in parts:
                self.apply(event_from_line(line))


def quota_windows(data):
    limits = (data.get("rateLimitsByLimitId") or {}).get("codex") or data.get("rateLimits") or {}
    result = []
    for slot in ("primary", "secondary"):
        window = limits.get(slot)
        if not window or window.get("usedPercent") is None:
            continue
        minutes = window.get("windowDurationMins")
        label = "周" if minutes == 10080 else ("5h" if minutes == 300 else "额度")
        reset = window.get("resetsAt")
        result.append({"label": label, "remaining": max(0, min(100, 100 - window["usedPercent"])),
                       "resets_at": reset, "minutes": minutes,
                       "starts_at": reset - minutes * 60 if reset and minutes else None})
    return result


def human_tokens(value):
    if value is None:
        return "—"
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1000:
        return f"{value / 1000:.1f}K"
    return str(value)


def reset_countdown_text(window, now=None):
    if not window or window.get("resets_at") is None:
        return "—"
    current = datetime.now().timestamp() if now is None else now
    minutes = math.ceil(max(0, window["resets_at"]-current)/60)
    days, minutes = divmod(minutes, 1440)
    hours, minutes = divmod(minutes, 60)
    if days:
        return f"{days}d {hours}h" if hours else f"{days}d"
    if hours:
        return f"{hours}h {minutes}m" if minutes else f"{hours}h"
    return f"{minutes}m"


def remaining_time_fraction(window,now=None):
    if not window or window.get('starts_at') is None or window.get('resets_at') is None:
        return None
    duration=window['resets_at']-window['starts_at']
    if duration<=0:return None
    current=datetime.now().timestamp() if now is None else now
    return max(0.,min(1.,(window['resets_at']-current)/duration))


def daily_quota_text(samples, window, now=None):
    """Sum observed intra-cycle deltas; never subtract across a quota reset."""
    now = now or datetime.now().astimezone()
    if not window or not window.get("resets_at"):
        return "—"
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    used = 100 - window["remaining"]
    rows = sorted((s for s in samples if isinstance(s.get("used"), (int, float))
                   and s.get("reset") and s["at"] <= now.timestamp()), key=lambda s:s["at"])
    after = [s for s in rows if midnight <= s["at"] <= now.timestamp()]
    if not after:
        return "—"
    if abs(after[-1]["reset"]-window["resets_at"]) > 2:
        return "—"
    total = 0
    first = last = after[0]
    for sample in after[1:]:
        if abs(sample["reset"]-last["reset"]) > 2:
            total += max(0,last["used"]-first["used"])
            first = sample
        last = sample
    total += max(0,used-first["used"])
    return f"{total:g}%"


def quota_window(data, minutes):
    return next((q for q in data.get('quota', []) if q.get('minutes') == minutes), None)


def chart_window(data):
    return quota_window(data, 10080) or quota_window(data, 300)


def visible_metrics(data, settings):
    """Display actual account windows; never infer them from a plan name."""
    if data.get('quota_error') or data.get('error'):
        current=datetime.now().timestamp()
        valid=[q for q in data.get('quota',[]) if q.get('resets_at') is None or q['resets_at']>current]
        data={**data,'quota':valid}
        if not quota_window(data,10080):data['daily_quota']='—'
    week, session = quota_window(data, 10080), quota_window(data, 300)
    show_week = settings.get('show_week', True)
    show_session = settings.get('show_session', True) and session is not None
    result = []
    both = show_week and week is not None and show_session
    if show_week and (week is not None or not data.get('quota')):
        value = f"{week['remaining']:g}%" if week else '—'
        result.append(('quota', ('7d ' if both else '') + value, week['remaining']/100 if week else None))
    if show_session:
        result.append(('session', f"5h {session['remaining']:g}%", session['remaining']/100))
    if settings.get('show_daily', True) and (week is not None or not data.get('quota')):
        value = data.get('daily_quota', '—')
        result.append(('spent', value, float(value.rstrip('%'))/100 if value != '—' else None))
    if settings.get('show_countdown', True):
        window = week if show_week and week else session if show_session else week or session
        result.append(('clock', reset_countdown_text(window), remaining_time_fraction(window)))
    return result
