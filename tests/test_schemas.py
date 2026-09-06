import pytest
from pydantic import ValidationError
from src.schemas.models import ResearchPaper, SourceInfo, ResearchPaperContent, Startup, StartupContent, StartupData

def test_record_type_uppercase_validation():
    s = SourceInfo(name="arXiv", url="https://arxiv.org/abs/2106.00000")
    c = ResearchPaperContent(title="Test Paper", paper_url="https://arxiv.org/abs/2106.00000")
    
    # Valid uppercase literal
    p = ResearchPaper(source=s, content=c, recordType="RESEARCH_PAPER")
    assert p.recordType == "RESEARCH_PAPER"

    # Invalid lowercase literal raises ValidationError
    with pytest.raises(ValidationError):
        ResearchPaper(source=s, content=c, recordType="paper")

def test_source_url_validation():
    # Valid HTTP/HTTPS URL
    s = SourceInfo(name="arXiv", url="https://arxiv.org/abs/2106.00000")
    assert s.url == "https://arxiv.org/abs/2106.00000"

    # Empty URL raises ValidationError
    with pytest.raises(ValidationError):
        SourceInfo(name="arXiv", url="")

    # Non-HTTP URL raises ValidationError
    with pytest.raises(ValidationError):
        SourceInfo(name="arXiv", url="N/A")
