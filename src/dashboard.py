"""Dated market and macro observations; no AI-generated numerical values."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from html import escape
from io import StringIO
import csv
import math
import requests
import yfinance as yf

@dataclass(frozen=True)
class Indicator:
    name: str
    provider: str
    symbol: str
    mode: str = 'price'

MARKETS = [Indicator(n,'yahoo',s) for n,s in [
 ('VIX','^VIX'),('US dollar index','DX-Y.NYB'),('WTI oil futures (USD/bbl)','CL=F'),
 ('S&P 500','^GSPC'),('Nasdaq Composite','^IXIC'),('Dow Jones','^DJI'),
 ('Hong Kong Hang Seng','^HSI'),('Japan Nikkei 225','^N225'),('UK FTSE 100','^FTSE'),
 ('Gold futures (USD/oz)','GC=F'),('EUR/USD (USD per EUR)','EURUSD=X'),
 ('USD/JPY (JPY per USD)','JPY=X'),('GBP/USD (USD per GBP)','GBPUSD=X'),
 ('USD/CNH (CNH per USD)','CNH=X'),('USD/HKD (HKD per USD)','HKD=X'),
 ('US aggregate bonds — AGG ETF proxy','AGG'),('Treasuries — IEF ETF proxy','IEF'),
 ('Investment-grade credit — LQD ETF proxy','LQD'),('High-yield credit — HYG ETF proxy','HYG')]]
SECTORS = [Indicator(n+' — ETF proxy','yahoo',s) for n,s in [
 ('Technology','XLK'),('Financials','XLF'),('Energy','XLE'),('Health care','XLV'),
 ('Industrials','XLI'),('Consumer discretionary','XLY'),('Consumer staples','XLP'),
 ('Utilities','XLU'),('Materials','XLB'),('Real estate','XLRE'),('Communication services','XLC')]]
RATES = [Indicator(n,'fred',s,'rate') for n,s in [
 ('US 2Y Treasury yield','DGS2'),('US 10Y Treasury yield','DGS10'),('US 30Y Treasury yield','DGS30'),
 ('10Y–2Y Treasury spread','T10Y2Y'),('Effective fed funds rate','DFF'),
 ('Fed target lower bound','DFEDTARL'),('Fed target upper bound','DFEDTARU'),
 ('Investment-grade credit OAS','BAMLC0A0CM'),('High-yield credit OAS','BAMLH0A0HYM2')]]
MACRO = [Indicator(n,'fred',s,m) for n,s,m in [
 ('Nonfarm payrolls (thousand jobs, SA)','PAYEMS','jobs'),
 ('CPI headline (SA)','CPIAUCSL','inflation'),('CPI core (SA)','CPILFESL','inflation'),
 ('PCE prices headline (SA)','PCEPI','inflation'),('PCE prices core (SA)','PCEPILFE','inflation'),
 ('PPI final demand (SA)','PPIFIS','inflation'),
 ('Retail sales (million USD, SA)','RSAFS','monthly'),
 ('Real GDP growth (annualized q/q, %)','A191RL1Q225SBEA','growth'),
 ('Unemployment rate (%, SA)','UNRATE','growth')]]

@dataclass
class Row:
    name: str
    value: str
    trend: str
    asof: str
    source: str
    change: float | None = None
    symbol: str = ""


def summarize_observations(spec, observations, now=None):
    now = now or datetime.now(timezone.utc).date()
    data=sorted((d,v) for d,v in observations if d <= now and math.isfinite(v))
    source = ('https://fred.stlouisfed.org/series/' if spec.provider=='fred' else 'https://finance.yahoo.com/quote/')+spec.symbol
    if not data:
        return Row(spec.name,'Unavailable','No verified data','—',source)
    d,v=data[-1]; previous=data[-2][1] if len(data)>1 else None
    def pct(old):
        return f'{(v/old-1)*100:+.2f}%' if old else 'N/A'
    value=f'{v:,.2f}'
    if spec.mode=='rate':
        value+=' %'; trend=f'{(v-previous)*100:+.1f} bp vs prior observation' if previous is not None else 'Prior unavailable'
    elif spec.mode=='jobs':
        trend=f'{v-previous:+,.0f}k jobs m/m' if previous is not None else 'Prior unavailable'
    elif spec.mode=='growth':
        value+=' %';trend=f'{v-previous:+.2f} percentage points vs prior period' if previous is not None else 'Prior unavailable'
    elif spec.mode in ('inflation','monthly'):
        trend=f'{pct(previous)} m/m' if previous is not None else 'Prior unavailable'
        year=[x for x in data if x[0].year==d.year-1 and x[0].month==d.month]
        if year: trend+=f'; {pct(year[-1][1])} y/y'
    else:
        trend=f'{pct(previous)} vs prior session' if previous is not None else 'Prior unavailable'
        month=[x for x in data if x[0]<=d-timedelta(days=30)]
        if month:trend+=f'; {pct(month[-1][1])} over ~1 month'
    age=(now-d).days
    threshold=100 if spec.symbol=='A191RL1Q225SBEA' else 70 if spec in MACRO else 7
    stamp=d.isoformat()+(' — stale' if age>threshold else '')
    return Row(spec.name,value,trend,stamp,source, ((v-previous)*100 if spec.mode=="rate" else (v/previous-1)*100) if previous else None, spec.symbol)


def fetch_indicator(spec):
    try:
        if spec.provider=='fred':
            response=requests.get('https://fred.stlouisfed.org/graph/fredgraph.csv',params={'id':spec.symbol,'cosd':(datetime.now(timezone.utc).date()-timedelta(days=800)).isoformat()},timeout=20)
            response.raise_for_status()
            data=[]
            for row in csv.reader(StringIO(response.text)):
                try: data.append((datetime.strptime(row[0],'%Y-%m-%d').date(),float(row[1])))
                except (ValueError,IndexError):continue
        else:
            history=yf.Ticker(spec.symbol).history(period='3mo',interval='1d',auto_adjust=False,timeout=15)
            # Exclude today's partial trading session. Adjusted prices handle splits/distributions.
            data=[(d.date(),float(v)) for d,v in history.get('Adj Close',history.get('Close',[])).items() if d.date()<datetime.now(timezone.utc).date()]
        return summarize_observations(spec,data)
    except Exception:
        return summarize_observations(spec,[])


def collect_dashboard():
    groups=[('Global markets, bonds, gold and FX',MARKETS),('US equity sectors',SECTORS),('Rates, Fed policy and credit spreads',RATES),('US macroeconomic indicators',MACRO)]
    with ThreadPoolExecutor(max_workers=4) as executor:
        return [(title,list(executor.map(fetch_indicator,specs))) for title,specs in groups]


def render_dashboard(groups):
    parts=['<section><h2>Market &amp; macro dashboard</h2><p>Latest available observations, not live quotes. Market trends compare completed daily sessions; monthly/quarterly data repeat until the next release and may be revised. Dates below are observation periods, not release dates. ETF proxies are not the underlying indexes; adjusted price changes can include distributions. Positive changes do not necessarily mean improving conditions.</p>']
    parts.append(render_watch(groups))
    for title,rows in groups:
        parts.append('<h3>'+escape(title)+'</h3><table style="width:100%;border-collapse:collapse;font-size:13px"><tr><th align="left">Indicator / as of</th><th align="left">Latest / trend</th></tr>')
        for r in rows:
            parts.append(f'<tr><td style="padding:8px 4px;border-bottom:1px solid #ddd"><a href="{escape(r.source,quote=True)}">{escape(r.name)}</a><br>{escape(r.asof)}</td><td style="padding:8px 4px;border-bottom:1px solid #ddd">{escape(r.value)}<br>{escape(r.trend)}</td></tr>')
        parts.append('</table>')
    parts.append('<h3>Release watch: ADP, ISM and FOMC</h3><p>ADP and ISM numerical readings require verified release evidence; they are not inferred from other indicators. Follow the official releases below. Material new reports and Fed decisions are searched for inclusion in the news section.</p><ul><li><a href="https://adpemploymentreport.com/">ADP National Employment Report</a></li><li><a href="https://www.ismworld.org/supply-management-news-and-reports/reports/ism-pmi-reports/">ISM Manufacturing and Services PMI</a></li><li><a href="https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm">FOMC decisions, statements and meeting calendar</a></li></ul></section>')
    return ''.join(parts)


# Editorial screening levels, not statistical significance or trading signals.
WATCH_RULES = {
    '^GSPC': (1.0, 'Broad equity repricing can affect wealth and risk appetite; check whether credit and sectors confirm the move.'),
    '^IXIC': (1.5, 'Growth shares are sensitive to earnings expectations and discount rates; compare Treasury yields before attributing the move.'),
    '^VIX': (10.0, 'Higher VIX implies more expected equity volatility and pricier options; lower VIX implies less. It does not predict market direction.'),
    'DGS2': (5.0, 'Higher short yields generally lower existing bond prices and can support USD, all else equal; lower yields reverse that channel. Check Fed expectations.'),
    'DGS10': (7.0, 'Higher long yields generally pressure bond prices and rate-sensitive equities; lower yields ease discount rates but may reflect weaker growth.'),
    'DX-Y.NYB': (0.5, 'A stronger dollar can pressure USD borrowers and US exporters; a weaker dollar can ease those pressures. Relative rates matter.'),
    'CL=F': (2.0, 'Higher oil can support producers while raising transport costs and inflation pressure; lower oil reverses those channels, depending on the cause.'),
    'GC=F': (1.5, 'Gold can react to real yields, USD and haven demand. Check those drivers before reading its move as a signal for stocks or FX.'),
    'BAMLH0A0HYM2': (10.0, 'Wider credit spreads imply higher risky borrowing costs and can warn of equity stress; tighter spreads suggest easier credit conditions.'),
}


def render_watch(groups):
    candidates = []
    for _, rows in groups:
        for row in rows:
            if row.symbol not in WATCH_RULES or row.change is None or 'stale' in row.asof:
                continue
            threshold, mechanism = WATCH_RULES[row.symbol]
            if abs(row.change) >= threshold:
                candidates.append((abs(row.change) / threshold, row, mechanism, threshold))
    candidates.sort(key=lambda item: item[0], reverse=True)
    parts = ['<h3>Watch today</h3><p>Up to three moves passing editorial screens (not forecasts). These are potential transmission channels, not verified explanations of the moves.</p>']
    if not candidates:
        parts.append('<p>No available, non-stale observations crossed the screening levels. Missing data do not imply calm markets.</p>')
    else:
        parts.append('<ul>')
        for _, row, mechanism, threshold in candidates[:3]:
            unit = 'bp' if row.symbol in ('DGS2', 'DGS10', 'BAMLH0A0HYM2') else '%'
            parts.append(f'<li style="margin-bottom:12px"><strong>{escape(row.name)}</strong>: {escape(row.trend.split(";")[0])} (as of {escape(row.asof)}). {escape(mechanism)} <small>Screen: absolute change ≥ {threshold:g} {unit}.</small></li>')
        parts.append('</ul>')
    return ''.join(parts)
