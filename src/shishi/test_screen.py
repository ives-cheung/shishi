import unittest
from screen import technical, profit_yoy, C

class TechnicalTests(unittest.TestCase):
    def setUp(self):
        from unittest.mock import patch
        self.policy_patch=patch.dict(C,{'missing_is_failure':False,'normalize_available_weights':True,'fundamental_mode':'soft_risk'})
        self.policy_patch.start();self.addCleanup(self.policy_patch.stop)
    def bars(self):
        return [{'date_ms':1700000000000+i*86400000,'open_price':10,'high_price':10.2,'low_price':9.8,'close_price':10,'volume':10000000,'turnover':100000000} for i in range(61)]
    def test_breakout_excludes_current_bar(self):
        bars=self.bars(); bars[-1].update(open_price=10,high_price=10.6,low_price=10,close_price=10.5,volume=20000000,turnover=210000000)
        m,reasons=technical(bars)
        self.assertFalse(reasons)
        self.assertAlmostEqual(m['breakout_ratio'],10.5/10.2)
        self.assertEqual(m['daily_volume_multiple'],2)
        self.assertEqual(m['turnover_multiple'],2.1)
    def test_missing_volume_never_passes(self):
        bars=self.bars(); bars[-2]['volume']=None
        m,reasons=technical(bars)
        self.assertIsNone(m); self.assertTrue(reasons)
    def test_duplicate_dates_rejected(self):
        bars=self.bars(); bars[-1]['date_ms']=bars[-2]['date_ms']
        self.assertIsNone(technical(bars)[0])
    def test_insufficient_history_rejected(self):
        self.assertIsNone(technical(self.bars()[:60])[0])
    def test_spike_fade_rejected(self):
        bars=self.bars(); bars[-1].update(high_price=12,close_price=10.5,volume=20000000,turnover=210000000)
        self.assertIn('收盘回落明显',technical(bars)[1])
    def test_profit_comparison_matches_same_period(self):
        current={'fiscal_year':2026,'fiscal_period':'Q2','net_profit':80}
        rows=[current,{'fiscal_year':2025,'fiscal_period':'Q1','net_profit':5},{'fiscal_year':2025,'fiscal_period':'Q2','net_profit':100}]
        self.assertAlmostEqual(profit_yoy(rows,current),-20)
        rows[-1]['net_profit']=-100
        self.assertIsNone(profit_yoy(rows,current))
    def test_volume_ratio_threshold_and_missing_policy(self):
        bars=self.bars();bars[-1].update(high_price=10.6,low_price=10,close_price=10.5,turnover=210000000)
        self.assertFalse(technical(bars)[1])
        cfg={**C,'missing_is_failure':True}
        self.assertIn('量比数据缺失',technical(bars,cfg)[1])
        bars[-1]['volume_ratio']=1.2
        self.assertIn('量比低于下限',technical(bars)[1])
        bars[-1]['volume_ratio']=1.3
        self.assertFalse(technical(bars)[1])
    def test_current_weights(self):
        self.assertEqual(sum(C['weights'].values()),100)
        self.assertEqual(C['weights']['volume_ratio']+C['weights']['turnover_rate'],30)

if __name__=='__main__': unittest.main()
