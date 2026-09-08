from datetime import date
from src.dashboard import Indicator, summarize_observations, render_dashboard

def test_rates_are_basis_points():
    r=summarize_observations(Indicator('Yield','fred','DGS10','rate'),[(date(2026,9,3),4.0),(date(2026,9,4),4.1)],date(2026,9,7))
    assert '+10.0 bp' in r.trend

def test_payroll_change_and_missing():
    r=summarize_observations(Indicator('NFP','fred','PAYEMS','jobs'),[(date(2026,7,1),150000),(date(2026,8,1),150120)],date(2026,9,7))
    assert '+120k jobs' in r.trend
    assert summarize_observations(Indicator('x','fred','x'),[]).value=='Unavailable'

def test_inflation_periods_and_future_filtered():
    spec=Indicator('CPI','fred','CPIAUCSL','inflation')
    r=summarize_observations(spec,[(date(2025,8,1),100),(date(2026,7,1),102),(date(2026,8,1),103),(date(2027,1,1),999)],date(2026,9,7))
    assert '+3.00% y/y' in r.trend and '2026-08-01' in r.asof
    assert 'observation periods' in render_dashboard([('Macro',[r])])
