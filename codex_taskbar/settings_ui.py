"""Native settings and tray entry; deliberately no general layout editor."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap, QColor, QPen
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QCheckBox, QPushButton
from .build_info import APP_NAME, VERSION
from . import startup

DISPLAY_LABELS = {
    'show_week': '周额度', 'show_session': '5 小时额度（可用时显示）',
    'show_countdown': '重置倒计时', 'show_daily': '今日额度消耗',
    'show_tasks': '任务轮播与计数',
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
        self.bar = bar; self.setFont(bar.font); self.setWindowTitle(f'设置 · {APP_NAME}')
        self.setWindowIcon(app_icon()); self.setMinimumWidth(340)
        self.setStyleSheet('''QDialog {background:#242930;color:#bac5d2;}
            QLabel,QCheckBox {color:#bac5d2;} QCheckBox {spacing:10px;padding:7px 0;}
            QPushButton {background:#303843;color:#bac5d2;border:0;border-radius:6px;padding:9px;}
            QPushButton:hover {background:#3b4552;}''')
        layout = QVBoxLayout(self); layout.setContentsMargins(24, 20, 24, 20); layout.setSpacing(8)
        title = QLabel('显示'); title.setStyleSheet('font-size:16px;color:#eef2f7;'); layout.addWidget(title)
        self.checks = {}
        for key, label in DISPLAY_LABELS.items():
            check = QCheckBox(label); check.setChecked(bar.settings[key]); layout.addWidget(check)
            check.toggled.connect(lambda checked, key=key: bar.set_display(key, checked)); self.checks[key] = check
        layout.addSpacing(8)
        self.hover = QCheckBox('悬停打开面板');self.hover.setChecked(bar.settings.get('hover_panels',False))
        self.hover.toggled.connect(bar.set_hover_panels);layout.addWidget(self.hover)
        self.login = QCheckBox('登录 Windows 后启动'); self.login.setChecked(startup.enabled())
        self.login.toggled.connect(bar.set_startup); layout.addWidget(self.login)
        self.connection = QLabel(); self.connection.setWordWrap(True)
        self.connection.setStyleSheet('color:#8797aa;font-size:12px;'); layout.addWidget(self.connection)
        layout.addSpacing(8)
        self.update_button = QPushButton(); self.update_button.clicked.connect(bar.update_clicked); layout.addWidget(self.update_button)
        version = QLabel(f'{APP_NAME}  {VERSION}'); version.setStyleSheet('color:#8797aa;font-size:12px;'); layout.addWidget(version)
        self.refresh()

    def refresh(self):
        self.login.blockSignals(True);self.login.setChecked(startup.enabled());self.login.blockSignals(False)
        data = self.bar.provider.get()
        if data.get('quota_error'): message = '额度暂未更新，当前显示上次有效记录。' if data.get('quota') else '暂时无法读取额度，请稍后再试。'
        elif data.get('error'): message = '部分数据暂未更新，当前保留已读取的内容。'
        elif data.get('loading'): message = '正在连接 Codex…'
        elif self.bar.placement_unavailable: message = '任务栏左侧空间不足，已收起到系统托盘。'
        else: message = '所有显示关闭后，仍可从系统托盘打开设置。'
        self.connection.setText(message)
        self.update_button.setText(self.bar.updater.message); self.update_button.setEnabled(not self.bar.updater.busy)
