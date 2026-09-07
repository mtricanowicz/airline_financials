from scripts.lint_summaries import _summary_metrics, discover


FIXTURE = """### Financial Insights
1. **Revenue rose 10% to $110 million.** Revenue increased from $100 million in Q1 2024.
2. **Management cited fuel costs.** The company reported expenses of $50 million due to fuel costs.

### Wrap Up
Revenue rose, but fuel costs remained a risk.
"""


def test_summary_metrics_capture_stage_a_signals():
    metrics = _summary_metrics(FIXTURE)

    assert metrics["word_count"] > 0
    assert metrics["item_count"] == 2
    assert metrics["figures_per_item"] == 2.0
    assert metrics["items_with_zero_figures"] == 0
    assert metrics["bold_body_jaccard"] < 1.0
    assert metrics["unattributed_causal_phrases"] == 0
    assert metrics["truncated"] is False


def test_summary_metrics_flag_repeated_stories_and_secondary_padding():
    text = """### Financial Insights
1. **Capacity increased 5% while load factor fell 2 points.** ASM rose 5% and load factor fell to 80%.
2. **Fuel expense increased to $5 billion.** Fuel prices increased and CASM rose.

### Operations Insights
3. **Traffic grew with capacity while fuel use increased.** RPM increased 4% while load factor fell to 80%; fuel consumption also increased.

### Legal and Regulatory Insights
4. **A lawsuit remains pending.** The company expects no material impact.

### Wrap Up
Capacity increased 5%, while fuel expense increased to $5 billion.
"""

    metrics = _summary_metrics(text)

    assert metrics["repeated_metric_families"]["capacity_and_traffic"] == 2
    assert metrics["repeated_metric_families"]["fuel"] == 2
    assert metrics["secondary_section_items"] == 1
    assert metrics["wrap_up_reused_figures"] == 2


def test_discover_reports_reused_phrases_and_airline_spread():
    texts = {"AAL 2024 Q1": FIXTURE, "DAL 2024 Q1": FIXTURE}

    result = discover(texts)

    reused = {entry["phrase"]: entry for entry in result["reused_4grams"]}
    assert any(entry["airline_spread"] == 2 for entry in reused.values())
