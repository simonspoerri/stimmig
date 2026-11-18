"""Database tables. Schema changes need an Alembic migration in ``migrations/versions``."""

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from .domain import ClaimClass, ClaimStatus, DocumentKind, Side, VisualizationStatus, VoteKind, VoteStatus


def _enum(cls: type[Any], name: str) -> Enum:
    return Enum(cls, name=name, values_callable=lambda e: [m.value for m in e])


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: JSONB, list[Any]: JSONB}  # noqa: RUF012 - SQLAlchemy API


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Vote(TimestampMixin, Base):
    __tablename__ = "votes"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    date: Mapped[date] = mapped_column(Date)
    title: Mapped[str] = mapped_column(Text)
    kind: Mapped[VoteKind] = mapped_column(_enum(VoteKind, "vote_kind"))
    official_url: Mapped[str] = mapped_column(Text)
    # The fixed list of public sources, decided before analysis starts (methodology §1.3).
    source_list: Mapped[list[Any]] = mapped_column(default=list)
    status: Mapped[VoteStatus] = mapped_column(_enum(VoteStatus, "vote_status"), default=VoteStatus.DRAFT)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    documents: Mapped[list["Document"]] = relationship(back_populates="vote", order_by="Document.created_at")
    claims: Mapped[list["Claim"]] = relationship(back_populates="vote", order_by="Claim.created_at")


class Document(TimestampMixin, Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    vote_id: Mapped[str] = mapped_column(ForeignKey("votes.id", ondelete="CASCADE"), index=True)
    kind: Mapped[DocumentKind] = mapped_column(_enum(DocumentKind, "document_kind"))
    side: Mapped[Side] = mapped_column(_enum(Side, "side"))
    title: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text)
    # Page, paragraph or anchor inside the source, shown next to quotes.
    locator: Mapped[str | None] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(String(200))

    vote: Mapped[Vote] = relationship(back_populates="documents")


class ExtractionRun(Base):
    __tablename__ = "extraction_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    model: Mapped[str] = mapped_column(String(100))
    request_key: Mapped[str] = mapped_column(String(64))
    accepted: Mapped[int]
    rejected: Mapped[list[Any]] = mapped_column(default=list)
    created_by: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Claim(TimestampMixin, Base):
    __tablename__ = "claims"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    vote_id: Mapped[str] = mapped_column(ForeignKey("votes.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    extraction_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("extraction_runs.id"))
    quote: Mapped[str] = mapped_column(Text)
    side: Mapped[Side] = mapped_column(_enum(Side, "side"))
    claim_class: Mapped[ClaimClass] = mapped_column("class", _enum(ClaimClass, "claim_class"))
    class_rationale: Mapped[str] = mapped_column(Text)
    # What the model proposed, kept so review corrections can feed the evals.
    proposed_class: Mapped[ClaimClass | None] = mapped_column(_enum(ClaimClass, "claim_class"))
    estimate_by: Mapped[str | None] = mapped_column(Text)
    not_visualized_reason: Mapped[str | None] = mapped_column(Text)
    status: Mapped[ClaimStatus] = mapped_column(_enum(ClaimStatus, "claim_status"), default=ClaimStatus.DRAFT)
    reviewed_by: Mapped[str | None] = mapped_column(String(200))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    vote: Mapped[Vote] = relationship(back_populates="claims")
    document: Mapped[Document] = relationship()
    visualizations: Mapped[list["Visualization"]] = relationship(
        back_populates="claim", order_by="Visualization.created_at"
    )


class Visualization(TimestampMixin, Base):
    __tablename__ = "visualizations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    claim_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("claims.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    spec: Mapped[dict[str, Any]]
    data_sources: Mapped[list[Any]] = mapped_column(default=list)
    status: Mapped[VisualizationStatus] = mapped_column(
        _enum(VisualizationStatus, "visualization_status"), default=VisualizationStatus.DRAFT
    )
    created_by: Mapped[str] = mapped_column(String(200))
    # Everyone who edited it; none of them may review it (four eyes).
    edited_by: Mapped[list[Any]] = mapped_column(default=list)
    reviewed_by: Mapped[str | None] = mapped_column(String(200))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_note: Mapped[str | None] = mapped_column(Text)

    claim: Mapped[Claim] = relationship(back_populates="visualizations")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    actor: Mapped[str] = mapped_column(String(200))
    action: Mapped[str] = mapped_column(String(80))
    entity: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str] = mapped_column(String(80), index=True)
    data: Mapped[dict[str, Any]] = mapped_column(default=dict)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
