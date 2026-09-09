"""Native settings and tray entry; deliberately no general layout editor."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap, QColor, QPen
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QPushButton, QComboBox
from .build_info import APP_NAME, VERSION
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
            QComboBox {background:#303843;color:#bac5d2;border:0;border-radius:6px;padding:7px 12px;}
            QComboBox QAbstractItemView {background:#303843;color:#bac5d2;selection-background-color:#3b4552;}''')
        layout = QVBoxLayout(self); layout.setContentsMargins(24, 20, 24, 20); layout.setSpacing(8)
        language_row=QHBoxLayout();self.language_label=QLabel();language_row.addWidget(self.language_label)
        self.language=QComboBox();self.language.addItem('English','en');self.language.addItem('简体中文','zh-CN')
        self.language.setCurrentIndex(self.language.findData(bar.settings.get('language','en')))
        self.language.currentIndexChanged.connect(lambda:bar.set_language(self.language.currentData()))
        language_row.addStretch();language_row.addWidget(self.language);layout.addLayout(language_row)
        self.title = QLabel(); self.title.setStyleSheet('font-size:16px;color:#eef2f7;'); layout.addWidget(self.title)
        self.checks = {}
        for key, label in DISPLAY_LABELS.items():
            check = QCheckBox(); check.setChecked(bar.settings[key]); layout.addWidget(check)
            check.toggled.connect(lambda checked, key=key: bar.set_display(key, checked)); self.checks[key] = check
        layout.addSpacing(8)
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
        for key,source in DISPLAY_LABELS.items():self.checks[key].setText(label(source))
        self.hover.setText(label('Open panels on hover'));self.login.setText(label('Start at Windows sign-in'))
        self.login.blockSignals(True);self.login.setChecked(startup.enabled());self.login.blockSignals(False)
        data = self.bar.provider.get()
        if data.get('quota_error'): message = 'Showing the last available quota.' if data.get('quota') else 'Quota unavailable. Try again later.'
        elif data.get('error'): message = 'Some data is unavailable. Showing the last available records.'
        elif data.get('loading'): message = 'Connecting to Codex…'
        elif self.bar.placement_unavailable: message = 'Not enough taskbar space. Settings are available in the system tray.'
        else: message = 'Settings remain available in the system tray when all displays are off.'
        self.connection.setText(label(message))
        self.update_button.setText(label(self.bar.updater.message,version=(self.bar.updater.release or {}).get('version','')))
        self.update_button.setEnabled(not self.bar.updater.busy)
