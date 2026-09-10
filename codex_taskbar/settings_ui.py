"""Native settings and tray entry; deliberately no general layout editor."""
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap, QColor, QPen
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QPushButton, QComboBox, QListView, QSlider
from .build_info import APP_NAME, VERSION
from .i18n import LANGUAGE_NAMES
from . import startup

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


class SettingsDialog(QDialog):
    def __init__(self, bar):
        super().__init__()
        self.bar = bar; self.setFont(bar.font)
        self.setWindowIcon(app_icon()); self.setMinimumWidth(340)
        self.setStyleSheet('''QDialog {background:#242930;color:#bac5d2;}
            QLabel,QCheckBox {color:#bac5d2;} QCheckBox {spacing:10px;padding:7px 0;}
            QPushButton {background:#303843;color:#bac5d2;border:0;border-radius:6px;padding:9px;}
            QPushButton:hover {background:#3b4552;}
            QComboBox {background:#303843;color:#bac5d2;border:1px solid transparent;border-radius:6px;padding:6px 26px 6px 11px;}
            QComboBox:hover {background:#35404c;}
            QComboBox:focus {border-color:#708aa8;}
            QComboBox::drop-down {subcontrol-origin:padding;subcontrol-position:top right;width:24px;border:0;background:transparent;}
            QComboBox::down-arrow {image:url(__CHEVRON__);width:12px;height:8px;}
            QComboBox QAbstractItemView {background:#303843;color:#bac5d2;border:1px solid #414b58;padding:4px;outline:0;}
            QComboBox QAbstractItemView::item {min-height:28px;padding:2px 8px;border-radius:4px;}
            QComboBox QAbstractItemView::item:selected {background:#405166;color:#dce5ef;}
            QSlider::groove:horizontal {height:4px;background:#475361;border-radius:2px;}
            QSlider::handle:horizontal {width:12px;margin:-4px 0;background:#8fbdec;border-radius:6px;}'''.replace(
                '__CHEVRON__',(Path(__file__).resolve().parents[1]/'assets/icons/chevron-down.svg').as_posix()))
        layout = QVBoxLayout(self); layout.setContentsMargins(24, 20, 24, 20); layout.setSpacing(8)
        language_row=QHBoxLayout();self.language_label=QLabel();language_row.addWidget(self.language_label)
        self.language=QComboBox()
        for code,name in LANGUAGE_NAMES:self.language.addItem(name,code)
        self.language.setView(QListView())
        self.language.setCurrentIndex(self.language.findData(bar.settings.get('language','en')))
        self.language.currentIndexChanged.connect(lambda:bar.set_language(self.language.currentData()))
        language_row.addStretch();language_row.addWidget(self.language);layout.addLayout(language_row)
        theme_row=QHBoxLayout();self.capsule_label=QLabel();theme_row.addWidget(self.capsule_label)
        self.capsule=QComboBox();self.capsule.addItem('','dark');self.capsule.addItem('','light');self.capsule.setView(QListView())
        self.capsule.setCurrentIndex(self.capsule.findData(bar.settings.get('capsule_theme','dark')))
        self.capsule.currentIndexChanged.connect(lambda:bar.set_capsule_theme(self.capsule.currentData()))
        theme_row.addStretch();theme_row.addWidget(self.capsule);layout.addLayout(theme_row)
        opacity_row=QHBoxLayout();self.transparency_label=QLabel();opacity_row.addWidget(self.transparency_label)
        self.transparency=QSlider(Qt.Orientation.Horizontal);self.transparency.setRange(0,100)
        self.transparency.setValue(bar.settings.get('capsule_transparency',0))
        self.transparency.valueChanged.connect(lambda value:bar.set_capsule_transparency(value,save=not self.transparency.isSliderDown()))
        self.transparency.sliderReleased.connect(bar.save_settings)
        self.transparency_value=QLabel();self.transparency_value.setMinimumWidth(36);self.transparency_value.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.transparency.valueChanged.connect(lambda value:self.transparency_value.setText(f'{value}%'))
        opacity_row.addWidget(self.transparency,1);opacity_row.addWidget(self.transparency_value);layout.addLayout(opacity_row)
        self.title = QLabel(); self.title.setStyleSheet('font-size:16px;color:#eef2f7;'); layout.addWidget(self.title)
        self.checks = {}
        for key, label in DISPLAY_LABELS.items():
            check = QCheckBox(); check.setChecked(bar.settings[key]); layout.addWidget(check)
            check.toggled.connect(lambda checked, key=key: bar.set_display(key, checked)); self.checks[key] = check
        layout.addSpacing(8)
        self.rotation=QCheckBox();self.rotation.setChecked(bar.settings.get('rotate_quotas',False))
        self.rotation.toggled.connect(bar.set_quota_rotation);layout.addWidget(self.rotation)
        self.hover = QCheckBox();self.hover.setChecked(bar.settings.get('hover_panels',False))
        self.hover.toggled.connect(bar.set_hover_panels);layout.addWidget(self.hover)
        self.login = QCheckBox(); self.login.setChecked(startup.enabled())
        self.login.toggled.connect(bar.set_startup); layout.addWidget(self.login)
        self.connection = QLabel(); self.connection.setWordWrap(True)
        self.connection.setStyleSheet('color:#8797aa;font-size:12px;'); layout.addWidget(self.connection)
        layout.addSpacing(8)
        self.update_button = QPushButton(); self.update_button.clicked.connect(bar.update_clicked); layout.addWidget(self.update_button)
        version = QLabel(f'{APP_NAME}  {VERSION}'); version.setStyleSheet('color:#8797aa;font-size:12px;'); layout.addWidget(version)
        self.refresh()

    def refresh(self):
        label=self.bar.label
        self.setWindowTitle(f'{label("Settings")} · {APP_NAME}')
        self.language_label.setText(label('Language'));self.title.setText(label('Display'))
        self.language.blockSignals(True)
        self.language.setCurrentIndex(self.language.findData(self.bar.settings.get('language','en')))
        self.language.blockSignals(False)
        self.capsule_label.setText(label('Capsule'));self.transparency_label.setText(label('Transparency'))
        self.capsule.blockSignals(True)
        self.capsule.setItemText(0,label('Dark'));self.capsule.setItemText(1,label('Light'))
        self.capsule.setCurrentIndex(self.capsule.findData(self.bar.settings.get('capsule_theme','dark')));self.capsule.blockSignals(False)
        self.transparency.blockSignals(True);self.transparency.setValue(self.bar.settings.get('capsule_transparency',0));self.transparency.blockSignals(False)
        self.transparency_value.setText(f'{self.transparency.value()}%')
        for key,source in DISPLAY_LABELS.items():self.checks[key].setText(label(source))
        self.rotation.setText(label('Rotate left-side indicators'))
        self.hover.setText(label('Open panels on hover'));self.login.setText(label('Start at Windows sign-in'))
        self.login.blockSignals(True);self.login.setChecked(startup.enabled());self.login.blockSignals(False)
        self.status_key=None;self.refresh_status()

    def refresh_status(self):
        label=self.bar.label
        data = self.bar.provider.get()
        key=(self.bar.language,data.get('quota_error'),bool(data.get('quota')),data.get('error'),data.get('loading'),
             self.bar.placement_unavailable,self.bar.updater.message,self.bar.updater.busy,(self.bar.updater.release or {}).get('version'))
        if key==getattr(self,'status_key',None):return
        self.status_key=key
        if data.get('quota_error'): message = 'Showing the last available quota.' if data.get('quota') else 'Quota unavailable. Try again later.'
        elif data.get('error'): message = 'Some data is unavailable. Showing the last available records.'
        elif data.get('loading'): message = 'Connecting to Codex…'
        elif self.bar.placement_unavailable: message = 'Not enough taskbar space. Settings are available in the system tray.'
        else: message = 'Settings remain available in the system tray when all displays are off.'
        self.connection.setText(label(message))
        self.update_button.setText(label(self.bar.updater.message,version=(self.bar.updater.release or {}).get('version','')))
        self.update_button.setEnabled(not self.bar.updater.busy)
