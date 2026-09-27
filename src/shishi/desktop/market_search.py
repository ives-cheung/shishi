import json,sys
from pathlib import Path
from PySide6.QtCore import QProcess,Qt,QSize
from runtime import worker_args
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLabel,QLineEdit,QPushButton,QTableWidget,QTableWidgetItem,QHeaderView,QAbstractItemView
import qtawesome as qta

class MarketSearch(QDialog):
    def __init__(self,owner):
        super().__init__(owner);self.owner=owner;self.proc=None;self.items=[];self.setWindowTitle('搜索 A 股 · 加入自选');self.resize(720,520)
        v=QVBoxLayout(self);v.setContentsMargins(24,24,24,24);v.setSpacing(16)
        title=QLabel('搜索 A 股');title.setStyleSheet('font-size:24px;font-weight:600;');v.addWidget(title)
        row=QHBoxLayout();self.input=QLineEdit();self.input.setPlaceholderText('输入代码或名称，例如 600519、贵州茅台');self.input.setMaxLength(80);self.input.setClearButtonEnabled(True);self.input.addAction(qta.icon('ph.magnifying-glass',color='#777'),QLineEdit.LeadingPosition);row.addWidget(self.input)
        self.search=QPushButton('搜索');self.search.setObjectName('primary');self.search.clicked.connect(self.start);row.addWidget(self.search);v.addLayout(row);self.input.returnPressed.connect(self.start);self.input.textChanged.connect(self.reset_results)
        self.state=QLabel('搜索全市场 A 股，不受筛选结果限制');self.state.setObjectName('muted');v.addWidget(self.state)
        self.table=QTableWidget(0,3);self.table.setHorizontalHeaderLabels(['股票名称','代码','自选']);self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch);self.table.verticalHeader().hide();self.table.setEditTriggers(QAbstractItemView.NoEditTriggers);self.table.setSelectionBehavior(QAbstractItemView.SelectRows);self.table.setShowGrid(False);v.addWidget(self.table,1)
        footer=QHBoxLayout();footer.addStretch();self.view=QPushButton('查看我的自选');self.view.clicked.connect(self.open_watchlist);footer.addWidget(self.view);v.addLayout(footer)
    def cancel_query(self):
        if self.proc:
            p=self.proc;self.proc=None;p.kill();p.waitForFinished(1000);p.deleteLater()
    def reset_results(self):
        self.cancel_query();self.items=[];self.table.setRowCount(0);self.search.setEnabled(True);self.state.setText('按回车或点击搜索')
    def start(self):
        query=self.input.text().strip()
        if not query:self.state.setText('请输入股票名称或代码');return
        self.cancel_query();self.items=[];self.table.setRowCount(0);self.search.setEnabled(False);self.state.setText('正在搜索 A 股…')
        proc=QProcess(self);self.proc=proc;proc.finished.connect(lambda code,status,p=proc:self.query_done(p,code));proc.errorOccurred.connect(lambda error,p=proc:self.failed(p,error));command=worker_args('search_worker',[query]);proc.start(command[0],command[1:])
    def failed(self,proc,error):
        if error==QProcess.FailedToStart and proc is self.proc:self.proc=None;self.search.setEnabled(True);self.state.setText('查询无法启动，请重试');proc.deleteLater()
    def query_done(self,proc,code):
        if proc is not self.proc:return
        self.proc=None;self.search.setEnabled(True)
        try:
            result=json.loads(bytes(proc.readAllStandardOutput()).decode())
            if code or result.get('error'):raise ValueError(result.get('error','查询失败'))
            if result.get('query')!=self.input.text().strip():return
            self.items=[r for r in result['items'] if r.get('asset_type')=='a-share'];self.render();self.state.setText(f'找到 {len(self.items)} 只股票'+('，请缩小关键词' if len(self.items)==50 else '') if self.items else '没有找到匹配的 A 股，请检查代码或名称')
        except Exception as exc:self.state.setText('搜索失败：'+str(exc)[:140])
        finally:proc.deleteLater()
    def render(self):
        self.table.setRowCount(len(self.items));saved={r['thscode'] for r in self.owner.watch.items}
        for i,r in enumerate(self.items):
            self.table.setItem(i,0,QTableWidgetItem(r['name']));self.table.setItem(i,1,QTableWidgetItem(r['thscode']));b=QPushButton('已加入' if r['thscode'] in saved else '加入自选');b.setIcon(qta.icon('ph.star',color='#777'));b.setEnabled(r['thscode'] not in saved);b.clicked.connect(lambda checked=False,stock=r:self.add(stock));self.table.setCellWidget(i,2,b);self.table.setRowHeight(i,58)
    def add(self,r):
        try:self.owner.watch.add(r['thscode'],r['name'])
        except OSError as exc:self.state.setText('保存失败：'+str(exc));return
        self.owner.populate_watchlist();self.owner.update_watch_button();self.render();self.state.setText(r['name']+' 已加入自选')
    def open_watchlist(self):self.owner.go(3);self.accept()
    def done_dialog(self):self.cancel_query()
    def reject(self):self.cancel_query();super().reject()
    def accept(self):self.cancel_query();super().accept()
    def closeEvent(self,event):self.cancel_query();event.accept()
