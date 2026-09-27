import unittest
from screen import score_pool,review_allowed,C
class Policy(unittest.TestCase):
 def setUp(self):
  from unittest.mock import patch
  self.policy_patch=patch.dict(C,{'missing_is_failure':False,'normalize_available_weights':True,'fundamental_mode':'soft_risk'})
  self.policy_patch.start();self.addCleanup(self.policy_patch.stop)
 def test_normalization(self):
  r={'gain':3,'turnover_multiple':2,'breakout_ratio':1,'sector_gain':2,'fraction':.1}
  d=score_pool([r],C).iloc[0]
  self.assertEqual(d.available_weight,70)
  self.assertAlmostEqual(d.score_observed,d.score_raw/70*100)
 def test_missing_sector(self):
  r={'gain':3,'turnover_multiple':2,'breakout_ratio':1,'sector_gain':None,'fraction':None}
  d=score_pool([r],C).iloc[0];self.assertEqual(d.available_weight,50);self.assertEqual(d.score_observed,100)
 def test_soft(self):
  self.assertTrue(review_allowed({'financial_flags':['loss'],'financial_missing':['roe']},C))
  self.assertFalse(review_allowed({'financial_flags':['loss'],'financial_missing':[]},{**C,'fundamental_mode':'hard_filter'}))
 def test_missing_fail(self):
  self.assertFalse(review_allowed({'financial_flags':[],'financial_missing':['roe']},{**C,'missing_is_failure':True}))
