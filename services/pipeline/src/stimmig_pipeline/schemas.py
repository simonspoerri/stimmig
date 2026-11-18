"""API request and response models. They define the OpenAPI schema the frontends' types are generated from."""

import re
import uuid
from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, HttpUrl

from .domain import ClaimClass, ClaimStatus, DocumentKind, Side, VisualizationStatus, VoteKind, VoteStatus

VOTE_ID = re.compile(r"^\d{4}-\d{2}-\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*$")


def _https(url: HttpUrl) -> HttpUrl:
    if url.scheme != "https":
        raise ValueError("source URLs must use https")
    return url


HttpsUrl = Annotated[HttpUrl, AfterValidator(_https)]


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


# --- votes -----------------------------------------------------------------


class SourceListEntry(ApiModel):
    label: str = Field(min_length=2)
    url: HttpsUrl


class VoteBase(ApiModel):
    date: date
    title: str = Field(min_length=3, max_length=300)
    kind: VoteKind
    official_url: HttpsUrl
    source_list: list[SourceListEntry] = Field(default_factory=list)


class VoteCreate(VoteBase):
    id: str = Field(pattern=VOTE_ID.pattern, description="YYYY-MM-DD-short-name, e.g. 2027-02-28-example")


class VoteUpdate(ApiModel):
    title: str | None = Field(default=None, min_length=3, max_length=300)
    kind: VoteKind | None = None
    official_url: HttpsUrl | None = None
    source_list: list[SourceListEntry] | None = None


class VoteSummary(VoteBase):
    id: str
    status: VoteStatus
    published_at: datetime | None
    claim_counts: dict[str, int] = Field(default_factory=dict, description="claims per status")


# --- documents -------------------------------------------------------------


class DocumentCreate(ApiModel):
    kind: DocumentKind
    side: Side
    title: str = Field(min_length=3)
    url: HttpsUrl
    locator: str | None = None
    text: str = Field(min_length=20)


class DocumentOut(ApiModel):
    id: uuid.UUID
    vote_id: str
    kind: DocumentKind
    side: Side
    title: str
    url: str
    locator: str | None
    created_by: str
    created_at: datetime


class DocumentDetail(DocumentOut):
    text: str


class ExtractionRunOut(ApiModel):
    id: uuid.UUID
    document_id: uuid.UUID
    model: str
    request_key: str
    accepted: int
    rejected: list[dict[str, str]]
    created_by: str
    created_at: datetime


# --- visualizations --------------------------------------------------------


class DataSource(ApiModel):
    publisher: str = Field(min_length=2)
    title: str = Field(min_length=3)
    url: HttpsUrl
    dataset_id: str | None = Field(default=None, description="Table or dataset id at the publisher")
    accessed_at: date


def _inline_data_only(spec: dict[str, Any]) -> dict[str, Any]:
    """Published charts never fetch anything at view time."""

    def check(node: Any) -> None:
        if isinstance(node, dict):
            data = node.get("data")
            if isinstance(data, dict) and "url" in data:
                raise ValueError("Vega-Lite data must be inline values, not a url")
            for value in node.values():
                check(value)
        elif isinstance(node, list):
            for item in node:
                check(item)

    check(spec)
    if "mark" not in spec and not any(k in spec for k in ("layer", "concat", "hconcat", "vconcat", "facet")):
        raise ValueError("not a Vega-Lite spec: needs a mark or a composition")
    return spec


VegaLiteSpec = Annotated[dict[str, Any], AfterValidator(_inline_data_only)]


class VisualizationCreate(ApiModel):
    title: str = Field(min_length=3)
    description: str = Field(min_length=10, description="Neutral description of what the chart shows")
    spec: VegaLiteSpec
    data_sources: list[DataSource] = Field(min_length=1)


class VisualizationUpdate(ApiModel):
    title: str | None = Field(default=None, min_length=3)
    description: str | None = Field(default=None, min_length=10)
    spec: VegaLiteSpec | None = None
    data_sources: list[DataSource] | None = Field(default=None, min_length=1)


class VisualizationReview(ApiModel):
    decision: Literal["approve", "reject"]
    note: str | None = None


class VisualizationOut(ApiModel):
    id: uuid.UUID
    claim_id: uuid.UUID
    title: str
    description: str
    spec: dict[str, Any]
    data_sources: list[DataSource]
    status: VisualizationStatus
    created_by: str
    edited_by: list[str]
    reviewed_by: str | None
    reviewed_at: datetime | None
    review_note: str | None
    created_at: datetime
    updated_at: datetime


# --- claims ----------------------------------------------------------------


class ClaimReview(ApiModel):
    status: Literal[ClaimStatus.APPROVED, ClaimStatus.REJECTED]
    claim_class: ClaimClass | None = Field(default=None, alias="class")
    class_rationale: str | None = Field(default=None, min_length=10)
    estimate_by: str | None = None
    not_visualized_reason: str | None = None


class ClaimOut(ApiModel):
    id: uuid.UUID
    vote_id: str
    document_id: uuid.UUID
    quote: str
    side: Side
    claim_class: ClaimClass = Field(serialization_alias="class")
    proposed_class: ClaimClass | None
    class_rationale: str
    estimate_by: str | None
    not_visualized_reason: str | None
    status: ClaimStatus
    reviewed_by: str | None
    reviewed_at: datetime | None
    created_at: datetime
    visualizations: list[VisualizationOut] = Field(default_factory=list)


class VoteDetail(VoteSummary):
    documents: list[DocumentOut]
    claims: list[ClaimOut]


class PublicationProblems(ApiModel):
    detail: str = "vote cannot be published"
    problems: list[str]


class AuditEventOut(ApiModel):
    id: int
    actor: str
    action: str
    entity: str
    entity_id: str
    data: dict[str, Any]
    at: datetime


class Me(ApiModel):
    subject: str
    email: str | None
    roles: list[str]
    permissions: list[str]


# --- public API ------------------------------------------------------------


class PublicSource(ApiModel):
    document: str
    locator: str | None
    url: str


class PublicVisualization(ApiModel):
    id: uuid.UUID
    title: str
    description: str
    spec: dict[str, Any]
    data_sources: list[DataSource]


class PublicFact(ApiModel):
    id: uuid.UUID
    quote: str
    side: Side
    source: PublicSource
    visualizations: list[PublicVisualization]
    not_visualized_reason: str | None


class PublicForecast(ApiModel):
    id: uuid.UUID
    quote: str
    side: Side
    estimate_by: str
    source: PublicSource


class PublicVoteSummary(ApiModel):
    id: str
    date: date
    title: str
    kind: VoteKind
    official_url: str
    published_at: datetime
    fact_count: int
    visualization_count: int


class PublicVote(PublicVoteSummary):
    source_list: list[SourceListEntry]
    facts: list[PublicFact]
    forecasts: list[PublicForecast]
