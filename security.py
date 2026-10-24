import hashlib
import hmac
from datetime import timedelta

import bcrypt
import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db, utcnow
from .errors import ApiError

bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode()[:72], bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode()[:72], hashed.encode())
    except ValueError:
        return False


def create_token(user_id: str, token_version: int) -> str:
    s = get_settings()
    exp = utcnow() + timedelta(minutes=s.jwt_expire_minutes)
    return jwt.encode({"sub": user_id, "v": token_version, "exp": exp}, s.jwt_secret, algorithm=s.jwt_algorithm)


def user_from_token(db: Session, token: str):
    from ..models import User

    s = get_settings()
    try:
        payload = jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm])
    except jwt.PyJWTError:
        return None
    user = db.get(User, payload.get("sub"))
    if not user or user.token_version != payload.get("v"):
        return None
    return user


def hash_ip(ip: str | None) -> str:
    """A keyed hash of the client address. The raw address is never stored."""
    return hmac.new(get_settings().jwt_secret.encode(), (ip or "?").encode(), hashlib.sha256).hexdigest()[:24]


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "?"


def current_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)):
    """Every protected route depends on this. Suspended accounts can still sign in to read and appeal, but not act."""
    if not creds:
        raise ApiError("UNAUTHORIZED", "Sign in to continue.", 401)
    user = user_from_token(db, creds.credentials)
    if not user:
        raise ApiError("UNAUTHORIZED", "Your session has expired. Sign in again.", 401)
    return user


def active_restriction(db: Session, user_id: str, kind: str):
    from ..models import Restriction

    now = utcnow()
    return db.scalar(
        select(Restriction).where(
            Restriction.user_id == user_id, Restriction.kind == kind, Restriction.lifted_at.is_(None),
            (Restriction.expires_at.is_(None)) | (Restriction.expires_at > now),
        )
    )


def acting_user(user=Depends(current_user), db: Session = Depends(get_db)):
    """For routes that change shared state: a suspended account is refused."""
    if active_restriction(db, user.id, "suspended"):
        raise ApiError("SUSPENDED", "Your account is suspended pending review. You can appeal from Settings.", 403)
    return user


def admin_user(user=Depends(current_user)):
    if user.role != "admin":
        raise ApiError("FORBIDDEN", "Reviewers only.", 403)
    return user
