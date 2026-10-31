"""
clerk_auth.py — Clerk backend authentication helper for Flask.

Uses the official `clerk-backend-api` Python SDK to verify session tokens
issued by ClerkJS on the frontend, extracting user identity for Flask sessions.
"""
import os
from functools import wraps
from flask import session, redirect, url_for, request, g

from clerk_backend_api import Clerk
from clerk_backend_api.security import AuthenticateRequestOptions

# Initialise Clerk SDK with Secret Key from environment
_clerk_secret_key = os.environ.get("CLERK_SECRET_KEY", "")
clerk = Clerk(bearer_auth=_clerk_secret_key) if _clerk_secret_key else None


def get_clerk_authorized_parties():
    """Return list of authorised frontend origins for CSRF protection."""
    raw = os.environ.get("CLERK_AUTHORIZED_PARTIES", "")
    parties = [p.strip() for p in raw.split(",") if p.strip()]
    if not parties:
        # Sensible defaults for local + Vercel
        parties = [
            "http://localhost:5000",
            "https://smart-hospital-appointment-manageme.vercel.app",
        ]
    return parties


def verify_clerk_request():
    """
    Attempt to verify a Clerk session from the current Flask request.
    Checks both `Authorization: Bearer <token>` header and the `__session` cookie.

    Returns:
        dict with 'user_id', 'email', 'name' keys on success, or None on failure.
    """
    if not clerk:
        return None

    try:
        state = clerk.authenticate_request(
            request,
            AuthenticateRequestOptions(
                authorized_parties=get_clerk_authorized_parties(),
            ),
        )
        if not state.is_signed_in:
            return None

        payload = state.payload or {}
        user_id = payload.get("sub")
        if not user_id:
            return None

        # Fetch full user profile from Clerk to get name/email
        user_info = _get_clerk_user(user_id)
        return user_info

    except Exception as e:
        print(f"[Clerk] Token verification error: {e}")
        return None


def _get_clerk_user(user_id: str) -> dict:
    """Fetch user profile from Clerk API by user_id."""
    try:
        user = clerk.users.get(user_id=user_id)
        # Primary email address
        email = ""
        if user.email_addresses:
            primary = next(
                (e for e in user.email_addresses if e.id == user.primary_email_address_id),
                user.email_addresses[0],
            )
            email = primary.email_address or ""

        first = user.first_name or ""
        last = user.last_name or ""
        full_name = f"{first} {last}".strip() or email.split("@")[0]

        return {
            "user_id": user_id,
            "email": email,
            "name": full_name,
        }
    except Exception as e:
        print(f"[Clerk] Failed to fetch user {user_id}: {e}")
        return {"user_id": user_id, "email": "", "name": "Unknown"}


def clerk_login_required(f):
    """
    Route decorator: requires a valid Clerk session cookie or Bearer token.
    Falls back gracefully to existing Flask session so legacy flows still work.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        # Already authenticated via Flask session (legacy or previously synced)
        if session.get("user"):
            return f(*args, **kwargs)

        # Try Clerk token verification
        user_info = verify_clerk_request()
        if user_info:
            # Sync Clerk identity into Flask session
            session["user"] = user_info["name"]
            session["email"] = user_info["email"]
            session["clerk_user_id"] = user_info["user_id"]
            return f(*args, **kwargs)

        return redirect(url_for("login"))
    return decorated
