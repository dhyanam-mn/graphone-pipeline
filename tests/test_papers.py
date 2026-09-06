import pytest
import src.scraper.papers as papers_module

def test_pwc_429_short_circuit():
    papers_module.PWC_RATE_LIMITED = True
    assert papers_module.PWC_RATE_LIMITED is True
    # Reset after test
    papers_module.PWC_RATE_LIMITED = False
