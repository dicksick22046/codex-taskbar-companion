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
from html import escape
from functools import lru_cache

BASE = Path(__file__).resolve().parents[1]
from .preferences import runtime_dir, migrate_legacy, read_settings, write_settings, DISPLAY_DEFAULTS, legacy_runtime_dirs
RUNTIME = runtime_dir()
try:
    from PySide6.QtCore import Qt, QTimer, QRect, QRectF, QPointF, QVariantAnimation, QEasingCurve,QAbstractAnimation
    from PySide6.QtGui import QColor, QFont, QFontDatabase, QFontMetricsF, QPainter, QPainterPath, QPen, QCursor, QLinearGradient
    from PySide6.QtWidgets import QApplication, QWidget, QMenu, QSystemTrayIcon, QPushButton, QMessageBox,QButtonGroup,QToolTip
    from PySide6.QtSvg import QSvgRenderer
except ImportError:
    if '--smoke-test' in sys.argv:raise SystemExit(1)
    raise
from .provider import Provider
from .usage import reset_countdown_text, remaining_time_fraction, visible_metrics, quota_window, chart_window, countdown_window, effective_quota_data, quota_is_cached
from .tasks import thread_url, panel_rows, task_category, category_counts, CATEGORY_LABELS, STATUS_CATEGORIES, duration_text,task_role_label
from . import windows
from . import startup
from .settings_ui import SettingsDialog, Toggle, app_icon
from .updates import UpdateController, install_after_exit
from .build_info import VERSION, APP_NAME, RELEASE_REPOSITORY
from .i18n import LANGUAGES, translate, project_label, task_title
from .presentation import floating_rect,remember_position,clamp_rect,panel_rect,AutoPlacement
from .motion import Spring
from .attention_notices import AttentionNotices
from .forecast import ResetForecast,SOURCE as FORECAST_SOURCE

PANEL, MUTED, ACCENT, BLUE = "#262b33", "#bac5d2", "#53d5a0", "#79b6f5"
TITLE_MUTED = "#8797aa"
ROTATE_SECONDS = 8
CONTENT_X = 18.
FONT_FAMILY = None
LILAC = "#b59bea"
AMBER = "#ebb45f"
FAILED = "#df8589"
CAPSULE_COLORS = {
    'dark': {'background':'#252b34','text':MUTED,'muted':TITLE_MUTED,'link':BLUE,'green':ACCENT,'amber':AMBER,'failed':FAILED,'stopped':'#8795a5','divider':'#53606d',
             'rings':{'quota':'#45ba91','session':'#51adb4','clock':'#5d9dd7','spent':'#a088d1'}},
    'light': {'background':'#eef1f5','text':'#27374b','muted':'#43556b','link':'#2169ad','green':'#19775d','amber':'#936005','failed':'#ab3443','stopped':'#596a7d','divider':'#abb7c5',
              'rings':{'quota':'#19775d','session':'#14767e','clock':'#286dab','spent':'#7150a1'}},
}
FLAGS = Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowDoesNotAcceptFocus | Qt.WindowType.NoDropShadowWindowHint


def face(size=None):
    global FONT_FAMILY
    if FONT_FAMILY is None:
        identifier=QFontDatabase.addApplicationFont(str(BASE/'assets/fonts/AlibabaPuHuiTi-3-55-Regular.ttf'))
        families=QFontDatabase.applicationFontFamilies(identifier)
        FONT_FAMILY=families[0] if families else QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont).family()
    return QFont(_configured_face(FONT_FAMILY,(size if size is not None else 9)+.5))


@lru_cache(maxsize=8)
def _configured_face(family,size):
    result=QFont(family)
    result.setPointSizeF(size)
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
    p=painter(widget);p.setPen(QPen(QColor('#454b56'),.7))
    surface=QLinearGradient(0,0,0,widget.height());surface.setColorAt(0,QColor('#30343c'));surface.setColorAt(1,QColor('#25282f'))
    p.setBrush(surface);p.drawRoundedRect(QRectF(widget.rect()).adjusted(.5,.5,-.5,-.5),12,12)
    return p


def pen(p, color=MUTED, width=1):
    line = QPen(QColor(color), width)
    line.setCapStyle(Qt.PenCapStyle.RoundCap)
    line.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(line)
    p.setBrush(Qt.BrushStyle.NoBrush)


def icon(p, kind, x, y, color=None, fraction=1):
    color=color or (ACCENT if kind=='task' else MUTED)
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
        halo=QColor(color);halo.setAlpha(40)
        p.setPen(Qt.PenStyle.NoPen);p.setBrush(halo);p.drawEllipse(QPointF(x,y),4.3,4.3)
        p.setBrush(QColor(color));p.drawEllipse(QPointF(x,y),2.4,2.4)


def text(p, x, y, value, font, color=MUTED):
    p.setFont(font);p.setPen(QColor(color))
    metrics=QFontMetricsF(font)
    p.drawText(QPointF(x,y+(metrics.ascent()-metrics.descent())/2),value)
    return metrics.horizontalAdvance(value)


def project_tag(p,x,y,value,font,available,language='en',color=BLUE,muted='#8795a5'):
    metrics=QFontMetricsF(font)
    label=metrics.elidedText(project_label(value,language),Qt.TextElideMode.ElideRight,max(0,available-12))
    width=metrics.horizontalAdvance(label)+12
    color=QColor(muted if not value else color)
    fill=QColor(color);fill.setAlpha(24)
    p.setPen(Qt.PenStyle.NoPen);p.setBrush(fill)
    p.drawRoundedRect(QRectF(x,y-9,width,18),5,5)
    text(p,x+6,y,label,font,color)
    return width


def side_tag_width(language='en',role='Side'):
    metrics=QFontMetricsF(face(7))
    return max(metrics.horizontalAdvance(translate(language,label)) for label in ('Main','Side'))+10


def side_tag(p,x,y,language='en',light=False,role='Side'):
    width=side_tag_width(language,role)
    p.setPen(Qt.PenStyle.NoPen);p.setBrush(QColor('#dce3ec' if light else '#3b424d'))
    p.drawRoundedRect(QRectF(x,y-7,width,14),3,3)
    label=translate(language,role);left=x+(width-QFontMetricsF(face(7)).horizontalAdvance(label))/2
    text(p,left,y,label,face(7),'#465a72' if light else '#a6b2c0')
    return width


def activity_count(p,x,y,count,color=ACCENT,pulse=True,text_color=None,glyph=None,emphasis=0):
    font=face(8);label=str(count)
    width=QFontMetricsF(font).horizontalAdvance(label)+24
    background=QColor(color);background.setAlpha(26+16*emphasis)
    p.setPen(Qt.PenStyle.NoPen);p.setBrush(background)
    p.drawRoundedRect(QRectF(x,y-9,width,18),9,9)
    if glyph:text(p,x+5,y,glyph,face(8),color)
    elif pulse:icon(p,'task',x+8,y,color)
    else:
        p.setBrush(QColor(color));p.drawEllipse(QPointF(x+8,y),2.5,2.5)
    text(p,x+17,y,label,font,text_color or ('#b0ddca' if pulse else QColor(color).lighter(115)))
    return width


def quota_update_label(owner,data):
    stamp=data.get('quota_updated_at')
    try:updated=datetime.fromisoformat(stamp).astimezone().strftime('%m.%d %H:%M')
    except (TypeError,ValueError):return owner.label('Update time unknown')
    return owner.label('Updated {time}',time=updated)


def quota_context_lines(owner,data,mode):
    current=effective_quota_data(data)
    if mode=='daily':
        value=current.get('daily_quota','—');label='Today used'
    else:
        window=quota_window(current,300 if mode=='session' else 10080)
        value=f"{window['remaining']:g}%" if window else '—'
        label='5h left' if mode=='session' else 'Week left'
    context=owner.label('Account quota')+' · '+owner.label(label)+' '+value
    if quota_is_cached(data):context+=' · '+owner.label('Cached')
    freshness=quota_update_label(owner,data)
    if mode=='daily':
        try:observed=owner.label('Observed since {time}',time=datetime.fromisoformat(current.get('daily_observed_at')).astimezone().strftime('%H:%M'))
        except (TypeError,ValueError):observed=owner.label('Observation start unknown')
        freshness+=' · '+observed
    return context,freshness


def usage_update_label(owner,data,compact=True):
    try:at=datetime.fromisoformat(data.get('usage_at')).astimezone()
    except (TypeError,ValueError):return owner.label('Update time unknown')
    pattern='%H:%M' if compact and at.date()==datetime.now().astimezone().date() else '%m.%d %H:%M'
    return owner.label('Updated {time}',time=at.strftime(pattern))


def connected_surface(box,edge=None):
    path=QPainterPath();path.setFillRule(Qt.FillRule.WindingFill)
    radius=min(14.,box.height()/2);path.addRoundedRect(box,radius,radius)
    if edge=='top':path.addRect(QRectF(box.left(),box.top(),box.width(),radius))
    elif edge=='bottom':path.addRect(QRectF(box.left(),box.bottom()-radius,box.width(),radius))
    return path.simplified()


class PinButton(QPushButton):
    ICON_SIZE=12
    def __init__(self,owner,parent,dark_panel=True):
        super().__init__(parent);self.owner=owner;self.dark_panel=dark_panel;self.setCheckable(True);self.setAutoDefault(False)
        self.setCursor(Qt.CursorShape.PointingHandCursor);self.setFixedSize(26,26)
        self.keyboard_focus=False;self.hover_value=0.;self.visual_key=None
        self.hover_tween=QVariantAnimation(self);self.hover_tween.setDuration(140);self.hover_tween.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.hover_tween.valueChanged.connect(self.set_hover_value)
    @property
    def light_surface(self):return not self.dark_panel and self.owner.settings.get('capsule_theme')=='light'
    def glyph_rect(self):return QRectF((self.width()-self.ICON_SIZE)/2,(self.height()-self.ICON_SIZE)/2,self.ICON_SIZE,self.ICON_SIZE)
    def set_hover_value(self,value):self.hover_value=float(value);self.update()
    def hover_to(self,target):
        self.hover_tween.stop()
        if not self.owner.motion_enabled:self.set_hover_value(target);return
        self.hover_tween.setStartValue(self.hover_value);self.hover_tween.setEndValue(target);self.hover_tween.start()
    def enterEvent(self,event):self.hover_to(1.);super().enterEvent(event)
    def leaveEvent(self,event):self.hover_to(0.);super().leaveEvent(event)
    def hideEvent(self,event):self.hover_tween.stop();self.hover_value=0.;super().hideEvent(event)
    def focusInEvent(self,event):
        self.keyboard_focus=event.reason() in (Qt.FocusReason.TabFocusReason,Qt.FocusReason.BacktabFocusReason,Qt.FocusReason.ShortcutFocusReason)
        super().focusInEvent(event);self.update()
    def focusOutEvent(self,event):self.keyboard_focus=False;super().focusOutEvent(event);self.update()
    def sync(self,checked):
        label=self.owner.label('Unpin status' if checked else 'Pin status');key=(checked,label,self.light_surface)
        if not self.owner.motion_enabled and self.hover_tween.state()!=QAbstractAnimation.State.Stopped:
            target=self.hover_tween.endValue();self.hover_tween.stop();self.set_hover_value(target)
        if key==self.visual_key and self.isChecked()==checked:return
        self.visual_key=key;self.setChecked(checked)
        self.setAccessibleName(label);self.setToolTip(label);self.update()
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        light=self.light_surface;accent='#2169ad' if light else BLUE
        color=accent if self.isChecked() else '#526174' if light else '#99a6b5'
        if not self.dark_panel:color='#667588' if light else '#8795a5'
        strength=1. if self.isDown() or self.keyboard_focus else self.hover_value
        if strength:
            fill=QColor('#c8d3df' if light else '#465364' if self.isDown() else '#35414f');fill.setAlphaF(strength)
            p.setPen(Qt.PenStyle.NoPen);p.setBrush(fill);p.drawRoundedRect(QRectF(3,3,20,20),5,5)
        if self.keyboard_focus:pen(p,'#2169ad' if light else BLUE,.8);p.drawRoundedRect(QRectF(3,3,20,20),5,5)
        pin_renderer(color).render(p,self.glyph_rect())
        if not self.dark_panel and strength:
            p.setOpacity(strength);pin_renderer(accent).render(p,self.glyph_rect())
        p.end()


@lru_cache(maxsize=6)
def pin_renderer(color):
    source=(BASE/'assets/icons/pin.svg').read_bytes().replace(b'currentColor',color.encode('ascii'))
    return QSvgRenderer(source)


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


def wheel_distance(event,step):
    pixels=event.pixelDelta().y()
    return pixels if pixels else event.angleDelta().y()/120*step


class StatusBar(QWidget):
    def __init__(self, provider):
        super().__init__(None, FLAGS)
        self.setWindowTitle("Codex 任务栏状态")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setMouseTracking(True)
        self.provider=provider
        self.popup=None
        self.data=provider.get();self.position=None;self.font=face()
        self.quota_kind=None;self.quota_rotated_at=time.monotonic();self.quota_paused_at=None;self.quota_hover=False
        self.quota_progress=1.;self.quota_previous=None;self.quota_target=1.
        self.quota_tween=QVariantAnimation(self)
        self.quota_tween.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.quota_tween.valueChanged.connect(self.set_quota_progress)
        self.quota_tween.finished.connect(self.finish_quota_transition)
        self.hit_regions=[];self.pressed=None;self.confirming_reset=False
        self.pressed_local=None;self.press_inside=False;self.right_pressed=None
        self.hover_target=None;self.hover_since=0.;self.hover_leave_since=None;self.hover_suppressed=None
        self.metrics=[];self.settings_dialog=None;self.task_finder=None;self.placement_unavailable=False;self.settings_errors=set()
        self.attention_notices=AttentionNotices();self.notification_kind='settings';self.notification_tasks=[]
        self.surface_loss_since=None;self.surface_repaired=False
        self.frame_key=None;self.panel_key=None
        self.host_key=None;self.drag_origin=None;self.dragging=False
        self.content_limit=None
        self.auto_placement=AutoPlacement()
        self.motion_enabled=windows.animations_enabled()
        self.settings=read_settings(RUNTIME/'ui_settings.json')
        self.chart_unit=self.settings['chart_unit']
        self.updater=UpdateController(RUNTIME,self);self.updater.changed.connect(self.update_status)
        self.updater.ready.connect(self.install_update)
        self.tray=QSystemTrayIcon(app_icon(),self);self.tray.setToolTip(APP_NAME)
        self.menu=QMenu(self);self.menu.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint,True);self.menu.setFont(face(8))
        self.menu.setStyleSheet('QMenu{background:#2b2f37;color:#d7dfe9;border:1px solid #474f5d;padding:6px;} QMenu::item{padding:8px 16px;border-radius:5px;} QMenu::item:selected{background:#426992;}')
        self.find_action=self.menu.addAction(self.label('Find task…'),lambda:QTimer.singleShot(0,self.open_finder))
        self.status_menu=QMenu(self.label('Task status'),self.menu)
        self.status_action=self.menu.addMenu(self.status_menu)
        self.menu.aboutToShow.connect(self.refresh_status_menu)
        self.status_menu.aboutToShow.connect(self.refresh_status_menu)
        self.settings_action=self.menu.addAction(self.label('Settings…'),lambda:QTimer.singleShot(0,self.open_settings))
        self.quit_action=self.menu.addAction(self.label('Quit'),self.close)
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(lambda reason:self.open_settings() if reason==QSystemTrayIcon.ActivationReason.Trigger else None)
        self.tray.messageClicked.connect(self.notification_clicked)
        self.tray.show()
        self.update_timer=QTimer(self);self.update_timer.setInterval(24*60*60*1000)
        self.update_timer.timeout.connect(self.updater.check)
        if RELEASE_REPOSITORY:self.update_timer.start();QTimer.singleShot(5000,self.updater.check)
        self.ring_values={};self.ring_tweens={}
        from .task_strip import PinnedPanel
        self.task_strip=PinnedPanel(self)
        self.forecast=ResetForecast(self)
        self.timer=QTimer(self);self.timer.timeout.connect(self.tick);self.timer.start(150)
        self.animation=QTimer(self);self.animation.timeout.connect(self.animate)
        self.stack_repair_pending=False
        self.native_handle=int(self.winId())  # Create the native handle only after transparency attributes are set.
        self.click_hook=windows.ClickHook(self.desktop_click)
        self.tick()

    def nativeEvent(self,event_type,message):
        native=windows.w.MSG.from_address(int(message))
        if native.message==windows.OPEN_SETTINGS_MESSAGE:
            QTimer.singleShot(0,self.open_settings);return True,0
        if native.message==0x001A:QTimer.singleShot(0,self.sync_motion)
        if hasattr(self,'native_handle') and windows.z_order_changed(native):self.schedule_stack_repair()
        return super().nativeEvent(event_type,message)

    def schedule_stack_repair(self):
        if self.stack_repair_pending:return
        self.stack_repair_pending=True;QTimer.singleShot(0,self.repair_stack)

    def repair_stack(self):
        try:
            if not self.isVisible() or self.confirming_reset:return
            if not self.floating:windows.follow_taskbar(int(self.winId()))
            if self.task_strip.isVisible():self.task_strip.ensure_visible();self.task_strip.update()
            if self.popup and self.popup.isVisible():self.popup.sync_owner();self.popup.update()
            self.update()
        finally:self.stack_repair_pending=False

    def sync_motion(self):
        enabled=windows.animations_enabled()
        if enabled==self.motion_enabled:return
        self.motion_enabled=enabled
        if not enabled:
            self.animation.stop();self.quota_tween.stop()
            self.quota_previous=None;self.quota_progress=1.
            for motion in self.ring_tweens.values():motion.stop()
            if self.popup and self.popup.reveal_target is not None:self.popup.reveal_to(self.popup.reveal_target,force=True)
            if self.settings_dialog:
                for control in self.settings_dialog.findChildren(Toggle):control.motion.snap(float(control.isChecked()))
                self.settings_dialog.stop_motion()
        self.task_strip.sync_motion();self.update()

    def desktop_click(self,x,y,button="left"):
        if self.confirming_reset:return False
        if not self.floating and button in ('left_up','right_up') and windows.taskbar_at_point(x,y):self.schedule_stack_repair()
        if self.floating:
            # Qt supplies normal press/move/release capture. Global interception
            # would also steal clicks from other windows covering a floating strip.
            if button in ('left_up','right_up'):return False
            if self.popup:
                boxes=[windows.rect(int(widget.winId())) for widget in (self,self.popup) if widget.isVisible()]
                if not any(box and box[0]<=x<box[2] and box[1]<=y<box[3] for box in boxes):QTimer.singleShot(0,self.hide_popup)
            return False
        if button=='left_up':
            pressed=self.release_press()
            if not pressed:return False
            mode,rect,payload=pressed
            if self.isVisible() and rect.contains(QPointF(x,y)) and windows.pointer_over(int(self.winId()),x,y):
                QTimer.singleShot(0,lambda m=mode:self.toggle_popup(m))
            return True
        if button=='right_up':
            pressed=self.right_pressed;self.right_pressed=None
            if pressed and self.isVisible() and pressed.contains(QPointF(x,y)) and windows.pointer_over(int(self.winId()),x,y):QTimer.singleShot(0,self.open_menu)
            return bool(pressed)
        def inside(widget):
            if not widget or not widget.isVisible():return False
            box=windows.rect(int(widget.winId()))
            return box is not None and box[0]<=x<box[2] and box[1]<=y<box[3]
        if inside(self) and windows.pointer_over(int(self.winId()),x,y):
            box=windows.rect(int(self.winId()));ratio=windows.user32.GetDpiForWindow(int(self.winId()))/96
            point=QPointF((x-box[0])/ratio,(y-box[1])/ratio)
            hit=next((h for h in self.hit_regions if h[1].contains(point)),None)
            if button=='right':self.right_pressed=QRectF(box[0],box[1],box[2]-box[0],box[3]-box[1]);return True
            if hit:
                mode,rect,payload=hit
                self.settle_quota(mode)
                self.begin_press(hit,QRectF(box[0]+rect.x()*ratio,box[1]+rect.y()*ratio,rect.width()*ratio,rect.height()*ratio))
                return True  # Transparent pixels must not forward a second action to the taskbar.
        if self.popup and not inside(self.popup):QTimer.singleShot(0,self.hide_popup)
        return False

    def begin_press(self,hit,rect=None):
        self.pressed=(hit[0],rect or hit[1],hit[2]);self.pressed_local=QRectF(hit[1]);self.press_inside=True
        self.update()

    def release_press(self):
        pressed=self.pressed;self.pressed=None;self.pressed_local=None;self.press_inside=False
        self.update();return pressed

    def toggle_popup(self,mode='usage',activate=True):
        self.settle_quota(mode)
        if self.popup and self.popup.mode==mode:
            closing=self.popup.reveal_target==1.
            self.hover_suppressed=mode if closing else None
            self.popup.reveal_to(0. if closing else 1.)
        else:
            self.hide_popup(immediate=True)
            if mode=='usage':self.popup=TaskPopup(self)
            elif mode=='session':self.popup=SessionPopup(self)
            elif mode=='resets':self.popup=ResetPopup(self)
            else:self.popup=TaskListPopup(self,mode)
            self.popup.refresh(self.data)
            windows.popup_glass(int(self.popup.winId()))
            self.popup.show()
        if activate and self.popup and self.popup.reveal_target==1.:
            self.popup.activateWindow();self.popup.setFocus(Qt.FocusReason.MouseFocusReason)
        self.update()

    def update_hover_popup(self,point,now=None):
        if (not self.settings.get('hover_panels') or not self.isVisible() or self.pressed or self.drag_origin or self.confirming_reset
                or self.menu.isVisible() or self.settings_dialog and self.settings_dialog.isVisible()):
            self.hover_target=None;self.hover_leave_since=None;return
        now=time.monotonic() if now is None else now
        local=self.mapFromGlobal(point)
        mode=next((m for m,r,t in self.hit_regions if r.contains(local)),None)
        if self.floating and QApplication.widgetAt(point) is not self:mode=None
        inside=bool(self.popup and self.popup.isVisible() and self.popup.geometry().contains(point))
        if inside:
            self.hover_target=None;self.hover_leave_since=None
            if self.hover_suppressed!=self.popup.mode:self.popup.reveal_to(1.)
            return
        if mode!=self.hover_suppressed:self.hover_suppressed=None
        if mode:
            self.hover_leave_since=None
            if mode!=self.hover_target:self.hover_target=mode;self.hover_since=now
            if mode==self.hover_suppressed:return
            if self.popup and self.popup.mode==mode:
                self.popup.reveal_to(1.);return
            if now-self.hover_since>=.35:self.toggle_popup(mode,activate=False)
        else:
            self.hover_target=None
            if self.popup:
                if self.hover_leave_since is None:self.hover_leave_since=now
                elif now-self.hover_leave_since>=.45:self.hide_popup()

    @property
    def language(self):
        return self.settings.get('language','en')

    def label(self,key,**values):
        return translate(self.language,key,**values)

    def set_language(self,value):
        if value not in LANGUAGES:return
        self.settings['language']=value;self.save_settings()
        if self.quota_previous:
            self.quota_previous=next((m for m in self.quota_choices() if m[0]==self.quota_previous[0]),None)
        self.settings_action.setText(self.label('Settings…'));self.quit_action.setText(self.label('Quit'))
        self.find_action.setText(self.label('Find task…'))
        self.refresh_status_menu()
        if self.task_finder:self.task_finder.refresh(self.data)
        if self.settings_dialog:self.settings_dialog.refresh()
        if self.popup:
            self.popup.setWindowTitle('Codex · '+self.label('Tasks' if isinstance(self.popup,TaskListPopup) else 'Usage'))
            self.popup.refresh(self.data)
        self.tick(resize=True)

    def set_hover_panels(self,value):
        self.settings['hover_panels']=bool(value)
        self.hover_target=None;self.hover_leave_since=None;self.hover_suppressed=None
        self.save_settings()

    def set_notify_input(self,value):
        self.attention_notices.update(self.data.get('tasks',[]),False,time.monotonic())
        self.settings['notify_input']=bool(value);self.save_settings()

    def check_attention(self):
        ids=self.attention_notices.update(self.data.get('tasks',[]),self.settings.get('notify_input',False),time.monotonic(),ready=not self.data.get('loading'))
        if ids:
            self.notification_kind='input';self.notification_tasks=ids
            self.tray.showMessage(self.label('Needs input'),self.label('A task needs input.' if len(ids)==1 else '{count} tasks need input.',count=len(ids)))

    def notification_clicked(self):
        if self.notification_kind=='input':
            tasks=[task for task in self.provider.get().get('tasks',[]) if task.get('needs_input') and task['id'] in self.notification_tasks]
            if len(tasks)==1:self.open_task(tasks[0])
            elif tasks and self.isVisible():self.toggle_popup('waiting')
            else:self.open_finder()
        elif self.notification_kind=='navigation':self.open_finder()
        else:
            self.open_settings()
            if self.settings_dialog:self.settings_dialog.navigation.setCurrentRow(2)

    @property
    def floating(self):
        return self.settings.get('placement')=='floating' or self.settings.get('placement')=='auto' and self.auto_placement.floating

    def set_placement(self,value):
        if value not in ('auto','taskbar','floating') or self.settings.get('placement')==value:return
        self.hide_popup(immediate=True);self.release_press();self.drag_origin=None;self.dragging=False
        self.settings['placement']=value;self.position=None;self.host_key=None
        self.auto_placement=AutoPlacement()
        self.save_settings();self.tick(resize=True)
        if self.settings_dialog:self.settings_dialog.refresh()

    def set_floating_topmost(self,value):
        self.settings['floating_topmost']=bool(value);self.host_key=None;self.save_settings();self.tick()

    def floating_screen(self):
        position=self.settings.get('floating_position') or {}
        selected=self.settings.get('floating_display',position.get('screen'))
        return next((screen for screen in QApplication.screens() if screen.name()==selected),QApplication.primaryScreen())

    def set_floating_display(self,name):
        screens=QApplication.screens();target=QApplication.primaryScreen() if name is None else next((screen for screen in screens if screen.name()==name),None)
        if target is None:return
        position=self.settings.get('floating_position')
        if name==self.settings.get('floating_display',(position or {}).get('screen')):return
        self.hide_popup(immediate=True);self.release_press();self.drag_origin=None;self.dragging=False
        if position:position={**position,'screen':target.name()}
        else:position=remember_position(floating_rect(target.availableGeometry()),target.availableGeometry(),target.name())
        self.settings.update(floating_display=name,floating_position=position);self.position=None
        self.save_settings();self.tick(resize=True)
        if self.settings_dialog:self.settings_dialog.refresh_displays()

    def set_capsule_theme(self,value):
        if value not in CAPSULE_COLORS:return
        self.settings['capsule_theme']=value;self.save_settings();self.update()

    def set_capsule_transparency(self,value,save=True):
        self.settings['capsule_transparency']=max(0,min(100,int(value)))
        if save:self.save_settings()
        self.update()

    def set_quota_rotation(self,value):
        self.settings['rotate_quotas']=bool(value)
        self.quota_kind=None;self.quota_paused_at=None;self.quota_rotated_at=time.monotonic()
        self.quota_tween.stop();self.quota_progress=1.;self.quota_previous=None
        self.save_settings();self.hide_popup(immediate=True);self.tick(resize=True)

    def quota_choices(self):
        metrics={kind:(value,fraction) for kind,value,fraction in visible_metrics(self.data,self.settings)}
        result=[]
        for kind in ('quota','spent','session','clock'):
            if kind in metrics:
                value,fraction=metrics[kind]
                label=self.label('Reset {time}',time=value) if kind=='clock' else self.metric_label(kind)+' '+value.removeprefix('7d ').removeprefix('5h ')
                result.append((kind,label,fraction))
        return result

    def metric_label(self,kind):
        return self.label('Reset {time}',time='').strip() if kind=='clock' else self.label({'quota':'Week left','spent':'Today used','session':'5h left'}[kind])

    def metric_parts(self,kind,value):
        label=self.metric_label(kind)
        return label,value.removeprefix(label+' ')

    def count_label(self,kind,count):
        return self.label('Needs input')+' '+str(count) if kind=='waiting' else str(count)

    def cached_width(self):
        return QFontMetricsF(face(7)).horizontalAdvance(self.label('Cached'))+12 if self.displayed_metrics() and quota_is_cached(self.data) else 0

    def displayed_metrics(self):
        metrics=visible_metrics(self.data,self.settings)
        choices=self.quota_choices()
        labels={kind:value for kind,value,fraction in choices}
        metrics=[(kind,labels[kind],fraction) for kind,value,fraction in metrics]
        if not self.settings.get('rotate_quotas'):return metrics
        current=next((m for m in choices if m[0]==self.quota_kind),choices[0] if choices else None)
        return [current] if current else []

    def metric_text_width(self,kind,value):
        metrics=QFontMetricsF(face(8))
        if not self.settings.get('rotate_quotas'):return metrics.horizontalAdvance(value)
        widths=[]
        for item,labelled,fraction in self.quota_choices():
            label,number=self.metric_parts(item,labelled)
            if item=='clock':
                template='6d 23h' if 'd' in number or number=='—' else '23h 59m' if 'h' in number else '59m'
                number_width=metrics.horizontalAdvance(template)
            else:number_width=max(metrics.horizontalAdvance('100%'),metrics.horizontalAdvance(number))
            widths.append(metrics.horizontalAdvance(label)+3+number_width)
        return max(widths,default=0)

    def content_width(self,limit):
        metrics=self.displayed_metrics();rotating=self.settings.get('rotate_quotas')
        x=CONTENT_X+sum((25 if rotating else 29)+self.metric_text_width(kind,value) for kind,value,_ in metrics)
        right=x-(13 if rotating else 17) if metrics else CONTENT_X
        cached=self.cached_width()
        if cached:x+=cached;right+=cached
        if not self.settings['show_tasks']:return min(limit,math.ceil(right+12))
        counts=category_counts(self.data)
        statuses=[kind for kind in STATUS_CATEGORIES if counts[kind]]
        if not statuses:return min(limit,math.ceil(right+12))
        if metrics:x+=7
        font_metrics=QFontMetricsF(face(8));badge_x=x-6
        for kind in statuses:badge_x+=font_metrics.horizontalAdvance(self.count_label(kind,counts[kind]))+30
        if statuses:right=badge_x-6
        titles=[task_title(task,self.language) for kind in self.settings.get('pinned_statuses',[]) if kind in counts for task in panel_rows(self.data,kind)]
        minimum=min(240,70+max(QFontMetricsF(self.font).horizontalAdvance(title) for title in titles)) if titles else 0
        return min(limit,math.ceil(max(minimum,right+12)))

    def fitted_width(self,limit,resize=False):
        target=self.content_width(limit)
        interacting=self.underMouse() or self.pressed or self.drag_origin or self.popup or self.menu.isVisible()
        if not resize and interacting and self.position:target=max(target,self.width())
        return min(limit,target)

    def set_quota_progress(self,value):
        self.quota_progress=float(value);self.update()

    def animate_quota_to(self,target):
        if not self.motion_enabled:
            self.quota_target=target;self.set_quota_progress(target);self.finish_quota_transition();return
        self.quota_tween.stop();self.quota_target=target
        self.quota_tween.blockSignals(True)
        self.quota_tween.setDuration(max(80,round(460*abs(target-self.quota_progress))))
        self.quota_tween.setStartValue(self.quota_progress);self.quota_tween.setEndValue(target)
        self.quota_tween.blockSignals(False);self.quota_tween.start()

    def finish_quota_transition(self):
        if self.quota_target==0. and self.quota_previous:self.quota_kind=self.quota_previous[0]
        self.quota_previous=None;self.quota_progress=1.;self.update()

    def settle_quota(self,mode):
        if not self.quota_previous or mode not in ('usage','daily','session','resets'):return
        kind={'usage':'quota','daily':'spent','session':'session','resets':'clock'}[mode]
        target=0. if kind==self.quota_previous[0] else 1.
        if target!=self.quota_target:self.animate_quota_to(target)

    def advance_quota(self,now=None):
        if not self.settings.get('rotate_quotas'):return
        now=time.monotonic() if now is None else now
        kinds=[kind for kind,value,fraction in self.quota_choices()]
        if self.quota_kind not in kinds:
            self.quota_kind=kinds[0] if kinds else None
            self.quota_rotated_at=now;self.quota_paused_at=None
            self.quota_tween.stop();self.quota_progress=1.;self.quota_previous=None
        if len(kinds)<2:
            self.quota_rotated_at=now;self.quota_paused_at=None;return
        paused=(self.quota_hover or self.pressed or self.drag_origin or self.confirming_reset or not self.isVisible()
                or self.popup and self.popup.mode in ('usage','daily','session','resets') or self.menu.isVisible()
                or self.settings_dialog and self.settings_dialog.isVisible())
        if paused:
            if self.quota_paused_at is None:self.quota_paused_at=now
            return
        if self.quota_paused_at is not None:
            self.quota_rotated_at+=now-self.quota_paused_at;self.quota_paused_at=None
        if now-self.quota_rotated_at>=ROTATE_SECONDS:
            self.quota_previous=next(m for m in self.quota_choices() if m[0]==self.quota_kind)
            self.quota_kind=kinds[(kinds.index(self.quota_kind)+1)%len(kinds)];self.quota_rotated_at=now
            self.quota_progress=0.;self.animate_quota_to(1.)

    def animate(self):
        self.task_strip.animate()
        if not self.task_strip.needs_animation:self.animation.stop()

    def set_chart_unit(self,unit):
        if unit not in ('M','100M') or unit==self.chart_unit:return
        self.chart_unit=unit
        self.save_settings()
        if self.popup:self.popup.refresh(self.data)
        if self.task_finder:self.task_finder.refresh(self.data)

    def save_settings(self):
        self.settings['chart_unit']=self.chart_unit
        error='Could not save settings. Changes apply until restart.'
        try:
            write_settings(RUNTIME/'ui_settings.json',self.settings)
            self.settings_errors.discard(error)
        except OSError as exc:self.settings_errors.add(error);print('Settings:',exc)
        if self.settings_dialog:self.settings_dialog.refresh_status()

    def set_display(self,key,value):
        if key not in DISPLAY_DEFAULTS:return
        self.quota_tween.stop();self.quota_previous=None;self.quota_progress=1.
        self.settings[key]=bool(value);self.save_settings();self.hide_popup(immediate=True);self.tick(resize=True)
        if key=='show_tasks' and self.settings_dialog:self.settings_dialog.refresh()

    def refresh_status_menu(self):
        self.status_menu.setTitle(self.label('Task status'));self.status_menu.clear()
        counts=category_counts(self.provider.get())
        for category in CATEGORY_LABELS:
            if counts[category] or category in self.settings.get('pinned_statuses',[]):
                action=self.status_menu.addAction(self.label(CATEGORY_LABELS[category])+' · '+str(counts[category]))
                action.setData(category)
                action.triggered.connect(lambda checked=False,mode=category:QTimer.singleShot(0,lambda:self.toggle_popup(mode)))
        if not self.status_menu.actions():self.status_menu.addAction(self.label('No tasks')).setEnabled(False)

    def set_status_pinned(self,category,pinned):
        if category not in STATUS_CATEGORIES:return
        selected=set(self.settings.get('pinned_statuses',[]))
        if pinned:selected.add(category);self.settings['show_tasks']=True
        else:selected.discard(category)
        self.settings['pinned_statuses']=[kind for kind in STATUS_CATEGORIES if kind in selected]
        self.save_settings();self.hide_popup(immediate=True);self.tick(resize=True)
        if self.settings_dialog:self.settings_dialog.refresh()

    def refresh_accessibility(self):
        values=[value for kind,value,fraction in self.displayed_metrics()]
        if values and quota_is_cached(self.data):values.append(self.label('Cached'))
        if self.settings['show_tasks']:
            counts=category_counts(self.data)
            values.extend(self.label(CATEGORY_LABELS[kind])+' '+str(counts[kind]) for kind in STATUS_CATEGORIES if counts[kind])
        self.setAccessibleName(self.label('Status bar')+(' · '+' · '.join(values) if values else ''))
        self.setAccessibleDescription(self.label('Account quota and task status. Use the tray menu to open task categories.')+' '+quota_update_label(self,self.data))

    def open_settings(self):
        self.hide_popup(immediate=True)
        if self.settings_dialog is None:self.settings_dialog=SettingsDialog(self)
        self.settings_dialog.refresh();self.settings_dialog.show()
        # SW_HIDE startup flags can suppress the first normal window of a background launch.
        windows.user32.ShowWindow(int(self.settings_dialog.winId()),1)
        self.settings_dialog.raise_();self.settings_dialog.activateWindow()

    def open_finder(self):
        from .task_finder import TaskFinder
        self.hide_popup(immediate=True)
        if self.task_finder is None:self.task_finder=TaskFinder(self)
        self.task_finder.refresh(self.provider.get());self.task_finder.show()
        windows.user32.ShowWindow(int(self.task_finder.winId()),1)
        self.task_finder.raise_();self.task_finder.activateWindow();self.task_finder.search.setFocus()

    def open_menu(self):
        self.hide_popup(immediate=True);self.menu.ensurePolished()
        bounds=(self.floating_screen() if self.floating else self.screen()).availableGeometry();size=self.menu.sizeHint()
        anchor=self.geometry();occupied=self.task_strip.occupied_geometry()
        if occupied.isValid():anchor=anchor.united(occupied)
        x=max(bounds.left(),min(QCursor.pos().x(),bounds.right()-size.width()+1))
        bottom=min(anchor.top(),bounds.bottom()+1)-TaskPopup.GAP
        y=max(bounds.top(),bottom-size.height())
        if self.floating:
            box=panel_rect(anchor,bounds,size.width(),size.height(),TaskPopup.GAP);x,y=box.x(),box.y()
        self.menu.popup(QPointF(x,y).toPoint())

    def set_startup(self,value):
        error='Could not change startup. The previous setting is retained.'
        try:
            startup.set_enabled(value)
            self.settings_errors.discard(error)
        except OSError as exc:self.settings_errors.add(error);print('Startup:',exc)
        if self.settings_dialog:self.settings_dialog.refresh()

    def update_status(self):
        if self.settings_dialog:self.settings_dialog.refresh()
        if self.updater.release and self.settings.get('notified_version')!=self.updater.release['version']:
            self.settings['notified_version']=self.updater.release['version'];self.save_settings()
            self.notification_kind='settings'
            self.tray.showMessage(APP_NAME,self.label('Version {version} is available. Update from Settings.',version=self.updater.release['version']))

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
            os.startfile(thread_url(task.get('navigation_id') or task['id']))
        except (OSError,ValueError) as exc:
            print(f'Task navigation: {exc}',file=sys.stderr)
            self.notification_kind='navigation';self.tray.showMessage(APP_NAME,self.label('Could not open Codex. Open Codex and try again.'))
            return False
        self.hide_popup(immediate=True)
        return True

    def confirm_reset(self):
        data=self.provider.get();credit=data.get('reset_selected');account=data.get('reset_account')
        if self.confirming_reset or data.get('reset_busy') or not credit or not account:return
        if not data.get('reset_retry') and credit.get('expiresAt') is not None and credit['expiresAt']<=time.time():return
        self.confirming_reset=True;self.hide_popup(immediate=True)
        try:
            message=self.label('Continue the reset request with an unconfirmed result?' if data.get('reset_retry') else 'Use one quota reset credit?')
            expiry=datetime.fromtimestamp(credit['expiresAt']).strftime('%m.%d %H:%M') if credit.get('expiresAt') is not None else self.label('Not provided')
            dialog=QMessageBox(self);dialog.setWindowTitle(self.label('Reset quota'));dialog.setFont(self.font)
            dialog.setText(message);dialog.setInformativeText(self.label('Credit expires: {time}',time=expiry))
            cancel=dialog.addButton(self.label('Cancel'),QMessageBox.ButtonRole.RejectRole)
            confirm=dialog.addButton(self.label('Confirm reset'),QMessageBox.ButtonRole.AcceptRole)
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
        if not self.motion_enabled:self.ring_values[kind]=target;return
        if kind not in self.ring_values:
            self.ring_values[kind]=target;return
        motion=self.ring_tweens.get(kind)
        if not motion and self.ring_values[kind]==target:return
        if motion and motion.endValue()==target:return
        if not motion:
            motion=QVariantAnimation(self);motion.setDuration(300)
            motion.setEasingCurve(QEasingCurve.Type.OutCubic)
            motion.valueChanged.connect(lambda value,k=kind:self.set_ring(k,value))
            self.ring_tweens[kind]=motion
        motion.stop();motion.setStartValue(self.ring_values[kind]);motion.setEndValue(target);motion.start()

    def track_pointer(self,point):
        inside=bool(self.pressed_local and self.pressed_local.contains(point))
        if inside!=self.press_inside:self.press_inside=inside;self.update()
        self.quota_hover=any(m in ('usage','daily','session','resets') and r.contains(point) for m,r,t in self.hit_regions)
        self.setCursor(Qt.CursorShape.PointingHandCursor if any(r.contains(point) for m,r,t in self.hit_regions) else Qt.CursorShape.ArrowCursor)
        hit=next((item for item in self.hit_regions if item[1].contains(point)),None)
        tip=''
        if hit:
            mode,_,_=hit
            tip=self.label({'usage':'Weekly quota remaining','daily':"Today's quota consumption",'session':'5-hour quota remaining','resets':'Next quota reset'}.get(mode,CATEGORY_LABELS.get(mode,mode)))
            if mode in ('usage','daily','session','resets'):
                tip=self.label('Account quota')+' · '+tip+'\n'+quota_update_label(self,self.data)
                if mode=='daily':tip+='\n'+quota_context_lines(self,self.data,'daily')[1].split(' · ',1)[1]
                if quota_is_cached(self.data):tip+='\n'+self.label('Showing the last available quota.')
            else:tip+=' · '+str(category_counts(self.data).get(mode,0))
        if self.toolTip()!=tip:self.setToolTip(tip)

    def mousePressEvent(self,event):
        if not self.floating:return super().mousePressEvent(event)
        if event.button()==Qt.MouseButton.RightButton:
            self.right_pressed=QRectF(self.rect());event.accept();return
        if event.button()!=Qt.MouseButton.LeftButton:return
        shape=QPainterPath();shape.addRoundedRect(QRectF(1,1,self.width()-2,self.height()-2),(self.height()-2)/2,(self.height()-2)/2)
        if not shape.contains(event.position()):return
        hit=next((h for h in self.hit_regions if h[1].contains(event.position())),None)
        if hit:self.settle_quota(hit[0])
        if hit:self.begin_press(hit)
        self.drag_origin=(event.globalPosition(),self.pos());self.dragging=False
        event.accept()

    def mouseReleaseEvent(self,event):
        if self.floating and event.button()==Qt.MouseButton.RightButton:
            pressed=self.right_pressed;self.right_pressed=None
            if pressed and pressed.contains(event.position()):self.open_menu()
            event.accept();return
        if not self.floating or event.button()!=Qt.MouseButton.LeftButton or self.drag_origin is None:return
        hit=self.release_press();dragged=self.dragging
        self.drag_origin=None;self.dragging=False
        if dragged:
            screen=QApplication.screenAt(self.geometry().center()) or self.screen()
            self.settings['floating_position']=remember_position(self.geometry(),screen.availableGeometry(),screen.name())
            if self.settings.get('floating_display') is not None or screen is not QApplication.primaryScreen():self.settings['floating_display']=screen.name()
            self.save_settings()
        elif hit and hit[1].contains(event.position()):
            self.toggle_popup(hit[0])
        elif not hit:self.hide_popup()
        self.track_pointer(event.position());event.accept()

    def mouseMoveEvent(self,event):
        if self.floating and self.drag_origin is not None:
            start,position=self.drag_origin;delta=event.globalPosition()-start
            if self.dragging or delta.manhattanLength()>=QApplication.startDragDistance():
                if not self.dragging:self.hide_popup(immediate=True)
                self.dragging=True;self.release_press();self.setCursor(Qt.CursorShape.ClosedHandCursor)
                screen=QApplication.screenAt(event.globalPosition().toPoint()) or self.screen()
                target=self.geometry();target.moveTopLeft(position+delta.toPoint())
                target=clamp_rect(target,screen.availableGeometry());self.setGeometry(target)
                self.position=target.getRect();self.task_strip.layout_rows(self.task_strip.size_motion.value);event.accept();return
        self.track_pointer(event.position())
        self.update_hover_popup(self.mapToGlobal(event.position().toPoint()))

    def leaveEvent(self,event):
        self.track_pointer(QPointF(-1,-1))
        self.hover_target=None;self.hover_suppressed=None

    def ensure_visible(self,now=None):
        hwnd=int(self.winId());window=self.windowHandle()
        native_visible=bool(windows.user32.IsWindowVisible(hwnd))
        minimized=bool(windows.user32.IsIconic(hwnd))
        exposed=bool(window and window.isExposed())
        if self.isVisible() and native_visible and not minimized and exposed:
            self.surface_loss_since=None;self.surface_repaired=False;return False
        if self.menu.isVisible() or self.confirming_reset:return False
        if not self.isVisible():
            self.surface_loss_since=None;self.surface_repaired=False
            self.show();windows.hide_border(hwnd);return True
        now=time.monotonic() if now is None else now
        if self.surface_loss_since is None:self.surface_loss_since=now
        if self.surface_repaired or now-self.surface_loss_since<.3:return False
        self.surface_repaired=True
        print(f'{datetime.now().astimezone().isoformat()} Window recovery: native_visible={native_visible}, minimized={minimized}, exposed={exposed}',flush=True)
        self.hide()
        if minimized:self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized)
        self.show();windows.hide_border(int(self.winId()));self.update()
        return True

    def tick(self,resize=False):
        fullscreen=windows.foreground_fullscreen()
        self.tick_status(resize,fullscreen)
        self.task_strip.refresh(self.data,resize=resize,hidden=fullscreen)
        if self.popup:
            panel_key=(self.popup,id(self.data),int(time.time()),self.position,self.task_strip.occupied_geometry().getRect())
            if panel_key!=self.panel_key:self.panel_key=panel_key;self.popup.refresh(self.data)
        if self.motion_enabled and self.task_strip.needs_animation:
            if not self.animation.isActive():self.animation.start(33)
        else:self.animation.stop()

    def hide_status(self,fullscreen=False):
        self.hide()
        if fullscreen or not isinstance(self.popup,TaskListPopup) or self.popup.mode=='daily':self.hide_popup(immediate=True)

    def tick_status(self,resize,fullscreen):
        self.data=self.provider.get()
        self.refresh_accessibility()
        self.check_attention()
        if self.settings_dialog and self.settings_dialog.isVisible():self.settings_dialog.refresh_status()
        if self.task_finder and self.task_finder.isVisible():self.task_finder.refresh(self.data)
        if not any(self.settings[key] for key in DISPLAY_DEFAULTS):
            self.hide_status(fullscreen);return
        metrics=self.displayed_metrics()
        if self.quota_previous:
            self.quota_previous=next((choice for choice in self.quota_choices() if choice[0]==self.quota_previous[0]),None)
        if not metrics and not self.settings['show_tasks']:
            self.hide_status(fullscreen);return
        minimum=self.content_width(math.inf)
        placed=windows.placement(minimum_width=minimum) if self.settings.get('placement')!='floating' else None
        if self.settings.get('placement')=='auto':
            before=self.floating
            locked=bool(self.pressed or self.drag_origin or self.popup or self.menu.isVisible() or self.confirming_reset)
            self.auto_placement.resolve(placed is not None,time.monotonic(),immediate=resize,locked=locked)
            if before!=self.floating:self.hide_popup(immediate=True);self.position=None;self.host_key=None
        if self.floating:
            screen=self.floating_screen()
            room=screen.availableGeometry().width()-32 if screen else 0
            box=(self.geometry() if self.drag_origin is not None else floating_rect(screen.availableGeometry(),self.settings.get('floating_position'),minimum)) if minimum<=room else None
            hidden=self.settings.get('placement')=='auto' and (bool(placed and placed[-1]) or fullscreen)
            placed=(*box.getRect(),1,hidden) if box else None
        self.placement_unavailable=placed is None
        if not placed:self.hide_status(fullscreen);return
        hwnd=int(self.winId())
        if not windows.user32.IsWindow(hwnd):
            # Explorer destroys owned native windows when rebuilding the taskbar.
            self.hide_popup(immediate=True);self.hide();self.destroy();self.create()
            self.position=None
            hwnd=int(self.winId())
        if hwnd!=self.native_handle:
            self.native_handle=hwnd;self.position=None
            self.surface_loss_since=None;self.surface_repaired=False
        x,y,w,h,scale,hidden=placed
        if hidden or fullscreen:
            self.hide();self.hide_popup(immediate=True);return
        logical=tuple(round(v/scale) for v in (x,y,w,h))
        if self.drag_origin is None:self.content_limit=self.floating_screen().availableGeometry().width()-32 if self.floating else logical[2]
        width=self.fitted_width(self.content_limit,resize=resize)
        if self.floating and self.drag_origin is None:
            logical=floating_rect(self.floating_screen().availableGeometry(),self.settings.get('floating_position'),width).getRect()
        else:logical=(logical[0],logical[1],width,logical[3])
        if self.position!=logical:self.setGeometry(*logical);self.position=logical
        recovered=self.ensure_visible()
        if self.floating:
            host_key=(int(self.winId()),self.settings.get('floating_topmost',True))
            if recovered or host_key!=self.host_key:
                windows.floating_window(*host_key);self.host_key=host_key
        else:windows.follow_taskbar(int(self.winId()))
        if not self.dragging:
            point=self.mapFromGlobal(QCursor.pos()) if not self.floating or QApplication.widgetAt(QCursor.pos()) is self else QPointF(-1,-1)
            self.track_pointer(point)
        self.advance_quota()
        self.metrics=visible_metrics(self.data,self.settings)
        for kind,value,fraction in self.metrics:
            if fraction is not None:
                if kind=='clock':self.ring_values[kind]=fraction
                else:self.animate_ring(kind,fraction)
        # Keep visibility/interaction checks responsive without repainting unchanged pixels.
        frame_key=(tuple((kind,value,None if fraction is None else round(fraction,4)) for kind,value,fraction in self.displayed_metrics()),
                   tuple(category_counts(self.data).items()) if self.settings['show_tasks'] else (),
                   self.position,tuple(self.settings.get(k) for k in DISPLAY_DEFAULTS),self.settings.get('rotate_quotas'),quota_is_cached(self.data))
        if frame_key!=self.frame_key:
            self.frame_key=frame_key;self.update()
        self.update_hover_popup(QCursor.pos())

    def paintEvent(self,event):
        p=painter(self);data=self.data
        theme=self.settings.get('capsule_theme','dark');palette=CAPSULE_COLORS[theme]
        self.hit_regions=[];self.feedback_regions={}
        def emphasis(mode):
            if self.pressed and self.pressed[0]==mode and self.press_inside:return 2
            return int(bool(self.popup and self.popup.mode==mode and self.popup.reveal_target==1.))
        def finish():
            # Windows passes mouse messages through alpha-zero pixels in layered windows.
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationOver)
            for mode,region in self.feedback_regions.items():
                state=emphasis(mode)
                if state:
                    color=QColor('#ffffff' if theme=='dark' else '#22354b');color.setAlpha(25 if state==2 else 14)
                    p.setPen(Qt.PenStyle.NoPen);p.setBrush(color);p.drawRoundedRect(region,7,7)
            if self.hit_regions:
                background=QColor(palette['background']);background.setAlpha(round(255*(1-self.settings.get('capsule_transparency',0)/100)))
                p.setPen(Qt.PenStyle.NoPen);p.setBrush(background)
                box=QRectF(1,1,self.width()-2,self.height()-2)
                p.drawPath(connected_surface(box,getattr(self.task_strip,'joined_edge',None)))
            if self.floating:
                shape=connected_surface(QRectF(1,1,self.width()-2,self.height()-2),getattr(self.task_strip,'joined_edge',None))
                p.setClipPath(shape,Qt.ClipOperation.IntersectClip)
            for mode,rect,target in self.hit_regions:p.fillRect(rect.toAlignedRect(),QColor(0,0,0,1))
            if self.floating and self.hit_regions:
                p.setPen(Qt.PenStyle.NoPen);p.setBrush(QColor(0,0,0,1))
                p.drawRoundedRect(QRectF(1,1,self.width()-2,self.height()-2),(self.height()-2)/2,(self.height()-2)/2)
            p.end()
        x,y=CONTENT_X,self.height()/2
        def field(kind,value,fraction):
            nonlocal x
            colors=palette['rings']
            color=QColor(colors[kind]);width=self.metric_text_width(kind,value)
            def draw_value(draw_kind,value,line_y):
                if self.settings.get('rotate_quotas'):
                    label,number=self.metric_parts(draw_kind,value)
                    text(p,x+12,line_y,label,face(8),palette['muted'])
                    number_x=x+12+QFontMetricsF(face(8)).horizontalAdvance(label)+3
                    text(p,number_x,line_y,number,face(8),palette['text'])
                else:text(p,x+12,line_y,value,face(8),palette['muted'])
            current_fraction=None if fraction is None else self.ring_values.get(kind,fraction)
            previous=self.quota_previous if self.settings.get('rotate_quotas') else None
            hit_kind=kind
            if previous:
                old_kind,old_value,old_fraction=previous;progress=self.quota_progress
                old_color=QColor(colors[old_kind])
                color=QColor.fromRgbF(*[a+(b-a)*progress for a,b in zip(old_color.getRgbF()[:3],color.getRgbF()[:3])])
                if old_fraction is not None and current_fraction is not None:
                    current_fraction=old_fraction+(current_fraction-old_fraction)*progress
                elif progress<.5:current_fraction=old_fraction
                if progress<.5:hit_kind=old_kind
                p.save();p.setClipRect(QRectF(x+11,0,width+2,self.height()),Qt.ClipOperation.IntersectClip)
                p.setOpacity(1-progress);draw_value(old_kind,old_value,y-14*progress)
                p.setOpacity(progress);draw_value(kind,value,y+14*(1-progress))
                p.restore()
            else:draw_value(kind,value,y)
            icon(p,kind,x,y,color,fraction=current_fraction)
            shown_width=width
            if self.settings.get('rotate_quotas'):
                font=QFontMetricsF(face(8));label,number=self.metric_parts(kind,value)
                shown_width=font.horizontalAdvance(label)+3+font.horizontalAdvance(number)
                if previous and self.quota_progress<.5:
                    label,number=self.metric_parts(previous[0],previous[1]);shown_width=font.horizontalAdvance(label)+3+font.horizontalAdvance(number)
            feedback=QRectF(x-11,4,shown_width+28,self.height()-8)
            x+=12+width+(13 if self.settings.get('rotate_quotas') else 17)
            mode={'quota':'usage','session':'session','spent':'daily','clock':'resets'}[hit_kind]
            self.hit_regions.append((mode,QRectF(feedback.x(),0,feedback.width(),self.height()),None))
            self.feedback_regions[mode]=feedback
        def separator():
            nonlocal x
            if not self.settings.get('rotate_quotas'):
                pen(p,palette['divider'],.7)
                p.drawLine(QPointF(x-6,y-5),QPointF(x-6,y+5))
            x+=7
        for kind,value,fraction in self.displayed_metrics():field(kind,value,fraction)
        cached=self.cached_width()
        if cached:
            text(p,x-5,y,self.label('Cached'),face(7),palette['muted']);x+=cached
        if not self.settings['show_tasks']:finish();return
        counts=category_counts(data)
        if not any(counts[k] for k in STATUS_CATEGORIES):finish();return
        if x>CONTENT_X:separator()
        badge_x=x-6
        if self.settings.get('rotate_quotas'):
            visible=[mode for mode in STATUS_CATEGORIES if counts[mode]];font=QFontMetricsF(face(8))
            total=sum(font.horizontalAdvance(self.count_label(mode,counts[mode]))+24 for mode in visible)+6*(len(visible)-1)
            badge_x=self.width()-12-total
        for mode,color in [('waiting',palette['amber']),('running',palette['green']),('unread',palette['amber']),('failed',palette['failed']),('stopped',palette['stopped'])]:
            if counts[mode]:
                width=activity_count(p,badge_x,y,self.count_label(mode,counts[mode]),color,pulse=False,text_color=color if theme=='light' else None,emphasis=emphasis(mode))
                self.hit_regions.append((mode,QRectF(badge_x-2,0,width+4,self.height()),None));badge_x+=width+6
        finish()

    def hide_popup(self,immediate=False):
        if self.popup:
            if immediate:
                self.hover_target=None;self.hover_leave_since=None
                popup=self.popup;self.popup=None;popup.fade.stop();popup.close();popup.deleteLater()
            else:self.popup.reveal_to(0.)
            self.update()

    def closeEvent(self,event):
        self.quota_tween.stop()
        self.task_strip.shutdown();self.task_strip.deleteLater()
        self.click_hook.close();self.timer.stop();self.animation.stop();self.update_timer.stop()
        self.tray.hide();self.hide_popup(immediate=True)
        if self.settings_dialog:self.settings_dialog.close()
        if self.task_finder:self.task_finder.close()
        self.provider.stop();event.accept();QApplication.instance().quit()


class TaskPopup(QWidget):
    mode='usage'
    GAP=8
    TITLE_HEIGHT=26
    UNIT_RECTS={'M':QRectF(277,9,28,24),'100M':QRectF(309,9,40,24)}
    def __init__(self,owner):
        super().__init__(None,FLAGS & ~Qt.WindowType.WindowDoesNotAcceptFocus)
        self.owner=owner;self.data={};self.rows=[];self.days=[];self.scroll=0;self.full_height=172
        self.setWindowTitle('Codex · '+owner.label('Usage'))
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setWindowOpacity(0.)
        self.reveal=0.;self.reveal_target=None
        self.fade=Spring(self,response=.18)
        self.fade.changed.connect(self.set_reveal);self.fade.finished.connect(self.finish_reveal)
        self.unit_buttons={};self.unit_group=QButtonGroup(self);self.unit_group.setExclusive(True)
        if self.mode in ('usage','daily'):
            for unit in ('M','100M'):
                button=QPushButton(unit,self);button.setFont(face(8));button.setCheckable(True);button.setAutoDefault(False);button.setCursor(Qt.CursorShape.PointingHandCursor)
                button.setAccessibleName(unit+' Tokens');button.setStyleSheet('QPushButton{background:transparent;color:#a0a7b4;border:1px solid transparent;border-radius:5px;} QPushButton:checked{color:#eef4fc;background:#46566f;} QPushButton:hover{color:#ffffff;} QPushButton:pressed{background:#365072;} QPushButton:focus{border-color:#82b6ff;}')
                button.clicked.connect(lambda checked=False,u=unit:self.owner.set_chart_unit(u));self.unit_group.addButton(button);self.unit_buttons[unit]=button

    def sync_units(self):
        for unit,button in self.unit_buttons.items():
            button.setVisible(self.mode in ('usage','daily'));button.setGeometry(self.unit_rects()[unit].toAlignedRect())
            button.blockSignals(True);button.setChecked(unit==self.owner.chart_unit);button.blockSignals(False)

    def keyPressEvent(self,event):
        if event.key()==Qt.Key.Key_Escape:self.owner.hide_popup();event.accept();return
        if event.key() in (Qt.Key.Key_Return,Qt.Key.Key_Enter) and self.focusWidget() in self.unit_buttons.values():
            self.focusWidget().click();event.accept();return
        super().keyPressEvent(event)

    def showEvent(self,event):
        super().showEvent(event)
        self.sync_owner()
        self.reveal_to(1.)

    def hideEvent(self,event):self.fade.stop();super().hideEvent(event)

    def set_reveal(self,value):
        self.reveal=max(0.,min(1.,float(value)));self.setWindowOpacity(self.reveal);self.update()

    def reveal_to(self,target,force=False):
        target=float(target)
        if target==self.reveal_target and not force:return
        self.reveal_target=target
        if getattr(self.owner,'motion_enabled',True):self.fade.retarget(target)
        else:self.fade.snap(target);self.finish_reveal()

    def finish_reveal(self):
        if self.reveal_target==0 and self.owner.popup is self:
            self.owner.popup=None;self.owner.update();self.close();self.deleteLater()

    def anchor_bottom(self):
        return self.anchor_rect().top()-self.GAP

    def anchor_rect(self):
        anchor=self.owner.geometry()
        group=getattr(self.owner,'task_strip',None)
        if group:
            occupied=group.occupied_geometry()
            if occupied.isValid():anchor=anchor.united(occupied)
        if getattr(self.owner,'floating',False):return anchor
        tray=windows.user32.FindWindowW('Shell_TrayWnd',None)
        bounds=windows.rect(tray) if tray else None
        if bounds:anchor.setTop(min(anchor.top(),round(bounds[1]/self.owner.devicePixelRatioF())))
        return anchor

    def sync_owner(self):
        group=getattr(self.owner,'task_strip',None)
        parent=group if group and group.isVisible() else self.owner
        parent_handle=int(parent.winId());hwnd=int(self.winId());window=self.windowHandle()
        if window and window.transientParent()!=parent.windowHandle():window.setTransientParent(parent.windowHandle())
        windows.follow_owner(hwnd,parent_handle,True)

    def owner_unplaced(self):
        return isinstance(self.owner,StatusBar) and self.owner.position is None

    def place_panel(self,width,height):
        self.requested_size=(width,height);self.reposition()

    def reposition(self):
        if not hasattr(self,'requested_size'):return
        width,height=self.requested_size
        if self.owner_unplaced():
            bounds=(self.owner.floating_screen() if self.owner.floating else self.owner.screen()).availableGeometry()
            anchor=QRect(bounds.left()+16,bounds.bottom()-29,min(420,bounds.width()-32),30)
            self.setGeometry(panel_rect(anchor,bounds,width,height,self.GAP))
        else:
            bounds=(self.owner.floating_screen() if getattr(self.owner,'floating',False) else self.owner.screen()).availableGeometry()
            self.setGeometry(panel_rect(self.anchor_rect(),bounds,width,height,self.GAP))
        if self.isVisible():self.sync_owner()

    def refresh(self,data):
        self.data=data;now=datetime.now().astimezone()
        week=chart_window(data)
        self.window_known=bool(week and week.get('starts_at') and week.get('resets_at'))
        self.start=datetime.fromtimestamp(week["starts_at"]).astimezone() if week and week.get("starts_at") else now
        self.end=datetime.fromtimestamp(week["resets_at"]).astimezone() if week and week.get("resets_at") else self.start+timedelta(days=7)
        self.days=[];day=self.start.date()
        while day<=self.end.date():self.days.append(day);day+=timedelta(days=1)
        self.full_height=158+self.TITLE_HEIGHT
        shown=round(self.full_height) if self.owner.floating else min(round(self.full_height),max(180,self.owner.y()-16))
        self.place_panel(self.usage_width(),shown)
        self.setToolTip(self.usage_tooltip())
        self.scroll=min(self.scroll,max(0,self.full_height-self.height()));self.sync_units();self.update()

    def paintEvent(self,event):
        p=panel_painter(self)
        if not self.window_known:
            self.usage_header(p,'—',None);p.setFont(face(8));p.setPen(QColor(TITLE_MUTED))
            p.drawText(QRectF(18,72,self.width()-36,max(20,self.height()-90)),Qt.AlignmentFlag.AlignCenter,self.owner.label('Connecting to Codex…' if self.data.get('loading') else 'No records yet'));p.end();return
        history=self.data.get("history",{});today=datetime.now().astimezone().date()
        values,extremes=chart_values(self.days,history,today)
        self.usage_header(p,f"{self.start:%m.%d} — {self.end:%m.%d %H:%M}",chart_total(values))
        p.setClipRect(QRectF(0,32+self.TITLE_HEIGHT,self.width(),max(0,self.height()-32-self.TITLE_HEIGHT)))
        p.translate(0,-self.scroll)
        maximum=max([v for v in values if v is not None]+[1]);step=(self.width()-36)/len(self.days)
        for i,(day,value) in enumerate(zip(self.days,values)):
            x=18+(i+.5)*step;bottom=121.+self.TITLE_HEIGHT;height=(value or 0)/maximum*64
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
        return {unit:rect.translated(self.width()-360,0) for unit,rect in self.UNIT_RECTS.items()}

    def usage_width(self):
        if self.mode=='session':return 360
        title=self.owner.label('Today · Tokens' if self.mode=='daily' else 'Cycle · Tokens')
        return math.ceil(max(360,QFontMetricsF(face(9)).horizontalAdvance(title)+
                             QFontMetricsF(face(7)).horizontalAdvance(usage_update_label(self.owner,self.data))+134))

    def usage_tooltip(self):
        return '\n'.join((self.owner.label('Local today · Tokens' if self.mode=='daily' else 'Local cycle · Tokens'),
                          usage_update_label(self.owner,self.data,False),*quota_context_lines(self.owner,self.data,self.mode)))

    def usage_header(self,p,period,total):
        width=text(p,18,21,self.owner.label('Today · Tokens' if self.mode=='daily' else 'Cycle · Tokens'),face(9),'#d7dfe9')
        text(p,18+width+12,21,usage_update_label(self.owner,self.data),face(7),TITLE_MUTED)
        boxes=list(self.unit_rects().values());unit_box=boxes[0].united(boxes[1]).adjusted(-2,-2,2,2)
        p.setPen(Qt.PenStyle.NoPen);p.setBrush(QColor('#20242b'));p.drawRoundedRect(unit_box,7,7)
        y=21+self.TITLE_HEIGHT
        icon(p,'chart',23,y,LILAC)
        total_label='Σ '+chart_number(total,self.owner.chart_unit);metrics=QFontMetricsF(face(8))
        shown=metrics.elidedText(period,Qt.TextElideMode.ElideRight,max(0,self.width()-39-18-14-metrics.horizontalAdvance(total_label)))
        total_x=39+metrics.horizontalAdvance(shown)+14
        text(p,39,y,shown,face(8),BLUE)
        text(p,total_x,y,total_label,face(8),LILAC)

    def mouseMoveEvent(self,event):
        if self.mode!='usage':
            self.setCursor(Qt.CursorShape.ArrowCursor);return
        over=any(rect.contains(event.position()) for rect in self.unit_rects().values())
        self.setCursor(Qt.CursorShape.PointingHandCursor if over else Qt.CursorShape.ArrowCursor)

    def wheelEvent(self,event):
        self.scroll=max(0,min(max(0,self.full_height-self.height()),self.scroll-wheel_distance(event,26)));self.update()


class SessionPopup(TaskPopup):
    mode='session'

    def refresh(self,data):
        self.data=data;self.place_panel(self.usage_width(),210)
        self.setToolTip('\n'.join(quota_context_lines(self.owner,data,self.mode)))
        self.update()

    def paintEvent(self,event):
        p=panel_painter(self);window=quota_window(effective_quota_data(self.data),300)
        text(p,18,21,'5h',face(8),'#51adb4')
        value=self.owner.label('{value}% remaining',value=f"{window['remaining']:g}") if window else '—'
        text(p,49,21,value,face(8),MUTED)
        reset=datetime.fromtimestamp(window['resets_at']).strftime('%H:%M') if window and window.get('resets_at') else '—'
        label=self.owner.label('Reset {time}',time=reset)
        text(p,self.width()-18-QFontMetricsF(face(7)).horizontalAdvance(label),21,label,face(7),'#8797aa')
        context=self.owner.label('Account quota')+(' · '+self.owner.label('Cached') if quota_is_cached(self.data) else '')
        text(p,18,43,context,face(7),MUTED)
        text(p,18,61,quota_update_label(self.owner,self.data),face(7),TITLE_MUTED)
        left,top,width,height=32.,87.,self.width()-54.,87.
        for fraction,label in ((1,'100'),(0,'0')):
            y=top+(1-fraction)*height;pen(p,'#46515d',.5)
            p.drawLine(QPointF(left,y),QPointF(left+width,y));text(p,9,y,label,face(6),'#8797aa')
        points=[]
        if window and window.get('starts_at') is not None and window.get('resets_at'):
            start,end=window['starts_at'],window['resets_at']
            rows=[s for s in self.data.get('session_history',[]) if s['reset']==end and start<=s['at']<=end]
            points=[QPointF(left+(s['at']-start)/(end-start)*width,top+(1-s['remaining']/100)*height) for s in rows] if end>start else []
            if points:
                path=QPainterPath(points[0])
                for point in points[1:]:path.lineTo(point)
                pen(p,'#51adb4',1.5);p.drawPath(path)
                p.setPen(Qt.PenStyle.NoPen);p.setBrush(QColor('#51adb4'));p.drawEllipse(points[-1],2.5,2.5)
            text(p,left,189,datetime.fromtimestamp(start).strftime('%H:%M'),face(7),'#8797aa')
            label=datetime.fromtimestamp(end).strftime('%H:%M')
            text(p,left+width-QFontMetricsF(face(7)).horizontalAdvance(label),189,label,face(7),'#8797aa')
        if not points:
            p.setFont(face(8));p.setPen(QColor(TITLE_MUTED));p.drawText(QRectF(left,top,width,height),Qt.AlignmentFlag.AlignCenter,self.owner.label('Connecting to Codex…' if self.data.get('loading') else 'No records yet'))
        p.end()


class ResetPopup(TaskPopup):
    mode='resets'
    WIDTH=300

    def __init__(self,owner):
        super().__init__(owner)
        self.button=QPushButton(owner.label('Reset quota'),self);self.button.setFont(face(8))
        self.button.setStyleSheet('QPushButton{color:#d2dce7;background:#354a5c;border:0;border-radius:6px;} QPushButton:hover{background:#405a71;} QPushButton:pressed{background:#293f52;} QPushButton:focus{border:1px solid #86b6e6;} QPushButton:disabled{color:#8795a5;background:#303740;}')
        self.button.clicked.connect(owner.confirm_reset)

    def refresh(self,data):
        self.data=data;self.rows=data.get('reset_events',[])
        self.owner.forecast.request();self.forecast=self.owner.forecast.get()
        self.forecast_height=24 if self.forecast else 0
        self.credits=data.get('reset_credits',[])
        self.history_height=26*max(1,len(self.rows) if self.owner.floating else min(6,len(self.rows)))
        self.credits_top=76+self.history_height+26
        height=self.credits_top+24+26*max(1,len(self.credits))+46+self.forecast_height
        self.full_height=height
        source_width=max([QFontMetricsF(face(7)).horizontalAdvance(self.history_label(row)) for row in self.rows]+[0])
        metrics=QFontMetricsF(face(8))
        date_width=max([metrics.horizontalAdvance(datetime.fromtimestamp(row['at']).strftime('%m.%d %H:%M')) for row in self.rows]+[0])
        number_width=max([metrics.horizontalAdvance(self.history_parts(row)[0]) for row in self.rows]+[0])
        unit_width=max([metrics.horizontalAdvance(self.history_parts(row)[1]) for row in self.rows]+[0])
        percent_width=max([QFontMetricsF(face(7)).horizontalAdvance(self.history_percent(row)) for row in self.rows]+[0])
        usage_width=number_width+4+unit_width+(12+percent_width if percent_width else 0)
        width=max(self.WIDTH,math.ceil(18+date_width+16+usage_width+24+source_width+18))
        self.place_panel(width,height)
        self.button.setGeometry(18,self.height()-48,self.width()-36,32)
        self.history_divider=self.width()-18-source_width-12
        self.token_right=self.history_divider-12
        self.token_left=self.token_right-usage_width
        self.number_right=self.token_left+number_width
        self.unit_left=self.number_right+4
        self.percent_left=self.unit_left+unit_width+12
        credit=data.get('reset_selected')
        eligible=bool(credit and data.get('reset_account'))
        if credit and not data.get('reset_retry') and credit.get('expiresAt') is not None:eligible=eligible and credit['expiresAt']>time.time()
        self.button.setEnabled(eligible and not data.get('reset_busy') and (not data.get('quota_error') or data.get('reset_retry',False)))
        label='Resetting…' if data.get('reset_busy') else 'Retry reset' if data.get('reset_retry') or data.get('reset_state')=='unavailable' else 'Nothing to reset' if data.get('reset_state')=='nothingToReset' else 'Reset quota'
        self.button.setText(self.owner.label(label))
        self.scroll=min(self.scroll,self.scroll_limit())
        self.setToolTip(self.owner.label('Local tokens; account quota percentages.')+'\n'+quota_update_label(self.owner,data)+'\n'+self.owner.label('Official resets are inferred from recovery outside scheduled or confirmed manual resets.')+'\n'+self.owner.label('Percentages are the last recorded quota usage before each reset; missing records show a dash.'))
        if self.forecast:
            confidence=self.owner.label({'low':'Low confidence','medium':'Medium confidence','high':'High confidence'}[self.forecast['confidence']])
            self.setToolTip(self.toolTip()+'\n'+self.owner.label('Community forecast for global resets, not your account schedule.')+' '+confidence+'\n'+FORECAST_SOURCE)
        self.update()

    def history_parts(self,row):
        tokens=row.get('tokens')
        if tokens is None:return '—',''
        return chart_number(tokens,'100M'),{'zh-CN':'亿','ja':'億'}.get(self.owner.language,'×100M')

    def history_usage(self,row):
        return self.owner.label('Tokens')+' '+' '.join(part for part in self.history_parts(row) if part)

    def history_label(self,row):
        label={'scheduled':'Scheduled','manual':'Manual','official':'Official'}.get(row['kind'],'')
        return self.owner.label(label) if label else ''

    def history_percent(self,row):
        before=row.get('before') or {};affected=row.get('windows') or ('10080','300')
        window=next((before[key] for key in ('10080','300') if key in affected and before.get(key)),{})
        remaining=window.get('remaining')
        if type(remaining) not in (int,float) or not math.isfinite(remaining) or not 0<=remaining<=100:return '—'
        return f'{100-remaining:g}%'

    def paintEvent(self,event):
        p=panel_painter(self);window=countdown_window(effective_quota_data(self.data),self.owner.settings)
        right=self.width()-18
        def right_label(value,y,color=MUTED,font=None):
            font=font or face(8)
            text(p,right-QFontMetricsF(font).horizontalAdvance(value),y,value,font,color)
        def divider(y):
            pen(p,'#3d4652',.6);p.drawLine(QPointF(18,y),QPointF(right,y))
        text(p,18,23,self.owner.label('Next reset'),face(8),'#94a2b3')
        value=datetime.fromtimestamp(window['resets_at']).strftime('%m.%d %H:%M') if window and window.get('resets_at') else '—'
        right_label(value,23,BLUE)
        if self.forecast:
            text(p,18,49,self.owner.label('Reset forecast'),face(8),'#94a2b3')
            hours=max(1,math.ceil((self.forecast['end']-time.time())/3600))
            right_label(self.owner.label('Within {hours}h · ~{value}%',hours=hours,value=f"{self.forecast['chance']:g}"),49,LILAC,face(7))
        p.translate(0,self.forecast_height);divider(44)
        if self.owner.floating:
            p.save();p.setClipRect(QRectF(0,48,self.width(),max(0,self.height()-104-self.forecast_height)));p.translate(0,-self.scroll)
        text(p,18,64,self.owner.label('Usage history'),face(8),'#94a2b3')
        p.save();p.setClipRect(QRectF(18,76,self.width()-36,self.history_height),Qt.ClipOperation.IntersectClip)
        if not self.rows:text(p,18,89,self.owner.label('No records yet'),face(8),'#94a2b3')
        for i,row in enumerate(self.rows):
            y=89+i*26-(0 if self.owner.floating else self.scroll)
            text(p,18,y,datetime.fromtimestamp(row['at']).strftime('%m.%d %H:%M'),face(8),MUTED)
            number,unit=self.history_parts(row)
            text(p,self.number_right-QFontMetricsF(face(8)).horizontalAdvance(number),y,number,face(8),MUTED)
            if unit:text(p,self.unit_left,y,unit,face(8),MUTED)
            percent=self.history_percent(row)
            if percent:text(p,self.percent_left,y,percent,face(7),TITLE_MUTED)
            label=self.history_label(row)
            if label:
                pen(p,'#53606d',.6);p.drawLine(QPointF(self.history_divider,y-5),QPointF(self.history_divider,y+5))
                right_label(label,y,LILAC if row['kind']=='official' else BLUE,face(7))
        p.restore()
        divider(self.credits_top-20)
        count=self.data.get('reset_available');credit=self.data.get('reset_selected')
        text(p,18,self.credits_top,self.owner.label('Reset credit expiry'),face(8),'#94a2b3')
        right_label(self.owner.label('{count} available',count=count) if count is not None else '—',self.credits_top,ACCENT)
        for i,item in enumerate(self.credits):
            selected=bool(credit and item['id']==credit['id'])
            expiry=datetime.fromtimestamp(item['expiresAt']).strftime('%m.%d %H:%M') if item.get('expiresAt') is not None else '—'
            y=self.credits_top+26+i*26
            text(p,18,y,expiry,face(8),MUTED)
            if selected:right_label(self.owner.label('Default'),y,BLUE,face(7))
        if not self.credits:text(p,18,self.credits_top+26,self.owner.label('No credits') if count==0 else '—',face(8),'#94a2b3')
        if self.owner.floating:p.restore()
        p.end()

    def scroll_limit(self):
        return max(0,self.full_height-self.height()) if self.owner.floating else max(0,len(self.rows)*26-self.history_height)

    def wheelEvent(self,event):
        self.scroll=max(0,min(self.scroll_limit(),self.scroll-wheel_distance(event,26)));self.update()


class TaskListPopup(TaskPopup):
    mode='daily'
    ROW_HEIGHT=34
    TITLE_X=88
    TITLE_WIDTH=150

    def __init__(self,owner,mode='daily'):
        super().__init__(owner)
        self.mode=mode
        self.setWindowTitle('Codex · '+owner.label('Tasks'))
        self.hovered=None;self.rows=[];self.hover_started=time.monotonic()
        self.keyboard_task=None;self.animation=QTimer(self);self.animation.timeout.connect(self.animate)
        self.pin_button=None
        if mode in STATUS_CATEGORIES:
            self.pin_button=PinButton(owner,self)
            self.pin_button.clicked.connect(lambda checked:owner.set_status_pinned(self.mode,checked))

    def showEvent(self,event):super().showEvent(event);self.sync_animation()
    def hideEvent(self,event):self.animation.stop();super().hideEvent(event)

    def sync_animation(self):
        hovered=next((t for t in self.rows if t['id']==self.hovered),None)
        extra=side_tag_width(self.owner.language,task_role_label(hovered))+7 if hovered and task_role_label(hovered) else 0
        marquee=hovered and QFontMetricsF(face()).horizontalAdvance(task_title(hovered,self.owner.language))>self.TITLE_WIDTH-extra
        needed=self.isVisible() and getattr(self.owner,'motion_enabled',True) and marquee
        if needed and not self.animation.isActive():self.animation.start(33)
        elif not needed:self.animation.stop()

    def animate(self):
        self.sync_animation()
        if self.animation.isActive():self.update()

    def refresh(self,data):
        self.data=data;self.rows=panel_rows(data,self.mode)
        metrics=QFontMetricsF(face(8))
        self.project_width=min(80,max([metrics.horizontalAdvance(project_label(t['project'],self.owner.language))+12 for t in self.rows]+[44]))
        self.TITLE_X=33+self.project_width+10
        title_metrics=QFontMetricsF(face())
        longest=max([title_metrics.horizontalAdvance(task_title(task,self.owner.language))+(side_tag_width(self.owner.language,task_role_label(task))+7 if task_role_label(task) else 0) for task in self.rows]+[0])
        self.values={t['id']:chart_number(t.get('tokens'),self.owner.chart_unit) if self.mode=='daily' else duration_text(t.get('round_seconds')) for t in self.rows}
        info_width=max([metrics.horizontalAdvance(value) for value in self.values.values()]+[24])
        width=min(getattr(self.owner,'content_limit',None) or self.owner.width(),max(260,math.ceil(self.TITLE_X+longest+24+info_width+18)))
        if self.mode=='daily':width=max(self.usage_width(),width)
        self.value_right=width-18
        self.info_divider=self.value_right-info_width-12
        self.TITLE_WIDTH=max(0,self.info_divider-12-self.TITLE_X)
        self.sections=[] if self.mode=='daily' else [(self.owner.label(CATEGORY_LABELS[self.mode]),0)]
        self.header_extra=self.TITLE_HEIGHT if self.mode=='daily' else 0
        self.row_positions=[];y=24.+self.header_extra;previous=None
        for task in self.rows:
            section=self.owner.label(CATEGORY_LABELS[task_category(task)])
            if self.mode=='daily' and section!=previous:
                if previous is not None:y+=8
                self.sections.append((section,y));y+=22;previous=section
            self.row_positions.append(y);y+=self.ROW_HEIGHT
        self.full_height=max(24+self.header_extra+self.ROW_HEIGHT,y)
        height=min(round(self.full_height+16),500) if self.owner.floating or self.owner_unplaced() else min(round(self.full_height+16),500,max(100,self.owner.y()-16))
        self.place_panel(width,height);height=self.height()
        self.value_right=self.width()-18;self.info_divider=self.value_right-info_width-12
        self.TITLE_WIDTH=max(0,self.info_divider-12-self.TITLE_X)
        self.scroll=min(self.scroll,max(0,self.full_height-(height-16)))
        if self.pin_button:
            self.pin_button.move(self.width()-34,5);self.pin_button.sync(self.mode in self.owner.settings.get('pinned_statuses',[]))
        if self.mode=='daily' and self.hovered is None:self.setToolTip(self.usage_tooltip())
        self.sync_units();self.track_hover(self.mapFromGlobal(QCursor.pos()));self.sync_animation()
        if self.keyboard_task not in {t['id'] for t in self.rows}:self.keyboard_task=self.rows[0]['id'] if self.rows else None
        self.update()

    def task_at(self,point):
        if self.mode=='daily' and any(rect.contains(point) for rect in self.unit_rects().values()):return None
        if self.mode=='daily' and point.y()<32+self.TITLE_HEIGHT:return None
        if not QRectF(10,8,self.width()-20,max(0,self.height()-16)).contains(point):return None
        local_y=point.y()-8+self.scroll
        return next((task for task,y in zip(self.rows,self.row_positions) if y<=local_y<y+self.ROW_HEIGHT),None)

    def track_hover(self,point):
        task=self.task_at(point);hovered=task['id'] if task else None
        if hovered!=self.hovered:
            self.hovered=hovered;self.hover_started=time.monotonic()
            self.setToolTip('<qt>'+escape(task_title(task,self.owner.language))+'</qt>' if task else self.usage_tooltip() if self.mode=='daily' else '')
        over_unit=self.mode=='daily' and any(rect.contains(point) for rect in self.unit_rects().values())
        self.setCursor(Qt.CursorShape.PointingHandCursor if task or over_unit else Qt.CursorShape.ArrowCursor)

    def paintEvent(self,event):
        p=panel_painter(self)
        def right_label(value,right,y,font,color=MUTED):
            text(p,right-QFontMetricsF(font).horizontalAdvance(value),y,value,font,color)
        top=32+self.TITLE_HEIGHT if self.mode=='daily' else 8
        p.save();p.setClipRect(QRectF(10,top,self.width()-20,max(0,self.height()-top-8)))
        if not self.rows:text(p,18,50+self.header_extra,self.owner.label('No tasks'),face(8),MUTED)
        for label,position in self.sections:
            text(p,18,8+position+10-self.scroll,label,face(8),'#8795a5')
        for task,position in zip(self.rows,self.row_positions):
            yy=8+position-self.scroll;y=yy+self.ROW_HEIGHT/2
            if yy+self.ROW_HEIGHT<8 or yy>self.height()-8:continue
            if task['id']==self.hovered or self.hasFocus() and task['id']==self.keyboard_task:
                selected=self.hasFocus() and task['id']==self.keyboard_task
                p.setPen(Qt.PenStyle.NoPen);p.setBrush(QColor('#3b4858' if task['id']==getattr(self,'pressed_task',None) else '#34465a' if selected else '#303740'))
                p.drawRoundedRect(QRectF(10,yy,self.width()-20,self.ROW_HEIGHT),5,5)
            if task.get('status')=='failed':
                pen(p,FAILED,1.2);p.drawEllipse(QPointF(22,y),3.6,3.6)
                p.drawLine(QPointF(22,y-1.8),QPointF(22,y+.1));p.drawPoint(QPointF(22,y+2))
            elif task.get('status')=='stopped':
                p.setPen(Qt.PenStyle.NoPen);p.setBrush(QColor('#8795a5'))
                p.drawRoundedRect(QRectF(19.5,y-2.5,5,5),.8,.8)
            elif task.get('needs_input'):text(p,19,y,'?',face(8),AMBER)
            elif task.get('running'):
                icon(p,'task',22,y)
            else:
                p.setPen(Qt.PenStyle.NoPen);p.setBrush(QColor(AMBER if task.get('unread') else '#718096'))
                p.drawEllipse(QPointF(22,y),2.4,2.4)
            project_tag(p,33,y,task['project'],face(8),self.project_width,self.owner.language)
            title_x=self.TITLE_X
            if task_role_label(task):title_x+=side_tag(p,title_x,y,self.owner.language,role=task_role_label(task))+7
            title_width=max(0,self.TITLE_WIDTH-(title_x-self.TITLE_X))
            title=task_title(task,self.owner.language);metrics=QFontMetricsF(face());shift=0.
            if task['id']==self.hovered and getattr(self.owner,'motion_enabled',True):
                shift=marquee_offset(time.monotonic()-self.hover_started,metrics.horizontalAdvance(title)-title_width)
            else:title=metrics.elidedText(title,Qt.TextElideMode.ElideRight,title_width)
            p.save();p.setClipRect(QRectF(title_x,yy,title_width,self.ROW_HEIGHT),Qt.ClipOperation.IntersectClip)
            text(p,title_x-shift,y,title,face());p.restore()
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
        task=self.task_at(event.position())
        self.pressed_task=task['id'] if task else None;self.keyboard_task=self.pressed_task;self.update()

    def mouseReleaseEvent(self,event):
        if event.button()!=Qt.MouseButton.LeftButton:return
        task=self.task_at(event.position())
        if task and task['id']==getattr(self,'pressed_task',None):self.owner.open_task(task)
        self.pressed_task=None;self.update()

    def mouseMoveEvent(self,event):
        self.track_hover(event.position());self.sync_animation();self.update()

    def leaveEvent(self,event):
        self.hovered=None;self.setToolTip('');self.sync_animation();self.update()

    def wheelEvent(self,event):
        self.pressed_task=None
        self.scroll=max(0,min(max(0,self.full_height-(self.height()-16)),self.scroll-wheel_distance(event,self.ROW_HEIGHT)))
        self.track_hover(self.mapFromGlobal(QCursor.pos()));self.update()

    def keyPressEvent(self,event):
        if self.focusWidget() in self.unit_buttons.values():super().keyPressEvent(event);return
        ids=[t['id'] for t in self.rows]
        if ids and event.key() in (Qt.Key.Key_Up,Qt.Key.Key_Down,Qt.Key.Key_Home,Qt.Key.Key_End):
            index=ids.index(self.keyboard_task) if self.keyboard_task in ids else 0
            if event.key()==Qt.Key.Key_Home:index=0
            elif event.key()==Qt.Key.Key_End:index=len(ids)-1
            else:index=max(0,min(len(ids)-1,index+(1 if event.key()==Qt.Key.Key_Down else -1)))
            self.keyboard_task=ids[index];top=32+self.TITLE_HEIGHT if self.mode=='daily' else 8;position=self.row_positions[index]+8
            self.scroll=max(0,min(max(0,self.full_height-(self.height()-16)),max(position+self.ROW_HEIGHT-self.height()+8,min(self.scroll,position-top))))
            if index==0:self.scroll=0
            self.update();event.accept();return
        if event.key() in (Qt.Key.Key_Return,Qt.Key.Key_Enter) and self.keyboard_task in ids:
            self.owner.open_task(self.rows[ids.index(self.keyboard_task)]);event.accept();return
        super().keyPressEvent(event)



def main():
    if sys.argv[1:]==["--smoke-test"]:
        from .task_finder import TaskFinder
        from .task_strip import TaskStrip
        return
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
    QToolTip.setFont(face(8))
    provider=Provider(RUNTIME);bar=StatusBar(provider)
    app.exec()


if __name__=="__main__":main()
