"""Local task finding over the Provider catalog; no API calls or stored search history."""
from datetime import datetime
from html import escape
from pathlib import Path
import math
from PySide6.QtCore import Qt,QAbstractTableModel,QModelIndex,QSize,QRectF,QEvent
from PySide6.QtGui import QColor,QFontMetricsF
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLineEdit,QComboBox,QListView,QTableView,QHeaderView,QLabel,QStyledItemDelegate,QAbstractItemView,QStyle
from .app import face,text,project_tag,side_tag,side_tag_width,chart_number,BLUE,ACCENT,AMBER,FAILED,MUTED
from .i18n import project_label,task_title,translate
from .tasks import task_rows,task_category,CATEGORY_LABELS,duration_text

COLUMNS=(('Project','project_label'),('Task','title'),('Status','status_label'),('Run time','total_seconds'),('Tokens','total_tokens'),('Turns','total_turns'),('Last active','at'))


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
        stats=(data.get('task_statistics') or {}).get(task['id'],{});ready=stats.get('ready',False)
        rows.append({'id':task['id'],'title':title,'project':project,'project_label':project_label(project,language),
                     'kind':kind if kind!='recent' else '', 'side_chat':bool((state or {}).get('side_chat')),
                     'status_label':translate(language,CATEGORY_LABELS[kind]) if kind and kind!='recent' else '',
                     'total_tokens':stats.get('tokens') if ready else None,'total_seconds':stats.get('seconds') if ready else None,
                     'total_turns':stats.get('turns') if ready else None,'partial':stats.get('partial',False),
                     'tokens_partial':stats.get('tokens_partial',False),
                     'indexing':bool(stats) and not ready and not stats.get('missing'),
                     'at':at,'stamp':stamp,'search':(project_label(project,language)+' '+title).casefold()})
    return sorted(rows,key=lambda row:(-row['at'],row['id']))


def filter_rows(rows,query='',project=None):
    terms=query.casefold().split()
    return [row for row in rows if (project is None or row['project']==project) and all(term in row['search'] for term in terms)]


def sort_rows(rows,column=6,descending=True):
    key=COLUMNS[column][1]
    def value(row):
        value=row.get(key)
        return None if value is None or value=='' or key=='at' and value==0 else value.casefold() if isinstance(value,str) else value
    stable=sorted(rows,key=lambda row:row['id']);known=[row for row in stable if value(row) is not None]
    return sorted(known,key=value,reverse=descending)+[row for row in stable if value(row) is None]


def cell_text(row,column,unit='M'):
    if column==0:return row['project_label']
    if column==1:return row['title']
    if column==2:return row['status_label']
    if column==6:return row['stamp']
    value=row[COLUMNS[column][1]]
    if value is None:return '…' if row['indexing'] else '—'
    if column==3:return ('≥ ' if row['partial'] else '')+duration_text(value)
    if column==4:
        if row.get('tokens_partial'):
            quantum=100000 if unit=='M' else 1000000;value=value//quantum*quantum
        return ('≥ ' if row.get('tokens_partial') else '')+chart_number(value,unit)+('M' if unit=='M' else ' ×100M')
    return str(value)


class TaskModel(QAbstractTableModel):
    def __init__(self,parent=None):super().__init__(parent);self.rows=[]
    def rowCount(self,parent=QModelIndex()):return 0 if parent.isValid() else len(self.rows)
    def columnCount(self,parent=QModelIndex()):return 0 if parent.isValid() else len(COLUMNS)
    def headerData(self,section,orientation,role=Qt.ItemDataRole.DisplayRole):
        if orientation!=Qt.Orientation.Horizontal:return None
        if role==Qt.ItemDataRole.DisplayRole:
            browser=self.parent();arrow=(' ↓' if browser.sort_descending else ' ↑') if section==browser.sort_column else ''
            return browser.bar.label(COLUMNS[section][0])+arrow
        if role==Qt.ItemDataRole.TextAlignmentRole:return Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter if section>=3 else Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter
        if role==Qt.ItemDataRole.ToolTipRole and section in (3,4,5):return self.parent().bar.label('Local recorded totals; run time excludes gaps, and turns count execution starts.')
    def data(self,index,role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0<=index.row()<len(self.rows):return None
        row=self.rows[index.row()]
        if role==Qt.ItemDataRole.UserRole:return row
        if role==Qt.ItemDataRole.DisplayRole:return cell_text(row,index.column(),self.parent().bar.chart_unit)
        if role==Qt.ItemDataRole.AccessibleTextRole:
            if index.column():return self.parent().bar.label(COLUMNS[index.column()][0])+': '+cell_text(row,index.column(),self.parent().bar.chart_unit)
            return ', '.join(row[k] for k in ('project_label','title','status_label','stamp') if row[k])
        if role==Qt.ItemDataRole.ToolTipRole:
            lines=[row[k] for k in ('project_label','title','stamp')]
            if index.column() in (3,4,5):
                lines.append(self.parent().bar.label('Local recorded totals; run time excludes gaps, and turns count execution starts.'))
                if row['total_tokens'] is not None:lines.append(('≥ ' if row.get('tokens_partial') else '')+f"{row['total_tokens']:,} Tokens")
            return '<qt>'+'<br>'.join(escape(line) for line in lines)+'</qt>'

    def replace(self,rows):
        if rows==self.rows:return False
        if [r['id'] for r in rows]==[r['id'] for r in self.rows]:
            self.rows=rows
            if rows:self.dataChanged.emit(self.index(0,0),self.index(len(rows)-1,len(COLUMNS)-1))
        else:self.beginResetModel();self.rows=rows;self.endResetModel()
        return True


class TaskDelegate(QStyledItemDelegate):
    def __init__(self,browser):super().__init__(browser);self.browser=browser
    def sizeHint(self,option,index):return QSize(1,40)
    def paint(self,p,option,index):
        row=index.data(Qt.ItemDataRole.UserRole);browser=self.browser;box=QRectF(option.rect);y=box.center().y()
        p.save();p.setClipRect(box);p.setRenderHint(p.RenderHint.Antialiasing)
        if option.state & (QStyle.StateFlag.State_Selected|QStyle.StateFlag.State_MouseOver):
            p.fillRect(box.adjusted(0,1,0,-1),QColor('#303a47'))
        x=box.left()+12
        column=index.column();right=box.right()-12;font=face(8)
        if column==0:project_tag(p,x,y,row['project'],font,max(0,box.width()-24),browser.bar.language)
        elif column==1:
            if row['side_chat']:x+=side_tag(p,x,y,browser.bar.language)+7
            title=QFontMetricsF(face()).elidedText(row['title'],Qt.TextElideMode.ElideRight,max(0,right-x))
            text(p,x,y,title,face(),MUTED)
        else:
            value=cell_text(row,column,browser.bar.chart_unit)
            colors={'waiting':AMBER,'running':ACCENT,'unread':AMBER,'failed':FAILED,'stopped':'#8795a5'}
            color=colors.get(row['kind'],MUTED) if column==2 else '#8eb1d4' if column==4 else '#8797aa' if column==6 else MUTED
            text(p,right-QFontMetricsF(font).horizontalAdvance(value) if column>=3 else x,y,value,font,color)
        p.restore()


class TaskView(QTableView):
    def keyPressEvent(self,event):
        if event.key() in (Qt.Key.Key_Return,Qt.Key.Key_Enter):
            self.parent().open_selected();event.accept()
        else:super().keyPressEvent(event)


class TaskFinder(QDialog):
    def __init__(self,bar):
        super().__init__();self.bar=bar;self.rows=[];self.input_key=None;self.pressed_id=None
        self.sort_column=6;self.sort_descending=True
        bounds=bar.screen().availableGeometry();max_width=max(320,bounds.width()-32);max_height=max(240,bounds.height()-48)
        self.setFont(bar.font);self.setMinimumSize(min(760,max_width),min(300,max_height))
        self.setStyleSheet('''QDialog,QTableView{background:#242930;color:#bac5d2;} QLabel{color:#8797aa;}
            QLineEdit,QComboBox{background:#303843;color:#bac5d2;border:1px solid #414b58;border-radius:5px;padding:8px;}
            QComboBox{padding-right:26px;}
            QComboBox::drop-down{width:24px;border:0;}
            QComboBox::down-arrow{image:url(__CHEVRON__);width:12px;height:8px;}
            QLineEdit:focus{border-color:#708aa8;} QTableView{border:0;outline:0;}
            QHeaderView::section{background:#242930;color:#8797aa;border:0;border-bottom:1px solid #414b58;padding:8px;}
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
        self.units=QComboBox();self.units.addItems(['M','100M']);self.units.setCurrentText(bar.chart_unit)
        self.units.currentTextChanged.connect(bar.set_chart_unit)
        controls.addWidget(self.search,1);controls.addWidget(self.projects);controls.addWidget(self.units);layout.addLayout(controls)
        self.view=TaskView(self);self.view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows);self.view.setShowGrid(False)
        self.view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers);self.view.setMouseTracking(True)
        self.model=TaskModel(self);self.view.setModel(self.model);self.view.setItemDelegate(TaskDelegate(self));layout.addWidget(self.view,1)
        self.view.verticalHeader().hide();self.view.verticalHeader().setDefaultSectionSize(40)
        header=self.view.horizontalHeader();header.setFont(face(8));header.setSectionsClickable(True)
        header.setSortIndicatorShown(False);header.setSortIndicator(6,Qt.SortOrder.DescendingOrder)
        header.sectionClicked.connect(self.choose_sort);header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1,QHeaderView.ResizeMode.Stretch)
        for column,width in ((0,106),(2,90),(3,100),(4,112),(5,72),(6,112)):self.view.setColumnWidth(column,width)
        self.empty=QLabel();self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter);layout.addWidget(self.empty,1)
        footer=QHBoxLayout();self.count=QLabel();footer.addWidget(self.count);footer.addStretch();self.scope=QLabel();footer.addWidget(self.scope);layout.addLayout(footer)
        self.project_width=80;self.stamp_width=72;self.status_width=55
        self.search.textChanged.connect(self.apply_filter);self.projects.currentIndexChanged.connect(self.apply_filter)
        self.search.returnPressed.connect(self.open_selected)
        self.view.pressed.connect(self.remember_press);self.view.clicked.connect(self.open_clicked)
        self.refresh(bar.provider.get())
        self.resize(min(1030,max_width),min(530,max(300,len(self.rows)*40+150),max_height))
        self.move(bounds.center()-self.rect().center())

    def showEvent(self,event):
        super().showEvent(event);self.bar.provider.set_statistics_active(True)

    def hideEvent(self,event):
        self.bar.provider.set_statistics_active(False);super().hideEvent(event)

    def choose_sort(self,column):
        self.sort_descending=not self.sort_descending if column==self.sort_column else column>=3
        self.sort_column=column;self.view.horizontalHeader().setSortIndicator(column,Qt.SortOrder.DescendingOrder if self.sort_descending else Qt.SortOrder.AscendingOrder)
        self.model.headerDataChanged.emit(Qt.Orientation.Horizontal,0,len(COLUMNS)-1)
        self.apply_filter()

    def eventFilter(self,watched,event):
        if watched is self.search and event.type()==QEvent.Type.KeyPress and event.key()==Qt.Key.Key_Down and self.model.rowCount():
            self.view.setFocus();self.view.setCurrentIndex(self.model.index(0,0));return True
        return super().eventFilter(watched,event)

    def refresh(self,data):
        states=task_rows(data)
        # Retain the catalog itself: object IDs can be reused while this window is hidden.
        key=(data.get('catalog'),data.get('task_statistics'),self.bar.language,self.bar.chart_unit,datetime.now().date(),
             tuple(tuple(t.get(k) for k in ('id','project','title','running','needs_input','unread','status','side_chat','activity_at')) for t in states),bool(data.get('loading')))
        if key==self.input_key:return
        format_key=(self.bar.language,self.bar.chart_unit);format_changed=format_key!=getattr(self,'format_key',None);self.format_key=format_key
        self.input_key=key;self.rows=finder_rows(data,self.bar.language)
        self.scope.setText(self.bar.label('All local history'))
        self.units.blockSignals(True);self.units.setCurrentText(self.bar.chart_unit);self.units.blockSignals(False)
        self.model.headerDataChanged.emit(Qt.Orientation.Horizontal,0,len(COLUMNS)-1)
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
        self.view.setColumnWidth(2,max(90,math.ceil(self.status_width+24)))
        self.loading=bool(data.get('loading'));self.apply_filter()
        if format_changed and self.model.rows:self.model.dataChanged.emit(self.model.index(0,0),self.model.index(len(self.model.rows)-1,len(COLUMNS)-1))

    def apply_filter(self,*args):
        current=self.view.currentIndex().data(Qt.ItemDataRole.UserRole) or {};selected=current.get('id')
        scroll=self.view.verticalScrollBar().value();rows=sort_rows(filter_rows(self.rows,self.search.text(),self.projects.currentData()),self.sort_column,self.sort_descending)
        if self.model.replace(rows):
            index=next((i for i,row in enumerate(rows) if row['id']==selected),0)
            self.view.setCurrentIndex(self.model.index(index,0));self.view.verticalScrollBar().setValue(scroll)
        self.view.setVisible(bool(rows));self.empty.setVisible(not rows)
        self.empty.setText(self.bar.label('Connecting to Codex…' if self.loading else 'No matching tasks'))
        pending=sum(row['indexing'] for row in rows)
        self.count.setText(self.bar.label('Results: {count}',count=len(rows))+'  ·  '+self.bar.label('Indexing local history: {count}',count=pending) if pending else self.bar.label('Results: {count}',count=len(rows)))
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
