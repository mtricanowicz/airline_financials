"""Unit tests for the deterministic, offline-friendly parts of the pipeline."""

from datetime import datetime

import pytest

from sec_pipeline.chunk import chunk_text
from sec_pipeline.config import PeriodSpec, build_periods
from sec_pipeline.edgar_client import _RateLimiter
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

    def test_fy_window_spans_year(self):
        start, end = PeriodSpec(2024, "FY").date_window()
        assert start == datetime(2024, 1, 1)
        assert end.year == 2025  # padded into the next year

    def test_build_periods_cartesian(self):
        specs = build_periods([2023, 2024], ["Q1", "FY"])
        assert len(specs) == 4
        assert PeriodSpec(2023, "Q1") in specs


class TestRateLimiter:
    def test_enforces_minimum_interval(self):
        import time

        limiter = _RateLimiter(max_per_second=50.0)
        start = time.monotonic()
        for _ in range(5):
            limiter.wait()
        assert time.monotonic() - start >= 4 * (1 / 50.0)
