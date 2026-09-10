"""Native settings and tray entry; deliberately no general layout editor."""
from pathlib import Path
from PySide6.QtCore import Qt,QSize,QRectF
from PySide6.QtGui import QIcon, QPainter, QPixmap, QColor, QPen,QFontMetricsF
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QPushButton, QComboBox, QListView, QSlider, QScrollArea, QWidget, QFrame,QTabWidget,QTabBar
from .build_info import APP_NAME, VERSION
from .i18n import LANGUAGE_NAMES
from . import startup
from .motion import Spring

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
        if self.isVisible() and getattr(getattr(self.window(),'bar',None),'motion_enabled',True):self.motion.retarget(float(checked))
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


class SettingsTabBar(QTabBar):
    def wheelEvent(self,event):event.ignore()


class SettingsDialog(QDialog):
    def __init__(self,bar):
        super().__init__();self.bar=bar;self.setFont(bar.font);self.setWindowIcon(app_icon());self.setMinimumSize(460,280)
        self.setStyleSheet('''QDialog,QScrollArea,QScrollArea>QWidget>QWidget{background:#222830;color:#bac5d2;}
            QLabel{color:#bac5d2;} QFrame#settingsCard{background:#2b323c;border:1px solid #39434f;border-radius:8px;}
            QFrame#settingsLine{background:#3b4551;max-height:1px;border:0;}
            QTabWidget::pane{border:0;} QTabBar::tab{color:#8797aa;background:transparent;padding:10px 18px;border-bottom:2px solid transparent;}
            QTabBar::tab:selected{color:#c7d8ed;border-bottom-color:#79b6f5;} QTabBar::tab:hover{background:#2b333e;}
            QPushButton{background:#3a5067;color:#d7e4f3;border:0;border-radius:5px;padding:8px 12px;}
            QPushButton:hover{background:#45617b;} QPushButton:disabled{background:#323b46;color:#8797aa;}
            QPushButton:pressed{background:#2e4358;}
            QComboBox{background:#343e4b;color:#bac5d2;border:1px solid #465262;border-radius:5px;padding:6px 27px 6px 10px;}
            QComboBox:focus{border-color:#79b6f5;} QComboBox::drop-down{width:24px;border:0;}
            QComboBox::down-arrow{image:url(__CHEVRON__);width:12px;height:8px;}
            QComboBox QAbstractItemView{background:#303843;color:#bac5d2;selection-background-color:#405166;border:1px solid #465262;outline:0;padding:4px;}
            QSlider::groove:horizontal{height:4px;background:#526174;border-radius:2px;}
            QSlider::handle:horizontal{width:12px;margin:-4px 0;background:#8fbdec;border-radius:6px;}
            QScrollBar:vertical{background:#222830;width:6px;margin:4px 0;}
            QScrollBar::handle:vertical{background:#536170;min-height:28px;border-radius:3px;}
            QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}
            QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical{background:none;}'''.replace('__CHEVRON__',(Path(__file__).resolve().parents[1]/'assets/icons/chevron-down.svg').as_posix()))
        outer=QVBoxLayout(self);outer.setContentsMargins(12,8,12,12);self.tabs=QTabWidget();outer.addWidget(self.tabs)
        self.tabs.setTabBar(SettingsTabBar())
        self.tabs.tabBar().setUsesScrollButtons(False);self.tabs.tabBar().setElideMode(Qt.TextElideMode.ElideNone)
        self.pages=[]
        for _ in range(3):
            scroll=QScrollArea();scroll.setFrameShape(QFrame.Shape.NoFrame);scroll.setWidgetResizable(True)
            body=QWidget();page=QVBoxLayout(body);page.setContentsMargins(8,16,8,8);page.setSpacing(12)
            page.setSizeConstraint(QVBoxLayout.SizeConstraint.SetMinimumSize);scroll.setWidget(body);self.pages.append(scroll);self.tabs.addTab(scroll,'')
        appearance=self.pages[0].widget().layout();indicators=self.pages[1].widget().layout();general=self.pages[2].widget().layout()
        def card(parent):
            frame=QFrame();frame.setObjectName('settingsCard');items=QVBoxLayout(frame);items.setContentsMargins(14,6,14,6);items.setSpacing(0);parent.addWidget(frame);return items
        def line(parent):
            result=QFrame();result.setObjectName('settingsLine');result.setFixedHeight(1);parent.addWidget(result);return result
        def row(parent,label,control):
            widget=QWidget();layout=QHBoxLayout(widget);layout.setContentsMargins(0,5,0,5);widget.setMinimumHeight(42)
            layout.addWidget(label);layout.addStretch();layout.addWidget(control);parent.addWidget(widget)
        def combo(values,current,callback):
            control=Choice();control.setView(QListView());control.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
            for text,value in values:control.addItem(text,value)
            control.setCurrentIndex(control.findData(current));control.currentIndexChanged.connect(lambda:callback(control.currentData()));return control
        def toggle(parent):
            container=QWidget();container.setMinimumHeight(42);items=QHBoxLayout(container);items.setContentsMargins(0,0,0,0)
            caption=QLabel();caption.setTextFormat(Qt.TextFormat.PlainText);caption.setWordWrap(True);caption.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
            control=Toggle(caption);control.row=container;caption.setBuddy(control)
            items.addWidget(caption,1);items.addSpacing(16);items.addWidget(control);parent.addWidget(container);return control
        position=card(appearance);self.placement_label=QLabel()
        self.placement=combo([('','taskbar'),('','floating')],bar.settings.get('placement','taskbar'),bar.set_placement)
        row(position,self.placement_label,self.placement);self.topmost_line=line(position)
        self.topmost=toggle(position);self.topmost.setChecked(bar.settings.get('floating_topmost',True));self.topmost.toggled.connect(bar.set_floating_topmost)
        colors=card(appearance);self.capsule_label=QLabel()
        self.capsule=combo([('','dark'),('','light')],bar.settings.get('capsule_theme','dark'),bar.set_capsule_theme);row(colors,self.capsule_label,self.capsule);line(colors)
        self.transparency_label=QLabel();opacity=QWidget();opacity_row=QHBoxLayout(opacity);opacity_row.setContentsMargins(0,0,0,0)
        self.transparency=ValueSlider(Qt.Orientation.Horizontal);self.transparency.setRange(0,100);self.transparency.setMinimumWidth(150)
        self.transparency.setValue(bar.settings.get('capsule_transparency',0));self.transparency_value=QLabel();self.transparency_value.setMinimumWidth(34);self.transparency_value.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter)
        self.transparency.valueChanged.connect(lambda value:bar.set_capsule_transparency(value,save=not self.transparency.isSliderDown()))
        self.transparency.valueChanged.connect(lambda value:self.transparency_value.setText(f'{value}%'));self.transparency.sliderReleased.connect(bar.save_settings)
        opacity_row.addWidget(self.transparency);opacity_row.addWidget(self.transparency_value);row(colors,self.transparency_label,opacity);appearance.addStretch()
        self.title=QLabel();self.title.setStyleSheet('color:#8797aa;');indicators.addWidget(self.title)
        visible=card(indicators);self.checks={}
        for number,key in enumerate(DISPLAY_LABELS):
            if number:line(visible)
            check=toggle(visible);check.setChecked(bar.settings[key]);check.toggled.connect(lambda checked,key=key:bar.set_display(key,checked));self.checks[key]=check
        behavior=card(indicators);self.rotation=toggle(behavior);self.rotation.setChecked(bar.settings.get('rotate_quotas',False));self.rotation.toggled.connect(bar.set_quota_rotation);line(behavior)
        self.hover=toggle(behavior);self.hover.setChecked(bar.settings.get('hover_panels',False));self.hover.toggled.connect(bar.set_hover_panels);indicators.addStretch()
        localization=card(general);self.language_label=QLabel();self.language=combo([(name,code) for code,name in LANGUAGE_NAMES],bar.settings.get('language','en'),bar.set_language);row(localization,self.language_label,self.language)
        startup_card=card(general);self.login=toggle(startup_card);self.login.setChecked(startup.enabled());self.login.toggled.connect(bar.set_startup)
        updates=card(general);self.update_label=QLabel();self.update_button=QPushButton();self.update_button.setAutoDefault(False);self.update_button.clicked.connect(bar.update_clicked);row(updates,self.update_label,self.update_button)
        self.connection=QLabel();self.connection.setWordWrap(True);self.connection.setStyleSheet('color:#8797aa;font-size:12px;');general.addWidget(self.connection)
        general.addStretch();version=QLabel(f'{APP_NAME}  {VERSION}');version.setStyleSheet('color:#748497;font-size:12px;');general.addWidget(version)
        self.refresh();self.resize(self.sizeHint())

    @property
    def scroll_area(self):return self.pages[self.tabs.currentIndex()]
    @property
    def body(self):return self.scroll_area.widget()
    def sizeHint(self):return QSize(520,min(460,max(280,self.screen().availableGeometry().height()-48)))

    def refresh(self):
        label=self.bar.label;self.setWindowTitle(f'{label("Settings")} · {APP_NAME}')
        for i,name in enumerate(('Appearance','Indicators','General')):self.tabs.setTabText(i,label(name))
        self.language_label.setText(label('Language'));self.title.setText(label('Display'));self.update_label.setText(label('Updates'))
        for control,key,options in ((self.language,'language',None),(self.placement,'placement',('Taskbar','Floating')),(self.capsule,'capsule_theme',('Dark','Light'))):
            control.blockSignals(True)
            if options:
                for i,value in enumerate(options):control.setItemText(i,label(value))
            control.setCurrentIndex(max(0,control.findData(self.bar.settings.get(key,{'language':'en','placement':'taskbar','capsule_theme':'dark'}[key]))));control.blockSignals(False)
        self.placement_label.setText(label('Placement'));self.capsule_label.setText(label('Capsule'));self.transparency_label.setText(label('Transparency'))
        self.topmost.setText(label('Keep on top'));self.topmost.setVisible(self.bar.floating);self.topmost_line.setVisible(self.bar.floating)
        self.topmost.row.setVisible(self.bar.floating)
        self.transparency.blockSignals(True);self.transparency.setValue(self.bar.settings.get('capsule_transparency',0));self.transparency.blockSignals(False);self.transparency_value.setText(f'{self.transparency.value()}%')
        for key,source in DISPLAY_LABELS.items():self.checks[key].setText(label(source))
        self.rotation.setText(label('Rotate left-side indicators'));self.hover.setText(label('Open panels on hover'));self.login.setText(label('Start at Windows sign-in'))
        self.login.blockSignals(True);self.login.setChecked(startup.enabled());self.login.blockSignals(False)
        self.status_key=None;self.refresh_status()

    def refresh_status(self):
        label=self.bar.label;data=self.bar.provider.get()
        key=(self.bar.language,data.get('quota_error'),bool(data.get('quota')),data.get('error'),data.get('loading'),self.bar.placement_unavailable,self.bar.updater.message,self.bar.updater.busy,(self.bar.updater.release or {}).get('version'))
        if key==getattr(self,'status_key',None):return
        self.status_key=key
        if data.get('quota_error'):message='Showing the last available quota.' if data.get('quota') else 'Quota unavailable. Try again later.'
        elif data.get('error'):message='Some data is unavailable. Showing the last available records.'
        elif data.get('loading'):message='Connecting to Codex…'
        elif self.bar.placement_unavailable and any(self.bar.settings.get(k) for k in DISPLAY_LABELS):message='Not enough taskbar space. Settings are available in the system tray.'
        else:message='Connected to Codex'
        self.connection.setText(label(message));self.update_button.setText(label(self.bar.updater.message,version=(self.bar.updater.release or {}).get('version','')));self.update_button.setEnabled(not self.bar.updater.busy)
