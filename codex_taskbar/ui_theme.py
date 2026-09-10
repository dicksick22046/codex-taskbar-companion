"""Shared desktop surfaces and explicit choice controls."""
from PySide6.QtCore import Qt,Signal,QRectF,QSize,QEvent
from PySide6.QtGui import QColor,QPainter,QPen,QFont
from PySide6.QtWidgets import QWidget,QHBoxLayout,QPushButton,QButtonGroup,QListWidget,QStyledItemDelegate,QStyle
from .motion import Spring

BACKGROUND='#222429'
SIDEBAR='#1a1c21'
CARD='#2c2f35'
TEXT='#e1e5ec'
SECONDARY='#a0a7b4'
BLUE='#82b6ff'


def typeface(base,size,weight=QFont.Weight.Normal):
    font=QFont(base);font.setPointSizeF(size);font.setWeight(weight);return font


class Segments(QWidget):
    currentIndexChanged=Signal(int)
    def __init__(self,parent=None):
        super().__init__(parent);self.items=[];self.index=-1;self.position=0.;self.keyboard_action=False
        self.group=QButtonGroup(self);self.group.setExclusive(True)
        self.layout_=QHBoxLayout(self);self.layout_.setContentsMargins(3,3,3,3);self.layout_.setSpacing(0)
        self.motion=Spring(self,response=.16);self.motion.changed.connect(self.move_selection)
        self.setFixedHeight(36)
    def addItem(self,text,value):
        button=QPushButton(text,self);button.setCheckable(True);button.setAutoDefault(False);button.setMinimumWidth(72);button.setFixedHeight(30)
        button.setCursor(Qt.CursorShape.PointingHandCursor);button.setStyleSheet('QPushButton{background:transparent;border:1px solid transparent;border-radius:6px;color:#a0a7b4;padding:0 12px;} QPushButton:checked{color:#f4f7fb;} QPushButton:hover{color:#ffffff;} QPushButton:focus{border-color:#82b6ff;}')
        index=len(self.items);self.items.append((button,value));self.group.addButton(button);self.layout_.addWidget(button)
        button.clicked.connect(lambda checked=False,i=index:self.setCurrentIndex(i))
        button.installEventFilter(self)
    def eventFilter(self,watched,event):
        if event.type()==QEvent.Type.KeyPress:self.keyboard_action=True
        elif event.type()==QEvent.Type.MouseButtonPress:self.keyboard_action=False
        return super().eventFilter(watched,event)
    def currentIndex(self):return self.index
    def currentData(self):return self.items[self.index][1] if self.index>=0 else None
    def currentText(self):return self.items[self.index][0].text() if self.index>=0 else ''
    def findData(self,value):return next((i for i,(_,data) in enumerate(self.items) if data==value),-1)
    def setItemText(self,index,text):self.items[index][0].setText(text);self.updateGeometry()
    def setCurrentIndex(self,index):
        if not 0<=index<len(self.items):return
        changed=index!=self.index;self.index=index;self.items[index][0].setChecked(True)
        target=float(self.items[index][0].x())
        if not changed:return
        if changed and self.isVisible() and not self.keyboard_action and getattr(getattr(self.window(),'bar',None),'motion_enabled',True):self.motion.retarget(target)
        else:self.motion.snap(target)
        if changed:self.currentIndexChanged.emit(index)
    def move_selection(self,value):self.position=float(value);self.update()
    def resizeEvent(self,event):
        super().resizeEvent(event)
        if self.index>=0:self.motion.snap(float(self.items[self.index][0].x()))
    def hideEvent(self,event):self.motion.snap(float(self.items[self.index][0].x()) if self.index>=0 else 0.);super().hideEvent(event)
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor('#41454e'),.7));p.setBrush(QColor('#1e2025'));p.drawRoundedRect(QRectF(self.rect()).adjusted(.5,.5,-.5,-.5),9,9)
        if self.index>=0:
            button=self.items[self.index][0];p.setPen(Qt.PenStyle.NoPen);p.setBrush(QColor('#46566f'))
            p.drawRoundedRect(QRectF(self.position,3,button.width(),30),6,6)
        p.end()


class NavigationDelegate(QStyledItemDelegate):
    def paint(self,p,option,index):
        nav=self.parent();box=QRectF(option.rect).adjusted(0,2,0,-2);row=index.row()
        p.save();p.setRenderHint(QPainter.RenderHint.Antialiasing)
        active=row==nav.currentRow();strength=nav.weights[row] if row<len(nav.weights) else 0.
        if strength or option.state&QStyle.StateFlag.State_MouseOver:
            color=QColor('#3566a1' if strength else '#2b2e36');color.setAlphaF(strength if strength else 1.)
            p.setPen(Qt.PenStyle.NoPen);p.setBrush(color);p.drawRoundedRect(box,7,7)
        if option.state&QStyle.StateFlag.State_HasFocus:
            p.setPen(QPen(QColor(BLUE),1));p.setBrush(Qt.BrushStyle.NoBrush);p.drawRoundedRect(box.adjusted(1,1,-1,-1),6,6)
        p.setFont(option.font);p.setPen(QColor('#f5f7fa' if active else SECONDARY))
        p.drawText(box.adjusted(12,0,-8,0),Qt.AlignmentFlag.AlignVCenter|Qt.AlignmentFlag.AlignLeft,index.data());p.restore()
    def sizeHint(self,option,index):return QSize(146,40)


class Navigation(QListWidget):
    def __init__(self,parent=None):
        super().__init__(parent);self.weights=[];self.motions=[];self.keyboard_navigation=False
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setMouseTracking(True);self.setItemDelegate(NavigationDelegate(self));self.setSpacing(2)
        self.currentRowChanged.connect(self.select_row)
    def set_weight(self,index,value):self.weights[index]=max(0.,min(1.,value));self.viewport().update()
    def select_row(self,row):
        while len(self.motions)<self.count():
            index=len(self.motions);motion=Spring(self,response=.16);motion.changed.connect(lambda value,i=index:self.set_weight(i,value));self.weights.append(0.);self.motions.append(motion)
        animate=self.isVisible() and not self.keyboard_navigation and getattr(getattr(self.window(),'bar',None),'motion_enabled',True)
        for index,motion in enumerate(self.motions):
            if animate:motion.retarget(float(index==row))
            else:motion.snap(float(index==row))
    def keyPressEvent(self,event):
        self.keyboard_navigation=True
        try:super().keyPressEvent(event)
        finally:self.keyboard_navigation=False
    def wheelEvent(self,event):event.ignore()
    def hideEvent(self,event):
        for index,motion in enumerate(self.motions):motion.snap(float(index==self.currentRow()))
        super().hideEvent(event)


CONTROLS='''
QLabel{color:#e1e5ec;}
QFrame#settingsCard{background:#2c2f35;border:1px solid #3b3f48;border-radius:11px;}
QFrame#settingsLine{background:#3b3f48;max-height:1px;border:0;}
QPushButton{background:#426992;color:#f1f5fa;border:1px solid transparent;border-radius:7px;padding:7px 12px;}
QPushButton:hover{background:#4e7aa8;} QPushButton:pressed{background:#345778;}
QPushButton:focus{border-color:#a0caff;} QPushButton:disabled{background:#343740;color:#929aa8;}
QComboBox{background:#383c45;color:#e1e5ec;border:1px solid #4a505b;border-radius:7px;padding:6px 28px 6px 12px;}
QComboBox:hover{border-color:#6a7484;} QComboBox:focus{border-color:#82b6ff;}
QComboBox::drop-down{width:26px;border:0;}
QComboBox::down-arrow{image:url(__CHEVRON__);width:12px;height:8px;}
QComboBox QAbstractItemView{background:#30343c;color:#e1e5ec;selection-background-color:#426992;border:1px solid #4a505b;outline:0;padding:5px;}
QSlider::groove:horizontal{height:4px;background:#505866;border-radius:2px;}
QSlider::sub-page:horizontal{background:#79afea;border-radius:2px;}
QSlider::handle:horizontal{width:14px;margin:-5px 0;background:#e8eef7;border:1px solid #cbd7e6;border-radius:7px;}
QSlider::handle:horizontal:focus{border-color:#82b6ff;}
QScrollBar:vertical{background:transparent;width:6px;margin:4px 0;}
QScrollBar::handle:vertical{background:#59616f;min-height:28px;border-radius:3px;}
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}
QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical{background:none;}
'''
