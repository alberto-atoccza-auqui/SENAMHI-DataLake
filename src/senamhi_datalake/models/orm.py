"""SQLAlchemy ORM models for the SENAMHI DataLake.

Defines User, Station, and ExtractionTask entities with proper
relationships and enumerated types.
"""
from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from ..core.database import Base


# ── Enumerations ──────────────────────────────────────────────────────

class StationCategory(str, enum.Enum):
    EAA = "EAA"    # Agricultural Automatic
    PE = "PE"      # Special Pluviometric
    CP = "CP"      # Main Climatological
    HLM = "HLM"    # Hydrological with Limnigraph
    MAP = "MAP"    # Airport Meteorology
    EHA = "EHA"    # Hydrological Automatic
    EHMA = "EHMA"  # Hydrometeorological Automatic
    CO = "CO"      # Ordinary Climatological
    EMA = "EMA"    # Automatic Meteorological
    PLU = "PLU"    # Pluviometric
    EAMA = "EAMA"  # Agrometeorological Automatic
    HLG = "HLG"    # Hydrological with Limnigraph


class StationType(str, enum.Enum):
    METEOROLOGICAL = "M"
    HYDROLOGICAL = "H"


class StationStatus(str, enum.Enum):
    REAL_TIME = "REAL"
    DEFERRED = "DIFERIDO"
    AUTOMATIC = "AUTOMATICA"


class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# ── ORM Models ────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(200), default="")
    is_active = Column(Boolean, default=True)
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )


class Station(Base):
    __tablename__ = "stations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    category = Column(String(10), nullable=False)
    station_type = Column(String(5), nullable=False)
    status = Column(String(20), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    legacy_code = Column(String(20), default="")
    department = Column(String(100), default="")
    province = Column(String(100), default="")
    watershed = Column(String(100), default="")

    extractions = relationship(
        "ExtractionTask", back_populates="station"
    )


class ExtractionTask(Base):
    __tablename__ = "extraction_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    station_id = Column(Integer, ForeignKey("stations.id"), nullable=False)
    mode = Column(String(10), nullable=False)
    status = Column(
        String(20), default=TaskStatus.PENDING.value
    )
    year = Column(Integer, nullable=True)
    month = Column(Integer, nullable=True)
    end_year = Column(Integer, nullable=True)
    parameters_json = Column(Text, default="{}")
    output_file = Column(String(500), default="")
    record_count = Column(Integer, default=0)
    error_detail = Column(Text, default="")
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    completed_at = Column(DateTime, nullable=True)

    station = relationship("Station", back_populates="extractions")
