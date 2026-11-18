"""Domain vocabulary shared by the database, the API and the extraction step."""

from enum import StrEnum


class VoteKind(StrEnum):
    POPULAR_INITIATIVE = "popular_initiative"
    MANDATORY_REFERENDUM = "mandatory_referendum"
    OPTIONAL_REFERENDUM = "optional_referendum"
    COUNTER_PROPOSAL = "counter_proposal"


class VoteStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"


class Side(StrEnum):
    """Who makes a claim. ``federal_council`` covers the Federal Council's own explanations."""

    PROPONENTS = "proponents"
    OPPONENTS = "opponents"
    FEDERAL_COUNCIL = "federal_council"


class DocumentKind(StrEnum):
    BOOKLET = "booklet"
    PARLIAMENT = "parliament"
    PUBLIC = "public"


class ClaimClass(StrEnum):
    """See docs/methodology.md, section 2."""

    FACT = "fact"
    FORECAST = "forecast"
    OPINION = "opinion"


class ClaimStatus(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    REJECTED = "rejected"


class VisualizationStatus(StrEnum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"
