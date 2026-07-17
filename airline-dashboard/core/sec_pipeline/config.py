"""Central configuration, paths, and the period model for the pipeline.

All secrets are read from the environment (see ``core/.env.example``). Nothing in
this module should contain credentials.
"""

from __future__ import annotations

import calendar
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from dateutil.relativedelta import relativedelta
from dotenv import load_dotenv

# Load core/.env if present. Never commit that file.
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
CORE_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = CORE_DIR.parent
DATA_DIR = ROOT_DIR / "data"
GENERATED_DIR = DATA_DIR / "generated"
MANUAL_DIR = DATA_DIR / "manual"
CACHE_DIR = CORE_DIR / ".cache"
RAW_DIR = DATA_DIR / "raw"
CHROMA_DIR = CACHE_DIR / "chroma"

for _d in (GENERATED_DIR, MANUAL_DIR, CACHE_DIR, RAW_DIR, CHROMA_DIR):
    _d.mkdir(parents=True, exist_ok=True)

SUMMARIES_PATH = GENERATED_DIR / "insights.json"

# ---------------------------------------------------------------------------
# Environment-driven settings
# ---------------------------------------------------------------------------
SEC_USER_AGENT = os.getenv("SEC_USER_AGENT", "Airline Dashboard contact@example.com")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
EMBEDDING_BACKEND = os.getenv("EMBEDDING_BACKEND", "local").lower()
OPENAI_CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
LOCAL_EMBEDDING_MODEL = os.getenv(
    "LOCAL_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
)

# SEC rate limit: no more than 10 requests per second.
SEC_MAX_REQUESTS_PER_SECOND = 8.0

# ---------------------------------------------------------------------------
# Airlines
# ---------------------------------------------------------------------------
# Fallback CIK map. The pipeline prefers the live ticker->CIK map from SEC and
# falls back to these values if the network lookup is unavailable.
AIRLINE_CIK_FALLBACK: dict[str, str] = {
    "AAL": "0000006201",  # American Airlines Group Inc
    "DAL": "0000027904",  # Delta Air Lines Inc
    "UAL": "0000100517",  # United Airlines Holdings Inc
    "LUV": "0000092380",  # Southwest Airlines Co
    "ALK": "0000766421",  # Alaska Air Group Inc
    "JBLU": "0001158463",  # JetBlue Airways Corp
    "ULCC": "0001670076",  # Frontier Group Holdings Inc
}

AIRLINE_NAMES: dict[str, str] = {
    "AAL": "American Airlines",
    "DAL": "Delta Air Lines",
    "UAL": "United Airlines",
    "LUV": "Southwest Airlines",
    "ALK": "Alaska Airlines",
    "JBLU": "JetBlue Airways",
    "ULCC": "Frontier Airlines",
}

# Filing forms relevant to a reporting period.
RELEVANT_FORMS = ("10-Q", "10-K", "8-K")

# ---------------------------------------------------------------------------
# Period model
# ---------------------------------------------------------------------------
QUARTERS = ("Q1", "Q2", "Q3", "Q4", "FY")


@dataclass(frozen=True)
class PeriodSpec:
    """A reporting period for one airline, e.g. AAL 2024 Q2."""

    year: int
    period: str  # one of QUARTERS

    def __post_init__(self) -> None:
        if self.period not in QUARTERS:
            raise ValueError(f"Invalid period {self.period!r}; expected one of {QUARTERS}")

    @property
    def label(self) -> str:
        """Compact label, e.g. '2024Q2' or '2024FY'."""
        return f"{self.year}{self.period}"

    @classmethod
    def from_label(cls, label: str) -> "PeriodSpec":
        year = int(label[:4])
        return cls(year=year, period=label[4:])

    def date_window(self) -> tuple[datetime, datetime]:
        """Start and end dates that bound the filings for this period.

        The end date is padded to capture filings released after period close
        (up to ~2 months for annual, ~1 month for quarterly).
        """
        if self.period == "FY":
            start_month, end_month = 1, 12
            pad = relativedelta(months=2)
        else:
            end_month = int(self.period[-1]) * 3
            start_month = end_month - 2
            pad = relativedelta(months=1, days=1)
        start = datetime(self.year, start_month, 1)
        end = datetime(self.year, end_month, calendar.monthrange(self.year, end_month)[1]) + pad
        return start, end


def build_periods(years: Iterable[int], periods: Iterable[str]) -> list[PeriodSpec]:
    """Cartesian product of years and periods as PeriodSpec objects."""
    return [PeriodSpec(year=y, period=p) for y in years for p in periods]
