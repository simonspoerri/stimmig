"""Claim extraction: one forced tool call, then deterministic checks."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from .domain import ClaimClass, Side
from .llm import LlmProvider, Tool, ToolCallRequest
from .verbatim import is_verbatim

PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "extract_claims.md"


class ReportedClaim(BaseModel):
    quote: str = Field(description="Verbatim passage from the text.")
    claim_class: ClaimClass = Field(alias="class", description="fact, forecast or opinion.")
    rationale: str = Field(description="One sentence: why this class fits.")
    estimate_by: str | None = Field(default=None, description="Only for forecasts: who makes the estimate.")


class ReportClaims(BaseModel):
    """Input of the ``report_claims`` tool. Also the source of the tool's JSON schema."""

    claims: list[ReportedClaim]


def _inline_refs(schema: dict[str, Any]) -> dict[str, Any]:
    """Resolve ``$ref``/``$defs`` so the tool schema is one self-contained object."""
    defs = schema.get("$defs", {})

    def resolve(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                return resolve(defs[node["$ref"].split("/")[-1]])
            return {k: resolve(v) for k, v in node.items() if k not in ("$defs", "title")}
        if isinstance(node, list):
            return [resolve(item) for item in node]
        return node

    resolved: dict[str, Any] = resolve(schema)
    return resolved


REPORT_CLAIMS_TOOL = Tool(
    name="report_claims",
    description="Reports all claims in the text, quoted verbatim and classified.",
    input_schema=_inline_refs(ReportClaims.model_json_schema(by_alias=True)),
)


@dataclass(frozen=True)
class ExtractionInput:
    vote_id: str
    document_title: str
    side: Side
    text: str


@dataclass(frozen=True)
class ExtractedClaim:
    quote: str
    claim_class: ClaimClass
    rationale: str
    estimate_by: str | None
    side: Side


@dataclass
class ExtractionResult:
    request_key: str
    accepted: list[ExtractedClaim] = field(default_factory=list)
    # Claims the model returned that failed a deterministic check.
    rejected: list[dict[str, str]] = field(default_factory=list)


class ExtractionOutputError(ValueError):
    pass


def build_request(data: ExtractionInput, model: str) -> ToolCallRequest:
    user = "\n".join(
        [
            f"Vote: {data.vote_id}",
            f"Document: {data.document_title}",
            f"Side: {data.side.value}",
            "",
            "<text>",
            data.text,
            "</text>",
        ]
    )
    return ToolCallRequest(model=model, system=PROMPT_PATH.read_text(), user=user, tool=REPORT_CLAIMS_TOOL)


def extract_claims(provider: LlmProvider, data: ExtractionInput, model: str) -> ExtractionResult:
    request = build_request(data, model)
    try:
        output = ReportClaims.model_validate(provider.call_tool(request))
    except ValidationError as error:
        raise ExtractionOutputError(
            f"model output does not match the report_claims schema: {error}"
        ) from error

    result = ExtractionResult(request_key=request.key())
    seen: set[str] = set()
    for claim in output.claims:
        quote = claim.quote.strip()
        if not is_verbatim(quote, data.text):
            result.rejected.append({"quote": quote, "reason": "not verbatim in source text"})
            continue
        if quote in seen:
            result.rejected.append({"quote": quote, "reason": "duplicate"})
            continue
        seen.add(quote)
        result.accepted.append(
            ExtractedClaim(
                quote=quote,
                claim_class=claim.claim_class,
                rationale=claim.rationale,
                estimate_by=claim.estimate_by if claim.claim_class is ClaimClass.FORECAST else None,
                side=data.side,
            )
        )
    return result
