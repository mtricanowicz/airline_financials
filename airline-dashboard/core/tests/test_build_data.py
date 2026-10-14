"""Offline regression tests for scoped financial dataset updates."""

import json
import sys

import pandas as pd
import pytest

from scripts import build_data


def record(airline="AAL", year=2025, quarter="Q2", **metrics):
    return {"Airline": airline, "Year": year, "Quarter": quarter, **metrics}


@pytest.fixture
def outputs(tmp_path, monkeypatch):
    monkeypatch.setattr(build_data, "FINANCIALS_PATH", tmp_path / "financials.json")
    monkeypatch.setattr(build_data, "BUYBACKS_PATH", tmp_path / "buybacks.json")
    monkeypatch.setattr(build_data, "DIAGNOSTICS_DIR", tmp_path / "diagnostics")
    for name, filename in (
        ("DIAGNOSTICS_SUMMARY_CSV", "coverage_summary.csv"),
        ("DIAGNOSTICS_DETAIL_CSV", "coverage_detail.csv"),
        ("DIAGNOSTICS_REPORT_JSON", "coverage_report.json"),
    ):
        monkeypatch.setattr(build_data, name, tmp_path / "diagnostics" / filename)
    monkeypatch.setattr(build_data, "load_auto", lambda *args: pd.DataFrame())
    monkeypatch.setattr(
        build_data,
        "load_manual",
        lambda: (pd.DataFrame(), pd.DataFrame(), pd.DataFrame()),
    )
    return tmp_path


def persist(rows):
    build_data.FINANCIALS_PATH.write_text(json.dumps(rows), encoding="utf-8")


def read_records():
    return json.loads(build_data.FINANCIALS_PATH.read_text(encoding="utf-8"))


def fail_load(*args):
    pytest.fail("Unselected source was loaded")


@pytest.mark.parametrize("overwrite", [False, True])
def test_value_merge_preserves_null_inputs_zero_and_unselected_metrics(overwrite):
    existing = pd.DataFrame(
        [
            record(**{"Operating Revenue": 100, "RPM": None, "Profit Sharing": 0, "ASM": 50}),
            record("DAL", **{"Operating Revenue": 200}),
        ]
    )
    new = pd.DataFrame(
        [
            record(**{"Operating Revenue": 150, "RPM": 40, "Profit Sharing": 10, "ASM": None}),
            record("UAL", **{"Operating Revenue": 300}),
        ]
    )
    merged = build_data._merge_financials(existing, new, overwrite).set_index("Airline")
    assert merged.at["AAL", "Operating Revenue"] == (150 if overwrite else 100)
    assert merged.at["AAL", "Profit Sharing"] == (10 if overwrite else 0)
    assert merged.at["AAL", "ASM"] == 50
    assert merged.at["AAL", "RPM"] == 40
    assert merged.at["DAL", "Operating Revenue"] == 200
    assert merged.at["UAL", "Operating Revenue"] == 300


@pytest.mark.parametrize("overwrite", [False, True])
def test_manual_only_scoped_updates_and_derived_metrics(outputs, monkeypatch, overwrite):
    outside = [
        record("DAL", **{"Operating Revenue": 200, "Operating Margin": 77}),
        record(year=2024, RPM=10),
        record(quarter="Q1", RPM=20),
    ]
    persist(
        [
            record(
                **{
                    "Operating Revenue": 100,
                    "Operating Income": 20,
                    "RPM": None,
                    "ASM": 50,
                    "Passenger Revenue": 80,
                    "Profit Sharing": 0,
                }
            ),
            *outside,
        ]
    )
    manual = pd.DataFrame(
        [
            record(**{"RPM": 40, "ASM": 60, "Passenger Revenue": 90, "Profit Sharing": 5}),
            record("DAL", RPM=999),
            record(year=2024, RPM=999),
            record(quarter="Q1", RPM=999),
        ]
    )
    monkeypatch.setattr(build_data, "load_auto", fail_load)
    monkeypatch.setattr(build_data, "load_filing_parser", fail_load)
    monkeypatch.setattr(build_data, "load_manual", lambda: (manual, pd.DataFrame(), pd.DataFrame()))
    build_data.build(
        ["AAL"], [2025], ["Q2"], overwrite=overwrite, sources=("manual",), use_filing_parser=True
    )
    rows = read_records()
    selected = next(
        r for r in rows if r["Airline"] == "AAL" and r["Year"] == 2025 and r["Quarter"] == "Q2"
    )
    assert selected["Operating Revenue"] == 100
    assert selected["Operating Margin"] == 20
    assert selected["RPM"] == 40
    assert selected["ASM"] == (60 if overwrite else 50)
    assert selected["Profit Sharing"] == (5 if overwrite else 0)
    assert selected["Load Factor"] == (66.67 if overwrite else 80)
    assert selected["Yield"] == ((90 if overwrite else 80) / 40)
    for original in outside:
        saved = next(
            r for r in rows if all(r[k] == original[k] for k in ("Airline", "Year", "Quarter"))
        )
        assert all(saved[k] == v for k, v in original.items())
    assert not build_data.BUYBACKS_PATH.exists()
    report = json.loads(build_data.DIAGNOSTICS_REPORT_JSON.read_text())
    assert report["requested_sources"] == ["manual"]
    assert report["requested_airlines"] == ["AAL"]
    first = build_data.FINANCIALS_PATH.read_text()
    build_data.build(["AAL"], [2025], ["Q2"], overwrite=overwrite, sources=("manual",))
    assert build_data.FINANCIALS_PATH.read_text() == first


def test_auto_only_retains_manual_metrics(outputs, monkeypatch):
    persist([record(**{"Operating Revenue": 100, "ASM": 50, "RPM": 40})])
    monkeypatch.setattr(build_data, "load_manual", fail_load)
    monkeypatch.setattr(
        build_data,
        "load_auto",
        lambda *args: pd.DataFrame([record(**{"Operating Revenue": 150})]),
    )
    build_data.build(["AAL"], [2025], ["Q2"], overwrite=True, sources=("auto",))
    saved = read_records()[0]
    assert saved["Operating Revenue"] == 150
    assert saved["RPM"] == 40
    assert saved["ASM"] == 50
    assert saved["TRASM"] == 3


def test_sequential_auto_and_manual_runs(outputs, monkeypatch):
    auto = pd.DataFrame([record(**{"Operating Revenue": 100, "Operating Expenses": 80})])
    manual = pd.DataFrame([record(**{"RPM": 40, "ASM": 50, "Passenger Revenue": 75})])
    monkeypatch.setattr(build_data, "load_auto", lambda *args: auto)
    monkeypatch.setattr(build_data, "load_manual", lambda: (manual, pd.DataFrame(), pd.DataFrame()))
    build_data.build(["AAL"], [2025], ["Q2"], sources=("auto",))
    build_data.build(["AAL"], [2025], ["Q2"], sources=("manual",))
    saved = read_records()[0]
    assert saved["Operating Revenue"] == 100
    assert saved["Load Factor"] == 80
    assert saved["PRASM"] == 1.5
    assert saved["CASM"] == 1.6


def test_combined_sources_auto_authoritative_manual_fallback(outputs, monkeypatch):
    auto = pd.DataFrame([record(**{"Operating Revenue": 100, "Passenger Revenue": None})])
    manual = pd.DataFrame(
        [
            record(
                **{
                    "Operating Revenue": 101,
                    "Passenger Revenue": 75,
                    "RPM": 40,
                    "Long-Term Debt": 300,
                }
            ),
            record("UAL", **{"Operating Revenue": 200, "RPM": 30}),
        ]
    )
    monkeypatch.setattr(build_data, "load_auto", lambda *args: auto)
    monkeypatch.setattr(build_data, "load_manual", lambda: (manual, pd.DataFrame(), pd.DataFrame()))
    build_data.build(["AAL", "UAL"], [2025], ["Q2"])
    rows = {r["Airline"]: r for r in read_records()}
    assert rows["AAL"]["Operating Revenue"] == 100
    assert rows["AAL"]["Passenger Revenue"] == 75
    assert rows["AAL"]["Long-Term Debt"] == 300
    assert rows["UAL"]["Operating Revenue"] == 200
    assert not any(k.endswith("_manual") for row in rows.values() for k in row)


@pytest.mark.parametrize("overwrite", [False, True])
@pytest.mark.parametrize("has_existing", [False, True])
def test_empty_sources_preserve_existing_data(outputs, overwrite, has_existing):
    original = record(RPM=40)
    if has_existing:
        persist([original])
    build_data.build(["AAL"], [2025], ["Q2"], overwrite=overwrite)
    rows = read_records()
    if has_existing:
        assert all(rows[0][k] == v for k, v in original.items())
    else:
        assert rows == []


def test_share_data_remains_explicit_and_unscoped(outputs, monkeypatch):
    repurchases = pd.DataFrame(
        [
            record(
                "DAL",
                year=2010,
                quarter="FY",
                **{"Shares Repurchased": 1_000_000, "Cost": 20_000_000},
            ),
        ]
    )
    sales = pd.DataFrame(
        [
            record(
                "UAL", year=2011, quarter="FY", **{"Shares Sold": 2_000_000, "Proceeds": 30_000_000}
            ),
        ]
    )
    monkeypatch.setattr(build_data, "load_manual", lambda: (pd.DataFrame(), repurchases, sales))
    build_data.BUYBACKS_PATH.write_text('{"repurchases": [], "sales": []}')
    build_data.build(["AAL"], [2025], ["Q2"], sources=("auto",))
    assert json.loads(build_data.BUYBACKS_PATH.read_text())["repurchases"] == []
    build_data.build(["AAL"], [2025], ["Q2"], sources=("auto",), share_data=True)
    saved = json.loads(build_data.BUYBACKS_PATH.read_text())
    assert saved["repurchases"][0]["Airline"] == "DAL"
    assert saved["repurchases"][0]["Year"] == 2010
    assert saved["sales"][0]["Airline"] == "UAL"


def test_filing_parser_only_runs_for_auto(outputs, monkeypatch):
    monkeypatch.setattr(build_data, "load_manual", fail_load)
    calls = []

    def filing_parser(*args):
        calls.append(args)
        return pd.DataFrame([record(**{"Passenger Revenue": 75, "Cargo Revenue": 5})])

    monkeypatch.setattr(build_data, "load_filing_parser", filing_parser)
    build_data.build(["AAL"], [2025], ["Q2"], sources=("auto",), use_filing_parser=True)
    assert len(calls) == 1
    assert read_records()[0]["Cargo Revenue"] == 5


def test_cli_passes_selected_flags(monkeypatch):
    calls = []
    monkeypatch.setattr(build_data, "build", lambda *args, **kwargs: calls.append((args, kwargs)))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build-data",
            "--airlines",
            "AAL",
            "--years",
            "2025",
            "--periods",
            "Q2",
            "--sources",
            "manual",
            "--overwrite",
            "--share-data",
            "--use-filing-parser",
        ],
    )
    build_data.main()
    args, kwargs = calls[0]
    assert args == (["AAL"], [2025], ["Q2"])
    assert kwargs == {
        "sources": ("manual",),
        "overwrite": True,
        "share_data": True,
        "use_filing_parser": True,
    }


@pytest.mark.parametrize("sources", [(), ("invalid",)])
def test_invalid_sources_fail_before_loading(outputs, monkeypatch, sources):
    monkeypatch.setattr(build_data, "load_auto", fail_load)
    with pytest.raises(ValueError, match="sources"):
        build_data.build(["AAL"], [2025], ["Q2"], sources=sources)


def test_diagnostics_use_stored_values_and_identify_skipped_sources(outputs, monkeypatch):
    persist([record(**{"Operating Revenue": 100, "RPM": None, "ASM": 50})])
    monkeypatch.setattr(build_data, "load_manual", fail_load)
    monkeypatch.setattr(
        build_data,
        "load_auto",
        lambda *args: pd.DataFrame([record(**{"Operating Revenue": None})]),
    )
    build_data.build(["AAL"], [2025], ["Q2"], sources=("auto",))
    summary = pd.read_csv(build_data.DIAGNOSTICS_SUMMARY_CSV).set_index("metric")
    assert summary.at["Operating Revenue", "populated_periods"] == 1
    assert summary.at["ASM", "populated_periods"] == 1
    detail = pd.read_csv(build_data.DIAGNOSTICS_DETAIL_CSV).set_index("metric")
    assert detail.at["RPM", "reason_code"] == "SOURCE_NOT_SELECTED"


def test_cli_default_sources_remain_combined(monkeypatch):
    calls = []
    monkeypatch.setattr(build_data, "build", lambda *args, **kwargs: calls.append(kwargs))
    monkeypatch.setattr(sys, "argv", ["build-data", "--years", "2025"])
    build_data.main()
    assert calls[0]["sources"] == ("auto", "manual")
    assert calls[0]["use_filing_parser"] is False
