"""Antialiased, translucent Windows status strip; data stays in provider.py."""
import ctypes
from datetime import datetime, timedelta
from pathlib import Path
import sys
import time
import math
import json
import os
import subprocess

BASE = Path(__file__).resolve().parent
from preferences import runtime_dir, migrate_legacy, read_settings, write_settings, DISPLAY_DEFAULTS, legacy_runtime_dirs
RUNTIME = runtime_dir()
sys.path.insert(0, str(BASE / ".deps"))
try:
    from PySide6.QtCore import Qt, QTimer, QRectF, QPointF, QVariantAnimation, QEasingCurve
    from PySide6.QtGui import QColor, QFont, QFontDatabase, QFontMetricsF, QPainter, QPainterPath, QPen, QCursor, QLinearGradient, QBrush
    from PySide6.QtWidgets import QApplication, QWidget, QMenu, QSystemTrayIcon
except ImportError:
    if '--smoke-test' in sys.argv:raise SystemExit(1)
    raise
from provider import Provider
from usage import reset_countdown_text, remaining_time_fraction, visible_metrics, quota_window, chart_window
from tasks import task_rows, task_metrics, thread_url
import windows
import startup
from settings_ui import SettingsDialog, app_icon
from updates import UpdateController, install_after_exit
from build_info import VERSION, APP_NAME, RELEASE_REPOSITORY

PANEL, MUTED, ACCENT, BLUE = "#1822272e", "#bac5d2", "#53d5a0", "#79b6f5"
TITLE_MUTED = "#8797aa"
ROTATE_SECONDS = 8
FONT_FAMILY = None
LILAC = "#b59bea"
AMBER = "#ebb45f"
FAILED = "#df8589"
FLAGS = Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowDoesNotAcceptFocus | Qt.WindowType.NoDropShadowWindowHint


def face(size=None):
    global FONT_FAMILY
    if FONT_FAMILY is None:
        identifier=QFontDatabase.addApplicationFont(str(BASE/'assets/fonts/AlibabaPuHuiTi-3-55-Regular.ttf'))
        families=QFontDatabase.applicationFontFamilies(identifier)
        FONT_FAMILY=families[0] if families else QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont).family()
    result=QFont(FONT_FAMILY)
    result.setPointSizeF((size if size is not None else 9)+.5)
    result.setWeight(QFont.Weight.Normal)
    result.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    result.setStyleStrategy(QFont.StyleStrategy.PreferAntialias|QFont.StyleStrategy.NoSubpixelAntialias)
    return result


def painter(widget):
    p = QPainter(widget)
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
    p.fillRect(widget.rect(),Qt.GlobalColor.transparent)
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
    p.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing | QPainter.RenderHint.SmoothPixmapTransform)
    return p


def panel_painter(widget):
    p=painter(widget);p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(PANEL));p.drawRoundedRect(QRectF(widget.rect()),9,9)
    sheen=QLinearGradient(0,0,0,max(1,widget.height()))
    sheen.setColorAt(0,QColor(255,255,255,12));sheen.setColorAt(.55,QColor(255,255,255,0))
    p.setBrush(QBrush(sheen));p.drawRoundedRect(QRectF(widget.rect()),9,9)
    return p


def pen(p, color=MUTED, width=1):
    line = QPen(QColor(color), width)
    line.setCapStyle(Qt.PenCapStyle.RoundCap)
    line.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(line)
    p.setBrush(Qt.BrushStyle.NoBrush)


def icon(p, kind, x, y, color=MUTED, fraction=1):
    pen(p, color)
    if kind in ("quota", "session", "spent", "clock"):
        ratio=p.device().devicePixelRatioF()
        stroke=1.4;offset=.5 if round(stroke*ratio)%2 else 0.
        x=(round(x*ratio-offset)+offset)/ratio
        y=(round(y*ratio-offset)+offset)/ratio
        box = QRectF(x-5.5, y-5.5, 11, 11)
        track=QColor(color);track.setAlpha(85)
        pen(p,track,stroke);p.drawEllipse(box)
        if fraction is not None:
            pen(p,color,stroke)
            p.drawArc(box,90*16,-round(360*16*fraction))
    elif kind == "chart":
        pen(p,color,1.5)
        for dx,height in [(-4,4),(0,9),(4,6)]:
            p.drawLine(QPointF(x+dx,y+4),QPointF(x+dx,y+4-height))
    elif kind == "task":
        phase=(1-math.cos(time.monotonic()*2*math.pi/2.4))/2
        halo=QColor(ACCENT);halo.setAlpha(round(24+35*phase))
        center=QColor(ACCENT);center.setAlpha(round(160+95*phase))
        p.setPen(Qt.PenStyle.NoPen);p.setBrush(halo);p.drawEllipse(QPointF(x,y),4.3,4.3)
        p.setBrush(center);p.drawEllipse(QPointF(x,y),2.4+.2*phase,2.4+.2*phase)


def text(p, x, y, value, font, color=MUTED):
    p.setFont(font);p.setPen(QColor(color))
    metrics=QFontMetricsF(font)
    p.drawText(QPointF(x,y+(metrics.ascent()-metrics.descent())/2),value)
    return metrics.horizontalAdvance(value)


def project_tag(p,x,y,value,font,available):
    metrics=QFontMetricsF(font)
    label=metrics.elidedText(value,Qt.TextElideMode.ElideRight,max(0,available-12))
    width=metrics.horizontalAdvance(label)+12
    color=QColor('#8795a5' if value=='无项目' else BLUE)
    outline=QColor(color);outline.setAlpha(155)
    pen(p,outline,.7)
    p.drawRoundedRect(QRectF(x,y-9,width,18),4,4)
    text(p,x+6,y,label,font,color)
    return width


def activity_count(p,x,y,count,color=ACCENT,pulse=True):
    font=face(8);label=str(count)
    width=QFontMetricsF(font).horizontalAdvance(label)+24
    background=QColor(color);background.setAlpha(26)
    p.setPen(Qt.PenStyle.NoPen);p.setBrush(background)
    p.drawRoundedRect(QRectF(x,y-9,width,18),9,9)
    if pulse:icon(p,'task',x+8,y)
    else:
        p.setBrush(QColor(color));p.drawEllipse(QPointF(x+8,y),2.5,2.5)
    text(p,x+17,y,label,font,'#b0ddca' if pulse else '#f0c98b')
    return width


def running_title(p,x,y,value,font,left,width):
    metrics=QFontMetricsF(font)
    phase=time.monotonic()%3.2
    if phase>=2.6:
        text(p,x,y,value,font,TITLE_MUTED)
        return
    band=24
    center=left-band+(width+2*band)*phase/2.6
    light=QLinearGradient(center-band,0,center+band,0)
    for position,color in ((0,TITLE_MUTED),(.3,'#a1cddc'),(.5,'#f4fcff'),(.7,'#a1cddc'),(1,TITLE_MUTED)):
        light.setColorAt(position,QColor(color))
    p.setFont(font);p.setPen(QPen(QBrush(light),1))
    p.drawText(QPointF(x,y+(metrics.ascent()-metrics.descent())/2),value)


def chart_values(days, history, today):
    values=[history.get(day.isoformat()) if day<=today else None for day in days]
    completed=[value for day,value in zip(days,values) if day<today and value is not None]
    limits={min(completed),max(completed)} if len(set(completed))>1 else set()
    extremes={day for day,value in zip(days,values) if day<today and value in limits}
    return values,extremes


def chart_number(value,unit):
    if value is None:return "—"
    factor,decimals={"M":(1_000_000,1),"100M":(100_000_000,2)}[unit]
    scaled=value/factor
    if value>0 and round(scaled,decimals)==0:
        return f"<{10**-decimals:.{decimals}f}"
    return f"{scaled:.{decimals}f}".rstrip("0").rstrip(".")


def chart_total(values):
    known=[value for value in values if value is not None]
    return sum(known) if known else None


def marquee_offset(elapsed,distance):
    if distance<=0:return 0.
    hold=.8;travel=max(.8,distance/32)
    t=max(0,elapsed)%(2*hold+2*travel)
    if t<hold:return 0.
    if t<hold+travel:
        return distance*(1-math.cos(math.pi*(t-hold)/travel))/2
    if t<2*hold+travel:return distance
    return distance*(1+math.cos(math.pi*(t-2*hold-travel)/travel))/2


class StatusBar(QWidget):
    def __init__(self, provider):
        super().__init__(None, FLAGS)
        self.setWindowTitle("Codex 任务栏状态")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.provider=provider
        self.current_id=None;self.rotated_at=time.monotonic();self.popup=None
        self.data=provider.get();self.task=None;self.position=None;self.font=face()
        self.task_rect=QRectF();self.task_hover=False;self.title_hover_started=time.monotonic()
        self.task_area=QRectF()
        self.usage_area=QRectF();self.metrics=[];self.settings_dialog=None;self.placement_unavailable=False
        self.settings=read_settings(RUNTIME/'ui_settings.json')
        self.chart_unit=self.settings['chart_unit']
        self.updater=UpdateController(RUNTIME,self);self.updater.changed.connect(self.update_status)
        self.updater.ready.connect(self.install_update)
        self.tray=QSystemTrayIcon(app_icon(),self);self.tray.setToolTip(APP_NAME)
        self.menu=QMenu();self.menu.setFont(face(8))
        self.menu.setStyleSheet('QMenu{background:#242930;color:#bac5d2;border:1px solid #3b4350;padding:5px;} QMenu::item{padding:7px 12px;} QMenu::item:selected{background:#3b4552;}')
        self.menu.addAction('设置…',lambda:QTimer.singleShot(0,self.open_settings))
        self.menu.addAction('退出',self.close)
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(lambda reason:self.open_settings() if reason==QSystemTrayIcon.ActivationReason.Trigger else None)
        self.tray.messageClicked.connect(self.open_settings)
        self.tray.show()
        self.update_timer=QTimer(self);self.update_timer.setInterval(24*60*60*1000)
        self.update_timer.timeout.connect(self.updater.check)
        if RELEASE_REPOSITORY:self.update_timer.start();QTimer.singleShot(5000,self.updater.check)
        self.previous_task=None;self.task_blend=1.;self.ring_values={};self.ring_tweens={}
        self.task_tween=QVariantAnimation(self);self.task_tween.setDuration(450)
        self.task_tween.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.task_tween.valueChanged.connect(self.set_task_blend)
        self.timer=QTimer(self);self.timer.timeout.connect(self.tick);self.timer.start(150)
        self.animation=QTimer(self);self.animation.timeout.connect(self.animate);self.animation.start(33)
        self.winId()  # Create the native handle only after transparency attributes are set.
        self.click_hook=windows.ClickHook(self.desktop_click)
        self.tick()

    def nativeEvent(self,event_type,message):
        native=windows.w.MSG.from_address(int(message))
        if native.message==windows.OPEN_SETTINGS_MESSAGE:
            QTimer.singleShot(0,self.open_settings);return True,0
        return super().nativeEvent(event_type,message)

    def desktop_click(self,x,y,button="left"):
        def inside(widget):
            if not widget or not widget.isVisible():return False
            box=windows.rect(int(widget.winId()))
            return box is not None and box[0]<=x<box[2] and box[1]<=y<box[3]
        if inside(self):
            box=windows.rect(int(self.winId()));ratio=windows.user32.GetDpiForWindow(int(self.winId()))/96
            point=QPointF((x-box[0])/ratio,(y-box[1])/ratio)
            mode='tasks' if self.task_area.contains(point) else 'usage' if self.usage_area.contains(point) else None
            if mode:
                if button=='right':QTimer.singleShot(0,self.open_menu)
                else:QTimer.singleShot(0,lambda:self.toggle_popup(mode))
                return True  # Transparent pixels must not forward a second action to the taskbar.
        if self.popup and not inside(self.popup):QTimer.singleShot(0,self.hide_popup)
        return False

    def toggle_popup(self,mode='usage'):
        if self.popup and self.popup.mode==mode:
            self.popup.reveal_to(0. if self.popup.reveal_target==1. else 1.)
        else:
            self.hide_popup(immediate=True)
            self.popup=TaskListPopup(self) if mode=='tasks' else TaskPopup(self)
            self.popup.refresh(self.data)
            windows.popup_glass(int(self.popup.winId()))
            self.popup.show()

    def animate(self):
        if self.isVisible() and self.task:
            self.update()
            if self.popup:self.popup.update()

    def set_task_blend(self,value):
        self.task_blend=float(value);self.update()

    def set_chart_unit(self,unit):
        if unit not in ('M','100M'):return
        self.chart_unit=unit
        self.save_settings()
        if self.popup:self.popup.update()

    def save_settings(self):
        self.settings['chart_unit']=self.chart_unit
        try:write_settings(RUNTIME/'ui_settings.json',self.settings)
        except OSError as exc:print('Settings:',exc)

    def set_display(self,key,value):
        if key not in DISPLAY_DEFAULTS:return
        self.settings[key]=bool(value);self.save_settings();self.hide_popup(immediate=True);self.tick()

    def open_settings(self):
        self.hide_popup(immediate=True)
        if self.settings_dialog is None:self.settings_dialog=SettingsDialog(self)
        self.settings_dialog.refresh();self.settings_dialog.show()
        # SW_HIDE startup flags can suppress the first normal window of a background launch.
        windows.user32.ShowWindow(int(self.settings_dialog.winId()),1)
        self.settings_dialog.raise_();self.settings_dialog.activateWindow()

    def open_menu(self):
        self.hide_popup(immediate=True);self.menu.popup(QCursor.pos())

    def set_startup(self,value):
        try:startup.set_enabled(value)
        except OSError as exc:print('Startup:',exc)

    def update_status(self):
        if self.settings_dialog:self.settings_dialog.refresh()
        if self.updater.release and self.settings.get('notified_version')!=self.updater.release['version']:
            self.settings['notified_version']=self.updater.release['version'];self.save_settings()
            self.tray.showMessage(APP_NAME,f"新版本 {self.updater.release['version']} 可用，可从右键菜单更新。")

    def update_clicked(self):
        if self.updater.release:self.updater.install()
        else:self.updater.check();self.open_settings()

    def install_update(self,path):
        command=[sys.executable]+([] if getattr(sys,'frozen',False) else [str(BASE/'app.py')])
        try:subprocess.Popen(command+['--install-update',path,str(os.getpid())],creationflags=0x08000000)
        except OSError as exc:print('Installer:',exc);return
        self.close()

    def open_task(self,task):
        try:
            os.startfile(thread_url(task['id']))
        except (OSError,ValueError) as exc:
            print(f'Task navigation: {exc}',file=sys.stderr)
            return
        self.hide_popup(immediate=True)

    def set_ring(self,kind,value):
        self.ring_values[kind]=float(value);self.update()

    def animate_ring(self,kind,target):
        if kind not in self.ring_values:
            self.ring_values[kind]=target;return
        motion=self.ring_tweens.get(kind)
        if motion and motion.endValue()==target:return
        if not motion:
            motion=QVariantAnimation(self);motion.setDuration(300)
            motion.setEasingCurve(QEasingCurve.Type.OutCubic)
            motion.valueChanged.connect(lambda value,k=kind:self.set_ring(k,value))
            self.ring_tweens[kind]=motion
        motion.stop();motion.setStartValue(self.ring_values[kind]);motion.setEndValue(target);motion.start()

    def selected_task(self, tasks):
        if not tasks:self.current_id=None;return None
        ids=[t["id"] for t in tasks]
        if self.current_id not in ids:
            self.current_id,self.rotated_at=ids[0],time.monotonic()
        elif self.popup is None and not getattr(self,'task_hover',False) and time.monotonic()-self.rotated_at>=ROTATE_SECONDS:
            self.current_id=ids[(ids.index(self.current_id)+1)%len(ids)];self.rotated_at=time.monotonic()
        return tasks[ids.index(self.current_id)]

    def tick(self):
        self.data=self.provider.get()
        if self.settings_dialog and self.settings_dialog.isVisible():self.settings_dialog.refresh()
        if not any(self.settings[key] for key in DISPLAY_DEFAULTS):
            self.hide();self.hide_popup(immediate=True);return
        metrics=visible_metrics(self.data,self.settings)
        minimum=12+sum(29+QFontMetricsF(face(8)).horizontalAdvance(value) for kind,value,fraction in metrics)
        if self.settings['show_tasks']:minimum+=80
        if not metrics and not self.settings['show_tasks']:
            self.hide();self.hide_popup(immediate=True);return
        placed=windows.placement(minimum_width=minimum)
        self.placement_unavailable=placed is None
        if not placed:self.hide();self.hide_popup(immediate=True);return
        if not windows.user32.IsWindow(int(self.winId())):
            # Explorer destroys owned native windows when rebuilding the taskbar.
            self.hide_popup(immediate=True);self.hide();self.destroy();self.create()
            self.position=None
        x,y,w,h,scale,hidden=placed
        if hidden:
            self.hide();self.hide_popup(immediate=True);return
        logical=tuple(round(v/scale) for v in (x,y,w,h))
        if self.position!=logical:self.setGeometry(*logical);self.position=logical
        if not self.isVisible():
            self.show();windows.hide_border(int(self.winId()))
        windows.follow_taskbar(int(self.winId()))
        hovering=self.task_rect.contains(self.mapFromGlobal(QCursor.pos()))
        if hovering!=self.task_hover:
            self.task_hover=hovering;self.title_hover_started=time.monotonic();self.rotated_at=time.monotonic()
        self.data=self.provider.get()
        previous=self.task;self.task=self.selected_task(self.data.get("tasks",[]) if self.settings['show_tasks'] else [])
        if previous and self.task and previous['id']!=self.task['id']:
            self.previous_task=previous;self.task_tween.stop()
            self.task_tween.setStartValue(0.);self.task_tween.setEndValue(1.);self.task_tween.start()
        elif not self.task:
            self.previous_task=None;self.task_tween.stop();self.task_blend=1.
        self.metrics=visible_metrics(self.data,self.settings)
        for kind,value,fraction in self.metrics:
            if fraction is not None:
                if kind=='clock':self.ring_values[kind]=fraction
                else:self.animate_ring(kind,fraction)
        self.update()
        if self.popup:self.popup.refresh(self.data)

    def paintEvent(self,event):
        p=painter(self);data=self.data
        x,y=12.,self.height()/2
        def field(kind,value,fraction):
            nonlocal x
            color={"quota":"#45ba91","session":"#51adb4","clock":"#5d9dd7","spent":"#a088d1"}[kind]
            icon(p,kind,x,y,color,fraction=None if fraction is None else self.ring_values.get(kind,fraction))
            x+=12
            ink=QColor(TITLE_MUTED)
            if kind=='spent' and value=='—':ink.setAlpha(90);value='–'
            x+=text(p,x,y,value,face(8),ink)+17
        def separator():
            nonlocal x
            pen(p,"#53606d",.7)
            p.drawLine(QPointF(x-6,y-5),QPointF(x-6,y+5));x+=7
        for kind,value,fraction in visible_metrics(data,self.settings):field(kind,value,fraction)
        self.usage_area=QRectF(0,0,max(0,x-6) if x>12 else 0,self.height())
        self.task_area=QRectF();self.task_rect=QRectF()
        if not self.settings['show_tasks']:p.end();return
        self.task_area=QRectF(x-6,0,0,self.height())
        if x>12:separator()
        badge_x=x-6
        if self.task:
            count=len({task['id'] for task in data.get('tasks',[])})
            badge_x+=activity_count(p,badge_x,y,count)+6
        unread_count=data.get('unread_count')
        if unread_count:
            badge_x+=activity_count(p,badge_x,y,unread_count,AMBER,pulse=False)+6
        if self.task or unread_count:x=badge_x+4
        if self.task:
            p.save();p.setClipRect(QRectF(x-2,0,max(0,self.width()-x+2),self.height()))
            def task_label(task,opacity,offset,current=False):
                p.save();p.setOpacity(opacity);p.translate(0,offset)
                title_x=x+project_tag(p,x,y,task['project'],face(8),min(112,max(0,(self.width()-x)*.35)))+10
                available=max(0,self.width()-title_x-6)
                label=task['title']
                metrics=QFontMetricsF(self.font)
                title_y=y-metrics.tightBoundingRect(label).center().y()-(metrics.ascent()-metrics.descent())/2
                shown=min(available,metrics.horizontalAdvance(label))
                if current:self.task_rect=QRectF(title_x,0,shown,self.height())
                if opacity>0:self.task_area.setRight(max(self.task_area.right(),min(self.width(),title_x+shown+6)))
                shift=0.
                if self.task_hover and self.popup is None:
                    shift=marquee_offset(time.monotonic()-self.title_hover_started,metrics.horizontalAdvance(label)-available)
                else:
                    label=metrics.elidedText(label,Qt.TextElideMode.ElideRight,available)
                p.setClipRect(QRectF(title_x,-offset,available,self.height()),Qt.ClipOperation.IntersectClip)
                if self.task_hover and shift>0:
                    text(p,title_x-shift,title_y,label,self.font)
                elif self.task_blend<1:
                    text(p,title_x,title_y,label,self.font,TITLE_MUTED)
                else:
                    running_title(p,title_x-shift,title_y,label,self.font,title_x,min(available,metrics.horizontalAdvance(label)))
                p.restore()
            if self.previous_task and self.task_blend<1:
                task_label(self.previous_task,1-self.task_blend,-22*self.task_blend)
            task_label(self.task,self.task_blend,22*(1-self.task_blend),current=True);p.restore()
        else:
            self.task_rect=QRectF()
            if unread_count:end=x+text(p,x,y,'Tasks',self.font,TITLE_MUTED)
            else:
                icon(p,'chart',x,y,MUTED);end=x+12+text(p,x+12,y,'Tasks',self.font)
            self.task_area.setRight(min(self.width(),end+6))
        p.end()

    def hide_popup(self,immediate=False):
        if self.popup:
            if immediate:
                popup=self.popup;self.popup=None;popup.fade.stop();popup.close();popup.deleteLater()
                self.rotated_at=time.monotonic()
            else:self.popup.reveal_to(0.)

    def closeEvent(self,event):
        self.click_hook.close();self.timer.stop();self.animation.stop();self.update_timer.stop()
        self.tray.hide();self.hide_popup(immediate=True)
        if self.settings_dialog:self.settings_dialog.close()
        self.provider.stop();event.accept();QApplication.instance().quit()


class TaskPopup(QWidget):
    mode='usage'
    UNIT_RECTS={'M':QRectF(277,9,28,24),'100M':QRectF(309,9,40,24)}
    def __init__(self,owner):
        super().__init__(None,FLAGS)
        self.owner=owner;self.data={};self.rows=[];self.days=[];self.scroll=0;self.full_height=172
        self.setWindowTitle("Codex 用量")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setMouseTracking(True)
        self.setWindowOpacity(0.)
        self.reveal=0.;self.reveal_target=None
        self.fade=QVariantAnimation(self);self.fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.fade.valueChanged.connect(self.set_reveal);self.fade.finished.connect(self.finish_reveal)

    def showEvent(self,event):
        super().showEvent(event)
        self.reveal_to(1.)

    def set_reveal(self,value):
        self.reveal=float(value);self.setWindowOpacity(self.reveal);self.update()

    def reveal_to(self,target):
        target=float(target)
        if target==self.reveal_target:return
        start=self.reveal
        self.reveal_target=target;self.fade.stop()
        self.fade.blockSignals(True)
        self.fade.setDuration(max(40,round(180*abs(target-start))))
        self.fade.setStartValue(start);self.fade.setEndValue(target)
        self.fade.blockSignals(False);self.fade.start()

    def finish_reveal(self):
        if self.reveal_target==0 and self.owner.popup is self:
            self.owner.popup=None;self.owner.rotated_at=time.monotonic()
            self.owner.title_hover_started=time.monotonic();self.close();self.deleteLater()

    def refresh(self,data):
        self.data=data;now=datetime.now().astimezone()
        week=chart_window(data)
        self.start=datetime.fromtimestamp(week["starts_at"]).astimezone() if week and week.get("starts_at") else now
        self.end=datetime.fromtimestamp(week["resets_at"]).astimezone() if week and week.get("resets_at") else self.start+timedelta(days=7)
        self.days=[];day=self.start.date()
        while day<=self.end.date():self.days.append(day);day+=timedelta(days=1)
        self.window_summary=quota_window(data,300)
        self.extra=24 if self.window_summary else 0
        self.full_height=158+self.extra
        shown=min(round(self.full_height),max(180,self.owner.y()-16))
        self.setGeometry(self.owner.x(),max(0,self.owner.y()-shown-7),360,shown)
        self.scroll=min(self.scroll,max(0,self.full_height-self.height()));self.update()

    def paintEvent(self,event):
        p=panel_painter(self)
        icon(p,"chart",23,21,LILAC)
        date_width=text(p,39,21,f"{self.start:%m.%d} — {self.end:%m.%d %H:%M}",face(8),BLUE)
        history=self.data.get("history",{});today=datetime.now().astimezone().date()
        values,extremes=chart_values(self.days,history,today)
        total='Σ '+chart_number(chart_total(values),self.owner.chart_unit)
        text(p,39+date_width+12,21,total,face(8),LILAC)
        for unit,rect in self.UNIT_RECTS.items():
            selected=unit==self.owner.chart_unit
            p.setFont(face(8));p.setPen(QColor(BLUE if selected else MUTED))
            p.drawText(rect,Qt.AlignmentFlag.AlignCenter,unit)
            if selected:
                pen(p,BLUE,1.2)
                p.drawLine(QPointF(rect.left()+5,rect.bottom()-2),QPointF(rect.right()-5,rect.bottom()-2))
        if self.window_summary:
            window=self.window_summary
            text(p,18,43,f"5h  {window['remaining']:g}%   ·   {reset_countdown_text(window)}",face(8),'#51adb4')
        maximum=max([v for v in values if v is not None]+[1]);step=324/len(self.days)
        for i,(day,value) in enumerate(zip(self.days,values)):
            x=18+(i+.5)*step;bottom=121.+self.extra;height=(value or 0)/maximum*64
            color=ACCENT if day==today else ("#687583" if value is None else (LILAC if day in extremes else BLUE))
            if value:
                h=max(2,height);radius=min(2,h/2);left=x-4.5;top=bottom-h
                path=QPainterPath(QPointF(left,bottom));path.lineTo(left,top+radius)
                path.quadTo(left,top,left+radius,top);path.lineTo(left+9-radius,top)
                path.quadTo(left+9,top,left+9,top+radius);path.lineTo(left+9,bottom);path.closeSubpath()
                p.fillPath(path,QColor(color))
            p.setFont(face(7));p.setPen(QColor(color))
            if day>today:
                pen(p,color,.7);p.drawLine(QPointF(x-2,bottom),QPointF(x+2,bottom))
            else:
                label_top=bottom-height-20 if value else bottom-8
                p.drawText(QRectF(x-step/2,label_top,step,16),Qt.AlignmentFlag.AlignCenter,chart_number(value,self.owner.chart_unit))
            p.setPen(QColor(color))
            p.drawText(QRectF(x-step/2,bottom+9,step,16),Qt.AlignmentFlag.AlignCenter,f"{day.month}/{day.day}")
        p.end()

    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton:
            for unit,rect in self.UNIT_RECTS.items():
                if rect.contains(event.position()):
                    self.owner.set_chart_unit(unit);event.accept();return

    def mouseMoveEvent(self,event):
        over=any(rect.contains(event.position()) for rect in self.UNIT_RECTS.values())
        self.setCursor(Qt.CursorShape.PointingHandCursor if over else Qt.CursorShape.ArrowCursor)

    def wheelEvent(self,event):
        self.scroll=max(0,min(max(0,self.full_height-self.height()),self.scroll-event.angleDelta().y()/120*26));self.update()


class TaskListPopup(TaskPopup):
    mode='tasks'
    ROW_HEIGHT=34
    TITLE_X=88
    TITLE_WIDTH=150

    def __init__(self,owner):
        super().__init__(owner)
        self.setWindowTitle('Codex 任务列表')
        self.hovered=None;self.rows=[];self.hover_started=time.monotonic()
        self.animation=QTimer(self);self.animation.timeout.connect(self.animate);self.animation.start(33)

    def animate(self):
        if self.hovered or any(t.get('running') for t in self.rows):self.update()

    def refresh(self,data):
        self.data=data;self.rows=task_rows(data)
        metrics=QFontMetricsF(face(8))
        self.project_width=min(80,max([metrics.horizontalAdvance(t['project'])+12 for t in self.rows]+[44]))
        self.TITLE_X=33+self.project_width+10
        title_metrics=QFontMetricsF(face())
        longest=max([title_metrics.horizontalAdvance(task['title']) for task in self.rows]+[0])
        values=[task_metrics(task) for task in self.rows]
        duration_width=max([metrics.horizontalAdvance(duration) for duration,tokens in values]+[20])
        token_width=max([metrics.horizontalAdvance(tokens) for duration,tokens in values]+[24])
        info_width=duration_width+12+token_width
        width=min(self.owner.width(),max(260,math.ceil(self.TITLE_X+longest+24+info_width+18)))
        self.token_right=width-18;self.time_right=self.token_right-token_width-12
        self.info_divider=self.time_right-duration_width-12
        self.TITLE_WIDTH=max(0,self.info_divider-12-self.TITLE_X)
        self.sections=[];self.row_positions=[];y=0.;previous=None
        for task in self.rows:
            section='Running' if task.get('running') else 'Recent'
            if section!=previous:
                if previous is not None:y+=8
                self.sections.append((section,y));y+=22;previous=section
            self.row_positions.append(y);y+=self.ROW_HEIGHT
        self.full_height=max(self.ROW_HEIGHT,y)
        height=min(round(self.full_height+16),500,max(100,self.owner.y()-16))
        screen=self.owner.screen().availableGeometry()
        left=max(screen.left(),min(self.owner.x(),screen.right()-width+1))
        self.setGeometry(left,max(screen.top(),self.owner.y()-height-7),width,height)
        self.scroll=min(self.scroll,max(0,self.full_height-(height-16)))
        self.track_hover(self.mapFromGlobal(QCursor.pos()))
        self.update()

    def task_at(self,point):
        if not QRectF(10,8,self.width()-20,max(0,self.height()-16)).contains(point):return None
        local_y=point.y()-8+self.scroll
        return next((task for task,y in zip(self.rows,self.row_positions) if y<=local_y<y+self.ROW_HEIGHT),None)

    def track_hover(self,point):
        task=self.task_at(point);hovered=task['id'] if task else None
        if hovered!=self.hovered:
            self.hovered=hovered;self.hover_started=time.monotonic()
        self.setCursor(Qt.CursorShape.PointingHandCursor if task else Qt.CursorShape.ArrowCursor)

    def paintEvent(self,event):
        p=panel_painter(self)
        def right_label(value,right,y,font,color=MUTED):
            text(p,right-QFontMetricsF(font).horizontalAdvance(value),y,value,font,color)
        p.save();p.setClipRect(QRectF(10,8,self.width()-20,max(0,self.height()-16)))
        if not self.rows:text(p,18,25,'No recent tasks',face(8),MUTED)
        for label,position in self.sections:
            text(p,18,8+position+10-self.scroll,label,face(8),'#8795a5')
        for task,position in zip(self.rows,self.row_positions):
            yy=8+position-self.scroll;y=yy+self.ROW_HEIGHT/2
            if yy+self.ROW_HEIGHT<8 or yy>self.height()-8:continue
            if task['id']==self.hovered:
                p.setPen(Qt.PenStyle.NoPen);p.setBrush(QColor('#303740'))
                p.drawRoundedRect(QRectF(10,yy,self.width()-20,self.ROW_HEIGHT),5,5)
            if task.get('status')=='failed':
                pen(p,FAILED,1.2);p.drawEllipse(QPointF(22,y),3.6,3.6)
                p.drawLine(QPointF(22,y-1.8),QPointF(22,y+.1));p.drawPoint(QPointF(22,y+2))
            elif task.get('status')=='stopped':
                p.setPen(Qt.PenStyle.NoPen);p.setBrush(QColor('#8795a5'))
                p.drawRoundedRect(QRectF(19.5,y-2.5,5,5),.8,.8)
            elif task.get('running'):icon(p,'task',22,y)
            else:
                p.setPen(Qt.PenStyle.NoPen);p.setBrush(QColor(AMBER if task.get('unread') else '#718096'))
                p.drawEllipse(QPointF(22,y),2.4,2.4)
            project_tag(p,33,y,task['project'],face(8),self.project_width)
            title=task['title'];metrics=QFontMetricsF(face());shift=0.
            if task['id']==self.hovered:
                shift=marquee_offset(time.monotonic()-self.hover_started,metrics.horizontalAdvance(title)-self.TITLE_WIDTH)
            else:title=metrics.elidedText(title,Qt.TextElideMode.ElideRight,self.TITLE_WIDTH)
            p.save();p.setClipRect(QRectF(self.TITLE_X,yy,self.TITLE_WIDTH,self.ROW_HEIGHT),Qt.ClipOperation.IntersectClip)
            text(p,self.TITLE_X-shift,y,title,face());p.restore()
            duration,tokens=task_metrics(task)
            pen(p,'#4a5566',.6);p.drawLine(QPointF(self.info_divider,y-5),QPointF(self.info_divider,y+5))
            right_label(duration,self.time_right,y,face(8),'#afa2c5')
            right_label(tokens,self.token_right,y,face(8),'#8eb1d4')
        p.restore();p.end()

    def mousePressEvent(self,event):
        if event.button()!=Qt.MouseButton.LeftButton:return
        task=self.task_at(event.position())
        self.pressed_task=task['id'] if task else None

    def mouseReleaseEvent(self,event):
        if event.button()!=Qt.MouseButton.LeftButton:return
        task=self.task_at(event.position())
        if task and task['id']==getattr(self,'pressed_task',None):self.owner.open_task(task)
        self.pressed_task=None

    def mouseMoveEvent(self,event):
        self.track_hover(event.position());self.update()

    def leaveEvent(self,event):
        self.hovered=None;self.update()

    def wheelEvent(self,event):
        self.pressed_task=None
        self.scroll=max(0,min(max(0,self.full_height-(self.height()-16)),self.scroll-event.angleDelta().y()/120*self.ROW_HEIGHT))
        self.track_hover(self.mapFromGlobal(QCursor.pos()));self.update()



def main():
    if sys.argv[1:]==["--smoke-test"]:return
    if len(sys.argv)==4 and sys.argv[1]=='--install-update':
        install_after_exit(sys.argv[2],int(sys.argv[3]),RUNTIME);return
    ctypes.windll.kernel32.CreateMutexW.restype=ctypes.c_void_p
    mutex=ctypes.windll.kernel32.CreateMutexW(None,False,"Local\\CodexTaskbarStatus")
    if ctypes.windll.kernel32.GetLastError()==183:
        hwnd=windows.user32.FindWindowW(None,"Codex 任务栏状态")
        if hwnd:windows.user32.PostMessageW(hwnd,windows.OPEN_SETTINGS_MESSAGE,0,0)
        return
    migrate_legacy(BASE/'.runtime',RUNTIME,legacy_runtime_dirs())
    sys.stdout=sys.stderr=(RUNTIME/"app.log").open("a",encoding="utf-8",buffering=1)
    app=QApplication(sys.argv);app.setQuitOnLastWindowClosed(False);app.setApplicationName(APP_NAME)
    provider=Provider(RUNTIME);bar=StatusBar(provider)
    app.exec()


if __name__=="__main__":main()
