"""
Room creator permissions (the room's moderator):
- edit the room's details before it starts; change topics before the race (with explicit confirmation once studying);
- mute a participant (1-120 minutes), unmute, remove a participant (they can't rejoin), hide a message;
- see this room's moderation log and the private join code; manage the quiz question bank.
A creator cannot read anything outside their room, cannot see reports filed by others, and cannot change
anyone's rewards. Platform reviewers handle reports and account-level restrictions.
"""
from datetime import timedelta

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..core.db import get_db, iso, parse_dt, utcnow
from ..core.errors import ApiError, forbidden, not_found, ok
from ..core.ratelimit import limiter
from ..core.security import acting_user, current_user
from ..models import ModerationAction, Profile, Room, RoomInvite, RoomParticipant, RoomTopic, User
from ..services import rooms as svc
from ..services.notify import notify
from ..services.realtime import hub, publish_after_commit
from ..services.relations import can_invite, eligible_invitees

router = APIRouter(prefix="/rooms", tags=["rooms"])


class QuizConfigIn(BaseModel):
    question_count: int | None = Field(default=None, ge=4, le=30)
    minutes: int | None = Field(default=None, ge=3, le=60)
    placement_bonuses: list[int] | None = None


class RoomIn(BaseModel):
    title: str = Field(min_length=3, max_length=100)
    subject: str = Field(min_length=2, max_length=80)
    course: str = Field(default="", max_length=80)
    year: int | None = Field(default=None, ge=1, le=8)
    description: str = Field(default="", max_length=500)
    topics: list[str] = Field(min_length=1, max_length=30)
    starts_at: str
    duration_minutes: int
    max_participants: int
    visibility: str = "public"
    ai_assistant_enabled: bool = True
    ai_notes_enabled: bool = True
    quiz: QuizConfigIn | None = None


@router.get("")
def discover(
    q: str = Query("", max_length=80), subject: str = "", course: str = "", topic: str = "", year: int | None = None,
    when: str = Query("any", pattern="^(any|live|today|week|later)$"), available: bool = False, interests: bool = False,
    sort: str = Query("soonest", pattern="^(soonest|popular|newest)$"), user: User = Depends(current_user), db: Session = Depends(get_db),
):
    now = utcnow()
    mine = select(RoomParticipant.room_id).where(RoomParticipant.user_id == user.id, RoomParticipant.status == "active")
    invited = select(RoomInvite.room_id).where(RoomInvite.invitee_id == user.id, RoomInvite.status.in_(("pending", "accepted")))
    stmt = select(Room).where(Room.status.in_(("scheduled", "studying")), or_(Room.visibility == "public", Room.id.in_(mine), Room.id.in_(invited)))
    if q.strip():
        like = f"%{q.strip().lower()}%"
        topic_rooms = select(RoomTopic.room_id).where(func.lower(RoomTopic.title).like(like))
        stmt = stmt.where(or_(func.lower(Room.title).like(like), func.lower(Room.subject).like(like), func.lower(Room.course).like(like), Room.id.in_(topic_rooms)))
    if subject:
        stmt = stmt.where(func.lower(Room.subject) == subject.lower())
    if course:
        stmt = stmt.where(func.lower(Room.course).like(f"%{course.lower()}%"))
    if topic:
        stmt = stmt.where(Room.id.in_(select(RoomTopic.room_id).where(func.lower(RoomTopic.title).like(f"%{topic.lower()}%"))))
    if year:
        stmt = stmt.where(or_(Room.year == year, Room.year.is_(None)))
    if when == "live":
        stmt = stmt.where(Room.status == "studying")
    elif when == "today":
        stmt = stmt.where(Room.starts_at < now + timedelta(hours=24))
    elif when == "week":
        stmt = stmt.where(Room.starts_at < now + timedelta(days=7))
    elif when == "later":
        stmt = stmt.where(Room.starts_at >= now + timedelta(days=7))
    if available:
        stmt = stmt.where(Room.participant_count < Room.max_participants)
    if interests:
        p = db.get(Profile, user.id)
        words = [w.lower() for w in (p.subjects or []) + (p.interests or []) + (p.courses or [])]
        if words:
            stmt = stmt.where(or_(*[func.lower(Room.subject).like(f"%{w}%") for w in words], *[func.lower(Room.course).like(f"%{w}%") for w in words]))
    order = {"soonest": Room.starts_at.asc(), "popular": Room.participant_count.desc(), "newest": Room.created_at.desc()}[sort]
    rooms = list(db.scalars(stmt.order_by(order).limit(60)))
    subjects = sorted({s for (s,) in db.execute(select(Room.subject).where(Room.status.in_(("scheduled", "studying")), Room.visibility == "public").distinct())})
    return ok({"rooms": [svc.card(db, r, user.id) for r in rooms], "subjects": subjects, "server_time": iso(now)})


@router.get("/mine")
def my_rooms(user: User = Depends(current_user), db: Session = Depends(get_db)):
    active = svc.joined_rooms(db, user.id, ("scheduled", "studying", "race"))
    past = list(db.scalars(select(Room).join(RoomParticipant, RoomParticipant.room_id == Room.id).where(
        RoomParticipant.user_id == user.id, Room.status.in_(("finished", "cancelled"))).order_by(Room.ends_at.desc()).limit(30)))
    return ok({"active": [svc.card(db, r, user.id) for r in active], "past": [svc.card(db, r, user.id) for r in past]})


@router.post("")
def create(body: RoomIn, user: User = Depends(acting_user), db: Session = Depends(get_db)):
    limiter.hit("room_create", user.id)
    try:
        starts = parse_dt(body.starts_at)
    except ValueError:
        raise ApiError("VALIDATION_ERROR", "Invalid start time.", 422)
    room = svc.create_room(db, user, title=body.title, subject=body.subject, course=body.course, year=body.year, description=body.description,
                           topics_in=body.topics, starts_at=starts, duration_minutes=body.duration_minutes, max_participants=body.max_participants,
                           visibility=body.visibility, ai_assistant=body.ai_assistant_enabled, ai_notes=body.ai_notes_enabled,
                           quiz_config=body.quiz.model_dump(exclude_none=True) if body.quiz else {})
    db.commit()
    return ok(svc.detail(db, room, user.id))


@router.get("/{room_id}")
def get_room(room_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    room = svc.get_room(db, room_id)
    svc.sync_room(db, room)
    if not svc.can_view(db, room, user.id):
        raise not_found("Room")
    return ok(svc.detail(db, room, user.id))


class JoinIn(BaseModel):
    code: str | None = Field(default=None, max_length=12)


@router.post("/{room_id}/join")
def join(room_id: str, body: JoinIn | None = None, user: User = Depends(acting_user), db: Session = Depends(get_db)):
    limiter.hit("room_join", user.id)
    room = svc.get_room(db, room_id)
    svc.join(db, room, user, body.code if body else None)
    db.commit()
    return ok(svc.detail(db, room, user.id))


@router.post("/{room_id}/leave")
def leave(room_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    room = svc.get_room(db, room_id)
    if room.status == "race":
        raise ApiError("RACE_RUNNING", "The race is running. Withdraw from the race instead.", 409)
    svc.leave(db, room, user)
    db.commit()
    hub.kick_from_room(room.id, user.id)
    return ok({"left": True})


class RoomEditIn(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    starts_at: str | None = None
    duration_minutes: int | None = None
    max_participants: int | None = None
    visibility: str | None = None
    ai_assistant_enabled: bool | None = None
    ai_notes_enabled: bool | None = None
    quiz: QuizConfigIn | None = None


@router.patch("/{room_id}")
def edit(room_id: str, body: RoomEditIn, user: User = Depends(acting_user), db: Session = Depends(get_db)):
    from ..core.config import get_settings

    room = svc.get_room(db, room_id)
    svc.require_creator(room, user.id)
    svc.sync_room(db, room)
    s = get_settings()
    if body.title is not None:
        room.title = body.title.strip()
    if body.description is not None:
        room.description = body.description.strip()
    if body.ai_assistant_enabled is not None:
        room.ai_assistant_enabled = body.ai_assistant_enabled
    if body.ai_notes_enabled is not None:
        room.ai_notes_enabled = body.ai_notes_enabled
    if body.visibility is not None:
        if body.visibility not in ("public", "private"):
            raise ApiError("VALIDATION_ERROR", "Visibility must be public or private.", 422)
        room.visibility = body.visibility
        room.join_code = room.join_code or (svc.new_join_code() if body.visibility == "private" else None)
    timing = body.starts_at is not None or body.duration_minutes is not None
    if timing or body.quiz is not None:
        if room.status != "scheduled":
            raise ApiError("ROOM_STARTED", "Timing and quiz rules are locked once the room has started.", 409)
        if body.starts_at:
            st = parse_dt(body.starts_at)
            if st < utcnow():
                raise ApiError("VALIDATION_ERROR", "The start time must be in the future.", 422)
            room.starts_at = st
        if body.duration_minutes is not None:
            if not (s.room_min_minutes <= body.duration_minutes <= s.room_max_minutes):
                raise ApiError("VALIDATION_ERROR", f"Duration must be {s.room_min_minutes}–{s.room_max_minutes} minutes.", 422)
            room.duration_minutes = body.duration_minutes
        room.ends_at = room.starts_at + timedelta(minutes=room.duration_minutes)
        if body.quiz is not None:
            room.quiz_config = {**(room.quiz_config or {}), **body.quiz.model_dump(exclude_none=True)}
    if body.max_participants is not None:
        if not (max(2, room.participant_count) <= body.max_participants <= s.room_max_participants):
            raise ApiError("VALIDATION_ERROR", "The limit can't be below the current number of participants.", 422)
        room.max_participants = body.max_participants
    publish_after_commit(db, "room", room.id, "room_updated", {})
    db.commit()
    return ok(svc.detail(db, room, user.id))


@router.post("/{room_id}/cancel")
def cancel(room_id: str, user: User = Depends(acting_user), db: Session = Depends(get_db)):
    room = svc.get_room(db, room_id)
    svc.require_creator(room, user.id)
    if room.status != "scheduled":
        raise ApiError("ROOM_STARTED", "Only rooms that haven't started can be cancelled.", 409)
    room.status = "cancelled"
    for p in db.scalars(select(RoomParticipant).where(RoomParticipant.room_id == room.id, RoomParticipant.status == "active", RoomParticipant.user_id != user.id)):
        notify(db, p.user_id, "room_update", f"Room cancelled: {room.title}", "The creator cancelled this room.", "/rooms", dedupe_key=f"room_cancel:{room.id}:{p.user_id}")
    publish_after_commit(db, "room", room.id, "room_phase", {"status": "cancelled"})
    db.commit()
    return ok({"cancelled": True})


# ---------------- topics ----------------

class TopicIn(BaseModel):
    done: bool


@router.put("/{room_id}/topics/{topic_id}")
def set_topic(room_id: str, topic_id: str, body: TopicIn, user: User = Depends(acting_user), db: Session = Depends(get_db)):
    limiter.hit("topic_toggle", user.id)
    room = svc.get_room(db, room_id)
    prog = svc.set_topic(db, room, user, topic_id, body.done)
    db.commit()
    return ok(prog)


class TopicsEditIn(BaseModel):
    topics: list[str] = Field(min_length=1, max_length=30)
    confirm_syllabus_change: bool = False


@router.put("/{room_id}/topics")
def edit_topics(room_id: str, body: TopicsEditIn, user: User = Depends(acting_user), db: Session = Depends(get_db)):
    """Replaces the checklist. Existing topics keep their id (and everyone's progress) when their title is unchanged."""
    room = svc.get_room(db, room_id)
    svc.require_creator(room, user.id)
    svc.sync_room(db, room)
    if room.status not in ("scheduled", "studying"):
        raise ApiError("SYLLABUS_LOCKED", "The syllabus is locked once the study phase ends.", 409)
    if room.status == "studying" and not body.confirm_syllabus_change:
        raise ApiError("CONFIRM_REQUIRED", "Changing topics during the study phase changes everyone's progress and the final quiz scope. Confirm to continue.", 409)
    _replace_topics(db, room, body.topics)
    svc.system_message(db, room.id, "The room creator updated the topic checklist.")
    publish_after_commit(db, "room", room.id, "room_updated", {})
    db.commit()
    return ok(svc.detail(db, room, user.id))


def _replace_topics(db: Session, room: Room, titles: list[str]) -> None:
    from ..models import Question, TopicProgress

    clean, seen = [], set()
    for t in titles:
        t = " ".join(str(t).split())[:100]
        if t and t.lower() not in seen:
            seen.add(t.lower())
            clean.append(t)
    if not clean:
        raise ApiError("VALIDATION_ERROR", "Keep at least one topic.", 422)
    existing = {t.title.lower(): t for t in svc.topics(db, room.id)}
    keep = set()
    for i, title in enumerate(clean):
        t = existing.get(title.lower())
        if t:
            t.position, t.title = i, title
            keep.add(t.id)
        else:
            db.add(RoomTopic(room_id=room.id, position=1000 + i, title=title))
    db.flush()
    for t in existing.values():
        if t.id not in keep:
            db.execute(TopicProgress.__table__.delete().where(TopicProgress.topic_id == t.id))
            db.execute(Question.__table__.update().where(Question.topic_id == t.id).values(topic_id=None))
            db.delete(t)
    db.flush()
    for i, t in enumerate(sorted(svc.topics(db, room.id), key=lambda t: clean.index(t.title) if t.title in clean else 999)):
        t.position = i


# ---------------- pomodoro ----------------

class PomodoroIn(BaseModel):
    action: str = Field(pattern="^(configure|focus|break|stop)$")
    focus_minutes: int | None = None
    break_minutes: int | None = None


@router.post("/{room_id}/pomodoro")
def pomodoro(room_id: str, body: PomodoroIn, user: User = Depends(acting_user), db: Session = Depends(get_db)):
    limiter.hit("pomodoro", user.id)
    room = svc.get_room(db, room_id)
    if body.action == "configure":
        st = svc.configure(db, room, user, body.focus_minutes or 25, body.break_minutes or 5)
    elif body.action == "focus":
        st = svc.start_focus(db, room, user)
    elif body.action == "break":
        st = svc.take_break(db, room, user)
    else:
        st = svc.stop(db, room, user)
    db.commit()
    return ok({"pomodoro": svc.pomodoro_view(st, room), "server_time": iso(utcnow())})


@router.get("/{room_id}/participants")
def participants(room_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    room = svc.get_room(db, room_id)
    svc.require_participant(db, room, user.id)
    return ok(svc.participants_view(db, room, user.id))


# ---------------- moderation ----------------

class ModerateIn(BaseModel):
    action: str = Field(pattern="^(mute|unmute|remove)$")
    user_id: str
    minutes: int | None = Field(default=None, ge=1, le=120)
    reason: str = Field(default="", max_length=300)


@router.post("/{room_id}/moderate")
def moderate(room_id: str, body: ModerateIn, user: User = Depends(acting_user), db: Session = Depends(get_db)):
    room = svc.get_room(db, room_id)
    svc.require_creator(room, user.id)
    if body.user_id == user.id:
        raise ApiError("VALIDATION_ERROR", "You can't moderate yourself.", 422)
    target = svc.participant(db, room.id, body.user_id)
    if not target or target.status != "active":
        raise not_found("Participant")
    if body.action == "mute":
        target.muted_until = utcnow() + timedelta(minutes=body.minutes or 10)
        notify(db, body.user_id, "moderation", f"You've been muted in {room.title}", f"For {body.minutes or 10} minutes." + (f" Reason: {body.reason}" if body.reason else ""), f"/rooms/{room.id}")
    elif body.action == "unmute":
        target.muted_until = None
    else:
        if room.status == "race":
            raise ApiError("RACE_RUNNING", "Participants can't be removed while the race is running.", 409)
        svc.leave(db, room, db.get(User, body.user_id), removed_by=user.id)
        notify(db, body.user_id, "moderation", f"You were removed from {room.title}", body.reason or "The room creator removed you.", "/rooms")
    db.add(ModerationAction(room_id=room.id, actor_id=user.id, target_user_id=body.user_id, action=body.action, reason=body.reason, minutes=body.minutes))
    publish_after_commit(db, "room", room.id, "participants_changed", {})
    db.commit()
    if body.action == "remove":
        hub.kick_from_room(room.id, body.user_id)
    return ok({"done": True})


@router.get("/{room_id}/moderation-log")
def moderation_log(room_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    room = svc.get_room(db, room_id)
    svc.require_creator(room, user.id)
    rows = db.execute(select(ModerationAction, User.name).join(User, User.id == ModerationAction.actor_id).where(ModerationAction.room_id == room.id).order_by(ModerationAction.created_at.desc()).limit(100)).all()
    names = {u.id: u.name for u in db.scalars(select(User).where(User.id.in_([a.target_user_id for a, _ in rows if a.target_user_id])))}
    return ok([{"action": a.action, "actor": n, "target": names.get(a.target_user_id), "message_id": a.message_id, "reason": a.reason, "minutes": a.minutes, "created_at": iso(a.created_at)} for a, n in rows])


# ---------------- invitations ----------------

class InviteIn(BaseModel):
    user_ids: list[str] = Field(min_length=1, max_length=20)


@router.get("/{room_id}/invitable")
def invitable(room_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    room = svc.get_room(db, room_id)
    svc.require_participant(db, room, user.id)
    in_room = set(db.scalars(select(RoomParticipant.user_id).where(RoomParticipant.room_id == room.id, RoomParticipant.status == "active")))
    pending = set(db.scalars(select(RoomInvite.invitee_id).where(RoomInvite.room_id == room.id, RoomInvite.status == "pending")))
    out = []
    for uid in eligible_invitees(db, user.id) - in_room:
        u = db.get(User, uid)
        out.append({"id": uid, "name": u.name, "can_invite": can_invite(db, user.id, uid), "pending": uid in pending})
    return ok(sorted(out, key=lambda r: r["name"]))


@router.post("/{room_id}/invites")
def invite(room_id: str, body: InviteIn, user: User = Depends(acting_user), db: Session = Depends(get_db)):
    room = svc.get_room(db, room_id)
    svc.sync_room(db, room)
    svc.require_participant(db, room, user.id)
    if room.status not in ("scheduled", "studying"):
        raise ApiError("ROOM_CLOSED", "This room can't be joined any more.", 409)
    if room.visibility == "private" and room.creator_id != user.id:
        raise forbidden("Only the creator can invite people to a private room.")
    sent = []
    for uid in dict.fromkeys(body.user_ids):
        limiter.hit("invite", user.id)
        if not db.get(User, uid) or not can_invite(db, user.id, uid):
            continue
        p = svc.participant(db, room.id, uid)
        if p and p.status in ("active", "removed"):
            continue
        if db.scalar(select(RoomInvite.id).where(RoomInvite.room_id == room.id, RoomInvite.invitee_id == uid, RoomInvite.status == "pending")):
            continue
        inv = RoomInvite(room_id=room.id, inviter_id=user.id, invitee_id=uid)
        db.add(inv)
        db.flush()
        notify(db, uid, "room_invite", f"{user.name} invited you to study", f"{room.title} ({room.subject})", "/invites", {"invite_id": inv.id, "room_id": room.id}, dedupe_key=f"room_invite:{inv.id}")
        sent.append(uid)
    db.commit()
    return ok({"sent": sent, "skipped": len(body.user_ids) - len(sent)})


