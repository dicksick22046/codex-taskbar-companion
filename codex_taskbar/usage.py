"""Incremental lifecycle and token metrics from the locally observed JSONL format."""
from datetime import datetime, timedelta, timezone
from bisect import bisect_right
import json
import math
from pathlib import Path
from .pricing import usage_cost

FIELDS = ("total_tokens", "input_tokens", "cached_input_tokens", "output_tokens")
LIFECYCLE = {"task_started", "task_complete", "turn_aborted"}


def inconsistent_total(usage):
    if not isinstance(usage,dict):return False
    total,inputs,outputs=(usage.get(key) for key in ('total_tokens','input_tokens','output_tokens'))
    return all(type(value) is int and value>=0 for value in (total,inputs,outputs)) and total!=inputs+outputs


def event_from_line(line):
    try:
        item = json.loads(line)
        if not isinstance(item,dict):return None
        payload=item.get('payload') or {}
        if not isinstance(payload,dict):return None
        if item.get('type') == 'session_meta':
            return {'kind':'session_meta', 'forked':bool(payload.get('forked_from_id'))}
        if item.get('type') == 'token_usage_record':
            return {'kind':'token_usage_record', 'usage':payload.get('thread_token_usage')}
        if item.get('type') == 'turn_context':
            return {'kind':'model_context', 'at':datetime.fromisoformat(item['timestamp'].replace('Z','+00:00')),
                    'turn':payload.get('turn_id'), 'model':payload.get('model')}
        if item.get('type')=='response_item':
            call=payload.get('call_id')
            if not isinstance(call,str) or not call:return None
            kind=payload.get('type')
            name=payload.get('name')
            if kind=='function_call' and isinstance(name,str) and name.rsplit('.',1)[-1]=='request_user_input':
                args=json.loads(payload.get('arguments','{}'));questions=args.get('questions') if isinstance(args,dict) else None
                if not isinstance(questions,list) or not questions or not all(isinstance(q,dict) and isinstance(q.get('id'),str) and isinstance(q.get('question'),str) and q['question'] for q in questions):return None
                return {'kind':'input_requested','at':datetime.fromisoformat(item['timestamp'].replace('Z','+00:00')),'turn':None,'call':call}
            if kind=='function_call_output':return {'kind':'input_resolved','at':datetime.fromisoformat(item['timestamp'].replace('Z','+00:00')),'turn':None,'call':call}
            return None
        if item.get("type") != "event_msg":
            return None
        payload = item.get("payload", {})
        kind = payload.get("type")
        if kind not in LIFECYCLE and kind != "token_count":
            return None
        at = datetime.fromisoformat(item["timestamp"].replace("Z", "+00:00"))
        # Retain no prompt, tool output, reasoning text, or assistant message.
        return {"kind": kind, "at": at, "turn": payload.get("turn_id"),
                "usage": (payload.get("info") or {}).get("total_token_usage"),
                "last_usage": (payload.get("info") or {}).get("last_token_usage")}
    except (ValueError, TypeError, KeyError):
        return None


class UsageCursor:
    def __init__(self, path, today=None, since=None, created_after=None, periods=()):
        self.path = Path(path)
        self.day = today or datetime.now().astimezone().date()
        self.since = since or datetime.combine(self.day, datetime.min.time()).astimezone()
        self.created_after = created_after
        self.periods=tuple(periods)
        self.period_starts=[row[1] for row in self.periods]
        self.period_totals={row[0]:0 for row in self.periods}
        self.period_usd = {}
        self.by_day = {}
        self.by_day_usd = {}
        self.daily_usd = None
        self.daily_cost_seen = False
        self.model = None
        self.model_turn = None
        self.offset = 0
        self.pending = b""
        self.last = None
        self.forked = created_after is not None
        self.fork_thread_usage = None
        self.fork_first_count = True
        self.new_turn_since_count = False
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
        self.pending_input={}

    def apply(self, event):
        if event is None:
            return
        kind = event["kind"]
        if kind == 'session_meta':
            self.forked = self.forked or event['forked']
            return
        if kind == 'token_usage_record':
            if self.fork_first_count and self.valid_usage(event.get('usage')):
                self.fork_thread_usage = event['usage']
            return
        if kind == 'model_context':
            self.model = event.get('model') if isinstance(event.get('model'), str) else None
            self.model_turn = event.get('turn')
            return
        if kind == 'token_count' and inconsistent_total(event.get('usage')):return
        original = self.created_after is None or event["at"].timestamp() >= self.created_after
        if kind in ('input_requested','input_resolved'):
            if original and self.running:
                if kind=='input_requested':self.pending_input[event['call']]=event['at'].isoformat()
                else:self.pending_input.pop(event['call'],None)
            return
        if original:
            self.activity_at = event["at"].isoformat()
        if kind == "task_started":
            if not event['turn'] or event['turn'] != self.model_turn:self.model = None
            if not self.running or self.turn!=event['turn']:
                self.pending_input.clear();self.new_turn_since_count = True
            if not self.running or self.turn != event["turn"] or self.duration_start is None:
                self.duration_start = event["at"] if original else None
                self.started_at = event["at"].isoformat()
            if original:self.duration_known = True
            self.running = True
            self.turn = event["turn"]
            self.ended_at = None
            self.completion_kind = None
            self.run_tokens = 0
        elif kind in ("task_complete", "turn_aborted"):
            if not self.turn or not event["turn"] or event["turn"] == self.turn:
                self.pending_input.clear()
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
            total = current.get('total_tokens')
            fork_baseline = self.inherited_baseline(current) if self.forked and self.fork_first_count else None
            unknown_fork_baseline = self.forked and self.fork_first_count and fork_baseline is None
            previous_usage = (fork_baseline if fork_baseline is not None else
                              None if not unknown_fork_baseline and self.new_turn_since_count and
                              self.one_call_baseline(current,event.get('last_usage')) else self.last)
            previous = (previous_usage or {}).get('total_tokens')
            if original and unknown_fork_baseline and type(total) is int and total>0:
                if local_day == self.day:
                    self.daily_usd = None
                    self.daily_cost_seen = True
                if event['at'] >= self.since:self.by_day_usd[local_day.isoformat()] = None
                if self.periods:
                    at=event['at'].timestamp();index=bisect_right(self.period_starts,at)-1
                    if index>=0 and at<self.periods[index][2]:self.period_usd[self.periods[index][0]] = None
            if original and not unknown_fork_baseline and type(total) is int and total >= 0:
                delta = total if previous is None or total < previous else total-previous
                cost = 0. if delta == 0 else usage_cost(self.model, current, previous_usage, event.get('last_usage'))
                if self.created_after is not None and self.last is None and fork_baseline is None and delta > 0:cost = None
                if local_day == self.day:
                    self.daily_usd = cost if not self.daily_cost_seen else self.add_cost(self.daily_usd, cost)
                    self.daily_cost_seen = True
                if event['at'] >= self.since:
                    name = local_day.isoformat()
                    self.by_day_usd[name] = self.add_cost(self.by_day_usd.get(name, 0.), cost)
                if self.periods:
                    at=event['at'].timestamp();index=bisect_right(self.period_starts,at)-1
                    if index>=0 and at<self.periods[index][2]:
                        key=self.periods[index][0]
                        self.period_usd[key] = self.add_cost(self.period_usd.get(key, 0.), cost)
            for key in FIELDS:
                value = current.get(key)
                previous = (previous_usage or {}).get(key)
                if isinstance(value, int):
                    delta = value if previous is None or value < previous else value - previous
                    if original and not unknown_fork_baseline and key == "total_tokens" and self.running and self.run_tokens is not None:
                        self.run_tokens += delta
                    if original and not unknown_fork_baseline and local_day == self.day:
                        self.daily[key] += delta
                    if original and not unknown_fork_baseline and key == "total_tokens" and event["at"] >= self.since:
                        name = local_day.isoformat()
                        self.by_day[name] = self.by_day.get(name, 0) + delta
                    if original and not unknown_fork_baseline and key=='total_tokens' and self.periods:
                        at=event['at'].timestamp();index=bisect_right(self.period_starts,at)-1
                        if index>=0 and at<self.periods[index][2]:self.period_totals[self.periods[index][0]]+=delta
            self.last = current
            if type(total) is int and total >= 0:
                self.new_turn_since_count = False
                self.fork_first_count = False
            self.usage_at = event["at"].isoformat()

    @staticmethod
    def valid_usage(usage):
        if not isinstance(usage,dict) or any(type(usage.get(key)) is not int or usage[key]<0 for key in FIELDS):return False
        written=usage.get('cache_write_input_tokens',0)
        return (type(written) is int and written>=0 and
                usage['total_tokens']==usage['input_tokens']+usage['output_tokens'] and
                usage['cached_input_tokens']+written<=usage['input_tokens'])

    def inherited_baseline(self,current):
        local=self.fork_thread_usage
        if not self.valid_usage(current) or not self.valid_usage(local):return None
        fields=FIELDS+('cache_write_input_tokens',)
        baseline={key:current.get(key,0)-local.get(key,0) for key in fields}
        return baseline if self.valid_usage(baseline) else None

    @staticmethod
    def one_call_baseline(current,step):
        fields=FIELDS+('cache_write_input_tokens',)
        if not isinstance(step,dict) or any(
            type(current.get(key,0 if key=='cache_write_input_tokens' else None)) is not int or
            current.get(key,0 if key=='cache_write_input_tokens' else None)<0 or
            current.get(key,0 if key=='cache_write_input_tokens' else None)!=step.get(key,0 if key=='cache_write_input_tokens' else None)
            for key in fields):return False
        return (current['total_tokens']==current['input_tokens']+current['output_tokens']
                and current['cached_input_tokens']+current.get('cache_write_input_tokens',0)<=current['input_tokens'])

    @staticmethod
    def add_cost(previous, cost):
        return None if previous is None or cost is None else previous + cost

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
        if self.periods:boundary=min(boundary,datetime.fromtimestamp(self.periods[0][1]).astimezone())
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
            self.__init__(self.path, today, self.since, self.created_after,self.periods)
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


def _daily_quota_samples(samples, window, now):
    if not window or not window.get("resets_at"):
        return []
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    rows = sorted((s for s in samples if isinstance(s.get("used"), (int, float))
                   and s.get("reset") and s["at"] <= now.timestamp()), key=lambda s:s["at"])
    after = [s for s in rows if midnight <= s["at"] <= now.timestamp()]
    if not after or abs(after[-1]["reset"]-window["resets_at"]) > 2:
        return []
    return after


def daily_observed_at(samples, window, now: datetime | None = None):
    """First usable observation today, including samples before a later reset."""
    now = now or datetime.now().astimezone()
    after = _daily_quota_samples(samples, window, now)
    return datetime.fromtimestamp(after[0]["at"], now.tzinfo).isoformat() if after else None


def daily_quota_text(samples, window, now=None):
    """Sum observed intra-cycle deltas; never subtract across a quota reset."""
    now = now or datetime.now().astimezone()
    after = _daily_quota_samples(samples, window, now)
    if not after:
        return "—"
    used = 100 - window["remaining"]
    total = 0
    first = last = after[0]
    for sample in after[1:]:
        if abs(sample["reset"]-last["reset"]) > 2 or sample['used'] < last['used']:
            total += max(0,last["used"]-first["used"])
            first = sample
        last = sample
    total += max(0,used-first["used"])
    return f"{total:g}%"


def quota_window(data, minutes):
    return next((q for q in data.get('quota', []) if q.get('minutes') == minutes), None)


def effective_quota_data(data, now: float | None = None):
    """Project current quota values without changing the snapshot or history."""
    current = datetime.now().timestamp() if now is None else now
    quota = [dict(q) for q in data.get('quota', [])
             if q.get('resets_at') is None or q['resets_at'] > current]
    result = {**data, 'quota': quota}
    if quota_window(result, 10080) is None:
        result.update(daily_quota='—', daily_observed_at=None)
    return result


def quota_is_cached(data):
    """A quota read failed while the snapshot retains a previous quota result."""
    return bool(data.get('quota_error') and data.get('quota'))


def chart_window(data):
    return quota_window(data, 10080) or quota_window(data, 300)


def countdown_window(data, settings):
    week,session=quota_window(data,10080),quota_window(data,300)
    if settings.get('show_week',True) and week:return week
    if settings.get('show_session',True) and session:return session
    return week or session


def visible_metrics(data, settings):
    """Display actual account windows; never infer them from a plan name."""
    has_session = quota_window(data, 300) is not None
    data = effective_quota_data(data)
    week, session = quota_window(data, 10080), quota_window(data, 300)
    show_week = settings.get('show_week', True)
    show_session = settings.get('show_session', True) and has_session
    result = []
    both = show_week and week is not None and show_session
    if show_week and (week is not None or not data.get('quota')):
        value = f"{week['remaining']:g}%" if week else '—'
        result.append(('quota', ('7d ' if both else '') + value, week['remaining']/100 if week else None))
    if show_session:
        value = f"{session['remaining']:g}%" if session else '—'
        result.append(('session', f"5h {value}", session['remaining']/100 if session else None))
    if settings.get('show_daily', True) and (week is not None or not data.get('quota')):
        value = data.get('daily_quota', '—')
        result.append(('spent', value, min(1.,max(0.,float(value.rstrip('%'))/100)) if value != '—' else None))
    if settings.get('show_countdown', True):
        window = countdown_window(data,settings)
        result.append(('clock', reset_countdown_text(window), remaining_time_fraction(window)))
    return result
