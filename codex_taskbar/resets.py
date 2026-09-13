"""Account-scoped reset observations and durable, user-confirmed reset attempts."""
import copy
import json
import math
import time
from pathlib import Path
from uuid import uuid4

from .preferences import write_json
from .usage import quota_windows


def available_credits(credits, now=None):
    now = time.time() if now is None else now
    if not isinstance(credits, dict):return []
    rows = credits.get('credits')
    if not isinstance(rows, list):return []
    valid = [c for c in rows if isinstance(c,dict) and c.get('status')=='available'
             and c.get('id') and c.get('resetType')=='codexRateLimits'
             and isinstance(c.get('grantedAt'),(int,float)) and math.isfinite(c['grantedAt'])
             and (c.get('expiresAt') is None or isinstance(c['expiresAt'], (int, float))
                  and math.isfinite(c['expiresAt']) and c['expiresAt'] > now)]
    return [dict(c) for c in sorted({c['id']:c for c in valid}.values(),
        key=lambda c:(c['expiresAt'] if c.get('expiresAt') is not None else math.inf,c['grantedAt'],c['id']))]


def default_credit(credits, now=None):
    rows=available_credits(credits,now)
    count=credits.get('availableCount') if isinstance(credits,dict) else None
    return rows[0] if isinstance(count,int) and count>0 and len(rows)==count else None


def scheduled_rollover(old,new,at):
    return (old.get('resets_at') is not None and old['resets_at']<=at
            and new.get('starts_at') is not None and new['starts_at']>=old['resets_at']
            and new['resets_at']>old['resets_at'])


def changed_windows(before, after, at=None):
    at=time.time() if at is None else at
    return [key for key, value in after.items() if key in before and
            (value['remaining'] > before[key]['remaining'] or scheduled_rollover(before[key],value,at))]


class ResetLedger:
    def __init__(self, path):
        self.path = Path(path)
        try:self.accounts = json.loads(self.path.read_text(encoding='utf-8'))
        except (OSError, ValueError):self.accounts = {}
        if not isinstance(self.accounts,dict):self.accounts={}
        for record in self.accounts.values():
            events=[]
            for event in record.get('events',[]):
                if event.get('kind')=='unknown' and event.get('before') and event.get('after'):
                    before,after=event['before'],event['after']
                    windows=changed_windows(before,after,event['at'])
                    if not windows:continue
                    scheduled=all(scheduled_rollover(before[k],after[k],event['at']) for k in windows)
                    event={**event,'windows':windows,'kind':'scheduled' if scheduled else 'official'}
                    if not scheduled:event['classification']='inferred'
                events.append(event)
            record['events']=events
        self.account = None
        self.credits = None
        self.state = 'idle'

    @property
    def record(self):
        if not self.account:return None
        return self.accounts.setdefault(self.account, {'windows': {}, 'events': [], 'pending': None})

    def save(self):write_json(self.path, self.accounts)

    def _observed_events(self, before, after, at):
        groups = {}
        for key in changed_windows(before, after, at):
            old, new = before[key], after[key]
            scheduled = scheduled_rollover(old,new,at)
            groups.setdefault('scheduled' if scheduled else 'official', []).append(key)
        for kind, windows in groups.items():
            self.record['events'].append({'id': str(uuid4()), 'at': at, 'kind': kind, 'windows': windows,
                                         'before':{k:dict(before[k]) for k in windows},
                                         'after':{k:dict(after[k]) for k in windows},
                                         **({'classification':'inferred'} if kind=='official' else {})})

    def observe(self, raw, at=None):
        at = time.time() if at is None else at
        previous_credits=self.credits
        account = raw.get('accountId')
        account = account if isinstance(account, str) and account else None
        if account != self.account:self.state = 'idle'
        self.account = account
        self.credits = raw.get('rateLimitResetCredits')
        if not account:return
        record = self.record
        current = {str(q['minutes']): q for q in quota_windows(raw)}
        if self.state in ('noCredit','nothingToReset','unavailable') and (previous_credits!=self.credits or record['windows']!=current):self.state='idle'
        followup = record.pop('followup', None)
        if followup:
            event = next((e for e in record['events'] if e['id'] == followup['id']), None)
            if event:event.update(windows=changed_windows(followup['before'], current),after=copy.deepcopy(current))
        elif not record.get('pending'):
            self._observed_events(record['windows'], current, at)
        record['windows'] = current
        session = current.get('300')
        if session:
            samples = [s for s in record.get('session_samples', []) if s['reset'] == session['resets_at']
                       and s['at'] >= (session['starts_at'] or 0)]
            samples.append({'at': at, 'reset': session['resets_at'], 'remaining': session['remaining']})
            record['session_samples'] = samples[-720:]
        record['events'] = record['events'][-100:]
        if record.get('pending'):self.state = 'uncertain'
        self.save()

    def begin(self, account, credit_id):
        if account != self.account or not self.record:raise ValueError('Reset account changed')
        pending = self.record.get('pending')
        if pending:
            if pending['credit']['id'] != credit_id:raise ValueError('Another reset is unresolved')
        else:
            credit = default_credit(self.credits)
            if not credit or credit['id'] != credit_id:raise ValueError('Selected reset credit changed or expired')
            pending = {'key': str(uuid4()), 'credit': credit, 'at': time.time(), 'before': self.record['windows']}
            self.record['pending'] = pending
        self.save()  # Persist before sending anything that could consume a credit, including retries.
        self.state = 'pending'
        return {'idempotencyKey': pending['key'], 'creditId': pending['credit']['id']}

    def finish(self, outcome):
        pending = self.record.get('pending') if self.record else None
        if not pending:raise ValueError('No reset attempt to finish')
        if outcome not in ('reset', 'alreadyRedeemed', 'noCredit', 'nothingToReset'):
            self.state = 'uncertain';raise ValueError('Unknown reset outcome')
        previous=copy.deepcopy(self.record)
        if outcome in ('reset', 'alreadyRedeemed'):
            if not any(e['id'] == pending['key'] for e in self.record['events']):
                self.record['events'].append({'id': pending['key'], 'at': time.time(), 'kind': 'manual',
                                             'windows': changed_windows(pending['before'], self.record['windows']),
                                             'before':copy.deepcopy(pending['before'])})
            self.record['followup'] = {'id': pending['key'], 'before': pending['before']}
        else:self._observed_events(pending['before'], self.record['windows'], time.time())
        self.record['pending'] = None
        self.state = outcome
        try:self.save()
        except Exception:
            self.accounts[self.account]=previous
            self.state='uncertain'
            raise

    def failed(self):
        self.state = 'uncertain' if self.record and self.record.get('pending') else 'unavailable'

    def periods(self):
        periods=[];previous=None
        for event in sorted(self.record['events'] if self.record else [],key=lambda e:e['at']):
            before=event.get('before',{})
            window=before.get('10080') or before.get('300') or {}
            start=previous if previous is not None else window.get('starts_at')
            if start is not None and start<event['at']:periods.append((event['id'],start,event['at']))
            previous=event['at']
        return tuple(periods)

    def view(self):
        pending = self.record.get('pending') if self.record else None
        selected = dict(pending['credit']) if pending else default_credit(self.credits)
        return {'reset_account': self.account, 'reset_selected': selected,
                'reset_credits':available_credits(self.credits),
                'reset_available': self.credits.get('availableCount') if isinstance(self.credits, dict) else None,
                'reset_events': [dict(e) for e in sorted(self.record['events'],key=lambda e:e['at'])] if self.record else [],
                'session_history': [dict(s) for s in self.record.get('session_samples', [])] if self.record else [],
                'reset_state': self.state, 'reset_retry': bool(pending)}
