"""Rules a vote must pass before it may be published (docs/architecture.md)."""

from .domain import ClaimClass, ClaimStatus, VisualizationStatus
from .models import Vote


def publication_problems(vote: Vote) -> list[str]:
    """Human-readable problems; an empty list means the vote may be published."""
    problems: list[str] = []
    approved = [c for c in vote.claims if c.status is ClaimStatus.APPROVED]
    drafts = [c for c in vote.claims if c.status is ClaimStatus.DRAFT]

    if not approved:
        problems.append("no approved claims")
    if drafts:
        problems.append(f"{len(drafts)} claim(s) not reviewed yet")

    for claim in approved:
        label = f'claim "{claim.quote[:60]}"'
        if claim.claim_class is ClaimClass.FACT:
            charts = [v for v in claim.visualizations if v.status is VisualizationStatus.APPROVED]
            if not charts and not claim.not_visualized_reason:
                problems.append(f"{label} is a fact without an approved chart or a not-visualized reason")
        elif claim.claim_class is ClaimClass.FORECAST and not claim.estimate_by:
            problems.append(f"{label} is a forecast without estimate_by")

        for viz in claim.visualizations:
            if viz.status is VisualizationStatus.IN_REVIEW:
                problems.append(f'chart "{viz.title}" is still in review')
    return problems
