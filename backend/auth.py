"""Parent registration, login, and access-token checks."""

from __future__ import annotations

import logging
from uuid import UUID

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.database import DatabaseError, get_settings, request_json

logger = logging.getLogger("nutribuddy.auth")

_bearer = HTTPBearer(auto_error=False)


class AuthenticatedParent:
    """The signed-in parent. The token is kept off the default text form."""

    def __init__(self, parent_id: UUID, email: str, access_token: str) -> None:
        self.id = parent_id
        self.email = email
        self.access_token = access_token

    def __repr__(self) -> str:
        return f"AuthenticatedParent(id={self.id})"


class AuthError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


class AuthResult:
    def __init__(
        self,
        email: str,
        name: str,
        access_token: str | None,
        parent_id: UUID | None,
        confirmation_required: bool,
    ) -> None:
        self.email = email
        self.name = name
        self.access_token = access_token
        self.parent_id = parent_id
        self.confirmation_required = confirmation_required


def register_parent(name: str, email: str, password: str) -> AuthResult:
    payload = _auth_request(
        "POST",
        "/auth/v1/signup",
        {"email": email, "password": password, "data": {"name": name, "consent_accepted": True}},
    )
    return _result_from_payload(payload, fallback_name=name, allow_confirmation=True)


def login_parent(email: str, password: str) -> AuthResult:
    payload = _auth_request(
        "POST",
        "/auth/v1/token",
        {"email": email, "password": password},
        params={"grant_type": "password"},
    )
    result = _result_from_payload(payload, fallback_name="", allow_confirmation=False)
    if not result.access_token or result.parent_id is None:
        raise AuthError(status.HTTP_401_UNAUTHORIZED, "The email or password was not accepted.")
    return result


def fetch_parent(token: str) -> AuthenticatedParent | None:
    try:
        payload = request_json("GET", "/auth/v1/user", token)
    except DatabaseError as exc:
        if exc.status_code in (401, 403):
            return None
        raise
    if not isinstance(payload, dict) or not payload.get("id"):
        return None
    return AuthenticatedParent(
        parent_id=UUID(str(payload["id"])),
        email=str(payload.get("email") or ""),
        access_token=token,
    )


def get_current_parent(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> AuthenticatedParent:
    if credentials is None or credentials.scheme.lower() != "bearer" or not credentials.credentials.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token.",
        )
    parent = fetch_parent(credentials.credentials.strip())
    if parent is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
        )
    return parent


def _auth_request(
    method: str,
    path: str,
    body: dict[str, object],
    params: dict[str, str] | None = None,
) -> dict[str, object]:
    try:
        settings = get_settings()
    except DatabaseError as exc:
        raise AuthError(status.HTTP_503_SERVICE_UNAVAILABLE, "The account service is not configured.") from exc
    headers = {
        "apikey": settings.supabase_key,
        "Authorization": f"Bearer {settings.supabase_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    try:
        response = httpx.request(
            method,
            f"{settings.supabase_url}{path}",
            headers=headers,
            params=params,
            json=body,
            timeout=20.0,
        )
    except httpx.HTTPError:
        logger.warning("Auth request could not connect path=%s", path)
        raise AuthError(status.HTTP_503_SERVICE_UNAVAILABLE, "The account service is unavailable.") from None
    if response.status_code >= 400:
        logger.info("Auth request failed path=%s status=%s", path, response.status_code)
        raise AuthError(response.status_code, _auth_detail(response))
    payload = response.json()
    if not isinstance(payload, dict):
        raise AuthError(status.HTTP_502_BAD_GATEWAY, "The account service returned an unexpected response.")
    return payload


def _auth_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    code = ""
    message = ""
    if isinstance(payload, dict):
        code = str(payload.get("error_code") or payload.get("error") or payload.get("code") or "")
        message = str(payload.get("msg") or payload.get("message") or payload.get("error_description") or "")
    lowered = f"{code} {message}".lower()
    if "already" in lowered or response.status_code == 409:
        return "An account with that email already exists. Try logging in."
    if "confirm" in lowered:
        return "Confirm the email address, then log in."
    if "password" in lowered and response.status_code != 400:
        return "That password was not accepted."
    if response.status_code in (400, 401, 403):
        return "The email or password was not accepted."
    return "The account service could not complete that request."


def _result_from_payload(payload: dict[str, object], fallback_name: str, allow_confirmation: bool) -> AuthResult:
    user = payload.get("user")
    user_payload = user if isinstance(user, dict) else payload
    raw_id = user_payload.get("id") if isinstance(user_payload, dict) else None
    email = str(user_payload.get("email") or "") if isinstance(user_payload, dict) else ""
    metadata = user_payload.get("user_metadata") if isinstance(user_payload, dict) else {}
    name = fallback_name
    if isinstance(metadata, dict) and metadata.get("name"):
        name = str(metadata["name"])
    token = payload.get("access_token")
    access_token = str(token) if isinstance(token, str) and token else None
    parent_id = UUID(str(raw_id)) if raw_id else None
    if access_token and parent_id is not None:
        return AuthResult(email, name, access_token, parent_id, False)
    if allow_confirmation and (parent_id is not None or email):
        return AuthResult(email, name, None, parent_id, True)
    raise AuthError(status.HTTP_502_BAD_GATEWAY, "The account service returned an unexpected response.")
