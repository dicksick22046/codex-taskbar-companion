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
    from PySide6.QtWidgets import QApplication, QWidget, QMenu, QSystemTrayIcon, QPushButton, QMessageBox
except ImportError:
    if '--smoke-test' in sys.argv:raise SystemExit(1)
    raise
from provider import Provider
from usage import reset_countdown_text, remaining_time_fraction, visible_metrics, quota_window, chart_window, countdown_window
from tasks import thread_url, panel_rows, task_category, category_counts, CATEGORY_LABELS, duration_text
from usage import human_tokens
import windows
import startup
from settings_ui import SettingsDialog, app_icon
from updates import UpdateController, install_after_exit
from build_info import VERSION, APP_NAME, RELEASE_REPOSITORY

PANEL, MUTED, ACCENT, BLUE = "#262b33", "#bac5d2", "#53d5a0", "#79b6f5"
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
    text(p,x+17,y,label,font,'#b0ddca' if pulse else QColor(color).lighter(115))
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
        self.hit_regions=[];self.pressed=None;self.confirming_reset=False
        self.metrics=[];self.settings_dialog=None;self.placement_unavailable=False
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
        if self.confirming_reset:return False
        if button=='left_up':
            pressed=self.pressed;self.pressed=None
            if not pressed:return False
            mode,rect,payload=pressed
            if self.isVisible() and rect.contains(QPointF(x,y)):
                if mode=='task':QTimer.singleShot(0,lambda t=payload:self.open_task(t))
                else:QTimer.singleShot(0,lambda m=mode:self.toggle_popup(m))
            return True
        def inside(widget):
            if not widget or not widget.isVisible():return False
            box=windows.rect(int(widget.winId()))
            return box is not None and box[0]<=x<box[2] and box[1]<=y<box[3]
        if inside(self):
            box=windows.rect(int(self.winId()));ratio=windows.user32.GetDpiForWindow(int(self.winId()))/96
            point=QPointF((x-box[0])/ratio,(y-box[1])/ratio)
            hit=next((h for h in self.hit_regions if h[1].contains(point)),None)
            if hit:
                mode,rect,payload=hit
                if button=='right':QTimer.singleShot(0,self.open_menu)
                else:self.pressed=(mode,QRectF(box[0]+rect.x()*ratio,box[1]+rect.y()*ratio,rect.width()*ratio,rect.height()*ratio),payload)
                return True  # Transparent pixels must not forward a second action to the taskbar.
        if self.popup and not inside(self.popup):QTimer.singleShot(0,self.hide_popup)
        return False

    def toggle_popup(self,mode='usage'):
        if self.popup and self.popup.mode==mode:
            self.popup.reveal_to(0. if self.popup.reveal_target==1. else 1.)
        else:
            self.hide_popup(immediate=True)
            if mode=='usage':self.popup=TaskPopup(self)
            elif mode=='session':self.popup=SessionPopup(self)
            elif mode=='resets':self.popup=ResetPopup(self)
            else:self.popup=TaskListPopup(self,mode)
            self.popup.refresh(self.data)
            windows.popup_glass(int(self.popup.winId()))
            self.popup.show()

    def animate(self):
        if self.isVisible() and self.task:
            self.update()

    def set_task_blend(self,value):
        self.task_blend=float(value);self.update()

    def set_chart_unit(self,unit):
        if unit not in ('M','100M'):return
        self.chart_unit=unit
        self.save_settings()
        if self.popup:self.popup.refresh(self.data)

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

    def confirm_reset(self):
        data=self.provider.get();credit=data.get('reset_selected');account=data.get('reset_account')
        if self.confirming_reset or data.get('reset_busy') or not credit or not account:return
        if not data.get('reset_retry') and credit.get('expiresAt') is not None and credit['expiresAt']<=time.time():return
        self.confirming_reset=True;self.hide_popup(immediate=True)
        try:
            message='继续上次未确认结果的重置请求？' if data.get('reset_retry') else '使用最新授予的一次额度重置机会？'
            expiry=datetime.fromtimestamp(credit['expiresAt']).strftime('%m.%d %H:%M') if credit.get('expiresAt') is not None else '未提供'
            dialog=QMessageBox(self);dialog.setWindowTitle('重置额度');dialog.setFont(self.font)
            dialog.setText(message);dialog.setInformativeText('机会到期时间：'+expiry)
            cancel=dialog.addButton('取消',QMessageBox.ButtonRole.RejectRole)
            confirm=dialog.addButton('确认重置',QMessageBox.ButtonRole.AcceptRole)
            dialog.setDefaultButton(cancel)
            dialog.adjustSize()
            dialog.move(self.screen().availableGeometry().center()-dialog.rect().center())
            dialog.show();windows.user32.ShowWindow(int(dialog.winId()),1)
            dialog.exec()
            if dialog.clickedButton() is confirm:self.provider.request_reset(account,credit['id'])
            dialog.deleteLater()
        finally:self.confirming_reset=False
        if self.isVisible():self.toggle_popup('resets')

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
        elif not getattr(self,'task_hover',False) and not getattr(self,'pressed',None) and not getattr(self,'confirming_reset',False) and time.monotonic()-self.rotated_at>=ROTATE_SECONDS:
            self.current_id=ids[(ids.index(self.current_id)+1)%len(ids)];self.rotated_at=time.monotonic()
        return tasks[ids.index(self.current_id)]

    def tick(self):
        self.data=self.provider.get()
        if self.settings_dialog and self.settings_dialog.isVisible():self.settings_dialog.refresh()
        if not any(self.settings[key] for key in DISPLAY_DEFAULTS):
            self.hide();self.hide_popup(immediate=True);return
        metrics=visible_metrics(self.data,self.settings)
        minimum=12+sum(29+QFontMetricsF(face(8)).horizontalAdvance(value) for kind,value,fraction in metrics)
        if self.settings['show_tasks']:
            counts=category_counts(self.data)
            minimum+=(60 if self.data.get('tasks') else 0)+sum(30+QFontMetricsF(face(8)).horizontalAdvance(str(counts[k])) for k in ('running','unread','failed','stopped') if counts[k])
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
        pointer=self.mapFromGlobal(QCursor.pos())
        hovering=self.task_area.contains(pointer)
        self.setCursor(Qt.CursorShape.PointingHandCursor if any(r.contains(pointer) for m,r,t in self.hit_regions) else Qt.CursorShape.ArrowCursor)
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
        self.hit_regions=[]
        x,y=12.,self.height()/2
        def field(kind,value,fraction):
            nonlocal x
            left=x-7
            color={"quota":"#45ba91","session":"#51adb4","clock":"#5d9dd7","spent":"#a088d1"}[kind]
            icon(p,kind,x,y,color,fraction=None if fraction is None else self.ring_values.get(kind,fraction))
            x+=12
            ink=QColor(TITLE_MUTED)
            if kind=='spent' and value=='—':ink.setAlpha(90);value='–'
            x+=text(p,x,y,value,face(8),ink)+17
            mode={'quota':'usage','session':'session','spent':'daily','clock':'resets'}[kind]
            self.hit_regions.append((mode,QRectF(left,0,x-left-8,self.height()),None))
        def separator():
            nonlocal x
            pen(p,"#53606d",.7)
            p.drawLine(QPointF(x-6,y-5),QPointF(x-6,y+5));x+=7
        for kind,value,fraction in visible_metrics(data,self.settings):field(kind,value,fraction)
        self.task_area=QRectF();self.task_rect=QRectF()
        if not self.settings['show_tasks']:p.end();return
        counts=category_counts(data)
        if not self.task and not any(counts[k] for k in ('running','unread','failed','stopped')):p.end();return
        if x>12:separator()
        badge_x=x-6
        for mode,color in [('running',ACCENT),('unread',AMBER),('failed',FAILED),('stopped','#8795a5')]:
            if counts[mode]:
                width=activity_count(p,badge_x,y,counts[mode],color,pulse=mode=='running')
                self.hit_regions.append((mode,QRectF(badge_x-2,0,width+4,self.height()),None));badge_x+=width+6
        if any(counts[k] for k in ('running','unread','failed','stopped')):x=badge_x+4
        if self.task:
            self.task_area=QRectF(x-2,0,0,self.height())
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
            shown=self.previous_task if self.previous_task and self.task_blend<.5 else self.task
            self.hit_regions.append(('task',QRectF(self.task_area),dict(shown)))
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
    GAP=8
    TITLE_HEIGHT=22
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

    def anchor_bottom(self):
        tray=windows.user32.FindWindowW('Shell_TrayWnd',None)
        bounds=windows.rect(tray) if tray else None
        top=min(self.owner.y(),round(bounds[1]/self.owner.devicePixelRatioF())) if bounds else self.owner.y()
        return top-self.GAP

    def refresh(self,data):
        self.data=data;now=datetime.now().astimezone()
        week=chart_window(data)
        self.start=datetime.fromtimestamp(week["starts_at"]).astimezone() if week and week.get("starts_at") else now
        self.end=datetime.fromtimestamp(week["resets_at"]).astimezone() if week and week.get("resets_at") else self.start+timedelta(days=7)
        self.days=[];day=self.start.date()
        while day<=self.end.date():self.days.append(day);day+=timedelta(days=1)
        self.window_summary=quota_window(data,300)
        self.extra=24 if self.window_summary else 0
        self.full_height=158+self.extra+self.TITLE_HEIGHT
        shown=min(round(self.full_height),max(180,self.owner.y()-16))
        self.setGeometry(self.owner.x(),max(0,self.anchor_bottom()-shown),360,shown)
        self.scroll=min(self.scroll,max(0,self.full_height-self.height()));self.update()

    def paintEvent(self,event):
        p=panel_painter(self)
        history=self.data.get("history",{});today=datetime.now().astimezone().date()
        values,extremes=chart_values(self.days,history,today)
        self.usage_header(p,f"{self.start:%m.%d} — {self.end:%m.%d %H:%M}",chart_total(values))
        if self.window_summary:
            window=self.window_summary
            text(p,18,43+self.TITLE_HEIGHT,f"5h  {window['remaining']:g}%   ·   {reset_countdown_text(window)}",face(8),'#51adb4')
        maximum=max([v for v in values if v is not None]+[1]);step=324/len(self.days)
        for i,(day,value) in enumerate(zip(self.days,values)):
            x=18+(i+.5)*step;bottom=121.+self.extra+self.TITLE_HEIGHT;height=(value or 0)/maximum*64
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

    def unit_rects(self):
        return {unit:rect.translated(self.width()-360,self.TITLE_HEIGHT) for unit,rect in self.UNIT_RECTS.items()}

    def usage_header(self,p,period,total):
        text(p,18,17,'Today · Tokens' if self.mode=='daily' else 'This cycle · Tokens',face(8),'#8795a5')
        y=21+self.TITLE_HEIGHT
        icon(p,'chart',23,y,LILAC)
        date_width=text(p,39,y,period,face(8),BLUE)
        text(p,39+date_width+12,y,'Σ '+chart_number(total,self.owner.chart_unit),face(8),LILAC)
        for unit,rect in self.unit_rects().items():
            selected=unit==self.owner.chart_unit
            p.setFont(face(8));p.setPen(QColor(BLUE if selected else MUTED))
            p.drawText(rect,Qt.AlignmentFlag.AlignCenter,unit)
            if selected:
                pen(p,BLUE,1.2)
                p.drawLine(QPointF(rect.left()+5,rect.bottom()-2),QPointF(rect.right()-5,rect.bottom()-2))

    def mousePressEvent(self,event):
        if self.mode not in ('usage','daily'):return
        if event.button()==Qt.MouseButton.LeftButton:
            for unit,rect in self.unit_rects().items():
                if rect.contains(event.position()):
                    self.owner.set_chart_unit(unit);event.accept();return

    def mouseMoveEvent(self,event):
        if self.mode!='usage':
            self.setCursor(Qt.CursorShape.ArrowCursor);return
        over=any(rect.contains(event.position()) for rect in self.unit_rects().values())
        self.setCursor(Qt.CursorShape.PointingHandCursor if over else Qt.CursorShape.ArrowCursor)

    def wheelEvent(self,event):
        self.scroll=max(0,min(max(0,self.full_height-self.height()),self.scroll-event.angleDelta().y()/120*26));self.update()


class SessionPopup(TaskPopup):
    mode='session'

    def refresh(self,data):
        self.data=data;self.setGeometry(self.owner.x(),max(0,self.anchor_bottom()-174),360,174)
        self.update()

    def paintEvent(self,event):
        p=panel_painter(self);window=quota_window(self.data,300)
        text(p,18,21,'5h',face(8),'#51adb4')
        value=f"{window['remaining']:g}% remaining" if window else '—'
        text(p,49,21,value,face(8),MUTED)
        reset=datetime.fromtimestamp(window['resets_at']).strftime('%H:%M') if window and window.get('resets_at') else '—'
        text(p,258,21,'Reset '+reset,face(7),'#8797aa')
        left,top,width,height=32.,51.,306.,87.
        for fraction,label in ((1,'100'),(0,'0')):
            y=top+(1-fraction)*height;pen(p,'#46515d',.5)
            p.drawLine(QPointF(left,y),QPointF(left+width,y));text(p,9,y,label,face(6),'#8797aa')
        if window and window.get('starts_at') is not None and window.get('resets_at'):
            start,end=window['starts_at'],window['resets_at']
            rows=[s for s in self.data.get('session_history',[]) if s['reset']==end and start<=s['at']<=end]
            points=[QPointF(left+(s['at']-start)/(end-start)*width,top+(1-s['remaining']/100)*height) for s in rows] if end>start else []
            if points:
                path=QPainterPath(points[0])
                for point in points[1:]:path.lineTo(point)
                pen(p,'#51adb4',1.5);p.drawPath(path)
                p.setPen(Qt.PenStyle.NoPen);p.setBrush(QColor('#51adb4'));p.drawEllipse(points[-1],2.5,2.5)
            text(p,left,153,datetime.fromtimestamp(start).strftime('%H:%M'),face(7),'#8797aa')
            label=datetime.fromtimestamp(end).strftime('%H:%M')
            text(p,left+width-QFontMetricsF(face(7)).horizontalAdvance(label),153,label,face(7),'#8797aa')
        p.end()


class ResetPopup(TaskPopup):
    mode='resets'

    def __init__(self,owner):
        super().__init__(owner)
        self.button=QPushButton('Reset quota',self);self.button.setFont(face(8))
        self.button.setStyleSheet('QPushButton{color:#d2dce7;background:#354a5c;border:0;border-radius:6px;} QPushButton:hover{background:#405a71;} QPushButton:disabled{color:#8795a5;background:#303740;}')
        self.button.clicked.connect(owner.confirm_reset)

    def refresh(self,data):
        self.data=data;self.rows=data.get('reset_events',[])
        self.credits=data.get('reset_credits',[])
        self.history_height=26*max(1,min(6,len(self.rows)))
        self.credits_top=76+self.history_height+26
        height=self.credits_top+24+26*max(1,len(self.credits))+54
        self.full_height=height
        self.setGeometry(self.owner.x(),max(0,self.anchor_bottom()-height),360,height)
        self.button.setGeometry(18,height-48,324,32)
        credit=data.get('reset_selected')
        eligible=bool(credit and data.get('reset_account'))
        if credit and not data.get('reset_retry') and credit.get('expiresAt') is not None:eligible=eligible and credit['expiresAt']>time.time()
        self.button.setEnabled(eligible and not data.get('reset_busy') and (not data.get('quota_error') or data.get('reset_retry',False)))
        label='Resetting…' if data.get('reset_busy') else 'Retry reset' if data.get('reset_retry') or data.get('reset_state')=='unavailable' else 'Nothing to reset' if data.get('reset_state')=='nothingToReset' else 'Reset quota'
        self.button.setText(label)
        self.scroll=min(self.scroll,max(0,len(self.rows)*26-self.history_height))
        self.update()

    def paintEvent(self,event):
        p=panel_painter(self);window=countdown_window(self.data,self.owner.settings)
        def right_label(value,y,color=MUTED,font=None):
            font=font or face(8)
            text(p,342-QFontMetricsF(font).horizontalAdvance(value),y,value,font,color)
        def divider(y):
            pen(p,'#3d4652',.6);p.drawLine(QPointF(18,y),QPointF(342,y))
        text(p,18,23,'Next reset',face(8),'#94a2b3')
        value=datetime.fromtimestamp(window['resets_at']).strftime('%m.%d %H:%M') if window and window.get('resets_at') else '—'
        right_label(value,23,BLUE);divider(44)
        text(p,18,64,'History',face(8),'#94a2b3')
        p.save();p.setClipRect(QRectF(18,76,324,self.history_height))
        labels={'scheduled':'Scheduled','manual':'Manual','official':'Official'}
        colors={'scheduled':BLUE,'manual':LILAC,'official':ACCENT}
        if not self.rows:text(p,18,89,'No records yet',face(8),'#94a2b3')
        for i,row in enumerate(self.rows):
            y=89+i*26-self.scroll
            text(p,18,y,datetime.fromtimestamp(row['at']).strftime('%m.%d %H:%M'),face(8),MUTED)
            label=labels.get(row['kind'],'')
            if len(self.data.get('quota',[]))>1:
                windows_text=' + '.join({'300':'5h','10080':'7d'}.get(k,k+'m') for k in row.get('windows',[]))
                label=' · '.join(part for part in (label,windows_text) if part)
            if label:right_label(label,y,colors.get(row['kind'],'#94a2b3'),face(7))
        p.restore()
        divider(self.credits_top-20)
        count=self.data.get('reset_available');credit=self.data.get('reset_selected')
        text(p,18,self.credits_top,'Expires',face(8),'#94a2b3')
        right_label(f'{count} available' if count is not None else '—',self.credits_top,ACCENT)
        for i,item in enumerate(self.credits):
            selected=bool(credit and item['id']==credit['id'])
            expiry=datetime.fromtimestamp(item['expiresAt']).strftime('%m.%d %H:%M') if item.get('expiresAt') is not None else '—'
            y=self.credits_top+26+i*26
            text(p,18,y,expiry,face(8),MUTED)
            if selected:right_label('Default',y,LILAC,face(7))
        if not self.credits:text(p,18,self.credits_top+26,'No credits' if count==0 else '—',face(8),'#94a2b3')
        p.end()

    def wheelEvent(self,event):
        self.scroll=max(0,min(max(0,len(self.rows)*26-self.history_height),self.scroll-event.angleDelta().y()/120*26));self.update()


class TaskListPopup(TaskPopup):
    mode='daily'
    ROW_HEIGHT=34
    TITLE_X=88
    TITLE_WIDTH=150

    def __init__(self,owner,mode='daily'):
        super().__init__(owner)
        self.mode=mode
        self.setWindowTitle('Codex 任务列表')
        self.hovered=None;self.rows=[];self.hover_started=time.monotonic()
        self.animation=QTimer(self);self.animation.timeout.connect(self.animate);self.animation.start(33)

    def animate(self):
        if self.hovered or any(t.get('running') for t in self.rows):self.update()

    def refresh(self,data):
        self.data=data;self.rows=panel_rows(data,self.mode)
        metrics=QFontMetricsF(face(8))
        self.project_width=min(80,max([metrics.horizontalAdvance(t['project'])+12 for t in self.rows]+[44]))
        self.TITLE_X=33+self.project_width+10
        title_metrics=QFontMetricsF(face())
        longest=max([title_metrics.horizontalAdvance(task['title']) for task in self.rows]+[0])
        self.values={t['id']:chart_number(t.get('tokens'),self.owner.chart_unit) if self.mode=='daily' else duration_text(t.get('round_seconds')) for t in self.rows}
        info_width=max([metrics.horizontalAdvance(value) for value in self.values.values()]+[24])
        width=min(self.owner.width(),max(260,math.ceil(self.TITLE_X+longest+24+info_width+18)))
        if self.mode=='daily':width=max(360,width)
        self.value_right=width-18
        self.info_divider=self.value_right-info_width-12
        self.TITLE_WIDTH=max(0,self.info_divider-12-self.TITLE_X)
        self.sections=[] if self.mode=='daily' else [(CATEGORY_LABELS[self.mode],0)]
        self.header_extra=self.TITLE_HEIGHT if self.mode=='daily' else 0
        self.row_positions=[];y=24.+self.header_extra;previous=None
        for task in self.rows:
            section=CATEGORY_LABELS[task_category(task)]
            if self.mode=='daily' and section!=previous:
                if previous is not None:y+=8
                self.sections.append((section,y));y+=22;previous=section
            self.row_positions.append(y);y+=self.ROW_HEIGHT
        self.full_height=max(24+self.header_extra+self.ROW_HEIGHT,y)
        height=min(round(self.full_height+16),500,max(100,self.owner.y()-16))
        screen=self.owner.screen().availableGeometry()
        left=max(screen.left(),min(self.owner.x(),screen.right()-width+1))
        self.setGeometry(left,max(screen.top(),self.anchor_bottom()-height),width,height)
        self.scroll=min(self.scroll,max(0,self.full_height-(height-16)))
        self.track_hover(self.mapFromGlobal(QCursor.pos()))
        self.update()

    def task_at(self,point):
        if self.mode=='daily' and point.y()<32+self.TITLE_HEIGHT:return None
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
        top=32+self.TITLE_HEIGHT if self.mode=='daily' else 8
        p.save();p.setClipRect(QRectF(10,top,self.width()-20,max(0,self.height()-top-8)))
        if not self.rows:text(p,18,50+self.header_extra,'No tasks',face(8),MUTED)
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
            pen(p,'#4a5566',.6);p.drawLine(QPointF(self.info_divider,y-5),QPointF(self.info_divider,y+5))
            right_label(self.values[task['id']],self.value_right,y,face(8),'#8eb1d4' if self.mode=='daily' else '#afa2c5')
        p.restore()
        if self.mode=='daily':
            total=(self.data.get('totals') or {}).get('total_tokens')
            self.usage_header(p,f'{datetime.now():%m.%d} 00:00–24:00',total)
        p.end()

    def mousePressEvent(self,event):
        if event.button()!=Qt.MouseButton.LeftButton:return
        self.pressed_task=None
        if self.mode=='daily' and any(rect.contains(event.position()) for rect in self.unit_rects().values()):
            super().mousePressEvent(event);return
        task=self.task_at(event.position())
        self.pressed_task=task['id'] if task else None

    def mouseReleaseEvent(self,event):
        if event.button()!=Qt.MouseButton.LeftButton:return
        task=self.task_at(event.position())
        if task and task['id']==getattr(self,'pressed_task',None):self.owner.open_task(task)
        self.pressed_task=None

    def mouseMoveEvent(self,event):
        self.track_hover(event.position());self.update()
        if self.mode=='daily' and any(rect.contains(event.position()) for rect in self.unit_rects().values()):
            self.setCursor(Qt.CursorShape.PointingHandCursor)

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
