"""Independent running-task presentation, driven by the owner's existing clocks."""
import time
from html import escape

from PySide6.QtCore import Qt,QPointF,QRectF,QVariantAnimation,QEasingCurve,QAbstractAnimation
from PySide6.QtGui import QColor,QFontMetricsF,QPainter,QPainterPath,QCursor
from PySide6.QtWidgets import QApplication,QWidget

from . import app as visuals
from . import windows
from .i18n import project_label,task_title,translate
from .presentation import task_strip_rect,clamp_rect,remember_position,panel_rect
from .tasks import panel_rows,task_role_label


class TaskStrip(QWidget):
    def __init__(self,owner):
        super().__init__(None,visuals.FLAGS)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowTitle('Codex · Running tasks')
        self.setMouseTracking(True)
        self.resize(420,30)
        self.owner=owner;self.data={};self.candidates=[]
        self.current_id=None;self.task=None;self.previous_task=None
        self.rotated_at=time.monotonic();self.paused_at=None
        self.task_hover=False;self.title_hover_started=self.rotated_at
        self.task_area=QRectF();self.task_rect=QRectF();self.hit_regions=[]
        self.pressed=None;self.pressed_local=None;self.press_inside=False;self.right_pressed=None
        self.drag_origin=None;self.dragging=False
        self.host_key=None;self.frame_key=None;self.surface_loss_since=None;self.surface_repaired=False
        self.hidden=False;self.stopped=False
        self.task_blend=1.;self.task_tween=QVariantAnimation(self)
        self.task_tween.setDuration(450);self.task_tween.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.task_tween.valueChanged.connect(self.set_task_blend)
        self.task_tween.finished.connect(self.finish_transition)

    @property
    def language(self):return self.owner.language

    @property
    def motion_enabled(self):return self.owner.motion_enabled

    @property
    def needs_animation(self):
        return bool(self.isVisible() and self.motion_enabled and self.task and self.task_hover and self.task_blend>=1.
                    and not self.pressed and not self.dragging and self.task_rect.width()>0
                    and QFontMetricsF(self.owner.font).horizontalAdvance(task_title(self.task,self.language))>self.task_rect.width()+.5)

    def sync_motion(self):
        if not self.motion_enabled:
            self.task_tween.stop();self.previous_task=None;self.task_blend=1.
        self.update()

    def animate(self):
        if self.needs_animation:self.update(self.task_area.toAlignedRect())

    def set_task_blend(self,value):
        self.task_blend=float(value)
        if self.isVisible():self.update()

    def finish_transition(self):
        self.previous_task=None;self.task_blend=1.
        if self.task_hover:self.title_hover_started=time.monotonic()

    def displayed_task(self):
        return self.previous_task if self.previous_task and self.task_blend<.5 else self.task

    def _sync_pause(self,now):
        dialog=self.owner.settings_dialog
        paused=bool(self.task_hover or self.pressed or self.drag_origin or self.hidden or
                    self.owner.confirming_reset or self.owner.menu.isVisible() or dialog and dialog.isVisible())
        if paused and self.paused_at is None:self.paused_at=now
        elif not paused and self.paused_at is not None:
            self.rotated_at+=now-self.paused_at;self.paused_at=None
        return paused

    def selected_task(self,tasks,advance=True):
        now=time.monotonic();paused=self._sync_pause(now)
        if not tasks:self.current_id=None;return None
        ids=[task['id'] for task in tasks]
        if self.current_id not in ids:
            self.current_id=ids[0];self.rotated_at=now
            if self.paused_at is not None:self.paused_at=now
            if self.task_hover:self.title_hover_started=now
        elif advance and not paused and len(ids)>1 and now-self.rotated_at>=visuals.ROTATE_SECONDS:
            self.current_id=ids[(ids.index(self.current_id)+1)%len(ids)];self.rotated_at=now
        return tasks[ids.index(self.current_id)]

    def selected_screen(self):
        position=self.owner.settings.get('task_strip_position')
        if position:
            return next((screen for screen in QApplication.screens() if screen.name()==position['screen']),QApplication.primaryScreen())
        if self.owner.isVisible():return self.owner.screen()
        return QApplication.primaryScreen()

    def refresh(self,data,resize=False,hidden=False):
        if self.stopped:return
        self.data=data;self.candidates=[dict(task) for task in panel_rows(data,'running')]
        self.hidden=bool(hidden or not self.owner.settings.get('show_task_strip',False))
        self.setAccessibleName(translate(self.language,'Running task strip'))
        self._sync_pause(time.monotonic())
        if not self.candidates or self.hidden:
            self.hide();self.track_pointer(QPointF(-1,-1));self.cancel_press()
            if not self.candidates:
                self.current_id=None;self.task=None;self.previous_task=None;self.task_tween.stop();self.task_blend=1.
                self.setAccessibleDescription('')
            return
        if self.isVisible() and not self.dragging:
            point=QCursor.pos()
            self.track_pointer(self.mapFromGlobal(point) if QApplication.widgetAt(point) is self else QPointF(-1,-1))
        if self.drag_origin is None and not self.pressed:
            previous=self.task;self.task=self.selected_task(self.candidates,advance=not resize)
            if previous and self.task and previous['id']!=self.task['id'] and self.motion_enabled:
                self.task_tween.stop();self.previous_task=previous;self.task_blend=0.
                self.task_tween.setStartValue(0.);self.task_tween.setEndValue(1.);self.task_tween.start()
            elif not self.motion_enabled:
                self.task_tween.stop();self.previous_task=None;self.task_blend=1.
        screen=self.selected_screen()
        if screen is None:self.hide();return
        if self.drag_origin is None:
            anchor=self.owner.geometry() if self.owner.isVisible() else None
            box=task_strip_rect(screen.availableGeometry(),anchor=anchor,position=self.owner.settings.get('task_strip_position'))
            if self.geometry()!=box:self.setGeometry(box)
        self.ensure_visible()
        frame_key=(tuple(self.task.get(key) for key in ('id','project','title','side_chat','task_role')) if self.task else None,
                   self.geometry().getRect(),self.language,self.owner.settings.get('capsule_theme'),
                   self.owner.settings.get('capsule_transparency'),self.task_hover)
        if frame_key!=self.frame_key:
            self.frame_key=frame_key
            if self.task:
                role=task_role_label(self.task)
                self.setAccessibleDescription(', '.join([project_label(self.task.get('project'),self.language),
                    *([translate(self.language,role)] if role else []),task_title(self.task,self.language)]))
            self.update()

    def ensure_visible(self):
        hwnd=int(self.winId());window=self.windowHandle();recovered=False
        native_visible=bool(windows.user32.IsWindowVisible(hwnd));minimized=bool(windows.user32.IsIconic(hwnd))
        exposed=bool(window and window.isExposed())
        if self.isVisible() and native_visible and not minimized and exposed:
            self.surface_loss_since=None;self.surface_repaired=False
        elif not self.owner.menu.isVisible() and not self.owner.confirming_reset:
            if not self.isVisible():
                self.surface_loss_since=None;self.surface_repaired=False;self.show();recovered=True
            else:
                now=time.monotonic()
                if self.surface_loss_since is None:self.surface_loss_since=now
                if not self.surface_repaired and now-self.surface_loss_since>=.3:
                    self.surface_repaired=True;self.hide()
                    if minimized:self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized)
                    self.show();recovered=True
        host_key=(int(self.winId()),self.owner.settings.get('floating_topmost',True))
        if recovered or host_key!=self.host_key:
            windows.hide_border(host_key[0]);windows.floating_window(*host_key);self.host_key=host_key
        return recovered

    def track_pointer(self,point):
        inside=bool(self.pressed_local and self.pressed_local.contains(point))
        if inside!=self.press_inside:self.press_inside=inside;self.update()
        hovering=self.task_area.contains(point)
        if hovering!=self.task_hover:
            self.task_hover=hovering;self.title_hover_started=time.monotonic()
            self._sync_pause(self.title_hover_started);self.update()
        self.setCursor(Qt.CursorShape.PointingHandCursor if hovering else Qt.CursorShape.ArrowCursor)
        task=self.displayed_task();tip=''
        if hovering and task:tip='<qt>'+escape(project_label(task.get('project'),self.language))+'<br>'+escape(task_title(task,self.language))+'</qt>'
        if self.toolTip()!=tip:self.setToolTip(tip)

    def begin_press(self,task,rect=None):
        self.pressed_local=QRectF(rect or self.task_area);self.pressed=(QRectF(self.pressed_local),dict(task));self.press_inside=True
        if self.task_tween.state()==QAbstractAnimation.State.Running:self.task_tween.pause()
        self._sync_pause(time.monotonic());self.update()

    def release_press(self):
        pressed=self.pressed;self.pressed=None;self.pressed_local=None;self.press_inside=False
        if self.task_tween.state()==QAbstractAnimation.State.Paused:self.task_tween.resume()
        self._sync_pause(time.monotonic());self.update();return pressed

    def cancel_press(self):
        self.drag_origin=None;self.dragging=False;self.right_pressed=None;self.release_press()

    def mousePressEvent(self,event):
        shape=QPainterPath();shape.addRoundedRect(QRectF(1,1,self.width()-2,self.height()-2),(self.height()-2)/2,(self.height()-2)/2)
        if not shape.contains(event.position()):return
        if event.button()==Qt.MouseButton.RightButton:
            self.right_pressed=QRectF(self.rect());event.accept();return
        if event.button()!=Qt.MouseButton.LeftButton:return
        task=self.displayed_task()
        if task and self.task_area.contains(event.position()):self.begin_press(task)
        self.drag_origin=(event.globalPosition(),self.pos());self.dragging=False
        self._sync_pause(time.monotonic());event.accept()

    def mouseReleaseEvent(self,event):
        if event.button()==Qt.MouseButton.RightButton:
            pressed=self.right_pressed;self.right_pressed=None
            if pressed and pressed.contains(event.position()):self.open_menu()
            event.accept();return
        if event.button()!=Qt.MouseButton.LeftButton or self.drag_origin is None:return
        pressed=self.release_press();dragged=self.dragging
        self.drag_origin=None;self.dragging=False
        if dragged:
            screen=QApplication.screenAt(self.geometry().center()) or self.screen()
            self.owner.settings['task_strip_position']=remember_position(self.geometry(),screen.availableGeometry(),screen.name())
            self.owner.save_settings()
        elif pressed and pressed[0].contains(event.position()) and any(task['id']==pressed[1]['id'] for task in self.candidates):
            self.owner.open_task(pressed[1])
        self.track_pointer(event.position());self._sync_pause(time.monotonic());event.accept()

    def mouseMoveEvent(self,event):
        if self.drag_origin is not None:
            start,position=self.drag_origin;delta=event.globalPosition()-start
            if self.dragging or delta.manhattanLength()>=QApplication.startDragDistance():
                if not self.dragging:self.owner.hide_popup(immediate=True)
                self.dragging=True;self.release_press();self.setCursor(Qt.CursorShape.ClosedHandCursor)
                screen=QApplication.screenAt(event.globalPosition().toPoint()) or self.screen()
                target=self.geometry();target.moveTopLeft(position+delta.toPoint())
                self.setGeometry(clamp_rect(target,screen.availableGeometry()));event.accept();return
        self.track_pointer(event.position())

    def leaveEvent(self,event):self.track_pointer(QPointF(-1,-1))

    def open_menu(self):
        self.owner.hide_popup(immediate=True);menu=self.owner.menu;menu.ensurePolished()
        size=menu.sizeHint();box=panel_rect(self.geometry(),self.screen().availableGeometry(),size.width(),size.height())
        menu.popup(box.topLeft())

    def project_available(self):return min(110,max(36,self.width()*.25))

    def paintEvent(self,event):
        p=visuals.painter(self);self.task_area=QRectF();self.task_rect=QRectF();self.hit_regions=[]
        if not self.task:p.end();return
        theme=self.owner.settings.get('capsule_theme','dark');palette=visuals.CAPSULE_COLORS[theme]
        x,y=14.,self.height()/2
        p.save();p.setClipRect(QRectF(x-2,0,max(0,self.width()-x+2),self.height()))
        def task_label(task,opacity,offset,current=False):
            p.save();p.setOpacity(opacity);p.translate(0,offset)
            title_x=x+visuals.project_tag(p,x,y,task.get('project'),visuals.face(8),self.project_available(),self.language,color=palette['link'],muted=palette['muted'])+10
            if task_role_label(task):title_x+=visuals.side_tag(p,title_x,y,self.language,light=theme=='light',role=task_role_label(task))+7
            available=max(0,self.width()-title_x-14);label=task_title(task,self.language);metrics=QFontMetricsF(self.owner.font)
            title_y=y-metrics.tightBoundingRect(label).center().y()-(metrics.ascent()-metrics.descent())/2
            shown=min(available,metrics.horizontalAdvance(label))
            if current:self.task_rect=QRectF(title_x,0,shown,self.height())
            if opacity>0:self.task_area=self.task_area.united(QRectF(x-4,0,max(0,title_x+shown+6-x+4),self.height()))
            shift=0.;marquee=self.task_hover and self.motion_enabled and self.task_blend>=1. and not self.pressed and not self.dragging
            if marquee:shift=visuals.marquee_offset(time.monotonic()-self.title_hover_started,metrics.horizontalAdvance(label)-available)
            else:label=metrics.elidedText(label,Qt.TextElideMode.ElideRight,available)
            p.setClipRect(QRectF(title_x,-offset,available,self.height()),Qt.ClipOperation.IntersectClip)
            visuals.text(p,title_x-shift,title_y,label,self.owner.font,palette['muted'] if self.task_blend<1 else palette['text'])
            p.restore()
        if self.previous_task and self.task_blend<1:task_label(self.previous_task,1-self.task_blend,-22*self.task_blend)
        task_label(self.task,self.task_blend,22*(1-self.task_blend),current=True);p.restore()
        self.task_area=self.task_area.intersected(QRectF(5,0,self.width()-10,self.height()))
        self.hit_regions=[('task',QRectF(self.task_area),dict(self.displayed_task()))]
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationOver)
        if self.pressed and self.press_inside:
            color=QColor('#ffffff' if theme=='dark' else '#22354b');color.setAlpha(25)
            p.setPen(Qt.PenStyle.NoPen);p.setBrush(color);p.drawRoundedRect(self.task_area.adjusted(0,4,0,-4),7,7)
        background=QColor(palette['background']);background.setAlpha(max(1,round(255*(1-self.owner.settings.get('capsule_transparency',0)/100))))
        p.setPen(Qt.PenStyle.NoPen);p.setBrush(background)
        box=QRectF(1,1,self.width()-2,self.height()-2);p.drawRoundedRect(box,box.height()/2,box.height()/2);p.end()

    def shutdown(self):
        self.stopped=True;self.task_tween.stop();self.cancel_press();self.hide()

    def closeEvent(self,event):self.shutdown();event.accept()
