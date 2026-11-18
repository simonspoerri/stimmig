"""Labelled eval datasets (``evals/datasets/*.json``)."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from ..domain import ClaimClass, Side

DATASETS_DIR = Path(__file__).resolve().parents[3] / "evals" / "datasets"

Split = Literal["dev", "test"]


class ExpectedClaim(BaseModel):
    quote: str
    claim_class: ClaimClass = Field(alias="class")


class ItemInput(BaseModel):
    vote_id: str
    document_title: str
    side: Side
    text: str


class Item(BaseModel):
    id: str
    #: ``dev`` items are for prompt work; ``test`` items are only ever scored.
    split: Split
    input: ItemInput
    expected: list[ExpectedClaim]


class Dataset(BaseModel):
    name: str
    description: str
    #: Synthetic datasets test the harness itself; they say nothing about model quality.
    synthetic: bool
    items: list[Item]


def load_datasets(directory: Path = DATASETS_DIR) -> list[Dataset]:
    return [Dataset.model_validate_json(p.read_text()) for p in sorted(directory.glob("*.json"))]
