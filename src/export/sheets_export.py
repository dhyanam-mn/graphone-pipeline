import os
import json
from typing import List, Dict, Any
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from tenacity import retry, stop_after_attempt, wait_exponential

from src.schemas.models import Startup, Product, ResearchPaper, Job, News, EntityMappingLog


def flatten_pydantic_model(model: Any) -> Dict[str, Any]:
    """Flattens a nested Pydantic model into dot-notation keys."""
    raw = model.model_dump()
    flat = {}

    def _flatten(obj, prefix=""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                _flatten(v, f"{prefix}{k}." if prefix else f"{k}.")
        elif isinstance(obj, list):
            flat[prefix.rstrip(".")] = json.dumps(obj, default=str)
        else:
            flat[prefix.rstrip(".")] = str(obj) if obj is not None else ""

    _flatten(raw)
    return flat


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
def _update_worksheet_chunk(worksheet: gspread.Worksheet, values: List[List[Any]], range_name: str) -> None:
    """Updates a chunk of worksheet rows with retry logic and exponential backoff (3 attempts)."""
    worksheet.update(values=values, range_name=range_name)


class GoogleSheetsSync:
    def __init__(self, batch_size: int = 500):
        self.creds_path = os.getenv("GOOGLE_SHEETS_CREDENTIALS_PATH", "./credentials/service_account.json")
        self.sheet_id = os.getenv("GOOGLE_SHEET_ID")
        self.client = None
        self.spreadsheet = None
        self.batch_size = batch_size

    def connect(self):
        if not os.path.exists(self.creds_path):
            raise FileNotFoundError(
                f"Google Sheets service account credentials file not found at '{self.creds_path}'. "
                "Please configure GOOGLE_SHEETS_CREDENTIALS_PATH in .env."
            )
        if not self.sheet_id:
            raise ValueError(
                "GOOGLE_SHEET_ID environment variable is missing. "
                "Please specify your target Google Sheet ID in .env."
            )

        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_name(self.creds_path, scope)
        self.client = gspread.authorize(creds)
        self.spreadsheet = self.client.open_by_key(self.sheet_id)

    def write_tab(self, tab_name: str, records: List[Any]) -> int:
        if not records:
            print(f"[sheets_export.py] Tab '{tab_name}' received 0 records.")
            return 0

        # Validate non-empty source URL on every record
        for idx, rec in enumerate(records):
            source_url = None
            if hasattr(rec, "source") and hasattr(rec.source, "url"):
                source_url = rec.source.url
            elif isinstance(rec, dict) and "url" in rec:
                source_url = rec.get("url")
            elif hasattr(rec, "url"):
                source_url = getattr(rec, "url")
            
            if tab_name != "Entity Mapping Log" and (not source_url or not str(source_url).strip()):
                raise ValueError(f"Record #{idx} in tab '{tab_name}' is missing a valid source.url!")

        # Flatten records to rows
        row_dicts = [flatten_pydantic_model(rec) if hasattr(rec, "model_dump") else rec for rec in records]
        
        # Build headers and data rows
        headers = list(dict.fromkeys([k for r in row_dicts for k in r.keys()]))
        data_rows = [[str(r.get(h, "")) for h in headers] for r in row_dicts]

        # Get or create worksheet tab
        total_needed_rows = len(data_rows) + 50
        total_needed_cols = len(headers) + 10
        try:
            worksheet = self.spreadsheet.worksheet(tab_name)
            worksheet.clear()
        except Exception:
            worksheet = self.spreadsheet.add_worksheet(title=tab_name, rows=total_needed_rows, cols=total_needed_cols)

        # Split data rows into batches of self.batch_size to prevent ConnectionResetError on large updates
        batch_size = self.batch_size
        total_written = 0

        num_batches = (len(data_rows) + batch_size - 1) // batch_size
        print(f"[sheets_export.py] Writing tab '{tab_name}' ({len(data_rows)} rows) in {num_batches} batch(es) of max {batch_size} rows...")

        for i in range(num_batches):
            start_idx = i * batch_size
            end_idx = min((i + 1) * batch_size, len(data_rows))
            chunk = data_rows[start_idx:end_idx]

            if i == 0:
                values_to_write = [headers] + chunk
                range_name = "A1"
            else:
                start_row = 2 + (i * batch_size)
                values_to_write = chunk
                range_name = f"A{start_row}"

            _update_worksheet_chunk(worksheet, values_to_write, range_name)
            total_written += len(chunk)
            print(f"[sheets_export.py] Tab '{tab_name}': Batch {i + 1}/{num_batches} ({len(chunk)} rows) written to range {range_name}.")

        print(f"[sheets_export.py] Successfully wrote {total_written} rows to tab '{tab_name}'.")
        return total_written

    def sync_all(
        self,
        startups: List[Startup],
        products: List[Product],
        papers: List[ResearchPaper],
        jobs: List[Job],
        news: List[News],
        mapping_log: List[EntityMappingLog]
    ) -> Dict[str, int]:
        self.connect()
        results = {
            "Startups": self.write_tab("Startups", startups),
            "Products": self.write_tab("Products", products),
            "Research Papers": self.write_tab("Research Papers", papers),
            "Jobs": self.write_tab("Jobs", jobs),
            "News": self.write_tab("News", news),
            "Entity Mapping Log": self.write_tab("Entity Mapping Log", mapping_log),
        }
        return results


def export_all(
    startups: List[Startup],
    products: List[Product],
    papers: List[ResearchPaper],
    jobs: List[Job],
    news: List[News],
    mapping_log: List[EntityMappingLog]
) -> Dict[str, int]:
    syncer = GoogleSheetsSync()
    return syncer.sync_all(
        startups=startups,
        products=products,
        papers=papers,
        jobs=jobs,
        news=news,
        mapping_log=mapping_log
    )
