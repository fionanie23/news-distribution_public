import json
from types import SimpleNamespace
from unittest.mock import patch
from src.desk_ideas import DESKS, FIELDS, validate_ideas, render_desk_ideas, generate_desk_ideas, build_evidence
from src.ranker import RankedStory
from src.dashboard import Row
from src.vix import VixSnapshot

def sample():
    return [dict(desk=d,status='conditional',evidence_ids=['N1'],**{k:'Conditional research' for k in FIELDS}) for d in DESKS]

def test_each_desk_and_two_roles_render():
    items=validate_ideas({'desks':sample()},{'N1':{}})
    html=render_desk_ideas(items,{'N1':{'label':'Source','url':'https://example.com','asof':'2026-09-13'}})
    assert all(d in html for d in DESKS)
    assert html.count('Trader expression')==4
    assert html.count('Portfolio-manager application')==4

def test_invalid_evidence_missing_fields_and_duplicate_desks_fail_closed():
    items=sample();items[0]['evidence_ids']=['invented'];del items[1]['risks'];items.append(items[2])
    result=validate_ideas({'desks':items},{'N1':{}})
    assert [i['status'] for i in result]==['no_trade','no_trade','no_trade','conditional']
    assert all(i['status']=='no_trade' for i in validate_ideas({'desks':None},{}))

def test_unavailable_data_and_api_failure_preserve_email():
    s=RankedStory('Fact','https://example.com','Source','2026-09-13T10:00:00Z',8,'Reason')
    groups=[('Markets',[Row('Missing','Unavailable','','','')])]
    assert len(build_evidence([s],groups,VixSnapshot(None,'')))==1
    with patch.dict('os.environ',{'OPENAI_API_KEY':'test-only'}),patch('src.desk_ideas.OpenAI',side_effect=RuntimeError('secret')):
        ideas,evidence=generate_desk_ideas([s],groups,VixSnapshot(None,''))
    assert len(ideas)==4 and all(i['status']=='no_trade' for i in ideas)
    assert 'secret' not in render_desk_ideas(ideas,evidence)

def test_generation_uses_news_and_market_evidence_and_escapes_html():
    s=RankedStory('Fact','https://example.com','Source','2026-09-13T10:00:00Z',8,'Reason','Original evidence')
    row=Row('10Y yield','4%','+10bp','2026-09-11','https://fred.stlouisfed.org/series/DGS10')
    items=sample();items[0]['thesis']='<script>alert(1)</script>'
    response=SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps({'desks':items})))])
    with patch.dict('os.environ',{'OPENAI_API_KEY':'test-only'}),patch('src.desk_ideas.OpenAI') as client:
        client.return_value.chat.completions.create.return_value=response
        ideas,evidence=generate_desk_ideas([s],[('Rates',[row])],VixSnapshot(None,''))
        payload=client.return_value.chat.completions.create.call_args.kwargs['messages'][1]['content']
    assert 'Original evidence' in payload and '10Y yield' in payload
    assert '<script>' not in render_desk_ideas(ideas,evidence)
