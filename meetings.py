from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..core.db import get_db, parse_dt
from ..core.errors import ApiError, not_found, ok
from ..core.ratelimit import limiter
from ..core.security import acting_user, current_user
from ..models import User
from ..services import meetings as svc

router = APIRouter(prefix="/meetings", tags=["meetings"])


class MeetingIn(BaseModel):
    title: str = Field(min_length=3, max_length=120)
    subject: str = Field(min_length=2, max_length=80)
    course: str = Field(default="", max_length=80)
    topics: list[str] = Field(default_factory=list, max_length=30)
    starts_at: str
    duration_minutes: int = Field(ge=15, le=360)
    max_participants: int = Field(ge=2, le=50)
    visibility: str = Field(default="private", pattern="^(public|private)$")
    recurrence: str = Field(default="none", pattern="^(none|daily|weekly)$")
    occurrences: int = Field(default=1, ge=1, le=12)
    reminder_minutes: list[int] = Field(default_factory=lambda: [60, 10], max_length=4)
    invitees: list[str] = Field(default_factory=list, max_length=30)
    create_room: bool = True
    room_id: str | None = None
    idempotency_key: str = Field(min_length=8, max_length=64)


def _dt(v: str):
    try:
        return parse_dt(v)
    except ValueError:
        raise ApiError("VALIDATION_ERROR", "Invalid date/time.", 422)


@router.post("")
def create(body: MeetingIn, user: User = Depends(acting_user), db: Session = Depends(get_db)):
    limiter.hit("meeting_create", user.id)
    data = body.model_dump()
    data["starts_at"] = _dt(body.starts_at)
    data["topics"] = [" ".join(t.split())[:100] for t in body.topics if t.strip()]
    return ok(svc.create(db, user, data))


@router.get("/conflicts")
def conflicts(starts_at: str, duration_minutes: int = Query(ge=15, le=360), user: User = Depends(current_user), db: Session = Depends(get_db)):
    return ok(svc.conflicts(db, user.id, _dt(starts_at), duration_minutes))


@router.get("")
def list_meetings(past: bool = False, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return ok([svc.view(db, m, user.id) for m in svc.list_for(db, user.id, past)])


@router.get("/{meeting_id}")
def get_meeting(meeting_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    m = svc.get(db, meeting_id)
    if not svc.can_see(db, m, user.id):
        raise not_found("Meeting")
    return ok(svc.view(db, m, user.id))


class MeetingEditIn(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=120)
    starts_at: str | None = None
    duration_minutes: int | None = Field(default=None, ge=15, le=360)
    reminder_minutes: list[int] | None = Field(default=None, max_length=4)
    scope: str = Field(default="this", pattern="^(this|following)$")


@router.patch("/{meeting_id}")
def edit(meeting_id: str, body: MeetingEditIn, user: User = Depends(acting_user), db: Session = Depends(get_db)):
    m = svc.get(db, meeting_id)
    data = body.model_dump(exclude={"scope"})
    if body.starts_at:
        data["starts_at"] = _dt(body.starts_at)
    if body.reminder_minutes is not None:
        data["reminder_minutes"] = sorted({int(x) for x in body.reminder_minutes if 0 < int(x) <= 10080})
    changed = svc.update(db, user, m, data, body.scope)
    return ok([svc.view(db, x, user.id) for x in changed])


class CancelIn(BaseModel):
    scope: str = Field(default="this", pattern="^(this|following)$")
    reason: str = Field(default="", max_length=200)


@router.post("/{meeting_id}/cancel")
def cancel(meeting_id: str, body: CancelIn, user: User = Depends(acting_user), db: Session = Depends(get_db)):
    m = svc.get(db, meeting_id)
    changed = svc.cancel(db, user, m, body.scope, body.reason)
    return ok({"cancelled": len(changed)})


class ResponseIn(BaseModel):
    accept: bool


@router.post("/{meeting_id}/respond")
def respond(meeting_id: str, body: ResponseIn, user: User = Depends(acting_user), db: Session = Depends(get_db)):
    m = svc.get(db, meeting_id)
    inv = svc.respond(db, user, m, body.accept)
    return ok({"status": inv.status})
