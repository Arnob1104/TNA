"""
Every request from the Next.js frontend carries the Supabase-issued JWT
in the Authorization header. Supabase's newer projects sign these with
an asymmetric key pair (ES256), not a shared secret - so we verify by
fetching the public key from the project's JWKS endpoint, which PyJWT's
PyJWKClient handles (including caching the key so we don't refetch on
every request).

This is the single most important file for multi-tenant safety: every
router depends on get_current_user, and every DB query must filter by
current_user.tenant_id.
"""

from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from app.config import settings
from app.db import fetch_one

bearer_scheme = HTTPBearer()

# Fetches and caches Supabase's public signing key(s) from the JWKS URL.
_jwk_client = PyJWKClient(settings.supabase_jwks_url)


@dataclass
class CurrentUser:
    user_id: str
    email: str | None
    tenant_id: str


def _decode_supabase_jwt(token: str) -> dict:
    try:
        signing_key = _jwk_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256", "RS256"],
            audience="authenticated",
        )
        return payload
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {exc}",
        )


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> CurrentUser:
    payload = _decode_supabase_jwt(credentials.credentials)
    user_id = payload.get("sub")
    email = payload.get("email")

    if not user_id:
        raise HTTPException(status_code=401, detail="Token missing subject")

    # tenant_id lives in a profiles table keyed by the Supabase auth user id.
    # (see supabase/schema.sql - profiles table, populated on signup)
    profile = fetch_one(
        "SELECT tenant_id FROM profiles WHERE user_id = :user_id",
        {"user_id": user_id},
    )
    if not profile:
        raise HTTPException(
            status_code=403,
            detail="No tenant is associated with this account yet.",
        )

    return CurrentUser(user_id=user_id, email=email, tenant_id=str(profile["tenant_id"]))
