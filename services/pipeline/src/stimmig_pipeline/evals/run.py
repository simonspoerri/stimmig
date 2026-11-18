"""Run datasets through the extraction, repeat, aggregate and check thresholds."""

import statistics
import tomllib
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from ..domain import ClaimClass
from ..extraction import ExtractionInput, extract_claims
from ..llm import LlmProvider
from .dataset import Dataset, Split
from .score import ItemScore, LabelledClaim, Metrics, metrics, score_item

THRESHOLDS_PATH = Path(__file__).resolve().parents[3] / "evals" / "thresholds.toml"

#: Gets the run index (0-based) and returns the provider for that run.
ProviderFactory = Callable[[int], LlmProvider]


@dataclass
class Group:
    """One dataset split, scored over several runs."""

    dataset: str
    split: Split
    synthetic: bool
    runs: list[Metrics] = field(default_factory=list)
    rejected_by_checks: list[int] = field(default_factory=list)
    #: Item details of the first run, for error analysis.
    items: list[ItemScore] = field(default_factory=list)

    def spread(self) -> dict[str, dict[str, float]]:
        values: dict[str, list[float]] = {}
        for run in self.runs:
            for key, value in run.as_dict().items():
                values.setdefault(key, []).append(value)
        return {key: {"mean": statistics.fmean(v), "min": min(v), "max": max(v)} for key, v in values.items()}


@dataclass
class Report:
    model: str
    runs: int
    groups: list[Group]
    failures: list[str] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "runs": self.runs,
            "failures": self.failures,
            "groups": [
                {
                    "dataset": g.dataset,
                    "split": g.split,
                    "synthetic": g.synthetic,
                    "metrics": g.spread(),
                    "rejected_by_checks": g.rejected_by_checks,
                    "items": [{**asdict(i), "confusion": _confusion(i)} for i in g.items],
                }
                for g in self.groups
            ],
        }


def _confusion(item: ItemScore) -> dict[str, int]:
    return {f"{exp}->{pred}": n for (exp, pred), n in sorted(item.confusion.items())}


def run_evals(
    datasets: list[Dataset],
    provider_for_run: ProviderFactory,
    model: str,
    *,
    runs: int = 1,
    splits: tuple[Split, ...] = ("dev", "test"),
) -> Report:
    groups: dict[tuple[str, Split], Group] = {}
    for run_index in range(runs):
        provider = provider_for_run(run_index)
        for dataset in datasets:
            for split in splits:
                items = [i for i in dataset.items if i.split == split]
                if not items:
                    continue
                group = groups.setdefault(
                    (dataset.name, split), Group(dataset.name, split, dataset.synthetic)
                )
                scores: list[ItemScore] = []
                rejected = 0
                for item in items:
                    result = extract_claims(provider, ExtractionInput(**item.input.model_dump()), model)
                    rejected += len(result.rejected)
                    scores.append(
                        score_item(
                            item.id,
                            [LabelledClaim(e.quote, e.claim_class) for e in item.expected],
                            [LabelledClaim(c.quote, ClaimClass(c.claim_class)) for c in result.accepted],
                        )
                    )
                group.runs.append(metrics(scores))
                group.rejected_by_checks.append(rejected)
                if run_index == 0:
                    group.items = scores
    return Report(model=model, runs=runs, groups=list(groups.values()))


def load_thresholds(path: Path = THRESHOLDS_PATH) -> dict[str, dict[str, float]]:
    with path.open("rb") as file:
        return tomllib.load(file)


def check_thresholds(report: Report, thresholds: dict[str, dict[str, float]]) -> list[str]:
    """Thresholds are checked against the worst run, not the average."""
    failures: list[str] = []
    for group in report.groups:
        limits = thresholds.get(group.split, {})
        spread = group.spread()
        name = f"{group.dataset}/{group.split}"
        for key, limit in limits.items():
            kind, metric = key.split("_", 1)
            if kind == "min" and spread[metric]["min"] < limit:
                failures.append(f"{name}: {metric} {spread[metric]['min']:.3f} < {limit}")
            if kind == "max" and spread[metric]["max"] > limit:
                failures.append(f"{name}: {metric} {spread[metric]['max']:.0f} > {limit:.0f}")
    report.failures = failures
    return failures


def _pct(spread: dict[str, float]) -> str:
    if spread["min"] == spread["max"]:
        return f"{spread['mean'] * 100:.1f} %"
    return f"{spread['mean'] * 100:.1f} % ({spread['min'] * 100:.0f}-{spread['max'] * 100:.0f})"


def to_markdown(report: Report) -> str:
    lines = [
        "# Eval report",
        "",
        f"Model `{report.model}`, {report.runs} run(s). Ranges in brackets are min-max over runs.",
        "",
        "| Dataset | Split | Precision | Recall | F1 | Class accuracy "
        "| Forecast/opinion as fact | Dropped by checks |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for g in report.groups:
        s = g.spread()
        name = f"{g.dataset} (synthetic)" if g.synthetic else g.dataset
        lines.append(
            f"| {name} | {g.split} | {_pct(s['precision'])} | {_pct(s['recall'])} | {_pct(s['f1'])} "
            f"| {_pct(s['class_accuracy'])} | {s['false_fact']['max']:.0f} | {max(g.rejected_by_checks)} |"
        )
    lines += ["", "Synthetic datasets only test the harness and say nothing about the model's quality.", ""]
    if report.failures:
        lines += ["## Thresholds failed", "", *[f"- {f}" for f in report.failures], ""]
    else:
        lines += ["All thresholds passed.", ""]

    dev_errors = [
        (g.dataset, i)
        for g in report.groups
        if g.split == "dev"
        for i in g.items
        if i.missed or i.spurious or i.misclassified
    ]
    if dev_errors:
        lines += ["## Errors on dev items (first run)", ""]
        for dataset, item in dev_errors:
            lines.append(f"### {dataset} / {item.item_id}")
            lines += [f"- missed: {q}" for q in item.missed]
            lines += [f"- spurious: {q}" for q in item.spurious]
            lines += [
                f"- {m['expected']} labelled {m['predicted']}: {m['quote']}" for m in item.misclassified
            ]
            lines.append("")
    return "\n".join(lines)
