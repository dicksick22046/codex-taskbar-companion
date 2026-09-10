"""Local task finding over the Provider catalog; no API calls or stored search history."""
from datetime import datetime
from html import escape
from pathlib import Path
import math
from PySide6.QtCore import Qt,QAbstractListModel,QModelIndex,QSize,QRectF,QEvent
from PySide6.QtGui import QColor,QFontMetricsF
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLineEdit,QComboBox,QListView,QLabel,QStyledItemDelegate,QAbstractItemView,QStyle
from .app import face,text,project_tag,side_tag,side_tag_width,BLUE,ACCENT,AMBER,FAILED,MUTED
from .i18n import project_label,task_title
from .tasks import task_rows,task_category,CATEGORY_LABELS


def timestamp(value):
    try:
        result=datetime.fromisoformat(value).timestamp() if isinstance(value,str) else float(value or 0)
        return result if math.isfinite(result) and result>0 and not isinstance(value,bool) else 0.
    except (ValueError,TypeError,OverflowError,OSError):return 0.


def finder_rows(data,language):
    states={task['id']:task for task in task_rows(data)}
    catalog={task['id']:task for task in data.get('catalog') or []}
    # Freshly started work can precede the next catalog refresh.
    for task in states.values():catalog.setdefault(task['id'],task)
    rows=[]
    for task in catalog.values():
        state=states.get(task['id']);kind=task_category(state) if state else ''
        at=max(timestamp(task.get('updated_at')),timestamp((state or {}).get('activity_at')))
        try:date=datetime.fromtimestamp(at).astimezone() if at else None
        except (ValueError,OverflowError,OSError):date=None
        now=datetime.now().astimezone()
        stamp=date.strftime('%H:%M' if date.date()==now.date() else '%m.%d %H:%M' if date.year==now.year else '%Y.%m.%d') if date else '—'
        project=task.get('project') or '';title=task_title(task,language)
        rows.append({'id':task['id'],'title':title,'project':project,'project_label':project_label(project,language),
                     'kind':kind if kind!='recent' else '', 'side_chat':bool((state or {}).get('side_chat')),
                     'at':at,'stamp':stamp,'search':(project_label(project,language)+' '+title).casefold()})
    return sorted(rows,key=lambda row:(-row['at'],row['id']))


def filter_rows(rows,query='',project=None):
    terms=query.casefold().split()
    return [row for row in rows if (project is None or row['project']==project) and all(term in row['search'] for term in terms)]


class TaskModel(QAbstractListModel):
    def __init__(self,parent=None):super().__init__(parent);self.rows=[]
    def rowCount(self,parent=QModelIndex()):return 0 if parent.isValid() else len(self.rows)
    def data(self,index,role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0<=index.row()<len(self.rows):return None
        row=self.rows[index.row()]
        if role==Qt.ItemDataRole.UserRole:return row
        if role in (Qt.ItemDataRole.DisplayRole,Qt.ItemDataRole.AccessibleTextRole):return row['project_label']+' · '+row['title']
        if role==Qt.ItemDataRole.ToolTipRole:return '<qt>'+'<br>'.join(escape(row[k]) for k in ('project_label','title','stamp'))+'</qt>'

    def replace(self,rows):
        if rows==self.rows:return False
        self.beginResetModel();self.rows=rows;self.endResetModel();return True


class TaskDelegate(QStyledItemDelegate):
    def __init__(self,browser):super().__init__(browser);self.browser=browser
    def sizeHint(self,option,index):return QSize(1,40)
    def paint(self,p,option,index):
        row=index.data(Qt.ItemDataRole.UserRole);browser=self.browser;box=QRectF(option.rect);y=box.center().y()
        p.save();p.setClipRect(box);p.setRenderHint(p.RenderHint.Antialiasing)
        if option.state & (QStyle.StateFlag.State_Selected|QStyle.StateFlag.State_MouseOver):
            p.setPen(Qt.PenStyle.NoPen);p.setBrush(QColor('#303a47'));p.drawRoundedRect(box.adjusted(2,1,-2,-1),5,5)
        x=box.left()+12
        project_tag(p,x,y,row['project'],face(8),browser.project_width,browser.bar.language)
        x+=browser.project_width+12
        if row['side_chat']:x+=side_tag(p,x,y,browser.bar.language)+7
        right=box.right()-12;font=face(8);metrics=QFontMetricsF(font)
        text(p,right-metrics.horizontalAdvance(row['stamp']),y,row['stamp'],font,'#8797aa')
        status_right=right-browser.stamp_width-14
        status=browser.bar.label(CATEGORY_LABELS[row['kind']]) if row['kind'] else ''
        colors={'running':ACCENT,'unread':AMBER,'failed':FAILED,'stopped':'#8795a5'}
        if status:text(p,status_right-metrics.horizontalAdvance(status),y,status,font,colors[row['kind']])
        title_right=status_right-browser.status_width-14
        title=QFontMetricsF(face()).elidedText(row['title'],Qt.TextElideMode.ElideRight,max(0,title_right-x))
        text(p,x,y,title,face(),MUTED);p.restore()


class TaskView(QListView):
    def keyPressEvent(self,event):
        if event.key() in (Qt.Key.Key_Return,Qt.Key.Key_Enter):
            self.parent().open_selected();event.accept()
        else:super().keyPressEvent(event)


class TaskFinder(QDialog):
    def __init__(self,bar):
        super().__init__();self.bar=bar;self.rows=[];self.input_key=None;self.pressed_id=None
        self.setFont(bar.font);self.setMinimumSize(560,300);self.resize(740,min(490,self.screen().availableGeometry().height()-60))
        self.setStyleSheet('''QDialog,QListView{background:#242930;color:#bac5d2;} QLabel{color:#8797aa;}
            QLineEdit,QComboBox{background:#303843;color:#bac5d2;border:1px solid #414b58;border-radius:5px;padding:8px;}
            QComboBox{padding-right:26px;}
            QComboBox::drop-down{width:24px;border:0;}
            QComboBox::down-arrow{image:url(__CHEVRON__);width:12px;height:8px;}
            QLineEdit:focus{border-color:#708aa8;} QListView{border:0;outline:0;}
            QComboBox QAbstractItemView{background:#303843;color:#bac5d2;selection-background-color:#405166;}
            QScrollBar:vertical{background:#242930;width:6px;margin:4px 0;}
            QScrollBar::handle:vertical{background:#536170;min-height:28px;border-radius:3px;}
            QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}
            QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical{background:none;}'''.replace('__CHEVRON__',(Path(__file__).resolve().parents[1]/'assets/icons/chevron-down.svg').as_posix()))
        layout=QVBoxLayout(self);layout.setContentsMargins(16,16,16,12);layout.setSpacing(10)
        controls=QHBoxLayout();self.search=QLineEdit();self.search.setClearButtonEnabled(True)
        self.search.installEventFilter(self)
        self.projects=QComboBox();self.projects.setMaximumWidth(200);self.projects.setView(QListView());self.projects.addItem('',None)
        self.projects.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        controls.addWidget(self.search,1);controls.addWidget(self.projects);layout.addLayout(controls)
        self.view=TaskView(self);self.view.setUniformItemSizes(True);self.view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.view.setResizeMode(QListView.ResizeMode.Adjust);self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers);self.view.setMouseTracking(True)
        self.model=TaskModel(self);self.view.setModel(self.model);self.view.setItemDelegate(TaskDelegate(self));layout.addWidget(self.view,1)
        self.empty=QLabel();self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter);layout.addWidget(self.empty,1)
        self.count=QLabel();layout.addWidget(self.count)
        self.project_width=80;self.stamp_width=72;self.status_width=55
        self.search.textChanged.connect(self.apply_filter);self.projects.currentIndexChanged.connect(self.apply_filter)
        self.search.returnPressed.connect(self.open_selected)
        self.view.pressed.connect(self.remember_press);self.view.clicked.connect(self.open_clicked)
        self.refresh(bar.provider.get())
        self.resize(740,min(490,max(300,len(self.rows)*40+100),self.screen().availableGeometry().height()-60))

    def eventFilter(self,watched,event):
        if watched is self.search and event.type()==QEvent.Type.KeyPress and event.key()==Qt.Key.Key_Down and self.model.rowCount():
            self.view.setFocus();self.view.setCurrentIndex(self.model.index(0,0));return True
        return super().eventFilter(watched,event)

    def refresh(self,data):
        states=task_rows(data)
        # Retain the catalog itself: object IDs can be reused while this window is hidden.
        key=(data.get('catalog'),self.bar.language,datetime.now().date(),
             tuple(tuple(t.get(k) for k in ('id','project','title','running','unread','status','side_chat','activity_at')) for t in states),bool(data.get('loading')))
        if key==self.input_key:return
        self.input_key=key;self.rows=finder_rows(data,self.bar.language)
        self.setWindowTitle(self.bar.label('Tasks'));self.search.setPlaceholderText(self.bar.label('Search tasks or projects'))
        selected=self.projects.currentData();names=sorted({row['project'] for row in self.rows},key=str.casefold)
        self.projects.blockSignals(True);self.projects.clear();self.projects.addItem(self.bar.label('All projects'),None)
        for name in names:self.projects.addItem(project_label(name,self.bar.language),name)
        self.projects.setCurrentIndex(max(0,self.projects.findData(selected)));self.projects.blockSignals(False)
        metrics=QFontMetricsF(face(8))
        self.project_width=min(112,max([metrics.horizontalAdvance(row['project_label'])+12 for row in self.rows]+[50]))
        self.stamp_width=max([metrics.horizontalAdvance(row['stamp']) for row in self.rows]+[50])
        kinds={row['kind'] for row in self.rows if row['kind']}
        self.status_width=max([metrics.horizontalAdvance(self.bar.label(CATEGORY_LABELS[k])) for k in kinds]+[0])
        self.loading=bool(data.get('loading'));self.apply_filter()

    def apply_filter(self,*args):
        current=self.view.currentIndex().data(Qt.ItemDataRole.UserRole) or {};selected=current.get('id')
        scroll=self.view.verticalScrollBar().value();rows=filter_rows(self.rows,self.search.text(),self.projects.currentData())
        if self.model.replace(rows):
            index=next((i for i,row in enumerate(rows) if row['id']==selected),0)
            self.view.setCurrentIndex(self.model.index(index,0));self.view.verticalScrollBar().setValue(scroll)
        self.view.setVisible(bool(rows));self.empty.setVisible(not rows)
        self.empty.setText(self.bar.label('Connecting to Codex…' if self.loading else 'No matching tasks'))
        self.count.setText(self.bar.label('Results: {count}',count=len(rows)))
        self.view.viewport().update()

    def remember_press(self,index):self.pressed_id=(index.data(Qt.ItemDataRole.UserRole) or {}).get('id')

    def open_clicked(self,index):
        row=index.data(Qt.ItemDataRole.UserRole)
        if row and row['id']==self.pressed_id:self.open_row(row)
        self.pressed_id=None

    def open_selected(self):
        row=self.view.currentIndex().data(Qt.ItemDataRole.UserRole)
        if row:self.open_row(row)

    def open_row(self,row):
        if self.bar.open_task(row):self.hide()
