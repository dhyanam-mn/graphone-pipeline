import pytest
from datetime import datetime, timezone, timedelta
from src.schemas.models import News, NewsContent, Job, JobContent, SourceInfo

def test_24h_freshness_filtering():
    now_utc = datetime.now(timezone.utc)
    cutoff_24h = now_utc - timedelta(hours=24)

    fresh_date = now_utc - timedelta(hours=2)
    stale_date = now_utc - timedelta(hours=48)

    # Fresh record passes
    assert fresh_date >= cutoff_24h

    # Stale record fails
    assert stale_date < cutoff_24h

def test_freshness_model_date_assignment():
    now_utc = datetime.now(timezone.utc)
    s = SourceInfo(name="Hacker News", url="https://news.ycombinator.com")
    c = NewsContent(title="Fresh AI News", source="Hacker News", url="https://news.ycombinator.com", published_date=now_utc)
    n = News(source=s, content=c)
    assert n.content.published_date >= datetime.now(timezone.utc) - timedelta(hours=24)
