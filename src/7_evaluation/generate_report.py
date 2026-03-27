"""
Evaluation Report Generator

Reads all evaluation artefacts and writes a single human-readable
Markdown report to evaluation/evaluation_report.md.

Usage:
    python src/7_evaluation/generate_report.py
    python src/7_evaluation/generate_report.py --output my_report.md
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


# ── Paths (relative to project root) ─────────────────────────────────────────

ROOT = Path(__file__).resolve().parent.parent.parent

EVAL_RESULTS_PATH      = ROOT / "results" / "evaluation_results.json"
LTR_COMPARISON_PATH    = ROOT / "evaluation" / "ltr_comparison.json"
COMPREHENSIVE_PATH     = ROOT / "evaluation" / "comprehensive_evaluation_report.json"
FAIRNESS_PATH          = ROOT / "evaluation" / "fairness_report.json"
EXPLANATION_PATH       = ROOT / "evaluation" / "explanation_quality_study.json"
TRAINING_SUMMARY_PATH  = ROOT / "models" / "ranker" / "training_summary.md"
DEFAULT_OUTPUT         = ROOT / "evaluation" / "evaluation_report.md"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_json(path: Path) -> Optional[Dict]:
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return None


def _pct(v: float) -> str:
    return f"{v * 100:.1f}%"


def _bar(v: float, width: int = 20) -> str:
    filled = int(round(v * width))
    return "█" * filled + "░" * (width - filled)


def _grade_emoji(grade: str) -> str:
    g = grade.upper()
    if g.startswith("A"):
        return "🟢"
    if g.startswith("B"):
        return "🟡"
    return "🔴"


# ── Section builders ──────────────────────────────────────────────────────────

def _section_overview(comp: Optional[Dict]) -> str:
    lines = ["## Overview\n"]
    if comp:
        grade = comp.get("overall_grade", "N/A")
        ts = comp.get("summary", {}).get("evaluation_timestamp", "unknown")
        nq = comp.get("summary", {}).get("total_queries_evaluated", "?")
        lines.append(f"| Field | Value |")
        lines.append(f"|-------|-------|")
        lines.append(f"| Overall grade | {_grade_emoji(grade)} **{grade}** |")
        lines.append(f"| Evaluation timestamp | {ts} |")
        lines.append(f"| Queries evaluated | {nq} |")
    else:
        lines.append("_Comprehensive evaluation report not found._")
    return "\n".join(lines)


def _section_method_comparison(eval_results: Optional[Dict]) -> str:
    lines = ["## Method Accuracy Comparison\n"]
    if not eval_results:
        lines.append("_`results/evaluation_results.json` not found. Run the evaluator first._")
        return "\n".join(lines)

    key_metrics = ["precision@5", "precision@10", "ndcg@5", "ndcg@10", "MAP", "recall@10"]
    header = "| Method | " + " | ".join(key_metrics) + " |"
    sep    = "|--------|" + "|".join(["--------"] * len(key_metrics)) + "|"
    lines += [header, sep]

    # Find best per metric
    best: Dict[str, float] = {m: 0.0 for m in key_metrics}
    for entry in eval_results.values():
        acc = entry.get("metrics", {}).get("accuracy", {})
        for m in key_metrics:
            best[m] = max(best[m], acc.get(m, 0.0))

    for method_key, entry in eval_results.items():
        name = entry.get("name", method_key)
        acc = entry.get("metrics", {}).get("accuracy", {})
        cells = []
        for m in key_metrics:
            val = acc.get(m, 0.0)
            cell = _pct(val)
            if abs(val - best[m]) < 1e-6:
                cell = f"**{cell}**"
            cells.append(cell)
        lines.append(f"| {name} | " + " | ".join(cells) + " |")

    lines.append("\n_Bold = best in column._")
    return "\n".join(lines)


def _section_ndcg_bars(eval_results: Optional[Dict]) -> str:
    lines = ["## NDCG@5 Visual Comparison\n", "```"]
    if not eval_results:
        lines.append("No data.")
        lines.append("```")
        return "\n".join(lines)

    entries = [
        (e.get("name", k), e.get("metrics", {}).get("accuracy", {}).get("ndcg@5", 0.0))
        for k, e in eval_results.items()
    ]
    entries.sort(key=lambda x: x[1], reverse=True)
    max_val = max(v for _, v in entries) if entries else 1.0

    for name, val in entries:
        bar = _bar(val / max_val if max_val > 0 else 0)
        lines.append(f"{name:<30} {bar} {_pct(val)}")

    lines.append("```")
    return "\n".join(lines)


def _section_diversity_heritage(eval_results: Optional[Dict]) -> str:
    lines = ["## Diversity & Heritage-Specific Metrics\n"]
    if not eval_results:
        lines.append("_No data._")
        return "\n".join(lines)

    lines.append("| Method | ILD | Coverage | Temporal Acc | Spatial Rel | Domain Align |")
    lines.append("|--------|-----|----------|-------------|-------------|--------------|")
    for k, entry in eval_results.items():
        name = entry.get("name", k)
        div = entry.get("metrics", {}).get("diversity", {})
        hs  = entry.get("metrics", {}).get("heritage_specific", {})
        lines.append(
            f"| {name} "
            f"| {_pct(div.get('intra_list_diversity', 0))} "
            f"| {_pct(div.get('coverage', 0))} "
            f"| {_pct(hs.get('temporal_accuracy', 0))} "
            f"| {_pct(hs.get('spatial_relevance', 0))} "
            f"| {_pct(hs.get('cultural_domain_alignment', 0))} |"
        )
    return "\n".join(lines)


def _section_efficiency(eval_results: Optional[Dict]) -> str:
    lines = ["## Query Efficiency\n"]
    if not eval_results:
        lines.append("_No data._")
        return "\n".join(lines)

    lines.append("| Method | Latency (ms) | QPS |")
    lines.append("|--------|-------------|-----|")
    for k, entry in eval_results.items():
        name = entry.get("name", k)
        eff = entry.get("metrics", {}).get("efficiency", {})
        lat = eff.get("avg_query_latency_ms", 0.0)
        qps = eff.get("queries_per_second", 0.0)
        lines.append(f"| {name} | {lat:.3f} ms | {int(qps):,} |")
    return "\n".join(lines)


def _section_ltr(ltr: Optional[Dict]) -> str:
    lines = ["## LTR Ensemble Comparison\n"]
    if not ltr:
        lines.append("_`evaluation/ltr_comparison.json` not found._")
        return "\n".join(lines)

    lines.append("| Method | Mean NDCG | Std Dev | Queries |")
    lines.append("|--------|-----------|---------|---------|")
    sorted_ltr = sorted(ltr.items(), key=lambda x: x[1].get("mean_ndcg", 0), reverse=True)
    for method, v in sorted_ltr:
        lines.append(
            f"| {method.upper()} "
            f"| {v.get('mean_ndcg', 0):.4f} "
            f"| ±{v.get('std_ndcg', 0):.4f} "
            f"| {v.get('num_queries', 0)} |"
        )
    return "\n".join(lines)


def _section_system_quality(comp: Optional[Dict]) -> str:
    lines = ["## System Quality Breakdown\n"]
    if not comp:
        lines.append("_Comprehensive report not available._")
        return "\n".join(lines)

    sections = {
        "Diversity":          comp.get("diversity", {}),
        "Fairness":           comp.get("fairness", {}),
        "Explanation Quality": comp.get("explanation_quality", {}),
        "User Experience":    comp.get("user_experience", {}),
        "Robustness":         comp.get("robustness", {}),
    }

    for title, data in sections.items():
        if not data:
            continue
        interp = data.pop("interpretation", "")
        lines.append(f"### {title}\n")
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        for k, v in data.items():
            if isinstance(v, float):
                display = f"{v:.4f}"
            elif isinstance(v, dict):
                display = ", ".join(f"{kk}: {vv:.3f}" if isinstance(vv, float) else f"{kk}: {vv}" for kk, vv in v.items())
            else:
                display = str(v)
            lines.append(f"| {k.replace('_', ' ').title()} | {display} |")
        if interp:
            lines.append(f"\n_{interp}_\n")
        data["interpretation"] = interp  # restore for idempotency
    return "\n".join(lines)


def _section_full_accuracy(eval_results: Optional[Dict]) -> str:
    lines = ["## Full Accuracy Breakdown (all k)\n"]
    if not eval_results:
        lines.append("_No data._")
        return "\n".join(lines)

    all_metrics = [
        "precision@5", "recall@5", "f1@5", "ndcg@5",
        "precision@10", "recall@10", "f1@10", "ndcg@10",
        "precision@20", "recall@20", "f1@20", "ndcg@20",
        "MAP",
    ]
    header = "| Method | " + " | ".join(all_metrics) + " |"
    sep    = "|--------|" + "|".join(["------"] * len(all_metrics)) + "|"
    lines += [header, sep]

    for k, entry in eval_results.items():
        name = entry.get("name", k)
        acc = entry.get("metrics", {}).get("accuracy", {})
        cells = [_pct(acc.get(m, 0.0)) for m in all_metrics]
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────────────────

def generate_report(output_path: Path = DEFAULT_OUTPUT) -> None:
    print("Loading evaluation artefacts...")

    eval_results = _load_json(EVAL_RESULTS_PATH)
    ltr          = _load_json(LTR_COMPARISON_PATH)
    comp         = _load_json(COMPREHENSIVE_PATH)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    sections = [
        f"# Heritage Document Recommender — Evaluation Report\n",
        f"_Generated: {timestamp}_\n",
        "---\n",
        _section_overview(comp),
        "---\n",
        _section_method_comparison(eval_results),
        "\n---\n",
        _section_ndcg_bars(eval_results),
        "\n---\n",
        _section_diversity_heritage(eval_results),
        "\n---\n",
        _section_efficiency(eval_results),
        "\n---\n",
        _section_ltr(ltr),
        "\n---\n",
        _section_system_quality(comp),
        "\n---\n",
        _section_full_accuracy(eval_results),
        "\n---\n",
        "## Notes\n",
        "- All accuracy metrics computed on ground-truth annotations from `data/evaluation/`.",
        "- SimRank-Only achieves highest relevance (NDCG@5 ≈ 82%) at the cost of lower diversity.",
        "- CombMNZ and Borda are the best LTR ensemble methods (~75% NDCG).",
        "- LTR models trained on 54 samples from 1 query type; retrain with more diverse queries for full benefit.",
    ]

    report = "\n".join(sections)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        f.write(report)

    print(f"Report written to: {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate evaluation report.")
    parser.add_argument(
        "--output", type=str, default=str(DEFAULT_OUTPUT),
        help="Output Markdown file path."
    )
    args = parser.parse_args()
    generate_report(Path(args.output))
