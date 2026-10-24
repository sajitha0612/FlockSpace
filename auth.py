from zoneinfo import available_timezones

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..core.db import get_db
from ..core.errors import ApiError, ok
from ..core.ratelimit import limiter
from ..core.security import client_ip, create_token, current_user, hash_ip, hash_password, verify_password
from ..models import Profile, SignupEvent, User
from ..services import email, safety
from .views import me_view

router = APIRouter(prefix="/auth", tags=["auth"])


class SignupIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    timezone: str = "UTC"


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)


class CodeIn(BaseModel):
    code: str = Field(min_length=6, max_length=6)


class ForgotIn(BaseModel):
    email: EmailStr


class ResetIn(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6)
    new_password: str = Field(min_length=8, max_length=128)


def _role(email_addr: str) -> str:
    return "admin" if email_addr.lower() in get_settings().admins else "student"


@router.post("/signup")
def signup(body: SignupIn, request: Request, db: Session = Depends(get_db)):
    ip = hash_ip(client_ip(request))
    limiter.hit("signup", ip)
    addr = body.email.lower()
    if db.scalar(select(User.id).where(func.lower(User.email) == addr)):
        raise ApiError("EMAIL_TAKEN", "An account with this email already exists. Sign in, or reset your password.", 409)
    if body.password.lower() in {"password", "12345678", "qwertyui", "password1"} or len(set(body.password)) < 4:
        raise ApiError("WEAK_PASSWORD", "Choose a less guessable password.", 422)
    tz = body.timezone if body.timezone in available_timezones() else "UTC"
    user = User(email=addr, password_hash=hash_password(body.password), name=" ".join(body.name.split()), role=_role(addr))
    db.add(user)
    db.flush()
    db.add(Profile(user_id=user.id, timezone=tz, daily_goal_minutes=get_settings().default_daily_goal_minutes))
    db.add(SignupEvent(user_id=user.id, ip_hash=ip))
    safety.check_signup(db, user, ip)
    db.commit()
    delivery, dev_code = email.issue_code_dev(db, user, "verify")
    return ok({"token": create_token(user.id, user.token_version), "user": me_view(db, user), "verification_delivery": delivery, "dev_code": dev_code})


@router.post("/login")
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    addr = body.email.lower()
    limiter.hit("login", f"{hash_ip(client_ip(request))}:{addr}")
    user = db.scalar(select(User).where(func.lower(User.email) == addr))
    if not user or not verify_password(body.password, user.password_hash):
        raise ApiError("BAD_CREDENTIALS", "Email or password is incorrect.", 401)
    if user.role != _role(addr) and _role(addr) == "admin":
        user.role = "admin"
        db.commit()
    return ok({"token": create_token(user.id, user.token_version), "user": me_view(db, user)})


@router.get("/me")
def me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return ok(me_view(db, user))


@router.post("/verify/send")
def send_verification(user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.email_verified:
        return ok({"already_verified": True})
    limiter.hit("verify_send", user.id)
    delivery, dev_code = email.issue_code_dev(db, user, "verify")
    return ok({"delivery": delivery, "dev_code": dev_code})


@router.post("/verify")
def verify(body: CodeIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    limiter.hit("verify_try", user.id)
    if not user.email_verified:
        email.check_code(db, user, "verify", body.code)
        user.email_verified = True
        db.commit()
    return ok(me_view(db, user))


@router.post("/password/forgot")
def forgot(body: ForgotIn, request: Request, db: Session = Depends(get_db)):
    limiter.hit("reset_send", f"{hash_ip(client_ip(request))}:{body.email.lower()}")
    user = db.scalar(select(User).where(func.lower(User.email) == body.email.lower()))
    if user:
        email.issue_code(db, user, "reset")
    # same answer either way, so this can't be used to discover who has an account
    return ok({"sent": True})


@router.post("/password/reset")
def reset(body: ResetIn, request: Request, db: Session = Depends(get_db)):
    limiter.hit("verify_try", f"reset:{hash_ip(client_ip(request))}:{body.email.lower()}")
    user = db.scalar(select(User).where(func.lower(User.email) == body.email.lower()))
    if not user:
        raise ApiError("CODE_INVALID", "That code isn't right.", 400)
    email.check_code(db, user, "reset", body.code)
    user.password_hash = hash_password(body.new_password)
    user.token_version += 1  # signs out every existing session
    user.email_verified = True  # receiving the code proves control of the inbox
    safety.audit(db, user.id, "password_reset", user.id)
    db.commit()
    return ok({"token": create_token(user.id, user.token_version), "user": me_view(db, user)})
