from pathlib import Path

import pytest

from stimmig_pipeline.domain import ClaimClass, Side
from stimmig_pipeline.extraction import (
    REPORT_CLAIMS_TOOL,
    ExtractionInput,
    ExtractionOutputError,
    build_request,
    extract_claims,
)
from stimmig_pipeline.llm import MissingRecordingError, ReplayProvider

from .conftest import FakeProvider

# Synthetic text - not from a real vote.
TEXT = (
    "Die Zahl der Beispiele ist seit 2010 um 40 Prozent gestiegen. "
    "Mit der Initiative würden die Kosten bis 2035 auf 2 Milliarden Franken anwachsen. "
    "Das ist schlicht unfair."
)
INPUT = ExtractionInput(
    vote_id="2099-01-01-example", document_title="synthetic", side=Side.OPPONENTS, text=TEXT
)


def test_keeps_verbatim_claims_and_drops_invented_or_duplicate_ones() -> None:
    fact = "Die Zahl der Beispiele ist seit 2010 um 40 Prozent gestiegen."
    provider = FakeProvider()
    provider.response = {
        "claims": [
            {"quote": fact, "class": "fact", "rationale": "Past, measurable development."},
            {"quote": fact, "class": "fact", "rationale": "Duplicate."},
            {"quote": "Die Zahl hat sich verdoppelt.", "class": "fact", "rationale": "Invented."},
            {
                "quote": "Mit der Initiative würden die Kosten bis 2035 auf 2 Milliarden Franken anwachsen.",
                "class": "forecast",
                "rationale": "Future costs.",
                "estimate_by": "Opponents' committee",
            },
            {
                "quote": "Das ist schlicht unfair.",
                "class": "opinion",
                "rationale": "Value judgement.",
                "estimate_by": "should be dropped",
            },
        ]
    }
    result = extract_claims(provider, INPUT, "test-model")
    assert [c.claim_class for c in result.accepted] == [
        ClaimClass.FACT,
        ClaimClass.FORECAST,
        ClaimClass.OPINION,
    ]
    assert result.accepted[1].estimate_by == "Opponents' committee"
    assert result.accepted[2].estimate_by is None
    assert [r["reason"] for r in result.rejected] == ["duplicate", "not verbatim in source text"]
    assert all(c.side is Side.OPPONENTS for c in result.accepted)


def test_fails_loudly_on_output_outside_the_tool_schema() -> None:
    provider = FakeProvider()
    provider.response = {"claims": [{"quote": "x", "class": "belief"}]}
    with pytest.raises(ExtractionOutputError):
        extract_claims(provider, INPUT, "test-model")


def test_tool_schema_is_self_contained_and_lists_the_classes() -> None:
    schema = REPORT_CLAIMS_TOOL.input_schema
    assert "$defs" not in str(schema)
    item = schema["properties"]["claims"]["items"]
    assert item["properties"]["class"]["enum"] == ["fact", "forecast", "opinion"]
    assert set(item["required"]) == {"quote", "class", "rationale"}


def test_request_key_changes_with_input_and_model() -> None:
    base = build_request(INPUT, "m1").key()
    assert base == build_request(INPUT, "m1").key()
    assert base != build_request(INPUT, "m2").key()
    changed = ExtractionInput(INPUT.vote_id, INPUT.document_title, INPUT.side, TEXT + " ")
    assert base != build_request(changed, "m1").key()


def test_replay_reports_missing_recording(tmp_path: Path) -> None:
    with pytest.raises(MissingRecordingError, match="Re-record"):
        extract_claims(ReplayProvider(tmp_path), INPUT, "test-model")
