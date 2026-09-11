"""Native settings and tray entry; deliberately no general layout editor."""
from pathlib import Path
from PySide6.QtCore import Qt,QSize,QRectF,QTimer
from PySide6.QtGui import QIcon, QPainter, QPixmap, QColor, QPen
from PySide6.QtWidgets import QApplication,QDialog, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QPushButton, QComboBox, QListView, QSlider, QScrollArea, QWidget, QFrame,QStackedWidget,QGraphicsOpacityEffect
from .build_info import APP_NAME, VERSION
from .i18n import LANGUAGE_NAMES
from . import startup,windows
from .motion import Spring
from .ui_theme import Segments,Navigation,CONTROLS,typeface
from .diagnostics import diagnostic_text

DISPLAY_LABELS = {
    'show_week': 'Weekly quota', 'show_session': '5-hour quota',
    'show_countdown': 'Reset countdown', 'show_daily': 'Daily quota usage',
    'show_tasks': 'Task rotation and counts',
}


def app_icon():
    pixmap = QPixmap(32, 32); pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor('#45ba91'), 3); pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen); painter.drawArc(5, 5, 22, 22, 90*16, -290*16)
    painter.setPen(Qt.PenStyle.NoPen); painter.setBrush(QColor('#a088d1')); painter.drawEllipse(12, 12, 8, 8)
    painter.end(); return QIcon(pixmap)


class Toggle(QCheckBox):
    """A switch-only target. Its caption is a separate, noninteractive label."""
    def __init__(self,caption=None):
        super().__init__();self.caption=caption;self.row=None;self.keyboard_focus=False
        self.setFixedSize(44,32);self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.progress=0.;self.motion=Spring(self,response=.16);self.motion.changed.connect(self.set_progress);self.toggled.connect(self.animate_state)
    def set_progress(self,value):self.progress=max(0.,min(1.,float(value)));self.update()
    def animate_state(self,checked):
        if self.isVisible() and not self.keyboard_focus and getattr(getattr(self.window(),'bar',None),'motion_enabled',True):self.motion.retarget(float(checked))
        else:self.motion.snap(float(checked))
    def setChecked(self,value):
        super().setChecked(value)
        if self.signalsBlocked() or not self.isVisible():self.motion.snap(float(self.isChecked()))
    def setText(self,value):
        super().setText(value);self.setAccessibleName(value)
        if self.caption is not None:self.caption.setText(value)
    def sizeHint(self):return QSize(44,32)
    def switch_rect(self):return QRectF(4,6,36,20)
    def hitButton(self,point):return self.switch_rect().adjusted(-2,-3,2,3).contains(point)
    def focusInEvent(self,event):
        self.keyboard_focus=event.reason() in (Qt.FocusReason.TabFocusReason,Qt.FocusReason.BacktabFocusReason,Qt.FocusReason.ShortcutFocusReason)
        super().focusInEvent(event);self.update()
    def mousePressEvent(self,event):
        self.keyboard_focus=False;super().mousePressEvent(event);self.update()
    def hideEvent(self,event):self.motion.snap(float(self.isChecked()));super().hideEvent(event)
    def keyPressEvent(self,event):
        self.keyboard_focus=True;super().keyPressEvent(event);self.update()
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        x,y=self.switch_rect().x(),self.switch_rect().y()
        if not self.isEnabled():p.setOpacity(.45)
        off=QColor('#4a5665');on=QColor('#6b9dcc')
        color=QColor.fromRgbF(*[a+(b-a)*self.progress for a,b in zip(off.getRgbF()[:3],on.getRgbF()[:3])])
        p.setPen(Qt.PenStyle.NoPen);p.setBrush(color)
        p.drawRoundedRect(QRectF(x,y,36,20),10,10)
        p.setBrush(QColor('#cddded' if self.isDown() else '#edf3fa'));p.drawEllipse(QRectF(x+3+16*self.progress,y+3,14,14))
        if self.hasFocus() and self.keyboard_focus:
            p.setBrush(Qt.BrushStyle.NoBrush);p.setPen(QPen(QColor('#86b6e6'),1));p.drawRoundedRect(self.switch_rect().adjusted(-3,-3,3,3),13,13)
        p.end()


class Choice(QComboBox):
    def wheelEvent(self,event):event.ignore()


class ValueSlider(QSlider):
    def wheelEvent(self,event):event.ignore()


class SettingsDialog(QDialog):
    def __init__(self,bar):
        super().__init__();self.bar=bar;self.setFont(bar.font);self.setWindowIcon(app_icon());self.setMinimumSize(620,300)
        self.setStyleSheet(('QWidget{font-family:"'+bar.font.family()+'";} QDialog,QFrame#rail{background:#1b1d22;} QWidget#content,QScrollArea,QScrollArea>QWidget>QWidget{background:#24262c;} QListWidget{background:transparent;border:0;outline:0;} '+CONTROLS).replace('__CHEVRON__',(Path(__file__).resolve().parents[1]/'assets/icons/chevron-down.svg').as_posix()))
        outer=QHBoxLayout(self);outer.setContentsMargins(0,0,0,0);outer.setSpacing(0)
        rail=QFrame();rail.setObjectName('rail');rail.setFixedWidth(174);sidebar=QVBoxLayout(rail);sidebar.setContentsMargins(14,24,14,16);sidebar.setSpacing(6)
        brand=QLabel('Codex');brand.setFont(typeface(bar.font,17));sidebar.addWidget(brand)
        product=QLabel('Taskbar Companion');product.setFont(typeface(bar.font,8));product.setStyleSheet('color:#8f98a7;');sidebar.addWidget(product);sidebar.addSpacing(24)
        self.navigation=Navigation();self.navigation.setFont(typeface(bar.font,9));self.navigation.addItems(['','','']);sidebar.addWidget(self.navigation,1)
        version=QLabel('v'+VERSION);version.setStyleSheet('color:#8f98a7;');version.setFont(typeface(bar.font,8));sidebar.addWidget(version)
        outer.addWidget(rail);content=QWidget();content.setObjectName('content');right=QVBoxLayout(content);right.setContentsMargins(0,0,0,0);right.setSpacing(0);outer.addWidget(content,1)
        self.stack=QStackedWidget();right.addWidget(self.stack,1)
        self.feedback=QLabel();self.feedback.setWordWrap(True);self.feedback.setStyleSheet('color:#ebb45f;padding:12px 24px;');self.feedback.hide();right.addWidget(self.feedback)
        self.page_effect=QGraphicsOpacityEffect(self.stack);self.page_effect.setOpacity(1);self.page_effect.setEnabled(False);self.stack.setGraphicsEffect(self.page_effect)
        self.page_motion=Spring(self,value=1.,response=.14);self.page_motion.changed.connect(self.page_effect.setOpacity);self.page_motion.finished.connect(lambda:self.page_effect.setEnabled(False))
        self.navigation.currentRowChanged.connect(self.select_page)
        self.pages=[];self.headings=[]
        for _ in range(3):
            scroll=QScrollArea();scroll.setFrameShape(QFrame.Shape.NoFrame);scroll.setWidgetResizable(True);scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            body=QWidget();page=QVBoxLayout(body);page.setContentsMargins(24,24,24,24);page.setSpacing(16)
            heading=QLabel();heading.setFont(typeface(bar.font,18));self.headings.append(heading);page.addWidget(heading);page.addSpacing(4)
            page.setSizeConstraint(QVBoxLayout.SizeConstraint.SetMinimumSize);scroll.setWidget(body);self.pages.append(scroll);self.stack.addWidget(scroll)
        appearance=self.pages[0].widget().layout();indicators=self.pages[1].widget().layout();general=self.pages[2].widget().layout()
        def card(parent):
            frame=QFrame();frame.setObjectName('settingsCard');items=QVBoxLayout(frame);items.setContentsMargins(14,0,14,0);items.setSpacing(0);parent.addWidget(frame);return items
        def line(parent):
            result=QFrame();result.setObjectName('settingsLine');result.setFixedHeight(1);parent.addWidget(result);return result
        def row(parent,label,control):
            widget=QWidget();layout=QHBoxLayout(widget);layout.setContentsMargins(0,8,0,8);widget.setMinimumHeight(48)
            label.setFont(bar.font);control.setFont(bar.font)
            layout.addWidget(label);layout.addStretch();layout.addWidget(control);parent.addWidget(widget)
        def combo(values,current,callback,segmented=False):
            control=Segments() if segmented else Choice()
            if not segmented:control.setView(QListView());control.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
            for text,value in values:control.addItem(text,value)
            control.setCurrentIndex(control.findData(current));control.currentIndexChanged.connect(lambda:callback(control.currentData()));return control
        def toggle(parent):
            container=QWidget();container.setMinimumHeight(48);items=QHBoxLayout(container);items.setContentsMargins(0,8,0,8)
            caption=QLabel();caption.setTextFormat(Qt.TextFormat.PlainText);caption.setWordWrap(True);caption.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
            caption.setFont(bar.font)
            control=Toggle(caption);control.row=container;caption.setBuddy(control)
            items.addWidget(caption,1);items.addSpacing(16);items.addWidget(control);parent.addWidget(container);return control
        position=card(appearance);self.placement_label=QLabel()
        self.placement=combo([('','taskbar'),('','floating'),('','auto')],bar.settings.get('placement','taskbar'),bar.set_placement,segmented=True)
        row(position,self.placement_label,self.placement);self.topmost_line=line(position)
        self.display_label=QLabel();self.display_label.setWordWrap(True);self.display=Choice();self.display.setView(QListView());self.display.setMaximumWidth(230)
        self.display.currentIndexChanged.connect(lambda:bar.set_floating_display(self.display.currentData()))
        row(position,self.display_label,self.display);self.display_row=self.display.parentWidget();self.display_line=line(position);self.display_key=None
        self.topmost=toggle(position);self.topmost.setChecked(bar.settings.get('floating_topmost',True));self.topmost.toggled.connect(bar.set_floating_topmost)
        colors=card(appearance);self.capsule_label=QLabel()
        self.capsule=combo([('','dark'),('','light')],bar.settings.get('capsule_theme','dark'),bar.set_capsule_theme,segmented=True);row(colors,self.capsule_label,self.capsule);line(colors)
        self.transparency_label=QLabel();opacity=QWidget();opacity_row=QHBoxLayout(opacity);opacity_row.setContentsMargins(0,0,0,0)
        self.transparency=ValueSlider(Qt.Orientation.Horizontal);self.transparency.setRange(0,100);self.transparency.setMinimumWidth(150)
        self.transparency.setValue(bar.settings.get('capsule_transparency',0));self.transparency_value=QLabel();self.transparency_value.setMinimumWidth(34);self.transparency_value.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter)
        self.transparency.valueChanged.connect(lambda value:bar.set_capsule_transparency(value,save=not self.transparency.isSliderDown()))
        self.transparency.valueChanged.connect(lambda value:self.transparency_value.setText(f'{value}%'));self.transparency.sliderReleased.connect(bar.save_settings)
        opacity_row.addWidget(self.transparency);opacity_row.addWidget(self.transparency_value);row(colors,self.transparency_label,opacity);appearance.addStretch()
        self.behavior_title=QLabel();self.behavior_title.setFont(typeface(bar.font,8));self.behavior_title.setStyleSheet('color:#a0a7b4;')
        visible=card(indicators);self.checks={}
        for number,key in enumerate(DISPLAY_LABELS):
            if number:line(visible)
            check=toggle(visible);check.setChecked(bar.settings[key]);check.toggled.connect(lambda checked,key=key:bar.set_display(key,checked));self.checks[key]=check
        indicators.addWidget(self.behavior_title);behavior=card(indicators);self.rotation=toggle(behavior);self.rotation.setChecked(bar.settings.get('rotate_quotas',False));self.rotation.toggled.connect(bar.set_quota_rotation);line(behavior)
        self.hover=toggle(behavior);self.hover.setChecked(bar.settings.get('hover_panels',False));self.hover.toggled.connect(bar.set_hover_panels);indicators.addStretch()
        localization=card(general);self.language_label=QLabel();self.language=combo([(name,code) for code,name in LANGUAGE_NAMES],bar.settings.get('language','en'),bar.set_language);row(localization,self.language_label,self.language)
        startup_card=card(general);self.login=toggle(startup_card);self.login.setChecked(startup.enabled());self.login.toggled.connect(bar.set_startup)
        line(startup_card);self.notify_input=toggle(startup_card);self.notify_input.setChecked(bar.settings.get('notify_input',False));self.notify_input.toggled.connect(bar.set_notify_input)
        updates=card(general);self.update_label=QLabel();self.update_button=QPushButton();self.update_button.setAutoDefault(False);self.update_button.clicked.connect(bar.update_clicked);row(updates,self.update_label,self.update_button)
        line(updates);self.support_label=QLabel();self.diagnostics_button=QPushButton();self.diagnostics_button.setAutoDefault(False)
        self.diagnostics_button.setStyleSheet('QPushButton{background:#383c45;} QPushButton:hover{background:#464d59;} QPushButton:pressed{background:#30353e;}')
        self.diagnostics_button.clicked.connect(self.copy_diagnostics);row(updates,self.support_label,self.diagnostics_button)
        self.copy_timer=QTimer(self);self.copy_timer.setSingleShot(True);self.copy_timer.timeout.connect(lambda:self.diagnostics_button.setText(self.bar.label('Copy diagnostics')))
        self.connection=QLabel();self.connection.setWordWrap(True);self.connection.setStyleSheet('color:#8797aa;font-size:12px;');general.addWidget(self.connection)
        general.addStretch()
        self.refresh();self.navigation.setCurrentRow(0);self.resize(self.sizeHint())
        screen=bar.floating_screen() if bar.floating else bar.screen();self.move(screen.availableGeometry().center()-self.rect().center())

    @property
    def scroll_area(self):return self.pages[self.stack.currentIndex()]
    @property
    def body(self):return self.scroll_area.widget()
    def sizeHint(self):
        bounds=(self.bar.floating_screen() if self.bar.floating else self.bar.screen()).availableGeometry()
        return QSize(min(700,bounds.width()-32),min(540,max(300,bounds.height()-48)))

    def select_page(self,index):
        self.stack.setCurrentIndex(index)
        if self.isVisible() and self.bar.motion_enabled and not self.navigation.keyboard_navigation:
            self.page_effect.setEnabled(True)
            if not self.page_motion.timer.isActive():self.page_motion.snap(.72)
            self.page_motion.retarget(1.)
        else:self.page_motion.snap(1.);self.page_effect.setEnabled(False)

    def hideEvent(self,event):
        self.page_motion.snap(1.);self.page_effect.setEnabled(False);self.copy_timer.stop();self.diagnostics_button.setText(self.bar.label('Copy diagnostics'));super().hideEvent(event)

    def stop_motion(self):
        for motion in self.findChildren(Spring):motion.snap(motion.target)
        self.page_effect.setEnabled(False)

    def copy_diagnostics(self):
        try:login=startup.enabled()
        except OSError:login=None
        bar=self.bar;handle=bar.windowHandle();native=bar.native_handle
        report=diagnostic_text(bar.settings,bar.provider.get(),{'visible':bar.isVisible(),'native_visible':bool(windows.user32.IsWindowVisible(native)) if native else None,'minimized':bool(windows.user32.IsIconic(native)) if native else None,'exposed':bool(handle.isExposed()) if handle else None,'width':bar.width(),'height':bar.height(),'placement_available':not bar.placement_unavailable,'effective_placement':'floating' if bar.floating else 'taskbar','animations':bar.motion_enabled,'font':bar.font.family(),'startup':login})
        QApplication.clipboard().setText(report);self.diagnostics_button.setText(bar.label('Copied'));self.copy_timer.start(2000)

    def refresh(self):
        label=self.bar.label;self.setWindowTitle(f'{label("Settings")} · {APP_NAME}')
        for i,name in enumerate(('Appearance','Indicators','General')):
            self.navigation.item(i).setText(label(name));self.headings[i].setText(label(name))
        self.language_label.setText(label('Language'));self.behavior_title.setText(label('Interaction'));self.update_label.setText(label('Updates'))
        self.support_label.setText(label('Support'));self.diagnostics_button.setText(label('Copied' if self.copy_timer.isActive() else 'Copy diagnostics'))
        for control,key,options in ((self.language,'language',None),(self.placement,'placement',('Taskbar','Floating','Auto')),(self.capsule,'capsule_theme',('Dark','Light'))):
            control.blockSignals(True)
            if options:
                for i,value in enumerate(options):control.setItemText(i,label(value))
            control.setCurrentIndex(max(0,control.findData(self.bar.settings.get(key,{'language':'en','placement':'taskbar','capsule_theme':'dark'}[key]))));control.blockSignals(False)
        self.placement_label.setText(label('Placement'));self.capsule_label.setText(label('Capsule'));self.transparency_label.setText(label('Transparency'))
        for caption,control in ((self.placement_label,self.placement),(self.display_label,self.display),(self.capsule_label,self.capsule),(self.transparency_label,self.transparency),(self.language_label,self.language)):
            caption.setBuddy(control);control.setAccessibleName(caption.text())
        floating_options=self.bar.settings.get('placement') in ('auto','floating')
        self.topmost.setText(label('Keep on top'));self.topmost.setVisible(floating_options);self.topmost_line.setVisible(floating_options)
        self.topmost.row.setVisible(floating_options);self.display_row.setVisible(floating_options);self.display_line.setVisible(floating_options)
        self.display_label.setText(label('Floating display'));self.display.setAccessibleName(label('Floating display'));self.refresh_displays()
        self.placement.items[2][0].setToolTip(label('Use floating mode when taskbar space is unavailable.'))
        self.transparency.blockSignals(True);self.transparency.setValue(self.bar.settings.get('capsule_transparency',0));self.transparency.blockSignals(False);self.transparency_value.setText(f'{self.transparency.value()}%')
        for key,source in DISPLAY_LABELS.items():self.checks[key].setText(label(source))
        self.rotation.setText(label('Rotate left-side indicators'));self.hover.setText(label('Open panels on hover'));self.login.setText(label('Start at Windows sign-in'))
        self.notify_input.setText(label('Notify when input is needed'))
        self.login.blockSignals(True);self.login.setChecked(startup.enabled());self.login.blockSignals(False)
        self.status_key=None;self.refresh_status()

    def refresh_status(self):
        label=self.bar.label;data=self.bar.provider.get()
        self.refresh_displays()
        errors=tuple(sorted(self.bar.settings_errors))
        fallback=self.bar.settings.get('placement')=='auto' and self.bar.floating
        key=(fallback,errors,self.bar.language,data.get('quota_error'),bool(data.get('quota')),data.get('error'),data.get('loading'),self.bar.placement_unavailable,self.bar.updater.message,self.bar.updater.busy,(self.bar.updater.release or {}).get('version'))
        if key==getattr(self,'status_key',None):return
        self.status_key=key
        self.feedback.setText('\n'.join(label(error) for error in errors));self.feedback.setVisible(bool(errors))
        if data.get('quota_error'):message='Showing the last available quota.' if data.get('quota') else 'Quota unavailable. Try again later.'
        elif data.get('error'):message='Some data is unavailable. Showing the last available records.'
        elif data.get('loading'):message='Connecting to Codex…'
        elif fallback:message='Taskbar space unavailable. Using floating mode.'
        elif self.bar.placement_unavailable and any(self.bar.settings.get(k) for k in DISPLAY_LABELS):message='Not enough taskbar space. Settings are available in the system tray.'
        else:message='Connected to Codex'
        self.connection.setText(label(message));self.update_button.setText(label(self.bar.updater.message,version=(self.bar.updater.release or {}).get('version','')));self.update_button.setEnabled(not self.bar.updater.busy)

    def refresh_displays(self):
        screens=QApplication.screens();position=self.bar.settings.get('floating_position') or {}
        selected=self.bar.settings.get('floating_display',position.get('screen'))
        entries=[(screen.name(),round(screen.size().width()*screen.devicePixelRatio()),round(screen.size().height()*screen.devicePixelRatio())) for screen in screens]
        key=(self.bar.language,selected,tuple(entries))
        if key==self.display_key:return
        self.display_key=key;self.display.blockSignals(True);self.display.clear();self.display.addItem(self.bar.label('Primary display'),None)
        for index,(name,width,height) in enumerate(entries):
            self.display.addItem(f'{index+1} · {width} × {height}',name)
            description=self.bar.label('Display {number}',number=index+1)+f' · {width} × {height}'
            self.display.setItemData(index+1,description,Qt.ItemDataRole.ToolTipRole);self.display.setItemData(index+1,description,Qt.ItemDataRole.AccessibleTextRole)
        if selected and selected not in [entry[0] for entry in entries]:
            self.display.addItem(self.bar.label('Display unavailable'),selected);self.display.model().item(self.display.count()-1).setEnabled(False)
        self.display.setCurrentIndex(max(0,self.display.findData(selected)));self.display.blockSignals(False)
        self.display.setToolTip(self.bar.label('The saved display is disconnected. Using primary temporarily.') if selected and selected not in [entry[0] for entry in entries] else self.display.currentText())
