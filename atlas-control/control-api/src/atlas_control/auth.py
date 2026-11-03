"""OIDC authentication + role gate (boundary: untrusted Bearer -> typed token)."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import jwt
from fastapi import Request


@dataclass(frozen=True, slots=True)
class TokenInfo:
    """Verified identity. Roles come from the IdP, never from the caller."""

    subject: str
    username: str
    roles: tuple[str, ...]


@dataclass
class InvalidToken(Exception):
    reason: str

    def __str__(self) -> str:
        return f"invalid token: {self.reason}"


@dataclass
class Forbidden(Exception):
    action: str

    def __str__(self) -> str:
        return f"forbidden: {self.action}"


@lru_cache(maxsize=1)
def _jwks_client(issuer: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(f"{issuer}/protocol/openid-connect/certs")


def verify_bearer(request: Request, issuer: str) -> TokenInfo:
    """Verify signature/issuer/expiry via JWKS. Raises InvalidToken."""
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise InvalidToken("missing bearer token")
    try:
        key = _jwks_client(issuer).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            key.key,
            algorithms=["RS256"],
            issuer=issuer,
            options={"verify_aud": False},
        )
    except jwt.PyJWTError as exc:
        raise InvalidToken(type(exc).__name__) from exc
    roles = claims.get("realm_access", {}).get("roles", [])
    if not isinstance(claims.get("sub"), str):
        raise InvalidToken("missing sub")
    return TokenInfo(
        subject=claims["sub"],
        username=str(claims.get("preferred_username", "")),
        roles=tuple(str(r) for r in roles if isinstance(r, str)),
    )


def require_role(token: TokenInfo, role: str, action: str) -> None:
    """ABAC gate: role membership is checked server-side on every request."""
    if role not in token.roles:
        raise Forbidden(action)
