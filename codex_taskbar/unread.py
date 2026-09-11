"""Read only Codex's local unread IDs; never infer read state from timestamps."""
import json
import base64
import hashlib
import os
from pathlib import Path


def identity_key(auth):
    """Match the desktop's read-state identity; retain no authentication token."""
    method=auth.get('authMethod')
    if method in ('chatgpt','chatgptAuthTokens'):
        try:
            part=auth['authToken'].split('.')[1]
            claims=json.loads(base64.urlsafe_b64decode(part+'='*(-len(part)%4)))['https://api.openai.com/auth']
            account=claims.get('chatgpt_account_id') or claims.get('account_id')
            user=claims.get('user_id') or claims.get('chatgpt_user_id')
            if not all(isinstance(v,str) and v for v in (account,user)):return None
            parts=['chatgpt',account,user]
        except (KeyError,IndexError,ValueError,TypeError,AttributeError):return None
    elif method is None and auth.get('requiresOpenaiAuth') is not False:return None
    elif method is not None and not isinstance(method,str):return None
    else:parts=['execution-storage',method or 'none']
    return hashlib.sha256(json.dumps(parts,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()


LOCAL_HOST_KEY='local:'+hashlib.sha256(b'["local","local",null]').hexdigest()


class UnreadState:
    def __init__(self, path=None):
        codex_home=Path(os.environ.get('CODEX_HOME') or Path.home()/'.codex')
        self.path=Path(path) if path is not None else codex_home/'.codex-global-state.json'
        self.signature=None
        self.ids=None
        self.identity=None

    def set_identity(self,key):
        if key!=self.identity:self.identity=key;self.signature=None;self.ids=None

    def read(self):
        try:
            stat=self.path.stat()
            signature=(stat.st_mtime_ns,stat.st_size)
            if signature==self.signature:return self.ids
            data=json.loads(self.path.read_text(encoding='utf-8'))
            if 'electron-thread-read-state-v1' in data:
                state=data['electron-thread-read-state-v1']
                if not self.identity or not isinstance(state,dict) or state.get('version')!=1:raise ValueError('Unread identity unavailable')
                identities=state['unreadByIdentity']
                if not isinstance(identities,dict):raise ValueError('Unsupported unread identities')
                hosts=identities.get(self.identity,{})
                if not isinstance(hosts,dict):raise ValueError('Unsupported unread hosts')
                if LOCAL_HOST_KEY not in hosts and any(k.startswith('local:') for k in hosts):raise ValueError('Different local execution host')
                ids=hosts.get(LOCAL_HOST_KEY,[])
            else:ids=data['electron-persisted-atom-state']['unread-thread-ids-by-host-v1']['local']
            if not isinstance(ids,list) or not all(isinstance(value,str) for value in ids):
                raise ValueError('Unsupported unread state')
            self.ids=set(ids);self.signature=signature
            return self.ids
        except (OSError,ValueError,KeyError,TypeError):
            self.ids=None;self.signature=None
            return None
