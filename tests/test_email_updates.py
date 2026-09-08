from datetime import date
from types import SimpleNamespace
from unittest.mock import patch
from src.email_renderer import format_story_time, render_email_html
from src.summarizer import BriefContent, BriefStory, summarize_ranked_stories
from src.ranker import RankedStory
from src.dashboard import Row, render_watch
from src.vix import VixSnapshot

def test_timezone_and_provenance():
    assert 'PDT' in format_story_time('2026-09-07T14:00:00+00:00')
    assert '07:00 AM' in format_story_time('2026-09-07T14:00:00+00:00')
    assert 'PST' in format_story_time('2026-01-07T15:00:00+00:00')
    assert 'publication time unavailable' in format_story_time('2026-09-07T14:00:00Z','first_seen')
    assert 'timezone unavailable' in format_story_time('2026-09-07T14:00:00')
    assert 'time unavailable' in format_story_time('2026-09-07')
    assert 'unavailable' in format_story_time('broken')

def test_summary_preserves_source_timestamp_not_model_timestamp():
    story = RankedStory('Example','https://example.com','Source','2026-09-07T14:00:00Z',8,'Reason',time_kind='first_seen')
    response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='{"stories":[{"id":0,"title":"Example","summary":"Fact","market_impact":"Potential: higher yields pressure bond prices.","published_at":"FAKE"}]}'))])
    with patch.dict('os.environ',{'OPENAI_API_KEY':'test-only'}), patch('src.summarizer.OpenAI') as client:
        client.return_value.chat.completions.create.return_value = response
        brief = summarize_ranked_stories([story])
    assert brief.stories[0].published_at == story.published_at
    assert brief.stories[0].time_kind == 'first_seen'
    assert 'Potential:' in brief.stories[0].market_impact

def test_render_escapes_analysis_and_shows_time():
    story = BriefStory('Example','https://example.com','Source',8,'Fact','Reason','2026-09-07T14:00:00Z',market_impact='<script>bad</script>')
    html = render_email_html(date(2026,9,7),VixSnapshot(None,'Unavailable'),BriefContent('Overview',[story]))
    assert '07:00 AM PDT' in html
    assert '<script>' not in html and '&lt;script&gt;' in html
    assert 'Market impact' in html

def test_watch_filters_stale_and_caps_at_three():
    rows=[Row('Yield','4%','+12 bp vs prior observation','2026-09-04','',12,'DGS10'),Row('Stale','1','+90%','2026-08-01 — stale','',90,'^VIX')]
    result=render_watch([('Markets',rows)])
    assert 'Yield' in result and 'Stale' not in result and 'bond prices' in result
    assert 'No available' in render_watch([])
    rows=[Row(s,'1','+30%','2026-09-04','',30,s) for s in ['^VIX','^GSPC','^IXIC','CL=F']]
    assert render_watch([('Markets',rows)]).count('<li ') == 3
