import sys, json, shutil, os, math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from runtime import RESOURCES,CONFIG,OUTPUT,DATA,FROZEN,read_key,save_key,worker_args
from datetime import datetime
from PySide6.QtCore import Qt, QProcess, QTimer, QPropertyAnimation, QSize, QPoint, QRectF, QVariantAnimation, QEasingCurve
from PySide6.QtGui import QFont, QDesktopServices, QIcon, QPainter, QColor, QPen, QPalette
import qtawesome as qta
from watchlist import WatchStore,TrendChart,TZ
from market_search import MarketSearch
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QStackedWidget,QLineEdit,QTableWidget,QTableWidgetItem,QHeaderView,QAbstractItemView,QFrame,QFormLayout,QGridLayout,QAbstractSpinBox,QDoubleSpinBox,QScrollArea,QCheckBox,QMessageBox,QComboBox,QProgressBar,QGraphicsOpacityEffect,QStyledItemDelegate,QStyleOptionViewItem,QDialog,QDialogButtonBox)
BASE=RESOURCES;ROOT=Path.home() if FROZEN else BASE.parents[1]
ARCHIVE=OUTPUT/'desktop-history'
STYLE='''
QWidget {background:white; color:#151515; font-family:"PingFang SC";font-size:14px;}
QFrame#sidebar {background:#252525;}
QLabel#sidebarLogo {background:transparent;}
QPushButton#railButton {background:transparent;border-radius:12px;padding:0;}
QPushButton#railButton:hover {background:#333333;}
QPushButton#railButton:checked {background:#303632;}
QToolTip {background:#333;color:white;border:none;padding:6px;}
QLabel#brand {font-size:24px;font-weight:650;}
QLabel#title {font-size:38px;font-weight:600;}
QLabel#muted {color:#777;font-size:13px;}
QLabel#number {font-size:30px;font-weight:500;}
QPushButton {border:none;background:#f4f4f4;border-radius:18px;padding:10px 20px;}
QPushButton:hover {background:#e9e9e9;}
QPushButton:checked {background:#e8e8e8;}
QPushButton#primary {background:#111;color:white;}
QPushButton#primary:hover {background:#333;}
QPushButton:disabled {color:#aaa;background:#eee;}
QLineEdit,QComboBox,QDoubleSpinBox {border:1px solid #e2e2e2;border-radius:10px;padding:8px;background:white;}
QTableWidget {border:none;gridline-color:#eee;selection-background-color:#f3f3f3;selection-color:#111;}
QTableWidget::item {padding:12px;border-bottom:1px solid #eee;}
QHeaderView::section {background:white;color:#888;border:none;border-bottom:1px solid #ddd;padding:12px;font-weight:400;}
QScrollArea {border:none;}
QScrollBar:vertical {background:transparent;width:6px;}
QScrollBar::handle:vertical {background:#ddd;border-radius:3px;min-height:30px;}
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {height:0;}
QComboBox::drop-down {border:none;width:20px;}
QFrame#panel {background:#f8f8f8;border-radius:20px;}
QFrame#panel QLabel {background:transparent;}
QFrame#refreshBox {background:#f6f6f6;border:1px solid #ebebeb;border-radius:16px;}
QFrame#refreshBox QLabel {background:transparent;}
QProgressBar {border:none;background:#eee;border-radius:3px;height:5px;}
QProgressBar::chunk {background:#222;border-radius:3px;}
'''
def label(text,kind=None):
    x=QLabel(text); x.setWordWrap(True)
    if kind:x.setObjectName(kind)
    return x

ICONS={'搜索 A 股':'ph.magnifying-glass','我的自选':'ph.star','加入自选':'ph.star','刷新行情':'ph.arrows-clockwise','移除自选':'ph.trash','选股工作台':'ph.chart-line-up','策略参数':'ph.sliders-horizontal','历史记录':'ph.clock-counter-clockwise','运行筛选':'ph.funnel','取消':'ph.x','保存策略':'ph.floppy-disk'}
def icon(name,color='#333'):
    return qta.icon(name,color=color)
def button(text,fn,primary=False):
    x=QPushButton(text);x.setCursor(Qt.PointingHandCursor);x.clicked.connect(fn)
    if primary:x.setObjectName('primary')
    if text in ICONS:x.setIcon(icon(ICONS[text],'white' if primary else '#333'));x.setIconSize(QSize(18,18))
    return x

class FilterCombo(QComboBox):
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setObjectName('listFilter');self.setFixedSize(178,42);self.setCursor(Qt.PointingHandCursor)
        arrow=(BASE/'desktop/assets/chevron-down.svg').as_posix()
        self.setStyleSheet(f"""
            QComboBox#listFilter {{border:1px solid #e5e5e5;border-radius:12px;background:#fafafa;padding:8px 34px 8px 14px;font-weight:500;}}
            QComboBox#listFilter:hover {{background:#f2f2f2;border-color:#d2d2d2;}}
            QComboBox#listFilter:focus {{border-color:#999;}}
            QComboBox#listFilter::drop-down {{border:none;width:32px;}}
            QComboBox#listFilter::down-arrow {{image:url({arrow});width:14px;height:14px;}}
        """)
        self.menu=QFrame(self,Qt.Popup|Qt.FramelessWindowHint|Qt.NoDropShadowWindowHint)
        self.menu.setAttribute(Qt.WA_TranslucentBackground)
        outer=QVBoxLayout(self.menu);outer.setContentsMargins(0,0,0,0)
        self.menu_panel=QFrame();self.menu_panel.setObjectName('filterMenu');outer.addWidget(self.menu_panel)
        self.menu_panel.setStyleSheet("""
            QFrame#filterMenu {background:white;border:1px solid #dedede;border-radius:14px;}
            QPushButton {text-align:left;background:transparent;border:0;border-radius:9px;padding:0 12px;font-size:14px;}
            QPushButton:hover {background:#f3f3f3;}
            QPushButton:checked {background:#ededed;font-weight:600;}
            QPushButton:focus {border:1px solid #aaa;}
        """)
        self.menu_layout=QVBoxLayout(self.menu_panel);self.menu_layout.setContentsMargins(7,7,7,7);self.menu_layout.setSpacing(4)
        self.menu_buttons=[]
    def showPopup(self):
        for b in self.menu_buttons:self.menu_layout.removeWidget(b);b.deleteLater()
        self.menu_buttons=[]
        for i in range(self.count()):
            b=QPushButton(self.itemText(i));b.setIcon(self.itemIcon(i));b.setIconSize(QSize(19,19));b.setFixedHeight(44);b.setCheckable(True);b.setChecked(i==self.currentIndex());b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda checked=False,n=i:self.choose(n));self.menu_layout.addWidget(b);self.menu_buttons.append(b)
        self.menu.setFixedWidth(max(self.width(),208));self.menu.adjustSize();self.menu.move(self.mapToGlobal(QPoint(0,self.height()+6)));self.menu.show()
        self.menu_buttons[self.currentIndex()].setFocus()
    def choose(self,index):self.setCurrentIndex(index);self.hidePopup();self.setFocus()
    def hidePopup(self):self.menu.hide();super().hidePopup()

class QuoteDelegate(QStyledItemDelegate):
    def paint(self,painter,option,index):
        opt=QStyleOptionViewItem(option)
        color=index.data(Qt.ForegroundRole)
        if color:opt.palette.setBrush(QPalette.HighlightedText,color)
        super().paint(painter,opt,index)

class NumberInput(QDoubleSpinBox):
    def __init__(self,parent=None):
        super().__init__(parent);self.setButtonSymbols(QAbstractSpinBox.NoButtons);self.setFixedHeight(36)
    def wheelEvent(self,event):event.ignore()
    def keyPressEvent(self,event):
        if event.key() in (Qt.Key_Up,Qt.Key_Down,Qt.Key_PageUp,Qt.Key_PageDown):event.ignore();return
        super().keyPressEvent(event)

class Toggle(QCheckBox):
    """Keyboard-accessible checkbox rendered as an animated switch."""
    def __init__(self,text='',parent=None):
        super().__init__(text,parent);self.position=0.0;self.setCursor(Qt.PointingHandCursor);self.setFocusPolicy(Qt.StrongFocus);self.setFixedHeight(34)
        self.animation=QVariantAnimation(self);self.animation.setDuration(160);self.animation.setEasingCurve(QEasingCurve.InOutCubic);self.animation.valueChanged.connect(self.move_thumb);self.toggled.connect(self.animate)
    def sizeHint(self):return QSize(52+(self.fontMetrics().horizontalAdvance(self.text())+12 if self.text() else 0),34)
    def hitButton(self,pos):return self.rect().contains(pos)
    def move_thumb(self,value):self.position=float(value);self.update()
    def animate(self,on):
        self.animation.stop();self.animation.setStartValue(self.position);self.animation.setEndValue(1.0 if on else 0.0);self.animation.start()
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing)
        if not self.isEnabled():p.setOpacity(.45)
        if self.hasFocus():
            p.setPen(QPen(QColor('#8ccfb0'),1.5));p.setBrush(Qt.NoBrush);p.drawRoundedRect(QRectF(1,1,50,32),16,16)
        p.setPen(Qt.NoPen);p.setBrush(QColor('#07a85a' if self.isChecked() else ('#bdbdbd' if self.underMouse() else '#cecece')));p.drawRoundedRect(QRectF(4,5,44,24),12,12)
        p.setBrush(QColor('white'));p.drawEllipse(QRectF(7+20*self.position,8,18,18))
        if self.text():
            p.setPen(QColor('#222'));p.drawText(QRectF(62,0,self.width()-62,34),Qt.AlignVCenter|Qt.AlignLeft,self.text())

class Window(QMainWindow):
    def __init__(self):
        super().__init__();self.setWindowTitle('拾势 · A股条件研究');self.resize(1280,860);self.setMinimumSize(1050,720)
        self.watch=WatchStore();self.watch_quotes={};self.watch_quotes_proc=None;self.quote_proc=None;self.quote_data=None;self.active_code=None;self.detail_stock=None;self.data={};self.rows=[];self.proc=None;self.buffer='';self.controls={};self.selected_path=None
        root=QWidget();self.setCentralWidget(root)
        shell=QHBoxLayout(root);shell.setContentsMargins(0,0,0,0);shell.setSpacing(0)
        rail=QFrame();rail.setObjectName('sidebar');rail.setFixedWidth(80)
        nav=QVBoxLayout(rail);nav.setContentsMargins(12,28,12,22);nav.setSpacing(18)
        mark=QLabel();mark.setObjectName('sidebarLogo');mark.setAlignment(Qt.AlignCenter);mark.setPixmap(QIcon(str(BASE/'desktop/assets/Shishi.icns')).pixmap(48,48));mark.setToolTip('拾势 · A股条件研究');nav.addWidget(mark);nav.addSpacing(20)
        self.tabs=[]
        for i,name in enumerate(['选股工作台','策略参数','历史记录','我的自选']):
            b=button('',lambda checked=False,n=i:self.go(n));b.setObjectName('railButton');b.setCheckable(True);b.setFixedSize(56,56);b.setIconSize(QSize(28,28));b.setToolTip(name);b.setAccessibleName(name);b.setProperty('navIcon',ICONS[name]);nav.addWidget(b);self.tabs.append(b)
        nav.addStretch();key_button=button('',self.api_settings);key_button.setObjectName('railButton');key_button.setFixedSize(56,48);key_button.setIcon(icon('ph.key','#aaa'));key_button.setToolTip('API Key 设置');nav.addWidget(key_button);shell.addWidget(rail)
        content=QWidget();shell.addWidget(content,1);layout=QVBoxLayout(content);layout.setContentsMargins(30,24,30,20);layout.setSpacing(18)
        self.stack=QStackedWidget();layout.addWidget(self.stack,1);self.fade=QGraphicsOpacityEffect(self.stack);self.stack.setGraphicsEffect(self.fade);self.animation=QPropertyAnimation(self.fade,b'opacity',self);self.animation.setDuration(180)
        self.build_home();self.build_settings();self.build_history();self.build_watchlist()
        self.status=label('就绪','muted');layout.addWidget(self.status)
        self.go(0);self.load_latest()
        if FROZEN and not read_key():QTimer.singleShot(500,self.api_settings)
    def api_settings(self):
        dialog=QDialog(self);dialog.setWindowTitle('API Key 设置');dialog.setMinimumWidth(460)
        layout=QVBoxLayout(dialog);layout.setContentsMargins(24,24,24,24);layout.setSpacing(16)
        layout.addWidget(label('连接同花顺数据','brand'))
        layout.addWidget(label('填写你自己申请的 API Key，保存在当前电脑。','muted'))
        field=QLineEdit();field.setEchoMode(QLineEdit.Password);field.setPlaceholderText('输入 API Key');field.setText(read_key());layout.addWidget(field)
        reveal=QCheckBox('显示 Key');reveal.toggled.connect(lambda on:field.setEchoMode(QLineEdit.Normal if on else QLineEdit.Password));layout.addWidget(reveal)
        layout.addWidget(button('申请 API Key',lambda:QDesktopServices.openUrl(QUrl('https://fuyao.aicubes.cn/admin/'))))
        controls=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);controls.button(QDialogButtonBox.Save).setText('保存');controls.button(QDialogButtonBox.Cancel).setText('取消');layout.addWidget(controls)
        def save():
            value=field.text().strip()
            if not value or any(ch.isspace() for ch in value):QMessageBox.warning(dialog,'格式不正确','请填写完整的 API Key。');return
            try:save_key(value)
            except OSError:QMessageBox.warning(dialog,'保存失败','无法保存到当前用户目录。');return
            self.status.setText('API Key 已保存 · 下次请求生效');dialog.accept()
        controls.accepted.connect(save);controls.rejected.connect(dialog.reject);dialog.exec()
    def go(self,i):
        self.stack.setCurrentIndex(i);self.animation.stop();self.animation.setStartValue(.55);self.animation.setEndValue(1.0);self.animation.start()
        for j,b in enumerate(self.tabs):
            b.setChecked(i==j);b.setIcon(icon(b.property('navIcon'),'#07c160' if i==j else '#969696'))
        if i==2:self.refresh_history()
        if i==3:self.populate_watchlist()
    def mode_changed(self):
        intraday=self.scan_mode.currentData()=='intraday'
        if intraday:self.refresh.setChecked(True)
        self.refresh.setEnabled(not intraday)
        self.refresh.setToolTip('盘中模式每次获取最新行情' if intraday else '开启：重新获取数据；关闭：复用当日缓存')
    def build_home(self):
        w=QWidget();v=QVBoxLayout(w);v.setContentsMargins(0,16,0,0);v.setSpacing(18)
        hero=QHBoxLayout();left=QVBoxLayout();left.addWidget(label('让条件先行。','title'));self.subtitle=label('用同一套标准，耐心寻找候选。','muted');left.addWidget(self.subtitle);hero.addLayout(left,1)
        self.scan_mode=FilterCombo();self.scan_mode.addItem(icon('ph.clock'),'盘中筛选','intraday');self.scan_mode.addItem(icon('ph.moon'),'盘后筛选','eod');self.scan_mode.setFixedWidth(178);self.scan_mode.setToolTip('盘中：交易日09:35–15:00；盘后：16:00后');hero.addWidget(self.scan_mode,0,Qt.AlignVCenter)
        refresh_box=QFrame();refresh_box.setObjectName('refreshBox');refresh_box.setFixedHeight(48);refresh_layout=QHBoxLayout(refresh_box);refresh_layout.setContentsMargins(14,4,10,4);refresh_layout.setSpacing(10)
        refresh_icon=QLabel();refresh_icon.setPixmap(icon('ph.arrows-clockwise','#555').pixmap(20,20));refresh_layout.addWidget(refresh_icon)
        self.refresh_hint=label('刷新行情');self.refresh_hint.setWordWrap(False);refresh_hint_font=self.refresh_hint.font();refresh_hint_font.setWeight(QFont.Medium);self.refresh_hint.setFont(refresh_hint_font);refresh_layout.addWidget(self.refresh_hint)
        self.refresh=Toggle();self.refresh.setAccessibleName('刷新远端数据');self.refresh.setToolTip('开启：重新获取数据；关闭：复用当日缓存');self.refresh.setChecked(True);self.refresh.toggled.connect(lambda on:self.refresh_hint.setText('刷新行情' if on else '使用缓存'));refresh_layout.addWidget(self.refresh);hero.addWidget(refresh_box,0,Qt.AlignVCenter);hero.addSpacing(6)
        self.scan_mode.currentIndexChanged.connect(self.mode_changed);self.mode_changed()
        self.run=button('运行筛选',self.start,True);hero.addWidget(self.run);self.cancel=button('取消',self.stop);self.cancel.hide();hero.addWidget(self.cancel);v.addLayout(hero)
        self.progress=QProgressBar();self.progress.setRange(0,0);self.progress.setTextVisible(False);self.progress.hide();v.addWidget(self.progress)
        stats=QHBoxLayout();self.numbers=[]
        for title in ['全部 A 股','价格与流动性','技术形态','板块初筛','待复核候选']:
            box=QVBoxLayout();n=label('—','number');box.addWidget(n);caption=QHBoxLayout();symbol=QLabel();symbol.setPixmap(icon(dict(zip(['全部 A 股','价格与流动性','技术形态','板块初筛','待复核候选'],['ph.globe','ph.currency-circle-dollar','ph.chart-line-up','ph.squares-four','ph.shield-check']))[title],'#777').pixmap(17,17));caption.addWidget(symbol);caption.addWidget(label(title,'muted'));caption.addStretch();box.addLayout(caption);stats.addLayout(box);self.numbers.append(n)
        v.addLayout(stats)
        toolbar=QHBoxLayout();self.filter=FilterCombo();self.filter.addItem(icon('ph.list'),'初筛名单');self.filter.addItem(icon('ph.shield-check'),'待复核候选');self.filter.currentIndexChanged.connect(self.render_rows);toolbar.addWidget(self.filter)
        self.search=QLineEdit();self.search.setPlaceholderText('筛选当前列表的名称或代码');self.search.addAction(icon('ph.magnifying-glass','#888'),QLineEdit.LeadingPosition);self.search.textChanged.connect(self.render_rows);toolbar.addWidget(self.search);toolbar.addStretch();toolbar.addWidget(button('搜索 A 股',self.open_market_search,True));v.addLayout(toolbar)
        body=QHBoxLayout();body.setSpacing(24);self.table=QTableWidget(0,5);self.table.setHorizontalHeaderLabels(['股票','价格','涨幅','观察分','排雷状态']);self.table.verticalHeader().hide();self.table.setShowGrid(False);self.table.setSelectionBehavior(QAbstractItemView.SelectRows);self.table.setSelectionMode(QAbstractItemView.SingleSelection);self.table.setEditTriggers(QAbstractItemView.NoEditTriggers);self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch);self.table.cellClicked.connect(self.detail);body.addWidget(self.table,3)
        panel=QFrame();panel.setObjectName('panel');panel.setMinimumWidth(300);panel.setMaximumWidth(370);pv=QVBoxLayout(panel);pv.setContentsMargins(24,24,24,24);self.detail_title=label('筛选详情','brand');pv.addWidget(self.detail_title);self.add_watch=button('加入自选',self.add_selected_watch);pv.addWidget(self.add_watch);self.risk_summary=label('');self.risk_summary.setTextFormat(Qt.PlainText);self.risk_summary.setStyleSheet('background:#fff3e5;color:#865222;border-radius:12px;padding:14px;font-size:14px;');pv.addWidget(self.risk_summary);self.detail_body=label('选择一只股票，查看入选证据与排雷原因。');self.detail_body.setTextFormat(Qt.PlainText);details_scroll=QScrollArea();details_scroll.setWidgetResizable(True);details_scroll.setStyleSheet('QScrollArea,QScrollArea>QWidget>QWidget {background:transparent;}');self.detail_body.setStyleSheet('background:transparent;color:#666;font-size:13px;');details_scroll.setWidget(self.detail_body);self.detail_body.setAlignment(Qt.AlignTop);pv.addWidget(details_scroll,1);pv.addWidget(label('日线前复权 · 同花顺数据\n仅供研究，非投资建议','muted'));body.addWidget(panel,2);v.addLayout(body,1)
        self.empty=label('');v.addWidget(self.empty);self.stack.addWidget(w)
    def open_market_search(self):
        if not hasattr(self,'market_dialog'):self.market_dialog=MarketSearch(self)
        self.market_dialog.show();self.market_dialog.raise_();self.market_dialog.activateWindow();self.market_dialog.input.setFocus();self.market_dialog.render()
    def update_watch_button(self):
        present=self.detail_stock and any(r['thscode']==self.detail_stock['thscode'] for r in self.watch.items)
        self.add_watch.setText('已加入自选' if present else '加入自选');self.add_watch.setEnabled(bool(self.detail_stock) and not present)
    def add_selected_watch(self):
        if self.detail_stock:
            r=self.detail_stock
            try:self.watch.add(r['thscode'],r['name'])
            except OSError as exc:QMessageBox.warning(self,'保存失败',str(exc));return
            self.update_watch_button();self.populate_watchlist();self.status.setText(r['name']+' 已加入自选')
    def build_watchlist(self):
        w=QWidget();v=QVBoxLayout(w);v.setSpacing(16);watch_heading=QHBoxLayout();watch_heading.addWidget(label('我的自选','title'));watch_heading.addStretch();watch_heading.addWidget(button('搜索 A 股',self.open_market_search,True));v.addLayout(watch_heading);v.addWidget(label('关注你想持续观察的股票。点击左侧列表，获取最新行情与日线走势。','muted'))
        body=QHBoxLayout();self.watch_table=QTableWidget(0,2);self.watch_table.setFixedWidth(290);self.watch_table.setHorizontalHeaderLabels(['自选股票','现价 / 涨跌幅']);self.watch_table.setShowGrid(False);self.watch_table.setItemDelegateForColumn(1,QuoteDelegate(self.watch_table));self.watch_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch);self.watch_table.verticalHeader().hide();self.watch_table.setEditTriggers(QAbstractItemView.NoEditTriggers);self.watch_table.setSelectionBehavior(QAbstractItemView.SelectRows);self.watch_table.setSelectionMode(QAbstractItemView.SingleSelection);self.watch_table.cellClicked.connect(self.select_watch);body.addWidget(self.watch_table)
        right=QVBoxLayout();heading=QHBoxLayout();self.watch_title=label('选择一只股票','brand');heading.addWidget(self.watch_title);heading.addStretch();self.quote_refresh=button('刷新行情',self.refresh_quote);self.quote_refresh.setEnabled(False);heading.addWidget(self.quote_refresh);self.watch_remove=button('移除自选',self.remove_watch);self.watch_remove.setEnabled(False);heading.addWidget(self.watch_remove);right.addLayout(heading)
        self.quote_label=label('—','number');right.addWidget(self.quote_label);self.quote_time=label('行情尚未加载','muted');right.addWidget(self.quote_time)
        period_row=QHBoxLayout();period_row.addWidget(label('日线 · 前复权收盘价','muted'));period_row.addStretch();self.period=QComboBox();self.period.addItems(['近3个月','近6个月','近1年']);self.period.currentIndexChanged.connect(self.draw_quote);period_row.addWidget(self.period);right.addLayout(period_row)
        self.chart=TrendChart();right.addWidget(self.chart,1);self.chart_date=label('当前数据源不提供盘中分时线；最新报价与历史日线分别显示。','muted');right.addWidget(self.chart_date);body.addLayout(right,1);v.addLayout(body,1);self.stack.addWidget(w);self.populate_watchlist()
    def populate_watchlist(self):
        self.watch_table.setRowCount(len(self.watch.items))
        for i,r in enumerate(self.watch.items):
            item=QTableWidgetItem(r['name']+'\n'+r['thscode']);item.setIcon(icon('ph.star','#999'));self.watch_table.setItem(i,0,item);self.watch_table.setRowHeight(i,82);self.paint_watch_quote(i,r['thscode'])
            if r['thscode']==self.active_code:self.watch_table.selectRow(i)
        if not self.watch.items:self.chart.clear('点击「搜索 A 股」，添加股票到自选')
        else:self.refresh_watch_quotes()
    def paint_watch_quote(self,row,code):
        q=self.watch_quotes.get(code,{})
        price=q.get('last_price');gain=q.get('price_change_ratio_pct')
        price=price if isinstance(price,(int,float)) and math.isfinite(price) else None
        gain=gain if isinstance(gain,(int,float)) and math.isfinite(gain) else None
        color='#d94848' if gain is not None and gain>0 else '#009b72' if gain is not None and gain<0 else '#888888'
        item=QTableWidgetItem((f'{price:.2f}' if price is not None else '—')+'\n'+(f'{gain:+.2f}%' if gain is not None else '—'))
        item.setTextAlignment(Qt.AlignRight|Qt.AlignVCenter);item.setForeground(QColor(color));item.setFont(QFont('PingFang SC',14,QFont.Medium));item.setToolTip('最新行情快照 · '+q.get('_time','尚未获取'))
        self.watch_table.setItem(row,1,item)
    def refresh_watch_quotes(self):
        if not self.watch.items:return
        if self.watch_quotes_proc:self.watch_quotes_proc.kill()
        proc=QProcess(self);self.watch_quotes_proc=proc
        proc.finished.connect(lambda code,status,p=proc:self.watch_quotes_finished(p,code))
        proc.errorOccurred.connect(lambda error,p=proc:self.watch_quotes_finished(p,-1) if error==QProcess.FailedToStart else None)
        command=worker_args('quote_worker',['--snapshot',','.join(r['thscode'] for r in self.watch.items)]);proc.start(command[0],command[1:])
    def watch_quotes_finished(self,proc,exitcode):
        if proc is not self.watch_quotes_proc:proc.deleteLater();return
        self.watch_quotes_proc=None
        try:
            payload=json.loads(bytes(proc.readAllStandardOutput()).decode())
            if exitcode!=0 or payload.get('error'):raise ValueError('行情更新失败')
            stamp=payload.get('timestamp');stamp=datetime.fromtimestamp(stamp/1000,TZ).strftime('%Y-%m-%d %H:%M') if stamp else '时间未知'
            for r in self.watch.items:self.watch_quotes[r['thscode']]={'_time':stamp}
            for q in payload.get('item',[]):self.watch_quotes[q['thscode']]={**q,'_time':stamp}
            for i,r in enumerate(self.watch.items):self.paint_watch_quote(i,r['thscode'])
        except Exception:
            for i,r in enumerate(self.watch.items):
                item=self.watch_table.item(i,1)
                if item:item.setToolTip('行情刷新失败，显示上次快照');item.setText(item.text().split('\n')[0]+'\n更新失败')
        finally:proc.deleteLater()
    def select_watch(self,i,col):
        if i>=len(self.watch.items):return
        r=self.watch.items[i];self.active_code=r['thscode'];self.watch_title.setText(r['name']+'  '+r['thscode']);self.watch_remove.setEnabled(True);self.refresh_quote()
    def refresh_quote(self):
        if not self.active_code:return
        self.refresh_watch_quotes()
        if self.quote_proc:self.quote_proc.kill()
        self.quote_data=None;self.chart.clear('正在获取日线…');self.quote_label.setText('—');self.quote_time.setText('正在获取最新行情…');self.chart_date.setText('日线前复权 · 同花顺数据');self.quote_refresh.setEnabled(False)
        proc=QProcess(self);self.quote_proc=proc;proc.setWorkingDirectory(str(ROOT));proc.setProperty('stock',self.active_code);proc.finished.connect(lambda code,status,p=proc:self.quote_finished(p,code));proc.errorOccurred.connect(lambda error,p=proc:self.quote_start_error(p,error));command=worker_args('quote_worker',[self.active_code]);proc.start(command[0],command[1:])
    def quote_start_error(self,proc,error):
        if error==QProcess.FailedToStart and proc is self.quote_proc:self.quote_proc=None;self.quote_refresh.setEnabled(True);self.chart.clear('无法启动行情查询，请重试')
    def quote_finished(self,proc,exitcode):
        if proc is not self.quote_proc:proc.deleteLater();return
        self.quote_proc=None;self.quote_refresh.setEnabled(True)
        try:
            payload=json.loads(bytes(proc.readAllStandardOutput()).decode())
            if exitcode!=0 or payload.get('error'):raise ValueError(payload.get('error','行情请求失败'))
            if payload['code']!=self.active_code:return
            self.quote_data=payload;items=payload['quote'].get('item',[]);q=next((r for r in items if r.get('thscode')==self.active_code),{})
            self.watch_quotes[self.active_code]=q
            for i,r in enumerate(self.watch.items):
                if r['thscode']==self.active_code:self.paint_watch_quote(i,self.active_code)
            price=q.get('last_price');gain=q.get('price_change_ratio_pct');self.quote_label.setStyleSheet('color:'+('#d94848' if gain is not None and gain>0 else '#009b72' if gain is not None and gain<0 else '#888888')+';');self.quote_label.setText((f'{price:.2f} 元' if price is not None else '暂无报价')+(f'    {gain:+.2f}%' if gain is not None else ''))
            stamp=payload['quote'].get('timestamp');t=datetime.fromtimestamp(stamp/1000,TZ).strftime('%Y-%m-%d %H:%M') if stamp else '时间未知';self.quote_time.setText('最新行情快照 · 上游数据时间 '+t);self.draw_quote()
        except Exception as exc:self.chart.clear('行情加载失败，请点击刷新重试');self.quote_time.setText(str(exc)[:180])
        finally:proc.deleteLater()
    def draw_quote(self):
        if not self.quote_data:return
        self.chart.set_bars(self.quote_data['history'].get('item',[]),[90,180,365][self.period.currentIndex()])
        if self.chart.bars:
            first=datetime.fromtimestamp(self.chart.bars[0]['date_ms']/1000,TZ).strftime('%Y-%m-%d');last=datetime.fromtimestamp(self.chart.bars[-1]['date_ms']/1000,TZ).strftime('%Y-%m-%d');self.chart_date.setText(f'{first} 至 {last} · {len(self.chart.bars)} 个交易日 · 前复权 · 悬停查看收盘价')
        else:self.chart_date.setText('没有可用日线；不使用模拟数据')
    def remove_watch(self):
        if not self.active_code:return
        try:self.watch.remove(self.active_code)
        except OSError as exc:QMessageBox.warning(self,'保存失败',str(exc));return
        if self.quote_proc:self.quote_proc.kill();self.quote_proc=None
        self.active_code=None;self.quote_data=None;self.watch_title.setText('选择一只股票');self.quote_label.setText('—');self.quote_time.setText('行情尚未加载');self.chart.clear('点击左侧自选股票查看走势');self.chart_date.setText('日线 · 前复权');self.quote_refresh.setEnabled(False);self.watch_remove.setEnabled(False);self.populate_watchlist();self.update_watch_button()
    def build_settings(self):
        w=QWidget();v=QVBoxLayout(w);v.setContentsMargins(0,0,0,0);v.setSpacing(12)
        heading=label('策略参数');heading.setStyleSheet('font-size:28px;font-weight:600;');v.addWidget(heading)
        v.addWidget(label('直接输入数值。保存后下次筛选生效，试运行参数尚未经回测。','muted'))
        scroll=QScrollArea();scroll.setWidgetResizable(True);content=QWidget();outer=QVBoxLayout(content);outer.setContentsMargins(0,12,8,16);outer.setSpacing(20)
        columns=QHBoxLayout();columns.setSpacing(24);cfg=json.loads(CONFIG.read_text());self.original=cfg.copy()
        groups=[('价格与成交',[
            ('preferred_max_price','优先价格上限 · 元'),('gain_min_pct','当日涨幅下限 · %'),('gain_max_pct','当日涨幅上限 · %'),('min_turnover_cny','当日成交额下限 · 元'),('min_avg20_turnover_cny','20日平均成交额下限 · 元'),('min_volume_ratio','量比下限 · 暂无数据'),('min_turnover_multiple','成交额倍数下限')]),
            ('技术与风险',[
            ('max_distance_from_low60_pct','距60日低点涨幅上限 · %'),('min_close_to_prior_high20','相对前20日高点下限'),('max_close_to_prior_high20','相对前20日高点上限'),('max_return5_pct','5日累计涨幅上限 · %'),('max_return20_pct','20日累计涨幅上限 · %')]),
            ('基本面排雷',[
            ('min_profit_yoy_pct','净利润同比下限 · %'),('max_debt_ratio_pct_nonfinancial','非金融业负债率上限 · %'),('max_pe_ttm','PE 上限'),('max_pb_mrq','PB 上限')])]
        for title,fields in groups:
            column=QVBoxLayout();column.setSpacing(10);h=label(title);h.setStyleSheet('font-size:16px;font-weight:600;padding-bottom:4px;');column.addWidget(h)
            for key,caption in fields:
                cell=QVBoxLayout();cell.setSpacing(4);cell.addWidget(label(caption,'muted'));s=NumberInput();s.setRange(-100 if key=='min_profit_yoy_pct' else 0,1e12);s.setDecimals(2);s.setValue(cfg[key]);s.setAccessibleName(caption);cell.addWidget(s);column.addLayout(cell);self.controls[key]=s
            if title=='技术与风险':
                self.hard=Toggle('严格限制价格上限');self.hard.setChecked(cfg['price_is_hard_filter']);column.addSpacing(4);column.addWidget(self.hard)
            if title=='基本面排雷':
                self.soft_risk=Toggle('基本面仅提示风险');self.soft_risk.setChecked(cfg.get('fundamental_mode')=='soft_risk');column.addWidget(self.soft_risk)
                self.normalize=Toggle('可用权重归一化');self.normalize.setChecked(cfg.get('normalize_available_weights',False));column.addWidget(self.normalize)
                self.missing_fail=Toggle('缺失数据判失败');self.missing_fail.setChecked(cfg.get('missing_is_failure',True));column.addWidget(self.missing_fail)
            column.addStretch();columns.addLayout(column,1)
        outer.addLayout(columns)
        weight_heading=QHBoxLayout();h=label('评分权重');h.setStyleSheet('font-size:16px;font-weight:600;');weight_heading.addWidget(h);weight_note=label('合计须为 100% · 缺失指标不补分','muted');weight_note.setWordWrap(False);weight_heading.addWidget(weight_note);weight_heading.addStretch();outer.addLayout(weight_heading)
        grid=QGridLayout();grid.setHorizontalSpacing(20);grid.setVerticalSpacing(10);self.weights={}
        titles={'gain':'涨幅','volume_ratio':'量比 · 暂无数据','turnover_rate':'换手率 · 暂无数据','turnover':'成交额','breakout20':'20日突破','sector_strength':'板块强度','sector_rank':'板块排名'}
        for i,(key,title) in enumerate(titles.items()):
            cell=QVBoxLayout();cell.setSpacing(4);cell.addWidget(label(title,'muted'));s=NumberInput();s.setRange(0,100);s.setValue(cfg['weights'][key]);s.setSuffix(' %');s.setAccessibleName(title);cell.addWidget(s);grid.addLayout(cell,i//4,i%4);self.weights[key]=s
        outer.addLayout(grid);outer.addStretch();scroll.setWidget(content);v.addWidget(scroll,1)
        row=QHBoxLayout();footer_note=label('数值支持直接输入，无需逐步加减。','muted');footer_note.setWordWrap(False);row.addWidget(footer_note);row.addStretch();self.save=button('保存策略',self.save_settings,True);row.addWidget(self.save);v.addLayout(row);self.stack.addWidget(w)
    def build_history(self):
        w=QWidget();v=QVBoxLayout(w);v.addWidget(label('每次筛选，都有记录。','title'));v.addWidget(label('保留数据日期、参数与筛选结果，便于对照。','muted'));self.history=QTableWidget(0,3);self.history.setHorizontalHeaderLabels(['保存记录','交易日','初筛 / 待复核']);self.history.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch);self.history.verticalHeader().hide();self.history.setEditTriggers(QAbstractItemView.NoEditTriggers);self.history.cellDoubleClicked.connect(self.open_history);v.addWidget(self.history);v.addWidget(label('双击一条记录查看。','muted'));self.stack.addWidget(w)
    def save_settings(self):
        cfg=json.loads(CONFIG.read_text());cfg.update({k:s.value() for k,s in self.controls.items()});cfg['weights']={k:s.value() for k,s in self.weights.items()};cfg['price_is_hard_filter']=self.hard.isChecked();cfg['fundamental_mode']='soft_risk' if self.soft_risk.isChecked() else 'hard_filter';cfg['normalize_available_weights']=self.normalize.isChecked();cfg['missing_is_failure']=self.missing_fail.isChecked()
        if abs(sum(cfg['weights'].values())-100)>.001 or cfg['gain_min_pct']>cfg['gain_max_pct'] or cfg['min_close_to_prior_high20']>cfg['max_close_to_prior_high20']:
            QMessageBox.warning(self,'参数需要调整','权重合计必须为100，且下限不能大于上限。');return
        tmp=CONFIG.with_suffix('.tmp');tmp.write_text(json.dumps(cfg,ensure_ascii=False,indent=2));tmp.replace(CONFIG);self.status.setText('策略已保存 · 下次运行生效')
    def paths(self):return sorted(OUTPUT.glob('*/result.json'),key=lambda p:p.stat().st_mtime,reverse=True)
    def load_latest(self):
        p=self.paths()
        if p:self.load(p[0])
    def load(self,p):
        try:self.data=json.loads(p.read_text());self.selected_path=p
        except Exception as e:self.status.setText('读取失败：'+str(e));return
        mode='盘中快照' if self.data.get('mode')=='intraday' else '盘后筛选'
        self.subtitle.setText(mode+' · '+self.data['asof']+'   /   '+self.data.get('generated_at','')[11:19])
        c=self.data['counts']
        for n,key in zip(self.numbers,['universe','snapshot_candidates','technical_pass','sector_pass','review5']):n.setText(f'{c[key]:,}')
        self.render_rows();self.status.setText('已载入筛选记录 · '+self.data['asof'])
    def render_rows(self):
        key='top20' if self.filter.currentIndex()==0 else 'review5';term=self.search.text().strip().lower();self.rows=[r for r in self.data.get(key,[]) if term in (r['name']+r['thscode']).lower()];self.table.setRowCount(len(self.rows))
        for i,r in enumerate(self.rows):
            values=[r['name'],f"{r['last_price']:.2f}",f"+{r['gain']:.2f}%",f"{r['score_observed']:.1f} / {r['score_available_max']:g}",r['review_status']]
            for j,val in enumerate(values):
                item=QTableWidgetItem(val)
                if j==4:item.setIcon(icon('ph.warning-circle' if r.get('financial_flags') else 'ph.shield-check','#a16b36' if r.get('financial_flags') else '#555'))
                self.table.setItem(i,j,item)
            self.table.setRowHeight(i,64)
        self.empty.setText('暂无候选' if not self.rows else '');self.empty.setVisible(not self.rows)
        if self.rows:self.table.selectRow(0);self.detail(0,0)
        else:self.risk_summary.hide();self.detail_stock=None;self.add_watch.setEnabled(False);self.detail_title.setText('暂无候选');self.detail_body.setText('没有数据时不凑数。可以查看初筛名单和排除原因，或调整策略后重新运行。')
    def detail(self,i,col):
        r=self.rows[i];self.detail_stock=r;self.update_watch_button();self.detail_title.setText(r['name']);parts=[r['thscode'],f"{'时段折算日量倍数' if self.data.get('mode')=='intraday' else '日量倍数'}   {r['daily_volume_multiple']:.2f}",f"{'时段折算成交额倍数' if self.data.get('mode')=='intraday' else '成交额倍数'}   {r['turnover_multiple']:.2f}",f"行业   {r['sector']}",f"板块排名   {r['rank']} / {r['covered']}",f"财报期   {r.get('report','—')}"]
        if r.get('net_profit_yoy_growth_ratio') is not None:parts.append(f"净利润同比   {r['net_profit_yoy_growth_ratio']:.2f}%")
        parts += [f"数据覆盖率   {r.get('coverage_pct',r.get('available_weight',65)):g}%"]
        if self.data.get('mode')=='intraday':parts+=['快照时间   '+r.get('quote_observed_at','')[11:19],'按交易时间线性折算，非真实量比']
        flags=r.get('financial_flags',[]);missing=r.get('financial_missing',[])
        reasons=flags+['数据待补：'+m for m in missing]
        self.risk_summary.setText(r['review_status']+'\n\n'+('\n'.join('• '+reason for reason in reasons) if reasons else '当前已检查项目未发现异常'))
        self.risk_summary.setStyleSheet('background:'+('#fff3e5' if reasons else '#edf5f0')+';color:'+('#865222' if reasons else '#34634c')+';border-radius:12px;padding:14px;font-size:14px;')
        self.risk_summary.show()
        self.detail_body.setText('\n'.join(parts));self.detail_body.setMinimumHeight(self.detail_body.sizeHint().height())
    def start(self):
        if self.proc:return
        self.scan_mode.setEnabled(False);self.run.setEnabled(False);self.save.setEnabled(False);self.refresh.setEnabled(False);self.cancel.show();self.progress.show();self.status.setText('准备读取市场数据…');self.buffer='';self.cancelled=False
        self.proc=QProcess(self);self.proc.setWorkingDirectory(str(ROOT));self.proc.setProcessChannelMode(QProcess.MergedChannels);self.proc.readyReadStandardOutput.connect(self.read_progress);self.proc.finished.connect(self.finished);self.proc.errorOccurred.connect(self.process_error)
        command=worker_args('screen',['--mode',self.scan_mode.currentData()]+(['--refresh'] if self.refresh.isChecked() else []));self.proc.start(command[0],command[1:])
    def read_progress(self):
        text=bytes(self.proc.readAllStandardOutput()).decode(errors='replace');self.buffer+=text
        lines=self.buffer.strip().splitlines()
        if lines:
            line=lines[-1]
            translations={'Universe=':'正在筛选全市场：','History ':'核对日线：','Sector membership ':'核对行业成分：','Technical passes=':'技术面通过：','Initial shortlist=':'正在进行财务排雷：'}
            for prefix,cn in translations.items():
                if line.startswith(prefix):line=cn+line[len(prefix):];break
            self.status.setText(line[:180])
    def stop(self):
        if self.proc:self.cancelled=True;self.proc.kill()
    def process_error(self,error):
        if error==QProcess.FailedToStart:self.finished(-1,None)
    def finished(self,code,status):
        self.proc=None;self.scan_mode.setEnabled(True);self.run.setEnabled(True);self.save.setEnabled(True);self.mode_changed();self.cancel.hide();self.progress.hide()
        if self.cancelled:self.status.setText('已取消，保留上次完成的结果。');return
        if code!=0:self.status.setText('筛选失败，保留上次结果。');QMessageBox.warning(self,'筛选未完成',self.buffer[-1200:] or '无法启动筛选程序');return
        self.load_latest();ARCHIVE.mkdir(parents=True,exist_ok=True)
        if self.selected_path:shutil.copy2(self.selected_path,ARCHIVE/(datetime.now().strftime('%Y%m%d-%H%M%S')+'.json'))
        self.status.setText('筛选完成 · 结果与本次参数已保存')
    def refresh_history(self):
        self.history_paths=sorted(ARCHIVE.glob('*.json'),reverse=True)+self.paths();self.history.setRowCount(len(self.history_paths))
        for i,p in enumerate(self.history_paths):
            try:
                d=json.loads(p.read_text());values=[p.stem if p.stem!='result' else p.parent.name+' / 既有记录',d['asof'],f"{d['counts']['top20']} / {d['counts']['review5']}"]
                for j,s in enumerate(values):self.history.setItem(i,j,QTableWidgetItem(s))
                self.history.setRowHeight(i,56)
            except Exception:pass
    def open_history(self,i,col):self.load(self.history_paths[i]);self.go(0)
    def closeEvent(self,event):
        if self.watch_quotes_proc:self.watch_quotes_proc.kill();self.watch_quotes_proc.waitForFinished(3000)
        if hasattr(self,'market_dialog'):self.market_dialog.cancel_query()
        if self.quote_proc:self.quote_proc.kill();self.quote_proc.waitForFinished(3000)
        if self.proc:self.proc.kill();self.proc.waitForFinished(3000)
        event.accept()

if __name__=='__main__':
    app=QApplication(sys.argv);app.setWindowIcon(QIcon(str(BASE/'desktop/assets/Shishi.icns')));app.setStyle('Fusion');app.setStyleSheet(STYLE);w=Window();w.show()
    if '--watchlist' in sys.argv:w.go(3)
    if '--capture-window' in sys.argv:QTimer.singleShot(600,lambda:w.grab().save(str((DATA if FROZEN else BASE/'desktop')/'live-watchlist.png')))
    if '--screenshot' in sys.argv:
        def capture():
            w.grab().save(str((DATA if FROZEN else BASE/'desktop')/'preview.png'));w.go(1);QTimer.singleShot(250,lambda:(w.grab().save(str((DATA if FROZEN else BASE/'desktop')/'settings.png')),app.quit()))
        QTimer.singleShot(1200,capture)
    sys.exit(app.exec())
