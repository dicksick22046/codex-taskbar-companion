"""Read only Codex's local unread IDs; never infer read state from timestamps."""
import json
import os
from pathlib import Path


class UnreadState:
    def __init__(self, path=None):
        codex_home=Path(os.environ.get('CODEX_HOME') or Path.home()/'.codex')
        self.path=Path(path) if path is not None else codex_home/'.codex-global-state.json'
        self.signature=None
        self.ids=None

    def read(self):
        try:
            stat=self.path.stat()
            signature=(stat.st_mtime_ns,stat.st_size)
            if signature==self.signature:return self.ids
            data=json.loads(self.path.read_text(encoding='utf-8'))
            ids=data['electron-persisted-atom-state']['unread-thread-ids-by-host-v1']['local']
            if not isinstance(ids,list) or not all(isinstance(value,str) for value in ids):
                raise ValueError('Unsupported unread state')
            self.ids=set(ids);self.signature=signature
            return self.ids
        except (OSError,ValueError,KeyError,TypeError):
            self.ids=None;self.signature=None
            return None
