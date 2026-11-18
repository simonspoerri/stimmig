"""Access-token verification and the role → permission mapping.

Roles come from the identity service as the ``roles`` claim of a JWT access
token issued for this API's resource (``aud``). This module is the only place
that decides what a role may do; keep it in sync with the permission table in
docs/architecture.md.
"""

from dataclasses import dataclass, field
from enum import StrEnum
from functools import lru_cache
from typing import Annotated, Any

import httpx
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import get_settings


class Role(StrEnum):
    ADMIN = "admin"
    REVIEWER = "reviewer"
    VISUALIZER = "visualizer"


class Permission(StrEnum):
    READ = "read"
    VOTES_WRITE = "votes:write"
    DOCUMENTS_WRITE = "documents:write"
    EXTRACTION_RUN = "extraction:run"
    CLAIMS_REVIEW = "claims:review"
    VISUALIZATIONS_WRITE = "visualizations:write"
    VISUALIZATIONS_REVIEW = "visualizations:review"
    VOTES_PUBLISH = "votes:publish"


ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.ADMIN: frozenset(
        {
            Permission.READ,
            Permission.VOTES_WRITE,
            Permission.DOCUMENTS_WRITE,
            Permission.EXTRACTION_RUN,
            Permission.VOTES_PUBLISH,
        }
    ),
    Role.REVIEWER: frozenset({Permission.READ, Permission.CLAIMS_REVIEW, Permission.VISUALIZATIONS_REVIEW}),
    Role.VISUALIZER: frozenset({Permission.READ, Permission.VISUALIZATIONS_WRITE}),
}


@dataclass(frozen=True)
class Principal:
    subject: str
    email: str | None
    roles: frozenset[Role]
    permissions: frozenset[Permission] = field(init=False)

    def __post_init__(self) -> None:
        perms: set[Permission] = set()
        for role in self.roles:
            perms |= ROLE_PERMISSIONS[role]
        object.__setattr__(self, "permissions", frozenset(perms))

    @property
    def actor(self) -> str:
        """How this user appears in records and the audit log."""
        return self.email or self.subject

    def can(self, permission: Permission) -> bool:
        return permission in self.permissions


def principal_from_claims(claims: dict[str, Any]) -> Principal:
    raw_roles = claims.get("roles", [])
    if not isinstance(raw_roles, list):
        raw_roles = []
    # Unknown roles are ignored rather than rejected, so the identity service
    # can introduce a role before this API knows about it.
    roles = frozenset(Role(r) for r in raw_roles if r in Role.__members__.values())
    email = claims.get("email")
    return Principal(subject=str(claims["sub"]), email=email if isinstance(email, str) else None, roles=roles)


class TokenVerifier:
    """Verifies ES256/RS256 JWT access tokens against the issuer's JWKS."""

    ALGORITHMS = ("ES256", "RS256", "EdDSA")

    def __init__(self, issuer: str, audience: str, jwks_url: str | None = None) -> None:
        self.issuer = issuer
        self.audience = audience
        self._jwks_url = jwks_url
        self._client: jwt.PyJWKClient | None = None

    def _jwks_client(self) -> jwt.PyJWKClient:
        if self._client is None:
            url = self._jwks_url
            if url is None:
                discovery = httpx.get(
                    f"{self.issuer.rstrip('/')}/.well-known/openid-configuration", timeout=5
                )
                discovery.raise_for_status()
                url = str(discovery.json()["jwks_uri"])
            # Keys are cached; an unknown kid triggers one refetch (key rotation).
            self._client = jwt.PyJWKClient(url, cache_keys=True, lifespan=600)
        return self._client

    def signing_key(self, token: str) -> Any:
        return self._jwks_client().get_signing_key_from_jwt(token).key

    def verify(self, token: str) -> Principal:
        try:
            claims = jwt.decode(
                token,
                self.signing_key(token),
                algorithms=list(self.ALGORITHMS),
                audience=self.audience,
                issuer=self.issuer,
                options={"require": ["exp", "iat", "sub", "aud", "iss"]},
            )
        except (jwt.PyJWTError, httpx.HTTPError) as error:
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                detail=f"invalid access token: {error}",
                headers={"WWW-Authenticate": 'Bearer error="invalid_token"'},
            ) from error
        return principal_from_claims(claims)


@lru_cache
def get_verifier() -> TokenVerifier:
    settings = get_settings()
    return TokenVerifier(settings.oidc_issuer, settings.api_audience, settings.jwks_url)


_bearer = HTTPBearer(auto_error=False)


def current_principal(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    verifier: Annotated[TokenVerifier, Depends(get_verifier)],
) -> Principal:
    if credentials is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return verifier.verify(credentials.credentials)


def require(permission: Permission) -> Any:
    """FastAPI dependency: the caller must hold ``permission``."""

    def check(principal: Annotated[Principal, Depends(current_principal)]) -> Principal:
        if not principal.can(permission):
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail=f"missing permission {permission.value}")
        return principal

    return Depends(check)
