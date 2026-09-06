from datetime import datetime, timezone
from enum import Enum
from typing import Literal, Optional, List, Any
from pydantic import BaseModel, Field, field_validator

class PricingModel(str, Enum):
    FREE = "FREE"
    FREEMIUM = "FREEMIUM"
    PAID = "PAID"
    ENTERPRISE = "ENTERPRISE"

class SourceInfo(BaseModel):
    name: str
    url: str

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("source.url cannot be empty")
        v = v.strip()
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError(f"source.url must be a valid HTTP or HTTPS URL, got: '{v}'")
        return v

# --- Content Sub-models ---

class StartupData(BaseModel):
    employeeCount: Optional[int] = None
    batch: Optional[str] = None
    location: Optional[str] = None
    tags: List[str] = Field(default_factory=list)

class StartupContent(BaseModel):
    entityName: str
    description: Optional[str] = None
    website: Optional[str] = None
    data: StartupData = Field(default_factory=StartupData)

class ProductContent(BaseModel):
    startupName: str
    productName: Optional[str] = None
    pricingModel: Optional[PricingModel] = None
    description: Optional[str] = None

class ResearchPaperContent(BaseModel):
    title: str
    authors: List[str] = Field(default_factory=list)
    paper_url: str
    github_url: Optional[str] = None
    github_stars: Optional[int] = None
    published_date: Optional[datetime] = None

class JobContent(BaseModel):
    company: str
    role_title: Optional[str] = None
    date: datetime
    is_remote: bool = False
    role_family: str

class NewsContent(BaseModel):
    title: str
    source: str
    url: str
    published_date: Optional[datetime] = None
    full_text: Optional[str] = None

# --- Main Entity Models ---

class Startup(BaseModel):
    schemaVersion: str = "1.0"
    recordType: Literal["STARTUP"] = "STARTUP"
    source: SourceInfo
    collectedAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    content: StartupContent

class Product(BaseModel):
    schemaVersion: str = "1.0"
    recordType: Literal["PRODUCT"] = "PRODUCT"
    source: SourceInfo
    collectedAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    content: ProductContent

class ResearchPaper(BaseModel):
    schemaVersion: str = "1.0"
    recordType: Literal["RESEARCH_PAPER"] = "RESEARCH_PAPER"
    source: SourceInfo
    collectedAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    content: ResearchPaperContent

class Job(BaseModel):
    schemaVersion: str = "1.0"
    recordType: Literal["JOB"] = "JOB"
    source: SourceInfo
    collectedAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    content: JobContent

class News(BaseModel):
    schemaVersion: str = "1.0"
    recordType: Literal["NEWS"] = "NEWS"
    source: SourceInfo
    collectedAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    content: NewsContent

class EntityMappingLog(BaseModel):
    raw_name: str
    canonical_name: str
    confidence: float
    method: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
