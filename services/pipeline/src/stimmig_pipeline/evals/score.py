"""Scoring of extracted claims against hand-labelled ones."""

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field

from ..domain import ClaimClass

#: Minimum token overlap (Jaccard) for a predicted quote to count as the expected one.
MATCH_THRESHOLD = 0.6

_TOKEN = re.compile(r"[^\W_]+")


@dataclass(frozen=True)
class LabelledClaim:
    quote: str
    claim_class: ClaimClass


@dataclass
class ItemScore:
    item_id: str
    true_positives: int
    false_positives: int
    false_negatives: int
    class_correct: int
    # (expected class, predicted class) -> count, for matched pairs
    confusion: Counter[tuple[str, str]]
    missed: list[str] = field(default_factory=list)
    spurious: list[str] = field(default_factory=list)
    misclassified: list[dict[str, str]] = field(default_factory=list)


@dataclass(frozen=True)
class Metrics:
    precision: float
    recall: float
    f1: float
    #: Share of matched claims whose class was right.
    class_accuracy: float
    #: The most harmful error for Stimmig: a forecast or opinion labelled as fact.
    false_fact: int

    def as_dict(self) -> dict[str, float]:
        return {
            "precision": self.precision,
            "recall": self.recall,
            "f1": self.f1,
            "class_accuracy": self.class_accuracy,
            "false_fact": float(self.false_fact),
        }


def _tokens(text: str) -> set[str]:
    return set(_TOKEN.findall(unicodedata.normalize("NFC", text).lower()))


def overlap(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def score_item(item_id: str, expected: list[LabelledClaim], predicted: list[LabelledClaim]) -> ItemScore:
    """Match quotes by token overlap, best pairs first, each claim used once.

    Quote boundaries legitimately vary (a model may include or drop a
    subordinate clause), so equality would be too strict.
    """
    pairs = sorted(
        (
            (score, ei, pi)
            for ei, e in enumerate(expected)
            for pi, p in enumerate(predicted)
            if (score := overlap(e.quote, p.quote)) >= MATCH_THRESHOLD
        ),
        reverse=True,
    )
    used_e: set[int] = set()
    used_p: set[int] = set()
    confusion: Counter[tuple[str, str]] = Counter()
    misclassified: list[dict[str, str]] = []
    for _, ei, pi in pairs:
        if ei in used_e or pi in used_p:
            continue
        used_e.add(ei)
        used_p.add(pi)
        exp, pred = expected[ei], predicted[pi]
        confusion[(exp.claim_class.value, pred.claim_class.value)] += 1
        if exp.claim_class is not pred.claim_class:
            misclassified.append(
                {"quote": exp.quote, "expected": exp.claim_class.value, "predicted": pred.claim_class.value}
            )

    return ItemScore(
        item_id=item_id,
        true_positives=len(used_e),
        false_positives=len(predicted) - len(used_p),
        false_negatives=len(expected) - len(used_e),
        class_correct=len(used_e) - len(misclassified),
        confusion=confusion,
        missed=[c.quote for i, c in enumerate(expected) if i not in used_e],
        spurious=[c.quote for i, c in enumerate(predicted) if i not in used_p],
        misclassified=misclassified,
    )


def metrics(scores: list[ItemScore]) -> Metrics:
    tp = sum(s.true_positives for s in scores)
    fp = sum(s.false_positives for s in scores)
    fn = sum(s.false_negatives for s in scores)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    confusion: Counter[tuple[str, str]] = Counter()
    for s in scores:
        confusion.update(s.confusion)
    false_fact = sum(
        n for (exp, pred), n in confusion.items() if pred == ClaimClass.FACT and exp != ClaimClass.FACT
    )
    return Metrics(
        precision=precision,
        recall=recall,
        f1=2 * precision * recall / (precision + recall) if precision + recall else 0.0,
        class_accuracy=sum(s.class_correct for s in scores) / tp if tp else 0.0,
        false_fact=false_fact,
    )
