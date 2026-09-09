"""Verifies the Supabase-issued JWT sent by the frontend and resolves it to a user id.

Without this, a client could pass any user_id it likes in a request body and create
sessions under someone else's account. The frontend (Phase 2) authenticates via
Supabase's own auth and sends the resulting access token as `Authorization: Bearer <jwt>`;
this dependency is what turns that token into a trusted user_id for the rest of the app.
"""

from uuid import UUID

from fastapi import Header, HTTPException

from app.db.supabase_client import get_supabase


def get_current_user_id(authorization: str | None = Header(default=None)) -> UUID:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header")
    token = authorization.removeprefix("Bearer ").strip()

    try:
        response = get_supabase().auth.get_user(token)
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc

    if response is None or response.user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return UUID(response.user.id)
