from typing import Any

from stimmig_pipeline.domain import ClaimClass
from stimmig_pipeline.evals.dataset import Dataset, load_datasets
from stimmig_pipeline.evals.run import check_thresholds, load_thresholds, run_evals, to_markdown
from stimmig_pipeline.evals.score import LabelledClaim, metrics, overlap, score_item
from stimmig_pipeline.llm import ReplayProvider, ToolCallRequest

FACT, FORECAST, OPINION = ClaimClass.FACT, ClaimClass.FORECAST, ClaimClass.OPINION


def test_overlap_bounds() -> None:
    assert overlap("Die Exporte steigen.", "die exporte steigen") == 1
    assert overlap("Exporte", "Importe") == 0


def test_matches_quotes_with_slightly_different_boundaries() -> None:
    score = score_item(
        "x",
        [LabelledClaim("Die Exporte sind seit 2015 um 30 Prozent gestiegen", FACT)],
        [LabelledClaim("Die Exporte sind seit 2015 um 30 Prozent gestiegen, sagt das SECO", FACT)],
    )
    assert (score.true_positives, score.class_correct) == (1, 1)


def test_counts_misses_spurious_claims_and_false_facts() -> None:
    score = score_item(
        "x",
        [
            LabelledClaim("Die Kosten werden bis 2035 auf 2 Milliarden steigen", FORECAST),
            LabelledClaim("Heute gibt es 120 solche Betriebe im Land", FACT),
        ],
        [
            LabelledClaim("Die Kosten werden bis 2035 auf 2 Milliarden steigen", FACT),
            LabelledClaim("Das ist ungerecht", OPINION),
        ],
    )
    assert (score.true_positives, score.false_positives, score.false_negatives) == (1, 1, 1)
    result = metrics([score])
    assert (result.precision, result.recall, result.class_accuracy, result.false_fact) == (0.5, 0.5, 0.0, 1)


def test_synthetic_dataset_passes_with_its_fixture_recordings() -> None:
    datasets = load_datasets()
    report = run_evals(datasets, lambda _: ReplayProvider(), "claude-sonnet-5-5")
    assert {(g.dataset, g.split) for g in report.groups} >= {
        ("synthetic-smoke", "dev"),
        ("synthetic-smoke", "test"),
    }
    assert check_thresholds(report, load_thresholds()) == []


class Flaky:
    """Answers perfectly on even runs and calls every forecast a fact on odd ones."""

    def __init__(self, run: int, expected: dict[str, list[dict[str, Any]]]) -> None:
        self.run, self.expected = run, expected

    def call_tool(self, request: ToolCallRequest) -> dict[str, Any]:
        claims = [dict(c) for c in self.expected[request.user]]
        if self.run % 2:
            for claim in claims:
                if claim["class"] == "forecast":
                    claim["class"] = "fact"
        return {"claims": claims}


def test_repeated_runs_report_spread_and_gate_on_the_worst_run() -> None:
    dataset: Dataset = load_datasets()[0]
    from stimmig_pipeline.extraction import ExtractionInput, build_request  # noqa: PLC0415

    expected = {
        build_request(ExtractionInput(**i.input.model_dump()), "m").user: [
            {"quote": e.quote, "class": e.claim_class.value, "rationale": "r", "estimate_by": "x"}
            for e in i.expected
        ]
        for i in dataset.items
    }
    report = run_evals([dataset], lambda run: Flaky(run, expected), "m", runs=2, splits=("dev",))
    spread = report.groups[0].spread()
    assert spread["false_fact"] == {"mean": 0.5, "min": 0.0, "max": 1.0}
    failures = check_thresholds(report, {"dev": {"max_false_fact": 0, "min_recall": 0.9}})
    assert failures == ["synthetic-smoke/dev: false_fact 1 > 0"]
    assert "Thresholds failed" in to_markdown(report)
