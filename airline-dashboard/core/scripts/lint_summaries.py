"""Measure summary specificity, repetition, attribution, and formatting quality."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

BANNED_PHRASES = (
    "this reflects",
    "reflecting",
    "driven by",
    "primarily driven by",
    "indicating",
    "marking",
    "showcasing",
    "robust",
    "solid",
    "strong",
    "remarkable",
    "significant",
    "well-positioned",
    "underscores the airline's commitment",
    "aims to enhance",
    "contributing to an increase in",
)

CAUSAL_PATTERNS = re.compile(
    r"\b(?:driven by|primarily driven by|due to|because of|as a result of|"
    r"attributed to|resulting from|reflecting)\b",
    re.IGNORECASE,
)
ATTRIBUTION_PATTERNS = re.compile(
    r"\b(?:management|the company|the airline|the filing|the report|"
    r"according to|stated|said|reported|disclosed|noted|explained|"
    r"announced|estimated|expects?|project(?:ed|s)?|guidance)\b",
    re.IGNORECASE,
)
FIGURE_PATTERN = re.compile(
    r"(?:\$\\?\s?\(?\d[\d,.]*(?:\.\d+)?\)?|\b\d[\d,.]*%|\b\d[\d,.]*\s*(?:million|billion|thousand|points?|aircraft|employees?|flights?)\b)",
    re.IGNORECASE,
)
WORD_PATTERN = re.compile(r"[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)*")
HEADING_PATTERN = re.compile(r"^#{3,6}\s+(.+?)\s*$", re.MULTILINE)
ITEM_PATTERN = re.compile(r"^\s*\d+\.\s+(.*?)(?=^\s*\d+\.\s+|^###\s+|\Z)", re.MULTILINE | re.DOTALL)
BOLD_PATTERN = re.compile(r"\*\*(.+?)\*\*")
METRIC_FAMILIES = {
    "capacity_and_traffic": re.compile(r"\b(?:asm|rpm|capacity|load factor|available seat miles|revenue passenger miles)\b", re.IGNORECASE),
    "fuel": re.compile(r"\bfuel\b", re.IGNORECASE),
    "revenue_and_unit_revenue": re.compile(r"\b(?:revenue|prasm|rasm|yield)\b", re.IGNORECASE),
    "costs_and_margins": re.compile(r"\b(?:casm|operating expense|operating cost|margin|profit|income)\b", re.IGNORECASE),
    "liquidity_and_debt": re.compile(r"\b(?:liquidity|cash|debt|borrowings|credit facility)\b", re.IGNORECASE),
}
SECONDARY_HEADINGS = {
    "Executive and Personnel Insights",
    "Legal and Regulatory Insights",
    "Balance Sheet and Debt Insights",
}


def _words(text: str) -> list[str]:
    return [word.lower() for word in WORD_PATTERN.findall(text)]


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]


def _outside_quotes(text: str) -> Iterable[str]:
    """Yield text fragments outside simple quoted spans."""
    for index, fragment in enumerate(re.split(r'("[^"]*"|“[^”]*”)', text)):
        if index % 2 == 0:
            yield fragment


def _phrase_hits(text: str) -> int:
    hits = 0
    for fragment in _outside_quotes(text):
        for phrase in BANNED_PHRASES:
            hits += len(re.findall(rf"\b{re.escape(phrase)}\b", fragment, re.IGNORECASE))
    return hits


def _causal_hits(text: str) -> int:
    hits = 0
    for sentence in _sentences(text):
        if not any(CAUSAL_PATTERNS.search(fragment) for fragment in _outside_quotes(sentence)):
            continue
        if not any(ATTRIBUTION_PATTERNS.search(fragment) for fragment in _outside_quotes(sentence)):
            hits += 1
    return hits


def _items(text: str) -> list[str]:
    return [match.group(1).strip() for match in ITEM_PATTERN.finditer(text)]


def _items_by_heading(text: str) -> list[tuple[str, str]]:
    sections = re.split(r"^###\s+(.+?)\s*$", text, flags=re.MULTILINE)
    items: list[tuple[str, str]] = []
    for index in range(1, len(sections), 2):
        heading = sections[index].strip()
        body = sections[index + 1]
        items.extend((heading, item) for item in _items(body))
    return items


def _metric_families(item: str) -> set[str]:
    return {name for name, pattern in METRIC_FAMILIES.items() if pattern.search(item)}


def _repeated_metric_families(items: list[str]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for item in items:
        counts.update(_metric_families(item))
    return {name: count for name, count in counts.items() if count > 1}


def _wrap_up_reused_figures(text: str) -> int:
    sections = re.split(r"^###\s+(.+?)\s*$", text, flags=re.MULTILINE)
    wrap_up = ""
    body_parts: list[str] = []
    for index in range(1, len(sections), 2):
        if sections[index].strip() == "Wrap Up":
            wrap_up = sections[index + 1]
        else:
            body_parts.append(sections[index + 1])
    body_figures = set(FIGURE_PATTERN.findall("\n".join(body_parts)))
    return sum(figure in body_figures for figure in FIGURE_PATTERN.findall(wrap_up))


def _body_without_takeaway(item: str) -> str:
    bold = BOLD_PATTERN.search(item)
    if not bold:
        return item
    return f"{item[:bold.start()]} {item[bold.end():]}"


def _jaccard(left: Iterable[str], right: Iterable[str]) -> float:
    left_set, right_set = set(left), set(right)
    if not left_set and not right_set:
        return 1.0
    return len(left_set & right_set) / len(left_set | right_set)


def _is_truncated(text: str) -> bool:
    meaningful = text.rstrip()
    return bool(meaningful) and meaningful[-1] not in ".!?)]}\"'`"


def _summary_metrics(text: str) -> dict[str, Any]:
    words = _words(text)
    items = _items(text)
    figures = [len(FIGURE_PATTERN.findall(item)) for item in items]
    overlaps = []
    for item in items:
        takeaway = BOLD_PATTERN.search(item)
        body = _body_without_takeaway(item)
        overlaps.append(_jaccard(_words(takeaway.group(1)) if takeaway else [], _words(body)))
    return {
        "word_count": len(words),
        "item_count": len(items),
        "banned_phrase_hits": _phrase_hits(text),
        "banned_phrase_hits_per_1000_words": round(_phrase_hits(text) * 1000 / max(1, len(words)), 3),
        "figures_per_item": round(sum(figures) / max(1, len(figures)), 3),
        "items_with_zero_figures": sum(value == 0 for value in figures),
        "bold_body_jaccard": round(sum(overlaps) / max(1, len(overlaps)), 3),
        "unattributed_causal_phrases": _causal_hits(text),
        "truncated": _is_truncated(text),
        "headings": HEADING_PATTERN.findall(text),
        "repeated_metric_families": _repeated_metric_families(items),
        "secondary_section_items": sum(heading in SECONDARY_HEADINGS for heading, _ in _items_by_heading(text)),
        "wrap_up_reused_figures": _wrap_up_reused_figures(text),
    }


def load_summaries(path: Path) -> dict[str, str]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    flattened: dict[str, str] = {}
    for airline, years in raw.items():
        for year, periods in years.items():
            for period, text in periods.items():
                if isinstance(text, str):
                    flattened[f"{airline} {year} {period}"] = text
    return flattened


def _ngrams(words: list[str], size: int = 4) -> Counter[tuple[str, ...]]:
    return Counter(tuple(words[index : index + size]) for index in range(len(words) - size + 1))


def _discovery_words(text: str) -> list[str]:
    content = re.sub(r"^#{1,6}.*$", "", text, flags=re.MULTILINE)
    content = re.sub(r"^\s*\d+\.\s+", "", content, flags=re.MULTILINE)
    return _words(content)


def _aggregate(summary_metrics: dict[str, dict[str, Any]], texts: dict[str, str]) -> dict[str, Any]:
    total_words = sum(metric["word_count"] for metric in summary_metrics.values())
    total_items = sum(metric["item_count"] for metric in summary_metrics.values())
    ngrams_by_summary = {key: _ngrams(_discovery_words(text)) for key, text in texts.items()}
    corpus_counts = Counter()
    for counts in ngrams_by_summary.values():
        corpus_counts.update(counts.keys())
    repeated = sum(count for phrase, count in corpus_counts.items() if count > 1)
    return {
        "summary_count": len(summary_metrics),
        "word_count": total_words,
        "item_count": total_items,
        "banned_phrase_hits_per_1000_words": round(
            sum(metric["banned_phrase_hits"] for metric in summary_metrics.values()) * 1000 / max(1, total_words), 3
        ),
        "figures_per_item": round(
            sum(len(FIGURE_PATTERN.findall(item)) for text in texts.values() for item in _items(text))
            / max(1, total_items),
            3,
        ),
        "items_with_zero_figures": sum(metric["items_with_zero_figures"] for metric in summary_metrics.values()),
        "bold_body_jaccard": round(
            sum(metric["bold_body_jaccard"] for metric in summary_metrics.values()) / max(1, len(summary_metrics)), 3
        ),
        "unattributed_causal_phrases": sum(
            metric["unattributed_causal_phrases"] for metric in summary_metrics.values()
        ),
        "truncated_summaries": sum(metric["truncated"] for metric in summary_metrics.values()),
        "cross_summary_repeated_4gram_rate": round(repeated / max(1, sum(corpus_counts.values())), 3),
    }


def discover(texts: dict[str, str], limit: int = 50) -> dict[str, Any]:
    phrase_spread: defaultdict[tuple[str, ...], set[str]] = defaultdict(set)
    counts: Counter[tuple[str, ...]] = Counter()
    openers: Counter[str] = Counter()
    for key, text in texts.items():
        content = re.sub(r"^#{1,6}.*$", "", text, flags=re.MULTILINE)
        sentences = _sentences(content)
        if sentences:
            opener = " ".join(_words(sentences[0])[:5])
            if opener:
                openers[opener] += 1
        for phrase in _ngrams(_discovery_words(text)):
            counts[phrase] += 1
            phrase_spread[phrase].add(key.split()[0])
    reused = [
        {"phrase": " ".join(phrase), "count": count, "airline_spread": len(phrase_spread[phrase])}
        for phrase, count in counts.most_common()
        if count > 1
    ]
    return {"sentence_openers": openers.most_common(limit), "reused_4grams": reused[:limit]}


def lint(path: Path) -> dict[str, Any]:
    texts = load_summaries(path)
    per_summary = {key: _summary_metrics(text) for key, text in texts.items()}
    return {"path": str(path), "per_summary": per_summary, "aggregate": _aggregate(per_summary, texts)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Lint generated SEC summary markdown.")
    parser.add_argument("path", type=Path, help="Path to an insights.json file")
    parser.add_argument("--baseline", type=Path, help="Baseline insights.json to compare")
    parser.add_argument("--compare", type=Path, help="Second insights.json to compare with --baseline")
    parser.add_argument("--discover", action="store_true", help="List reused openers and n-grams")
    args = parser.parse_args()

    result = lint(args.path)
    if args.baseline and args.compare:
        baseline = lint(args.baseline)["aggregate"]
        comparison = lint(args.compare)["aggregate"]
        result["comparison"] = {
            key: {"baseline": baseline.get(key), "compare": comparison.get(key)}
            for key in sorted(set(baseline) | set(comparison))
        }
    if args.discover:
        result["discover"] = discover(load_summaries(args.path))
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
