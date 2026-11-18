"""Public, read-only API used by apps/web. Only approved content of published votes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..db import get_session
from ..domain import ClaimClass, ClaimStatus, VisualizationStatus, VoteStatus
from ..models import Claim, Vote
from ..schemas import (
    DataSource,
    PublicFact,
    PublicForecast,
    PublicSource,
    PublicVisualization,
    PublicVote,
    PublicVoteSummary,
    SourceListEntry,
)

router = APIRouter(prefix="/public/v1", tags=["public"])

SessionDep = Annotated[Session, Depends(get_session)]
CACHE_CONTROL = "public, max-age=60, stale-while-revalidate=600"


def _published_votes(session: Session, vote_id: str | None = None) -> list[Vote]:
    query = (
        select(Vote)
        .where(Vote.status == VoteStatus.PUBLISHED)
        .options(
            selectinload(Vote.claims).selectinload(Claim.visualizations),
            selectinload(Vote.claims).selectinload(Claim.document),
        )
        .order_by(Vote.date.desc())
    )
    if vote_id is not None:
        query = query.where(Vote.id == vote_id)
    return list(session.scalars(query).all())


def _source(claim: Claim) -> PublicSource:
    return PublicSource(document=claim.document.title, locator=claim.document.locator, url=claim.document.url)


def _public_vote(vote: Vote) -> PublicVote:
    facts: list[PublicFact] = []
    forecasts: list[PublicForecast] = []
    for claim in vote.claims:
        if claim.status is not ClaimStatus.APPROVED:
            continue
        if claim.claim_class is ClaimClass.FACT:
            charts = [
                PublicVisualization(
                    id=v.id,
                    title=v.title,
                    description=v.description,
                    spec=v.spec,
                    data_sources=[DataSource.model_validate(s) for s in v.data_sources],
                )
                for v in claim.visualizations
                if v.status is VisualizationStatus.APPROVED
            ]
            facts.append(
                PublicFact(
                    id=claim.id,
                    quote=claim.quote,
                    side=claim.side,
                    source=_source(claim),
                    visualizations=charts,
                    not_visualized_reason=None if charts else claim.not_visualized_reason,
                )
            )
        elif claim.claim_class is ClaimClass.FORECAST and claim.estimate_by:
            forecasts.append(
                PublicForecast(
                    id=claim.id,
                    quote=claim.quote,
                    side=claim.side,
                    estimate_by=claim.estimate_by,
                    source=_source(claim),
                )
            )
    assert vote.published_at is not None
    return PublicVote(
        id=vote.id,
        date=vote.date,
        title=vote.title,
        kind=vote.kind,
        official_url=vote.official_url,
        published_at=vote.published_at,
        fact_count=len(facts),
        visualization_count=sum(len(f.visualizations) for f in facts),
        source_list=[SourceListEntry.model_validate(s) for s in vote.source_list],
        facts=facts,
        forecasts=forecasts,
    )


@router.get("/votes")
def list_published_votes(session: SessionDep, response: Response) -> list[PublicVoteSummary]:
    response.headers["Cache-Control"] = CACHE_CONTROL
    return [PublicVoteSummary.model_validate(_public_vote(v).model_dump()) for v in _published_votes(session)]


@router.get("/votes/{vote_id}")
def get_published_vote(vote_id: str, session: SessionDep, response: Response) -> PublicVote:
    votes = _published_votes(session, vote_id)
    if not votes:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="vote not found")
    response.headers["Cache-Control"] = CACHE_CONTROL
    return _public_vote(votes[0])
