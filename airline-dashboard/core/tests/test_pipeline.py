"""Unit tests for the deterministic, offline-friendly parts of the pipeline."""

from datetime import datetime

import pytest

from sec_pipeline.chunk import chunk_text
from sec_pipeline.config import PeriodSpec, build_periods
from sec_pipeline.edgar_client import Exhibit, Filing, _RateLimiter
from sec_pipeline.pipeline import build_period_chunks
from sec_pipeline.parse import clean_text, html_to_text


class TestChunk:
    def test_short_text_single_chunk(self):
        chunks = chunk_text("A short paragraph.", chunk_size=1200)
        assert chunks == ["A short paragraph."]

    def test_long_text_splits_with_overlap(self):
        text = " ".join(f"Sentence number {i}." for i in range(400))
        chunks = chunk_text(text, chunk_size=200, overlap=40)
        assert len(chunks) > 1
        assert all(len(c) <= 260 for c in chunks)  # size + tolerance

    def test_empty_text(self):
        assert chunk_text("") == []


class TestParse:
    def test_clean_text_collapses_inline_whitespace(self):
        assert clean_text("a\t  b   c") == "a b c"

    def test_clean_text_preserves_paragraphs(self):
        assert clean_text("para one\n\n\n\npara two") == "para one\n\npara two"

    def test_html_to_text_drops_markup(self):
        html = "<html><body><p>Revenue rose.</p><script>x=1</script></body></html>"
        out = html_to_text(html.encode())
        assert "Revenue rose." in out
        assert "x=1" not in out


class TestPeriodSpec:
    def test_label_roundtrip(self):
        spec = PeriodSpec(2024, "Q2")
        assert spec.label == "2024Q2"
        assert PeriodSpec.from_label("2024Q2") == spec

    def test_invalid_period_rejected(self):
        with pytest.raises(ValueError):
            PeriodSpec(2024, "Q5")

    def test_quarter_window(self):
        start, end = PeriodSpec(2024, "Q2").date_window()
        assert start == datetime(2024, 4, 1)
        assert end.month in (7, 8)  # padded past quarter close

    def test_q4_window_includes_late_annual_filings(self):
        start, end = PeriodSpec(2020, "Q4").date_window()
        assert start == datetime(2020, 10, 1)
        assert end == datetime(2021, 3, 31)

    def test_fy_window_spans_year(self):
        start, end = PeriodSpec(2024, "FY").date_window()
        assert start == datetime(2024, 1, 1)
        assert end == datetime(2025, 3, 31)

    def test_period_end_excludes_filing_grace_period(self):
        assert PeriodSpec(2020, "Q4").period_end() == datetime(2020, 12, 31)
        assert PeriodSpec(2020, "FY").period_end() == datetime(2020, 12, 31)
        assert PeriodSpec(2020, "Q2").period_end() == datetime(2020, 6, 30)

    def test_build_periods_cartesian(self):
        specs = build_periods([2023, 2024], ["Q1", "FY"])
        assert len(specs) == 4
        assert PeriodSpec(2023, "Q1") in specs


def test_build_period_chunks_keeps_8k_exhibit_provenance():
    filing = Filing("0000000000-24-000001", "8-K", datetime(2024, 7, 23), "cover.htm")

    class Client:
        def filings_in_window(self, *args):
            return [filing]

        def fetch_document(self, *args):
            return b"The cover filing incorporates an earnings release."

        def list_exhibits(self, *args):
            return [Exhibit("earnings-release.htm", "EX-99.1")]

        def fetch_exhibit(self, *args):
            return b"Management expects third-quarter capacity to increase 5% to 7%."

    chunks = build_period_chunks(Client(), "0000000000", PeriodSpec(2024, "Q2"))
    assert {chunk.metadata["source_id"] for chunk in chunks} == {
        "8-K:0000000000-24-000001",
        "8-K:0000000000-24-000001:EX-99.1",
    }
    exhibit_chunk = next(chunk for chunk in chunks if chunk.metadata["exhibit_type"] == "EX-99.1")
    assert "third-quarter capacity" in exhibit_chunk.text


class TestRateLimiter:
    def test_enforces_minimum_interval(self):
        import time

        limiter = _RateLimiter(max_per_second=50.0)
        start = time.monotonic()
        for _ in range(5):
            limiter.wait()
        assert time.monotonic() - start >= 4 * (1 / 50.0)
