"""Automatic status rows with account-scoped, per-execution dismissals."""
import json
from pathlib import Path
from .preferences import write_json
from .tasks import task_rows,task_category

SUMMARY_CATEGORIES=('waiting','running','unread','failed')


def execution_key(task):
    turn=str(task.get('turn_id') or task.get('started_at') or task.get('ended_at') or '')
    requests=task.get('input_ids') if task.get('needs_input') else None
    return json.dumps([turn,sorted(requests)]) if isinstance(requests,list) and requests and all(isinstance(item,str) for item in requests) else turn


class StatusSummaries:
    def __init__(self,path):
        self.path=Path(path);self.account=None;self.account_confirmed=False;self.anonymous={};self.rows={kind:[] for kind in SUMMARY_CATEGORIES};self.preferred={}
        try:raw=json.loads(self.path.read_text(encoding='utf-8'))
        except (OSError,ValueError):raw={}
        self.accounts={}
        if isinstance(raw,dict):
            for account,groups in raw.items():
                if isinstance(account,str) and isinstance(groups,dict):
                    self.accounts[account]={kind:{key:value for key,value in entries.items() if isinstance(key,str) and isinstance(value,str)}
                        for kind,entries in groups.items() if kind in SUMMARY_CATEGORIES and isinstance(entries,dict)}

    @property
    def dismissed(self):
        return self.accounts.setdefault(self.account,{}) if self.account else self.anonymous

    @property
    def active(self):return [kind for kind in SUMMARY_CATEGORIES if self.rows[kind] and kind not in self.dismissed]

    def update(self,data):
        tasks=task_rows(data);by_id={task['id']:task for task in tasks}
        self.rows={kind:[task for task in tasks if task_category(task)==kind] for kind in SUMMARY_CATEGORIES}
        if data.get('loading') or data.get('error'):return
        account=data.get('task_account')
        account=account if isinstance(account,str) and account else None
        self.account_confirmed=account is not None
        if account is None and self.account is not None:return
        if account!=self.account:
            self.account=account;self.anonymous={};self.preferred.clear()
        changed=False
        for kind,closed in list(self.dismissed.items()):
            incoming=[task for task in self.rows[kind] if task['id'] not in closed or execution_key(task)!=closed[task['id']]]
            if incoming:
                del self.dismissed[kind];self.preferred[kind]=incoming[0]['id'];changed=True;continue
            for identifier in list(closed):
                task=by_id.get(identifier)
                if task and task_category(task)!=kind and not (kind=='unread' and task.get('unread') is None):
                    del closed[identifier];changed=True
            if not closed:del self.dismissed[kind];changed=True
        if changed:self.save()

    def dismiss(self,kind):
        if kind not in SUMMARY_CATEGORIES or not self.rows[kind]:return
        self.dismissed[kind]={task['id']:execution_key(task) for task in self.rows[kind]}
        self.preferred.pop(kind,None);self.save()

    def save(self):
        if not self.account or not self.account_confirmed:return
        try:write_json(self.path,self.accounts)
        except OSError as exc:print(f'Status summary dismissal: {exc}')
