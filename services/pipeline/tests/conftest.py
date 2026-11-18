"""Test fixtures: a real Postgres test database, locally signed tokens, a fake model."""

import os
import time
import uuid
from collections.abc import Callable, Iterator
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from sqlalchemy import text

os.environ.setdefault(
    "STIMMIG_DATABASE_URL",
    os.environ.get("TEST_DATABASE_URL", "postgresql+psycopg://postgres@localhost:5432/stimmig_pipeline_test"),
)
os.environ["STIMMIG_LLM_MODE"] = "replay"

from stimmig_pipeline.api.admin import get_llm_provider
from stimmig_pipeline.api.app import create_app
from stimmig_pipeline.auth import TokenVerifier, get_verifier
from stimmig_pipeline.db import get_engine, migrate
from stimmig_pipeline.llm import ToolCallRequest

ISSUER = "https://identity.test"
AUDIENCE = "urn:stimmig:api"
_KEY = ec.generate_private_key(ec.SECP256R1())


class LocalVerifier(TokenVerifier):
    def signing_key(self, token: str) -> Any:
        return _KEY.public_key()


def make_token(
    roles: list[str],
    email: str = "someone@stimmig.test",
    *,
    audience: str = AUDIENCE,
    expires_in: int = 600,
    key: Any = None,
) -> str:
    now = int(time.time())
    claims = {
        "iss": ISSUER,
        "aud": audience,
        "sub": str(uuid.uuid5(uuid.NAMESPACE_URL, email)),
        "email": email,
        "roles": roles,
        "iat": now,
        "exp": now + expires_in,
    }
    return jwt.encode(claims, key or _KEY, algorithm="ES256")


class FakeProvider:
    """Returns a canned tool answer and remembers the requests it saw."""

    def __init__(self) -> None:
        self.response: dict[str, Any] = {"claims": []}
        self.requests: list[ToolCallRequest] = []

    def call_tool(self, request: ToolCallRequest) -> dict[str, Any]:
        self.requests.append(request)
        return self.response


@pytest.fixture(scope="session", autouse=True)
def _schema() -> None:
    migrate()


@pytest.fixture(autouse=True)
def _clean_tables() -> Iterator[None]:
    yield
    with get_engine().begin() as conn:
        conn.execute(
            text("TRUNCATE audit_events, visualizations, claims, extraction_runs, documents, votes CASCADE")
        )


@pytest.fixture
def fake_llm() -> FakeProvider:
    return FakeProvider()


@pytest.fixture
def client(fake_llm: FakeProvider) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_verifier] = lambda: LocalVerifier(ISSUER, AUDIENCE)
    app.dependency_overrides[get_llm_provider] = lambda: fake_llm
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def as_user() -> Callable[..., dict[str, str]]:
    def headers(*roles: str, email: str | None = None) -> dict[str, str]:
        return {"Authorization": f"Bearer {make_token(list(roles), email or f'{roles[0]}@stimmig.test')}"}

    return headers
