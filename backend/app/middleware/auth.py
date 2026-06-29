"""
Authentication middleware.

POC: Extracts user identity from X-User-Id header.
Production: Would validate JWT token and extract user_id from claims.

The key insight is that authorization logic (participant checks) lives in
the service layer and is INDEPENDENT of how authentication works. Swapping
from header-based to JWT requires only changing this file.
"""

from fastapi import Header, HTTPException


async def get_current_user_id(x_user_id: str = Header(None)) -> int:
    """
    Extract and validate the current user ID from request headers.

    In production, this would:
    1. Extract Bearer token from Authorization header
    2. Validate JWT signature and expiry
    3. Extract user_id from token claims
    4. Optionally check token revocation list (Redis)
    """
    if x_user_id is None:
        raise HTTPException(
            status_code=401,
            detail={"code": "UNAUTHORIZED", "message": "X-User-Id header is required"},
        )

    try:
        user_id = int(x_user_id)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=401,
            detail={"code": "UNAUTHORIZED", "message": "X-User-Id must be a valid integer"},
        )

    if user_id <= 0:
        raise HTTPException(
            status_code=401,
            detail={"code": "UNAUTHORIZED", "message": "X-User-Id must be positive"},
        )

    return user_id
