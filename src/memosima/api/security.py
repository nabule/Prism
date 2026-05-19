from __future__ import annotations

from fastapi import HTTPException, Request, status


def require_admin(request: Request) -> None:
    token = getattr(request.app.state, "admin_token", None)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin token is not configured",
        )
    header = request.headers.get("Authorization", "")
    expected = f"Bearer {token}"
    if header != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin token",
        )

