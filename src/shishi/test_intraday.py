import unittest
from datetime import datetime,timedelta
from intraday import TZ,elapsed_minutes,select_session,snapshot_time,intraday_technical
from screen import C,technical
class IntradayTests(unittest.TestCase):
    def setUp(self):
        from unittest.mock import patch
        self.policy_patch=patch.dict(C,{'missing_is_failure':False,'normalize_available_weights':True,'fundamental_mode':'soft_risk'})
        self.policy_patch.start();self.addCleanup(self.policy_patch.stop)
    def at(self,h,m=0):return datetime(2026,9,28,h,m,tzinfo=TZ)
    def test_lunch_and_sessions(self):
        self.assertEqual(elapsed_minutes(self.at(9,30)),0)
        self.assertEqual(elapsed_minutes(self.at(10,30)),60)
        self.assertEqual(elapsed_minutes(self.at(12,30)),120)
        self.assertEqual(elapsed_minutes(self.at(13,30)),150)
        self.assertEqual(elapsed_minutes(self.at(15)),240)
        cal=[{'date':'20260924'},{'date':'20260928'},{'date':'20260929'}]
        self.assertEqual(select_session(cal,self.at(10),'intraday'),('20260928','20260924'))
        self.assertEqual(select_session(cal,self.at(16),'eod'),('20260928','20260928'))
        for at,mode in [(self.at(9,30),'intraday'),(self.at(16),'intraday'),(self.at(10),'eod')]:
            with self.assertRaises(ValueError):select_session(cal,at,mode)
        with self.assertRaises(ValueError):select_session(cal,self.at(10)-timedelta(days=1),'intraday')
    def test_stale_and_lunch_time(self):
        stamp=lambda d:int(d.timestamp()*1000)
        self.assertEqual(snapshot_time(stamp(self.at(11,30)),self.at(12,30)),self.at(11,30))
        for at in [self.at(9,40),self.at(10,1),self.at(10)-timedelta(days=1)]:
            with self.assertRaises(ValueError):snapshot_time(stamp(at),self.at(10))
    def test_intraday_uses_prior_bars_and_progress(self):
        end=datetime(2026,9,24,tzinfo=TZ)
        bars=[dict(date_ms=int((end-timedelta(days=59-i)).timestamp()*1000),open_price=10,high_price=10.2,low_price=9.8,close_price=10,volume=10000000,turnover=100000000) for i in range(60)]
        q=dict(last_price=10.5,prev_price=10,open_price=10,high_price=10.6,low_price=10,volume=5000000,turnover=40000000,price_change_ratio_pct=5)
        m,reasons=intraday_technical(bars,q,self.at(10,30),'20260924',C,technical)
        self.assertFalse(reasons);self.assertAlmostEqual(m['turnover_multiple'],1.6);self.assertAlmostEqual(m['breakout_ratio'],10.5/10.2)
        self.assertEqual(m['observed_turnover'],40000000);self.assertEqual(m['gain'],5)
        # Today's incomplete historical bar must not contaminate the prior high.
        extra={**bars[-1],'date_ms':int(self.at(10).timestamp()*1000),'high_price':100}
        self.assertEqual(intraday_technical(bars+[extra],q,self.at(10,30),'20260924',C,technical)[0],m)
        self.assertTrue(intraday_technical(bars[:-1],q,self.at(10,30),'20260924',C,technical)[1])
        q['last_price']=None
        self.assertTrue(intraday_technical(bars,q,self.at(10,30),'20260924',C,technical)[1])
class PipelineTests(unittest.TestCase):
    def setUp(self):
        from unittest.mock import patch
        self.policy_patch=patch.dict(C,{'missing_is_failure':False,'normalize_available_weights':True,'fundamental_mode':'soft_risk'})
        self.policy_patch.start();self.addCleanup(self.policy_patch.stop)
    def test_full_intraday_pipeline_with_fixture_transport(self):
        import screen,json,tempfile
        from pathlib import Path
        from unittest.mock import patch
        at=datetime(2026,9,28,10,30,tzinfo=TZ)
        class Clock(datetime):
            @classmethod
            def now(cls,tz=None):return at
        end=datetime(2026,9,24,tzinfo=TZ)
        bars=[dict(date_ms=int((end-timedelta(days=59-i)).timestamp()*1000),open_price=10,high_price=10.2,low_price=9.8,close_price=10,volume=10000000,turnover=100000000) for i in range(60)]
        quote=dict(thscode='600000.SH',last_price=10.5,prev_price=10,open_price=10,high_price=10.6,low_price=10,volume=5000000,turnover=40000000,price_change_ratio_pct=5)
        calls=[]
        def fetch(path,params):
            calls.append(path)
            if 'trading-days' in path:return {'item':[{'date':'20260924'},{'date':'20260928'}]}
            if 'tickers/list' in path:return {'item':[{'thscode':'600000.SH','name':'测试股票'}]}
            if path=='/api/a-share/prices/snapshot':return {'item':[quote],'total':1,'timestamp':int(at.timestamp()*1000)}
            if 'historical' in path:return {'item':bars}
            if 'ths-index-list' in path:return {'item':[{'thscode':'881000.TI','name':'测试行业'}]}
            if 'a-share-index/prices/snapshot' in path:return {'item':[{'thscode':'881000.TI','price_change_ratio_pct':2}],'timestamp':int(at.timestamp()*1000)}
            if 'ths-stock-list' in path:return {'item':[{'thscode':'600000.SH'}]+[{'thscode':f'{i:06}.SH'} for i in range(10)]}
            if 'valuations' in path:return {'item':[]}
            raise ValueError('fixture: missing financials')
        with tempfile.TemporaryDirectory() as tmp,patch.object(screen,'ROOT',Path(tmp)),patch.object(screen,'datetime',Clock),patch.object(screen,'_get',fetch),patch.object(screen.time,'sleep'),patch('sys.argv',['screen.py','--mode','intraday']):
            screen.main()
            result=json.loads((Path(tmp)/'out/stock-screen/20260928-intraday/result.json').read_text())
            self.assertEqual(result['mode'],'intraday');self.assertEqual(result['counts']['technical_pass'],1)
            self.assertEqual(result['counts']['review5'],1);self.assertEqual(result['top20'][0]['observed_turnover'],40000000)
            screen.main()
            self.assertEqual(calls.count('/api/a-share/prices/snapshot'),2)
            self.assertEqual(calls.count('/api/a-share/prices/historical'),1)

if __name__=='__main__':unittest.main()
