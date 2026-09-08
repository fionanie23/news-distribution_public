from datetime import date
from src.email_renderer import render_email_html, render_subject
from src.summarizer import BriefContent
from src.vix import VixSnapshot

def test_empty_brief_is_english():
    html = render_email_html(date(2026,9,7),VixSnapshot(None,'Unavailable'),BriefContent('No major developments.',[]))
    assert 'lang="en"' in html
    assert 'No stories met' in html
    assert not any('\u4e00' <= c <= '\u9fff' for c in html)
    assert render_subject(date(2026,9,7)).startswith('US & Global Finance Brief')
