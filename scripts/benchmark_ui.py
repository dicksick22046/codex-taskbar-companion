"""Repeatable hidden-widget repaint benchmark; no live account, mouse input or window activation."""
import json
from pathlib import Path
import sys
import time
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tests import test_interactions as fixtures


def main():
    fixtures.InteractionTests.setUpClass()
    fixture=fixtures.InteractionTests();fixture.setUp();bar=fixture.bar
    bar.settings['show_tasks']=False
    requests=[]
    def draw(*args):
        requests.append(1);bar.grab()
    try:
        with patch('codex_taskbar.app.windows.placement',return_value=(0,900,1200,30,1,False)),patch.object(bar,'ensure_visible'), \
             patch('codex_taskbar.app.windows.follow_taskbar'),patch.object(bar,'track_pointer'),patch.object(bar,'update',side_effect=draw):
            bar.tick();requests.clear();start=time.process_time()
            for _ in range(300):bar.tick()
            print(json.dumps({'scenario':'300 unchanged ticks; hidden raster rendering; mocked placement; no live Provider',
                              'update_requests':len(requests),'cpu_seconds':round(time.process_time()-start,4)}))
    finally:fixture.tearDown()


if __name__=='__main__':main()
