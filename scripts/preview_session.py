"""Standalone 5h preview: real widgets, synthetic data, no account or desktop hooks."""
import argparse
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from codex_taskbar import app


class PreviewData:
    def __init__(self):
        now=time.time();start=now-2*3600;end=start+5*3600
        self.data={'tasks':[],'quota':[{'minutes':300,'label':'5h','remaining':60,'starts_at':start,'resets_at':end}],
            'session_history':[{'at':start+offset,'reset':end,'remaining':remaining}
                for offset,remaining in ((0,100),(600,98),(1800,90),(3600,82),(5400,70),(7200,60))]}

    def get(self):return self.data
    def stop(self):pass
    def request_reset(self,*args):raise AssertionError('Preview cannot consume reset credits')


class PreviewBar(app.StatusBar):
    def __init__(self,runtime,hover=False):
        with patch.object(app,'RUNTIME',runtime),patch.object(app,'RELEASE_REPOSITORY',''), \
             patch.object(app.windows,'ClickHook'),patch.object(app,'QSystemTrayIcon'):
            super().__init__(PreviewData())
        self.setWindowFlags(app.Qt.WindowType.Window | app.Qt.WindowType.CustomizeWindowHint |
                            app.Qt.WindowType.WindowTitleHint | app.Qt.WindowType.WindowCloseButtonHint)
        self.setWindowTitle('5h 预览 · 模拟数据')
        self.settings=dict.fromkeys(app.DISPLAY_DEFAULTS,False)
        self.settings.update(show_session=True,hover_panels=hover)
        self.preview_pressed=False
        self.resize(250,42)
        center=self.screen().availableGeometry().center()
        self.move(center.x()-self.width()//2,center.y()-self.height()//2)

    def tick(self):
        self.data=self.provider.get();self.update()
        if self.popup:self.popup.refresh(self.data)
        self.update_hover_popup(app.QCursor.pos())

    def paintEvent(self,event):
        super().paintEvent(event)
        p=app.QPainter(self);p.setCompositionMode(app.QPainter.CompositionMode.CompositionMode_DestinationOver)
        p.fillRect(self.rect(),app.QColor(app.PANEL));p.end()

    def toggle_popup(self,mode='session'):
        if mode=='session':super().toggle_popup(mode)

    def mousePressEvent(self,event):
        self.preview_pressed=event.button()==app.Qt.MouseButton.LeftButton and any(r.contains(event.position()) for m,r,t in self.hit_regions)
        self.pressed=self.preview_pressed

    def mouseReleaseEvent(self,event):
        if self.preview_pressed and event.button()==app.Qt.MouseButton.LeftButton and any(r.contains(event.position()) for m,r,t in self.hit_regions):
            self.toggle_popup()
        self.preview_pressed=False
        self.pressed=None

    def hideEvent(self,event):
        self.hide_popup(immediate=True)
        super().hideEvent(event)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hover',action='store_true',help='Use the real hover-open behavior')
    parser.add_argument('--check',action='store_true',help='Validate without showing windows or moving the pointer')
    args=parser.parse_args()
    q=app.QApplication([])
    with tempfile.TemporaryDirectory(prefix='codex-5h-preview-') as folder:
        preview=PreviewBar(Path(folder),args.hover)
        if args.check:
            from unittest.mock import Mock
            preview.timer.stop();preview.animation.stop();preview.grab()
            assert [mode for mode,rect,payload in preview.hit_regions]==['session']
            event=Mock();event.button.return_value=app.Qt.MouseButton.LeftButton
            event.position.return_value=preview.hit_regions[0][1].center()
            with patch.object(preview,'toggle_popup') as opened:
                preview.mousePressEvent(event);preview.mouseReleaseEvent(event)
                opened.assert_called_once_with()
            preview.popup=app.SessionPopup(preview);preview.popup.refresh(preview.data)
            assert len(preview.popup.data['session_history'])==6
            preview.popup.grab();preview.close()
            assert not list(Path(folder).iterdir())
            print('5h button and panel verified; no live data, files, hooks or pointer changes.')
            return
        preview.show()
        app.windows.user32.ShowWindow(int(preview.winId()),4)
        q.exec()


if __name__=='__main__':main()
