"""Admin API, used by apps/admin. Every route checks a permission (see auth.py)."""

import uuid
from collections import Counter
from datetime import UTC, datetime
from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .. import audit
from ..auth import Permission, Principal, current_principal, require
from ..config import get_settings
from ..db import get_session
from ..domain import ClaimClass, ClaimStatus, VisualizationStatus, VoteStatus
from ..extraction import ExtractionInput, ExtractionOutputError, extract_claims
from ..llm import LlmProvider, MissingRecordingError, provider_for_mode
from ..models import AuditEvent, Claim, Document, ExtractionRun, Visualization, Vote
from ..publication import publication_problems
from ..schemas import (
    AuditEventOut,
    ClaimOut,
    ClaimReview,
    DocumentCreate,
    DocumentDetail,
    DocumentOut,
    ExtractionRunOut,
    Me,
    PublicationProblems,
    VisualizationCreate,
    VisualizationOut,
    VisualizationReview,
    VisualizationUpdate,
    VoteCreate,
    VoteDetail,
    VoteSummary,
    VoteUpdate,
)

router = APIRouter(prefix="/api", tags=["admin"])

SessionDep = Annotated[Session, Depends(get_session)]


@lru_cache
def get_llm_provider() -> LlmProvider:
    return provider_for_mode(get_settings().llm_mode)


def _now() -> datetime:
    return datetime.now(UTC)


def _get_vote(session: Session, vote_id: str) -> Vote:
    vote = session.scalars(
        select(Vote)
        .where(Vote.id == vote_id)
        .options(
            selectinload(Vote.documents),
            selectinload(Vote.claims).selectinload(Claim.visualizations),
        )
    ).one_or_none()
    if vote is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"vote {vote_id} not found")
    return vote


def _get[T: (Document, Claim, Visualization)](session: Session, model: type[T], entity_id: uuid.UUID) -> T:
    entity = session.get(model, entity_id)
    if entity is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail=f"{model.__tablename__[:-1]} {entity_id} not found"
        )
    return entity


def _summary(vote: Vote) -> VoteSummary:
    summary = VoteSummary.model_validate(vote)
    summary.claim_counts = dict(Counter(c.status.value for c in vote.claims))
    return summary


# --- who am I --------------------------------------------------------------


@router.get("/me")
def me(principal: Annotated[Principal, Depends(current_principal)]) -> Me:
    return Me(
        subject=principal.subject,
        email=principal.email,
        roles=sorted(r.value for r in principal.roles),
        permissions=sorted(p.value for p in principal.permissions),
    )


# --- votes -----------------------------------------------------------------


@router.get("/votes")
def list_votes(session: SessionDep, _: Annotated[Principal, require(Permission.READ)]) -> list[VoteSummary]:
    votes = session.scalars(select(Vote).options(selectinload(Vote.claims)).order_by(Vote.date.desc())).all()
    return [_summary(v) for v in votes]


@router.post("/votes", status_code=status.HTTP_201_CREATED)
def create_vote(
    body: VoteCreate, session: SessionDep, principal: Annotated[Principal, require(Permission.VOTES_WRITE)]
) -> VoteSummary:
    if session.get(Vote, body.id):
        raise HTTPException(status.HTTP_409_CONFLICT, detail=f"vote {body.id} already exists")
    data = body.model_dump(mode="json")
    vote = Vote(**{**data, "date": body.date})
    session.add(vote)
    audit.record(session, principal, "vote.create", "vote", vote.id, **data)
    session.commit()
    return _summary(_get_vote(session, vote.id))


@router.get("/votes/{vote_id}")
def get_vote(
    vote_id: str, session: SessionDep, _: Annotated[Principal, require(Permission.READ)]
) -> VoteDetail:
    vote = _get_vote(session, vote_id)
    detail = VoteDetail.model_validate(vote)
    detail.claim_counts = _summary(vote).claim_counts
    return detail


@router.patch("/votes/{vote_id}")
def update_vote(
    vote_id: str,
    body: VoteUpdate,
    session: SessionDep,
    principal: Annotated[Principal, require(Permission.VOTES_WRITE)],
) -> VoteSummary:
    vote = _get_vote(session, vote_id)
    changes = body.model_dump(mode="json", exclude_unset=True)
    for key, value in changes.items():
        setattr(vote, key, value)
    audit.record(session, principal, "vote.update", "vote", vote.id, **changes)
    session.commit()
    return _summary(_get_vote(session, vote_id))


@router.post(
    "/votes/{vote_id}/publish",
    response_model=VoteSummary,
    responses={409: {"model": PublicationProblems}},
)
def publish_vote(
    vote_id: str, session: SessionDep, principal: Annotated[Principal, require(Permission.VOTES_PUBLISH)]
) -> VoteSummary | JSONResponse:
    vote = _get_vote(session, vote_id)
    problems = publication_problems(vote)
    if problems:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT, content=PublicationProblems(problems=problems).model_dump()
        )
    vote.status = VoteStatus.PUBLISHED
    vote.published_at = vote.published_at or _now()
    audit.record(session, principal, "vote.publish", "vote", vote.id)
    session.commit()
    return _summary(_get_vote(session, vote_id))


@router.post("/votes/{vote_id}/unpublish")
def unpublish_vote(
    vote_id: str, session: SessionDep, principal: Annotated[Principal, require(Permission.VOTES_PUBLISH)]
) -> VoteSummary:
    vote = _get_vote(session, vote_id)
    vote.status = VoteStatus.DRAFT
    audit.record(session, principal, "vote.unpublish", "vote", vote.id)
    session.commit()
    return _summary(_get_vote(session, vote_id))


@router.get("/votes/{vote_id}/audit")
def vote_audit(
    vote_id: str, session: SessionDep, _: Annotated[Principal, require(Permission.READ)]
) -> list[AuditEventOut]:
    vote = _get_vote(session, vote_id)
    ids = {vote.id} | {str(d.id) for d in vote.documents} | {str(c.id) for c in vote.claims}
    ids |= {str(v.id) for c in vote.claims for v in c.visualizations}
    events = session.scalars(
        select(AuditEvent).where(AuditEvent.entity_id.in_(ids)).order_by(AuditEvent.at.desc()).limit(500)
    ).all()
    return [AuditEventOut.model_validate(e) for e in events]


# --- documents and extraction ---------------------------------------------


@router.post("/votes/{vote_id}/documents", status_code=status.HTTP_201_CREATED)
def add_document(
    vote_id: str,
    body: DocumentCreate,
    session: SessionDep,
    principal: Annotated[Principal, require(Permission.DOCUMENTS_WRITE)],
) -> DocumentOut:
    _get_vote(session, vote_id)
    document = Document(vote_id=vote_id, created_by=principal.actor, **body.model_dump(mode="json"))
    session.add(document)
    session.flush()
    audit.record(session, principal, "document.create", "document", document.id, title=body.title)
    session.commit()
    return DocumentOut.model_validate(document)


@router.get("/documents/{document_id}")
def get_document(
    document_id: uuid.UUID, session: SessionDep, _: Annotated[Principal, require(Permission.READ)]
) -> DocumentDetail:
    return DocumentDetail.model_validate(_get(session, Document, document_id))


@router.post("/documents/{document_id}/extract", status_code=status.HTTP_201_CREATED)
def run_extraction(
    document_id: uuid.UUID,
    session: SessionDep,
    provider: Annotated[LlmProvider, Depends(get_llm_provider)],
    principal: Annotated[Principal, require(Permission.EXTRACTION_RUN)],
) -> ExtractionRunOut:
    document: Document = _get(session, Document, document_id)
    model = get_settings().model
    try:
        result = extract_claims(
            provider,
            ExtractionInput(
                vote_id=document.vote_id,
                document_title=document.title,
                side=document.side,
                text=document.text,
            ),
            model,
        )
    except (ExtractionOutputError, MissingRecordingError) as error:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=str(error)) from error

    run = ExtractionRun(
        document_id=document.id,
        model=model,
        request_key=result.request_key,
        accepted=len(result.accepted),
        rejected=result.rejected,
        created_by=principal.actor,
    )
    session.add(run)
    session.flush()

    # Re-running an extraction must not duplicate claims that are already there.
    existing = {c.quote for c in session.scalars(select(Claim).where(Claim.document_id == document.id))}
    for claim in result.accepted:
        if claim.quote in existing:
            continue
        session.add(
            Claim(
                vote_id=document.vote_id,
                document_id=document.id,
                extraction_run_id=run.id,
                quote=claim.quote,
                side=claim.side,
                claim_class=claim.claim_class,
                proposed_class=claim.claim_class,
                class_rationale=claim.rationale,
                estimate_by=claim.estimate_by,
            )
        )
    audit.record(
        session,
        principal,
        "extraction.run",
        "document",
        document.id,
        run=str(run.id),
        accepted=run.accepted,
        rejected=len(run.rejected),
    )
    session.commit()
    return ExtractionRunOut.model_validate(run)


# --- claims ----------------------------------------------------------------


@router.get("/claims/{claim_id}")
def get_claim(
    claim_id: uuid.UUID, session: SessionDep, _: Annotated[Principal, require(Permission.READ)]
) -> ClaimOut:
    return ClaimOut.model_validate(_get(session, Claim, claim_id))


@router.post("/claims/{claim_id}/review")
def review_claim(
    claim_id: uuid.UUID,
    body: ClaimReview,
    session: SessionDep,
    principal: Annotated[Principal, require(Permission.CLAIMS_REVIEW)],
) -> ClaimOut:
    claim: Claim = _get(session, Claim, claim_id)
    changes = body.model_dump(exclude_unset=True, exclude={"status"})
    for key, value in changes.items():
        setattr(claim, key, value)
    if claim.claim_class is not ClaimClass.FORECAST:
        claim.estimate_by = None
    if claim.claim_class is not ClaimClass.FACT:
        claim.not_visualized_reason = None
    if (
        body.status is ClaimStatus.APPROVED
        and claim.claim_class is ClaimClass.FORECAST
        and not claim.estimate_by
    ):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, detail="an approved forecast needs estimate_by"
        )
    claim.status = body.status
    claim.reviewed_by = principal.actor
    claim.reviewed_at = _now()
    audit.record(
        session,
        principal,
        f"claim.{body.status.value}",
        "claim",
        claim.id,
        **{k: str(v) for k, v in changes.items()},
    )
    session.commit()
    session.refresh(claim)
    return ClaimOut.model_validate(claim)


# --- visualizations ----------------------------------------------------------


@router.post("/claims/{claim_id}/visualizations", status_code=status.HTTP_201_CREATED)
def create_visualization(
    claim_id: uuid.UUID,
    body: VisualizationCreate,
    session: SessionDep,
    principal: Annotated[Principal, require(Permission.VISUALIZATIONS_WRITE)],
) -> VisualizationOut:
    claim: Claim = _get(session, Claim, claim_id)
    if claim.claim_class is not ClaimClass.FACT or claim.status is not ClaimStatus.APPROVED:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="charts can only be made for approved facts")
    data = body.model_dump(mode="json")
    viz = Visualization(claim_id=claim.id, created_by=principal.actor, edited_by=[principal.actor], **data)
    session.add(viz)
    session.flush()
    audit.record(session, principal, "visualization.create", "visualization", viz.id, title=body.title)
    session.commit()
    return VisualizationOut.model_validate(viz)


@router.get("/visualizations/{viz_id}")
def get_visualization(
    viz_id: uuid.UUID, session: SessionDep, _: Annotated[Principal, require(Permission.READ)]
) -> VisualizationOut:
    return VisualizationOut.model_validate(_get(session, Visualization, viz_id))


@router.patch("/visualizations/{viz_id}")
def update_visualization(
    viz_id: uuid.UUID,
    body: VisualizationUpdate,
    session: SessionDep,
    principal: Annotated[Principal, require(Permission.VISUALIZATIONS_WRITE)],
) -> VisualizationOut:
    viz: Visualization = _get(session, Visualization, viz_id)
    if viz.status in (VisualizationStatus.IN_REVIEW, VisualizationStatus.APPROVED):
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail=f"a chart that is {viz.status.value} cannot be edited"
        )
    changes = body.model_dump(mode="json", exclude_unset=True)
    for key, value in changes.items():
        setattr(viz, key, value)
    viz.status = VisualizationStatus.DRAFT
    if principal.actor not in viz.edited_by:
        viz.edited_by = [*viz.edited_by, principal.actor]
    audit.record(session, principal, "visualization.update", "visualization", viz.id, fields=sorted(changes))
    session.commit()
    return VisualizationOut.model_validate(viz)


@router.post("/visualizations/{viz_id}/submit")
def submit_visualization(
    viz_id: uuid.UUID,
    session: SessionDep,
    principal: Annotated[Principal, require(Permission.VISUALIZATIONS_WRITE)],
) -> VisualizationOut:
    viz: Visualization = _get(session, Visualization, viz_id)
    if viz.status is not VisualizationStatus.DRAFT:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="only drafts can be submitted for review")
    viz.status = VisualizationStatus.IN_REVIEW
    audit.record(session, principal, "visualization.submit", "visualization", viz.id)
    session.commit()
    return VisualizationOut.model_validate(viz)


@router.post("/visualizations/{viz_id}/review")
def review_visualization(
    viz_id: uuid.UUID,
    body: VisualizationReview,
    session: SessionDep,
    principal: Annotated[Principal, require(Permission.VISUALIZATIONS_REVIEW)],
) -> VisualizationOut:
    viz: Visualization = _get(session, Visualization, viz_id)
    if viz.status is not VisualizationStatus.IN_REVIEW:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="only charts in review can be reviewed")
    if principal.actor in viz.edited_by:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="four-eyes principle: you edited this chart")
    if body.decision == "reject" and not body.note:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="a rejection needs a note")
    viz.status = VisualizationStatus.APPROVED if body.decision == "approve" else VisualizationStatus.REJECTED
    viz.reviewed_by = principal.actor
    viz.reviewed_at = _now()
    viz.review_note = body.note
    audit.record(
        session, principal, f"visualization.{body.decision}", "visualization", viz.id, note=body.note
    )
    session.commit()
    return VisualizationOut.model_validate(viz)
