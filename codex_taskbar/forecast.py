"""Public community forecast only; no account data or authentication headers."""
from datetime import datetime
import json,math,time,threading,urllib.request
from PySide6.QtCore import QObject,Signal

SOURCE='https://codex-reset.today/developers'
ENDPOINT='https://codex-reset.today/api/v1/status?provider=codex'


def parse_forecast(payload,now=None):
    now=time.time() if now is None else now
    try:
        data=payload['data'];forecast=data['next_reset_estimate']
        if data.get('provider')!='codex' or data['freshness']['state']!='fresh':return None
        chance=forecast['chance_percent'];confidence=forecast['confidence']
        generated=datetime.fromisoformat(forecast['generated_at'].replace('Z','+00:00')).timestamp()
        end=datetime.fromisoformat(forecast['forecast_window_ends_at'].replace('Z','+00:00')).timestamp()
        if type(chance) not in (int,float) or not math.isfinite(chance) or not 0<=chance<=100:return None
        if confidence not in ('low','medium','high') or not -300<=now-generated<=21600 or not now<end<=generated+7*86400:return None
        return dict(chance=chance,confidence=confidence,generated=generated,end=end)
    except (KeyError,TypeError,ValueError,AttributeError):return None


class ResetForecast(QObject):
    changed=Signal()
    received=Signal(object)
    def __init__(self,parent=None):
        super().__init__(parent);self.received.connect(self.finished)
        self.pending=False;self.next_check=0.;self.value=None

    def get(self):
        if self.value and time.time()<min(self.value['end'],self.value['generated']+21600):return self.value
        return None

    def request(self):
        if self.pending or time.monotonic()<self.next_check:return
        self.pending=True;self.next_check=time.monotonic()+120
        threading.Thread(target=self.fetch,daemon=True).start()

    def fetch(self):
        value=None
        try:
            request=urllib.request.Request(ENDPOINT,headers={'Accept':'application/json','User-Agent':'CodexTaskbarCompanion'})
            with urllib.request.urlopen(request,timeout=4) as response:raw=response.read(512001)
            if len(raw)<=512000:value=parse_forecast(json.loads(raw))
        except (OSError,ValueError,TypeError):pass
        try:self.received.emit(value)
        except RuntimeError:pass

    def finished(self,value):
        self.pending=False
        self.value=value;self.next_check=time.monotonic()+(900 if value else 120);self.changed.emit()
