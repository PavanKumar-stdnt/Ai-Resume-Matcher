"""
api/dependencies.py — Custom API-key security layer.

Implements a constant-time comparison check on every inbound request so that
the server's behaviour is identical regardless of whether the supplied key is
almost-correct or completely wrong, guarding against timing-based enumeration
attacks.

Usage (FastAPI dependency injection):
    @router.post("/match")
    async def match(
        _: None = Depends(verify_api_key),
        ...
    ):
        ...
"""

from __future__ import annotations

import hmac
import logging

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader

from src.config import Settings, get_settings

logger = logging.getLogger(__name__)

# FastAPI's built-in header extractor — raises 403 automatically if the header
# is absent, which is what we want before we even reach the equality check.
_api_key_header = APIKeyHeader(name="X-API-KEY", auto_error=True)


async def verify_api_key(
    request: Request,  # noqa: ARG001 — retained for potential future IP logging
    api_key: str = Depends(_api_key_header),
    settings: Settings = Depends(get_settings),
) -> None:
    """FastAPI dependency that enforces the X-API-KEY header token.

    Uses ``hmac.compare_digest`` for a constant-time comparison so that
    response timing cannot be used to infer partial key matches.

    Parameters
    ----------
    request:
        The incoming HTTP request (available for audit-logging if needed).
    api_key:
        The value supplied by the client in the ``X-API-KEY`` header.
    settings:
        Injected application settings containing the expected secret.

    Raises
    ------
    HTTPException (403 Forbidden)
        If the supplied key does not match the configured secret.
    """
    expected = settings.api_secret_key

    # hmac.compare_digest requires both operands to be the same type.
    keys_match: bool = hmac.compare_digest(
        api_key.encode("utf-8"),
        expected.encode("utf-8"),
    )

    if not keys_match:
        logger.warning(
            "Rejected request with invalid API key from host '%s'.",
            request.client.host if request.client else "unknown",
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing API key.",
        )

    logger.debug("API key verified successfully.")
