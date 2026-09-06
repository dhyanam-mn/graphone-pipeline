import pytest
from unittest.mock import MagicMock
from src.export.sheets_export import flatten_pydantic_model, GoogleSheetsSync
from src.schemas.models import Startup, StartupContent, StartupData, SourceInfo

def test_sheets_export_payload_formatting():
    s = SourceInfo(name="Y Combinator", url="https://airbyte.com")
    c = StartupContent(entityName="Airbyte", website="https://airbyte.com", description="Context layer for production-grade AI agents", data=StartupData(batch="Winter 2020"))
    startup = Startup(source=s, content=c)

    flat = flatten_pydantic_model(startup)
    assert flat["recordType"] == "STARTUP"
    assert flat["content.entityName"] == "Airbyte"
    assert flat["source.url"] == "https://airbyte.com"


def test_sheets_export_batched_chunks(monkeypatch):
    syncer = GoogleSheetsSync(batch_size=500)
    mock_worksheet = MagicMock()
    mock_spreadsheet = MagicMock()
    mock_spreadsheet.worksheet.return_value = mock_worksheet
    syncer.spreadsheet = mock_spreadsheet

    records = [
        Startup(
            source=SourceInfo(name="YC", url=f"https://example.com/{i}"),
            content=StartupContent(entityName=f"Startup {i}", description="Desc", website=f"https://example.com/{i}")
        )
        for i in range(1200)
    ]

    mock_update_chunk = MagicMock()
    monkeypatch.setattr("src.export.sheets_export._update_worksheet_chunk", mock_update_chunk)

    written = syncer.write_tab("Startups", records)
    assert written == 1200
    # 1200 rows with batch_size=500 should result in 3 chunks: (500 + header), 500, 200
    assert mock_update_chunk.call_count == 3

    # Verify range names
    calls = mock_update_chunk.call_args_list
    assert calls[0].args[2] == "A1"
    assert calls[1].args[2] == "A502"
    assert calls[2].args[2] == "A1002"
