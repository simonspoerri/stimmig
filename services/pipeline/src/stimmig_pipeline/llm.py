"""The narrow interface through which the pipeline reaches the language model.

The pipeline only ever asks for one forced tool call and reads its structured
input back. Keeping the interface this small is what makes record/replay – and
therefore secret-free, reproducible CI – possible (docs/adr/0004).
"""

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

RECORDINGS_DIR = Path(__file__).resolve().parents[2] / "evals" / "recordings"


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass(frozen=True)
class ToolCallRequest:
    model: str
    system: str
    user: str
    tool: Tool
    max_tokens: int = 4096

    def key(self) -> str:
        """Stable hash of everything that influences the answer."""
        canonical = json.dumps(asdict(self), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()[:24]


class LlmProvider(Protocol):
    def call_tool(self, request: ToolCallRequest) -> dict[str, Any]: ...


class AnthropicProvider:
    """Calls the Anthropic Messages API. Needs ``ANTHROPIC_API_KEY``."""

    def __init__(self, client: Any | None = None) -> None:
        self._client = client

    def _get_client(self) -> Any:
        if self._client is None:
            import anthropic  # noqa: PLC0415 - only needed for live runs

            self._client = anthropic.Anthropic()
        return self._client

    def call_tool(self, request: ToolCallRequest) -> dict[str, Any]:
        response = self._get_client().messages.create(
            model=request.model,
            max_tokens=request.max_tokens,
            system=request.system,
            messages=[{"role": "user", "content": request.user}],
            tools=[asdict(request.tool)],
            tool_choice={"type": "tool", "name": request.tool.name},
        )
        for block in response.content:
            if block.type == "tool_use" and block.name == request.tool.name:
                return dict(block.input)
        raise RuntimeError(
            f"model returned no {request.tool.name} call (stop_reason: {response.stop_reason})"
        )


class MissingRecordingError(LookupError):
    pass


class RecordingProvider:
    """Passes calls through to ``inner`` and stores every answer for replay."""

    def __init__(self, inner: LlmProvider, directory: Path = RECORDINGS_DIR) -> None:
        self.inner = inner
        self.directory = directory

    def call_tool(self, request: ToolCallRequest) -> dict[str, Any]:
        response = self.inner.call_tool(request)
        self.directory.mkdir(parents=True, exist_ok=True)
        recording = {
            "request_hash": request.key(),
            "model": request.model,
            "tool": request.tool.name,
            "provenance": f"recorded from {request.model} on {datetime.now(UTC).date().isoformat()}",
            "response": response,
        }
        path = self.directory / f"{request.key()}.json"
        path.write_text(json.dumps(recording, ensure_ascii=False, indent=2) + "\n")
        return response


class ReplayProvider:
    """Answers from stored recordings only. Never calls the model."""

    def __init__(self, directory: Path = RECORDINGS_DIR) -> None:
        self.directory = directory

    def call_tool(self, request: ToolCallRequest) -> dict[str, Any]:
        path = self.directory / f"{request.key()}.json"
        if not path.exists():
            raise MissingRecordingError(
                f"no recording {request.key()} for tool {request.tool.name}: the prompt, model or input "
                "changed. Re-record with a live run (stimmig-evals --live)."
            )
        response: dict[str, Any] = json.loads(path.read_text())["response"]
        return response


def provider_for_mode(mode: str) -> LlmProvider:
    if mode == "replay":
        return ReplayProvider()
    if mode == "record":
        return RecordingProvider(AnthropicProvider())
    if mode == "live":
        return AnthropicProvider()
    raise ValueError(f"unknown llm mode {mode!r}; use live, record or replay")
