from pathlib import Path
import json,math
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
from PySide6.QtCore import Qt,QRectF,QPointF
from PySide6.QtGui import QPainter,QPen,QColor,QPainterPath,QLinearGradient
from PySide6.QtWidgets import QWidget,QToolTip

TZ=ZoneInfo('Asia/Shanghai')
DEFAULT=Path.home()/'Library/Application Support/shishi/watchlist.json'
class WatchStore:
    def __init__(self,path=DEFAULT):
        self.path=Path(path)
        self.items=json.loads(self.path.read_text()) if self.path.exists() else []
        if not isinstance(self.items,list):raise ValueError('Invalid watchlist')
    def save(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        tmp=self.path.with_suffix('.tmp');tmp.write_text(json.dumps(self.items,ensure_ascii=False,indent=2));tmp.replace(self.path)
    def add(self,code,name):
        if any(r['thscode']==code for r in self.items):return False
        self.items.append({'thscode':code,'name':name});self.save();return True
    def remove(self,code):self.items=[r for r in self.items if r['thscode']!=code];self.save()

def clean_bars(bars):
    rows={}
    for r in bars:
        price=r.get('close_price');t=r.get('date_ms')
        if isinstance(t,(int,float)) and isinstance(price,(int,float)) and math.isfinite(price) and price>0:rows[t]=r
    return sorted(rows.values(),key=lambda r:r['date_ms'])

class TrendChart(QWidget):
    def __init__(self):
        super().__init__();self.bars=[];self.points=[];self.setMinimumHeight(290);self.setMouseTracking(True);self.message='加入自选后，点击股票查看走势'
    def set_bars(self,bars,days=90):
        rows=clean_bars(bars)
        if rows:
            cutoff=rows[-1]['date_ms']-days*86400000;rows=[r for r in rows if r['date_ms']>=cutoff]
        self.bars=rows;self.message='暂无可用日线' if not rows else '';self.update()
    def clear(self,message):self.bars=[];self.points=[];self.message=message;self.update()
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);p.fillRect(self.rect(),QColor('white'))
        if not self.bars:
            p.setPen(QColor('#888'));p.drawText(self.rect(),Qt.AlignCenter,self.message);return
        plot=QRectF(64,25,max(10,self.width()-88),max(10,self.height()-65));vals=[r['close_price'] for r in self.bars];lo=min(vals);hi=max(vals);pad=max((hi-lo)*.12,hi*.005);lo-=pad;hi+=pad
        for i in range(5):
            y=plot.top()+plot.height()*i/4;p.setPen(QPen(QColor('#ededed'),1));p.drawLine(QPointF(plot.left(),y),QPointF(plot.right(),y));p.setPen(QColor('#888'));p.drawText(QRectF(0,y-10,54,20),Qt.AlignRight|Qt.AlignVCenter,f'{hi-(hi-lo)*i/4:.2f}')
        self.points=[QPointF(plot.left()+i*plot.width()/max(1,len(vals)-1),plot.bottom()-(val-lo)/(hi-lo)*plot.height()) for i,val in enumerate(vals)]
        path=QPainterPath(self.points[0])
        for point in self.points[1:]:path.lineTo(point)
        fill=QPainterPath(path);fill.lineTo(plot.right(),plot.bottom());fill.lineTo(plot.left(),plot.bottom());fill.closeSubpath();gradient=QLinearGradient(0,plot.top(),0,plot.bottom());gradient.setColorAt(0,QColor(7,161,90,32));gradient.setColorAt(1,QColor(7,161,90,0));p.fillPath(fill,gradient);p.setPen(QPen(QColor('#149269'),2));p.drawPath(path)
        for idx,align,x in [(0,Qt.AlignLeft,plot.left()),(len(vals)//2,Qt.AlignHCenter,plot.center().x()-50),(len(vals)-1,Qt.AlignRight,plot.right()-100)]:
            date=datetime.fromtimestamp(self.bars[idx]['date_ms']/1000,TZ).strftime('%Y-%m-%d');p.setPen(QColor('#888'));p.drawText(QRectF(x,plot.bottom()+12,100,24),align,date)
    def mouseMoveEvent(self,event):
        if not self.points:return
        i=min(range(len(self.points)),key=lambda n:abs(self.points[n].x()-event.position().x()));r=self.bars[i];date=datetime.fromtimestamp(r['date_ms']/1000,TZ).strftime('%Y-%m-%d');QToolTip.showText(event.globalPosition().toPoint(),f"{date}\n前复权收盘：{r['close_price']:.2f} 元",self)
