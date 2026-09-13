"""Attached pinned task rows, driven by the owner's existing clocks."""
import time
from html import escape

from PySide6.QtCore import Qt,QPointF,QRectF,QVariantAnimation,QEasingCurve,QAbstractAnimation
from PySide6.QtGui import QColor,QFontMetricsF,QPainter,QPainterPath,QCursor
from PySide6.QtWidgets import QApplication,QWidget

from . import app as visuals
from . import windows
from .i18n import project_label,task_title,translate
from .presentation import panel_rect
from .motion import Spring
from .tasks import panel_rows,task_role_label,STATUS_CATEGORIES,CATEGORY_LABELS


class TaskStrip(QWidget):
    def __init__(self,owner,category="running",parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.category=category
        self.setMouseTracking(True)
        self.resize(420,30)
        self.owner=owner;self.data={};self.candidates=[]
        self.current_id=None;self.task=None;self.previous_task=None
        self.rotated_at=time.monotonic();self.paused_at=None
        self.task_hover=False;self.title_hover_started=self.rotated_at
        self.task_area=QRectF();self.task_rect=QRectF();self.hit_regions=[]
        self.pressed=None;self.pressed_local=None;self.press_inside=False
        self.drag_origin=None;self.dragging=False
        self.frame_key=None
        self.hidden=False;self.stopped=False
        self.task_blend=1.;self.task_tween=QVariantAnimation(self)
        self.task_tween.setDuration(450);self.task_tween.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.task_tween.valueChanged.connect(self.set_task_blend)
        self.task_tween.finished.connect(self.finish_transition)
        self.pin_button=visuals.PinButton(owner,self,dark_panel=False);self.pin_button.sync(True)
        self.pin_button.clicked.connect(lambda checked:owner.set_status_pinned(self.category,False))

    @property
    def language(self):return self.owner.language

    @property
    def motion_enabled(self):return self.owner.motion_enabled

    @property
    def needs_animation(self):
        return self.running_feedback or bool(self.isVisible() and self.motion_enabled and self.task and self.task_hover and self.task_blend>=1.
                    and not self.pressed and not self.dragging and self.task_rect.width()>0
                    and QFontMetricsF(self.owner.font).horizontalAdvance(task_title(self.task,self.language))>self.task_rect.width()+.5)

    @property
    def running_feedback(self):return bool(self.isVisible() and self.motion_enabled and self.task and self.category=='running')

    def sync_motion(self):
        if not self.motion_enabled:
            self.task_tween.stop();self.previous_task=None;self.task_blend=1.
        self.update()

    def animate(self):
        if self.running_feedback:self.update(QRectF(4,3,self.width()-40,self.height()-6).toAlignedRect())
        elif self.needs_animation:self.update(self.task_area.toAlignedRect())

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
        paused=bool(self.task_hover or self.pressed or self.drag_origin or self.hidden or getattr(self.owner,'dragging',False) or
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

    def refresh(self,data,resize=False,hidden=False):
        if self.stopped:return
        self.data=data;self.candidates=[dict(task) for task in panel_rows(data,self.category)]
        self.hidden=bool(hidden);self.pin_button.move(self.width()-32,2);self.pin_button.sync(True)
        self.setAccessibleName(translate(self.language,CATEGORY_LABELS[self.category]))
        self._sync_pause(time.monotonic())
        if not self.candidates or self.hidden:
            self.hide();self.track_pointer(QPointF(-1,-1));self.cancel_press()
            if not self.candidates:self.current_id=None;self.task=None;self.previous_task=None;self.task_tween.stop();self.task_blend=1.
            return
        if self.isVisible():
            point=QCursor.pos();widget=QApplication.widgetAt(point)
            self.track_pointer(self.mapFromGlobal(point) if widget is self or widget and self.isAncestorOf(widget) else QPointF(-1,-1))
        if not self.pressed and self.drag_origin is None:
            previous=self.task;self.task=self.selected_task(self.candidates,advance=not resize)
            if previous and self.task and previous['id']!=self.task['id'] and self.motion_enabled:
                self.task_tween.stop();self.previous_task=previous;self.task_blend=0.
                self.task_tween.setStartValue(0.);self.task_tween.setEndValue(1.);self.task_tween.start()
            elif not self.motion_enabled:self.task_tween.stop();self.previous_task=None;self.task_blend=1.
        self.show()
        key=(tuple(self.task.get(k) for k in ('id','title','project','side_chat','task_role')) if self.task else None,
             self.geometry().getRect(),self.language,self.owner.settings.get('capsule_theme'),self.task_hover)
        if key!=self.frame_key:
            self.frame_key=key
            if self.task:self.setAccessibleDescription(task_title(self.task,self.language))
            self.update()

    def track_pointer(self,point):
        inside=bool(self.pressed_local and self.pressed_local.contains(point))
        if inside!=self.press_inside:self.press_inside=inside;self.update()
        hovering=QRectF(self.rect()).contains(point)
        if hovering!=self.task_hover:
            self.task_hover=hovering;self.title_hover_started=time.monotonic();self._sync_pause(self.title_hover_started);self.update()
        self.setCursor(Qt.CursorShape.PointingHandCursor if self.task_area.contains(point) else Qt.CursorShape.ArrowCursor)
        task=self.displayed_task();tip=''
        if hovering and task:
            role=task_role_label(task)
            parts=[translate(self.language,CATEGORY_LABELS[self.category]),project_label(task.get('project'),self.language),
                   *([translate(self.language,role)] if role else []),task_title(task,self.language)]
            tip='<qt>'+'<br>'.join(escape(part) for part in parts)+'</qt>'
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
        self.drag_origin=None;self.dragging=False;self.release_press()

    def mousePressEvent(self,event):
        if event.button()!=Qt.MouseButton.LeftButton:return
        task=self.displayed_task()
        if task and self.task_area.contains(event.position()):
            self.begin_press(task);self.drag_origin=event.globalPosition();self.dragging=False;event.accept()

    def mouseReleaseEvent(self,event):
        if event.button()!=Qt.MouseButton.LeftButton:return
        pressed=self.release_press();dragged=self.dragging;self.drag_origin=None;self.dragging=False
        if not dragged and pressed and pressed[0].contains(event.position()) and any(t['id']==pressed[1]['id'] for t in self.candidates):self.owner.open_task(pressed[1])
        self.track_pointer(event.position());self._sync_pause(time.monotonic());event.accept()

    def mouseMoveEvent(self,event):
        if self.drag_origin is not None and (event.globalPosition()-self.drag_origin).manhattanLength()>=QApplication.startDragDistance():
            self.dragging=True;self.release_press()
        self.track_pointer(event.position())

    def leaveEvent(self,event):self.track_pointer(QPointF(-1,-1))

    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHints(QPainter.RenderHint.Antialiasing|QPainter.RenderHint.TextAntialiasing)
        self.task_area=QRectF();self.task_rect=QRectF();self.hit_regions=[]
        if not self.task:p.end();return
        theme=self.owner.settings.get('capsule_theme','dark');palette=visuals.CAPSULE_COLORS[theme];y=self.height()/2
        if self.task_hover or self.pressed:
            color=QColor('#ffffff' if theme=='dark' else '#22354b');color.setAlpha(30 if self.pressed and self.press_inside else 18)
            p.setPen(Qt.PenStyle.NoPen);p.setBrush(color);p.drawRoundedRect(QRectF(4,3,self.width()-8,self.height()-6),5,5)
        color=palette[{'running':'green','waiting':'amber','unread':'amber','failed':'failed','stopped':'stopped'}[self.category]]
        visuals.running_dot(p,17,y,color,self.category=='running' and self.motion_enabled)
        def label(task,opacity,offset,current=False):
            metrics=QFontMetricsF(self.owner.font);title=task_title(task,self.language);available=max(0,self.width()-70)
            shown=min(available,metrics.horizontalAdvance(title))
            area=QRectF(30,0,shown,self.height())
            if current:self.task_rect=area
            if opacity>0:self.task_area=self.task_area.united(area.adjusted(-5,0,6,0))
            p.save();p.setOpacity(opacity);p.setClipRect(QRectF(30,0,available,self.height()))
            shift=0.
            if self.task_hover and self.motion_enabled and self.task_blend>=1 and not self.pressed and not self.dragging:
                shift=visuals.marquee_offset(time.monotonic()-self.title_hover_started,metrics.horizontalAdvance(title)-available)
            else:title=metrics.elidedText(title,Qt.TextElideMode.ElideRight,available)
            if self.category=='running' and self.motion_enabled and self.task_blend>=1 and not self.task_hover and not self.pressed:
                visuals.running_title(p,30,y+offset,title,self.owner.font,30,shown,palette['text'],theme=='light')
            else:visuals.text(p,30-shift,y+offset,title,self.owner.font,palette['text'])
            p.restore()
        if self.previous_task and self.task_blend<1:label(self.previous_task,1-self.task_blend,-14*self.task_blend)
        label(self.task,self.task_blend,14*(1-self.task_blend),True)
        self.hit_regions=[('task',QRectF(self.task_area),dict(self.displayed_task()))];p.end()

    def shutdown(self):self.stopped=True;self.task_tween.stop();self.cancel_press();self.hide()
    def closeEvent(self,event):self.shutdown();event.accept()


class PinnedPanel(QWidget):
    def __init__(self,owner):
        super().__init__(None,visuals.FLAGS)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground);self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.owner=owner;self.setWindowTitle('Codex · Pinned tasks');self.joined_edge=None;self.active=[];self.stopped=False
        self.rows={kind:TaskStrip(owner,kind,self) for kind in STATUS_CATEGORIES}
        self.size_motion=Spring(self,response=.18);self.size_motion.changed.connect(self.layout_rows)
        self.host_key=None;self.surface_loss_since=None;self.surface_repaired=False;self.frame_key=None

    def nativeEvent(self,event_type,message):
        native=windows.w.MSG.from_address(int(message))
        if hasattr(self,'owner') and hasattr(self.owner,'native_handle') and windows.z_order_changed(native):self.owner.schedule_stack_repair()
        return super().nativeEvent(event_type,message)

    @property
    def needs_animation(self):return any(row.needs_animation for row in self.rows.values())
    def animate(self):
        for row in self.rows.values():row.animate()
    def sync_motion(self):
        for row in self.rows.values():row.sync_motion()
        if not self.owner.motion_enabled:self.size_motion.snap(self.size_motion.target)
    def occupied_geometry(self):
        if not self.isVisible() or self.joined_edge is None:return QRectF().toRect()
        box=self.geometry();target=round(self.size_motion.target)
        if target>=2:
            screen=self.owner.screen();bounds=screen.availableGeometry() if self.owner.floating else screen.geometry()
            box=box.united(panel_rect(self.owner.geometry(),bounds,self.owner.width(),target,-1))
        return box
    def reposition_popup(self):
        popup=self.owner.popup
        if isinstance(popup,visuals.TaskPopup):
            size=popup.size();popup.reposition()
            if popup.size()!=size:popup.refresh(popup.data)
    def refresh(self,data,resize=False,hidden=False):
        if self.stopped:return
        visible=not hidden and self.owner.isVisible() and self.owner.settings.get('show_tasks',True)
        selected=self.owner.settings.get('pinned_statuses',[])
        active=[kind for kind in STATUS_CATEGORIES if kind in selected and panel_rows(data,kind)] if visible else []
        for kind,row in self.rows.items():
            row.resize(self.owner.width(),30);row.refresh(data,resize,hidden=kind not in active)
        self.active=active
        if not visible:
            self.size_motion.snap(0);return
        target=len(active)*30+1 if active else 0
        if target!=self.size_motion.target:
            if self.owner.motion_enabled:self.size_motion.retarget(target)
            else:self.size_motion.snap(target)
        else:self.layout_rows(self.size_motion.value)
        self.setAccessibleName(self.owner.label('Pinned tasks'))
        key=(self.owner.settings.get('capsule_theme'),self.owner.settings.get('capsule_transparency'),self.geometry().getRect(),tuple(active))
        if key!=self.frame_key:self.frame_key=key;self.update()

    def layout_rows(self,value):
        height=round(value)
        if height<2 or not self.owner.isVisible():
            self.hide()
            if self.joined_edge is not None:self.joined_edge=None;self.owner.update();self.reposition_popup()
            return
        screen=self.owner.screen();bounds=screen.availableGeometry() if self.owner.floating else screen.geometry()
        box=panel_rect(self.owner.geometry(),bounds,self.owner.width(),height,-1)
        moved=box!=self.geometry()
        if moved:self.setGeometry(box)
        edge='top' if box.top()<self.owner.y() else 'bottom'
        if edge!=self.joined_edge:self.joined_edge=edge;self.owner.update()
        offset=height-(len(self.active)*30+1) if edge=='top' else 0
        for index,kind in enumerate(self.active):self.rows[kind].move(0,offset+index*30)
        self.ensure_visible()
        if moved:self.update();self.reposition_popup()

    def ensure_visible(self):
        hwnd=int(self.winId());window=self.windowHandle();recovered=False
        native_visible=bool(windows.user32.IsWindowVisible(hwnd));minimized=bool(windows.user32.IsIconic(hwnd))
        exposed=bool(window and window.isExposed())
        if self.isVisible() and native_visible and not minimized and exposed:
            self.surface_loss_since=None;self.surface_repaired=False
        elif not self.owner.menu.isVisible() and not self.owner.confirming_reset:
            if not self.isVisible():self.surface_loss_since=None;self.surface_repaired=False;self.show();recovered=True
            else:
                now=time.monotonic()
                if self.surface_loss_since is None:self.surface_loss_since=now
                if not self.surface_repaired and now-self.surface_loss_since>=.3:
                    self.surface_repaired=True;self.hide()
                    if minimized:self.setWindowState(self.windowState() & ~Qt.WindowState.WindowMinimized)
                    self.show();recovered=True
        key=(int(self.winId()),True if not self.owner.floating else self.owner.settings.get('floating_topmost',True))
        if recovered or key!=self.host_key:windows.hide_border(key[0]);self.host_key=key
        window=self.windowHandle();parent=self.owner.windowHandle()
        if window and parent and window.transientParent()!=parent:window.setTransientParent(parent)
        windows.follow_owner(key[0],int(self.owner.winId()),key[1])
        return recovered

    def paintEvent(self,event):
        p=visuals.painter(self);color=QColor(visuals.CAPSULE_COLORS[self.owner.settings.get('capsule_theme','dark')]['background'])
        color.setAlpha(max(1,round(255*(1-self.owner.settings.get('capsule_transparency',0)/100))))
        p.setPen(Qt.PenStyle.NoPen);p.setBrush(color)
        p.drawPath(visuals.connected_surface(QRectF(1,1,self.width()-2,self.height()-1),'bottom' if self.joined_edge=='top' else 'top'));p.end()
    def shutdown(self):
        self.stopped=True;self.size_motion.stop()
        for row in self.rows.values():row.shutdown()
        self.hide();self.joined_edge=None
    def closeEvent(self,event):self.shutdown();event.accept()
