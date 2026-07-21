"""Pydantic DTOs (Data Transfer Objects) for API request/response validation.

All schemas use from_attributes=True so they can be
populated from SQLAlchemy ORM instances directly.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


# ── Auth ──────────────────────────────────────────────────────────────


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    username: str
    password: str


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)
    email: str
    password: str = Field(..., min_length=6)
    full_name: str = ""


class UserOut(BaseModel):
    id: int
    username: str
    email: str
    full_name: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Stations ──────────────────────────────────────────────────────────


class StationOut(BaseModel):
    id: int
    code: str
    name: str
    category: str
    station_type: str
    status: str
    latitude: float
    longitude: float
    legacy_code: str = ""
    department: str = ""
    province: str = ""
    watershed: str = ""

    model_config = {"from_attributes": True}


class StationListOut(BaseModel):
    total: int
    stations: List[StationOut]


# ── Extraction ────────────────────────────────────────────────────────


class ExtractionRequest(BaseModel):
    station_code: str
    mode: str = Field(..., pattern=r"^(month|year|period)$")
    year: int = Field(..., ge=2000, le=2050)
    month: Optional[int] = Field(default=None, ge=1, le=12)
    end_year: Optional[int] = Field(default=None, ge=2000, le=2050)
    consolidated: bool = True

    @field_validator("month")
    @classmethod
    def _require_month_for_month_mode(cls, v, info):
        if info.data.get("mode") == "month" and v is None:
            raise ValueError("month is required for mode='month'")
        return v

    @field_validator("end_year")
    @classmethod
    def _require_end_year_for_period_mode(cls, v, info):
        if info.data.get("mode") == "period" and v is None:
            raise ValueError("end_year is required for mode='period'")
        return v


class ExtractionTaskOut(BaseModel):
    id: int
    station_id: int
    station_name: str = ""
    mode: str
    status: str
    year: Optional[int] = None
    month: Optional[int] = None
    end_year: Optional[int] = None
    output_file: str = ""
    record_count: int = 0
    error_detail: str = ""
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ExtractionStatusOut(BaseModel):
    pending: int = 0
    running: int = 0
    completed: int = 0
    failed: int = 0
    recent: List[ExtractionTaskOut] = []


# ── Data ──────────────────────────────────────────────────────────────


class DataPreviewOut(BaseModel):
    station_name: str
    station_code: str
    headers: List[str]
    row_count: int
    date_range: Optional[str] = None
    sample_rows: List[List[str]] = []


class DataQueryRequest(BaseModel):
    station_code: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    limit: int = 1000
    offset: int = 0


class DataQueryOut(BaseModel):
    station_code: str
    station_name: str
    headers: List[str]
    total_rows: int
    rows: List[dict]


# ── System ────────────────────────────────────────────────────────────


class SystemStatusOut(BaseModel):
    project: str
    version: str
    stations_count: int
    total_extractions: int
    active_extractions: int
    database_size_mb: float
    data_path: str = ""


class FileInfo(BaseModel):
    station: str
    filename: str
    path: str
    size_mb: float
    rows: int


class FileListOut(BaseModel):
    total: int
    files: List[FileInfo]
