"""
Social connections. Following and buddies are separate: following is one-way and needs no approval; a buddy
link needs a request and an acceptance. Neither one grants access to private rooms. Blocking is enforced
here on the server for every action (see services/relations.py for exactly what a block does).
"""
from datetime import timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..core.db import get_db, iso, utcnow
from ..core.errors import ApiError, forbidden, not_found, ok
from ..core.ratelimit import limiter
from ..core.security import acting_user, current_user
from ..models import Block, Buddy, BuddyRequest, Follow, MeetingInvite, Nudge, Profile, Room, RoomInvite, RoomParticipant, SessionFeedback, User
from ..services import matching
from ..services import rooms as room_service
from ..services.notify import notify
from ..services.relations import blocked_either, blocked_ids, buddies, can_see_activity, follows, pair, settings_of
from ..services.social_status import activity_status

router = APIRouter(tags=["social"])

NUDGES = {
    "study_together": "Let's study together!",
    "keep_going": "Keep going!",
    "pomodoro": "Ready for a Pomodoro session?",
    "finish_goals": "Let's finish our study goals today!",
}
FEEDBACK_TAGS = {"helpful": "Helpful study partner", "schedule": "Good schedule compatibility", "collaboration": "Effective collaboration",
                 "again": "Would study together again", "not_fit": "Partnership was not a good fit"}


def _user(db: Session, user_id: str) -> User:
    u = db.get(User, user_id)
    if not u:
        raise not_found("Student")
    return u


def _card(db: Session, u: User, viewer: str) -> dict:
    p = db.get(Profile, u.id)
    return {"id": u.id, "name": u.name, "year": p.year if p else None, "subjects": (p.subjects or [])[:3] if p else [], "bird": p.bird if p else {},
            "activity": activity_status(db, u.id) if can_see_activity(db, u.id, viewer) else None}


# ---------------- following ----------------

@router.post("/users/{user_id}/follow")
def follow(user_id: str, user: User = Depends(acting_user), db: Session = Depends(get_db)):
    if user_id == user.id:
        raise ApiError("VALIDATION_ERROR", "You can't follow yourself.", 422)
    _user(db, user_id)
    if blocked_either(db, user.id, user_id):
        raise forbidden("You can't follow this student.")
    if follows(db, user.id, user_id):
        return ok({"following": True})
    limiter.hit("follow", user.id)
    try:
        with db.begin_nested():
            db.add(Follow(follower_id=user.id, followee_id=user_id))
    except IntegrityError:
        return ok({"following": True})
    notify(db, user_id, "follow", f"{user.name} started following you", "", f"/u/{user.id}", dedupe_key=f"follow:{user.id}:{user_id}:{utcnow().date()}")
    db.commit()
    return ok({"following": True})


@router.delete("/users/{user_id}/follow")
def unfollow(user_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    limiter.hit("follow", user.id)
    db.execute(Follow.__table__.delete().where(Follow.follower_id == user.id, Follow.followee_id == user_id))
    db.commit()
    return ok({"following": False})


@router.get("/me/connections")
def connections(user: User = Depends(current_user), db: Session = Depends(get_db)):
    hidden = blocked_ids(db, user.id)
    following = [u for u in db.scalars(select(User).join(Follow, Follow.followee_id == User.id).where(Follow.follower_id == user.id)) if u.id not in hidden]
    followers = [u for u in db.scalars(select(User).join(Follow, Follow.follower_id == User.id).where(Follow.followee_id == user.id)) if u.id not in hidden]
    rows = db.execute(select(Buddy).where(or_(Buddy.user_a == user.id, Buddy.user_b == user.id))).scalars()
    buddy_ids = [b.user_b if b.user_a == user.id else b.user_a for b in rows]
    buddy_users = [db.get(User, i) for i in buddy_ids if i not in hidden]
    return ok({"following": [_card(db, u, user.id) for u in following], "followers": [_card(db, u, user.id) for u in followers],
               "buddies": [_card(db, u, user.id) for u in buddy_users if u]})


# ---------------- buddy requests ----------------

@router.post("/users/{user_id}/buddy-request")
def send_request(user_id: str, user: User = Depends(acting_user), db: Session = Depends(get_db)):
    if user_id == user.id:
        raise ApiError("VALIDATION_ERROR", "You can't buddy yourself.", 422)
    _user(db, user_id)
    if blocked_either(db, user.id, user_id) or settings_of(db, user_id).get("who_can_request") == "nobody":
        raise forbidden("This student isn't accepting buddy requests.")
    if buddies(db, user.id, user_id):
        raise ApiError("ALREADY_BUDDIES", "You're already buddies.", 409)
    if db.scalar(select(BuddyRequest.id).where(BuddyRequest.from_id == user_id, BuddyRequest.to_id == user.id, BuddyRequest.status == "pending")):
        raise ApiError("REQUEST_WAITING", "They've already sent you a request: accept it from your requests.", 409)
    if db.scalar(select(BuddyRequest.id).where(BuddyRequest.from_id == user.id, BuddyRequest.to_id == user_id, BuddyRequest.status == "pending")):
        raise ApiError("ALREADY_REQUESTED", "Your request is already pending.", 409)
    recent_reject = db.scalar(select(BuddyRequest.id).where(BuddyRequest.from_id == user.id, BuddyRequest.to_id == user_id, BuddyRequest.status == "rejected",
                                                           BuddyRequest.responded_at >= utcnow() - timedelta(days=7)))
    if recent_reject:
        raise ApiError("COOLDOWN", "They declined recently. You can ask again after a week.", 429)
    limiter.hit("buddy_request", user.id)
    req = BuddyRequest(from_id=user.id, to_id=user_id)
    try:
        with db.begin_nested():
            db.add(req)
            db.flush()
    except IntegrityError:
        raise ApiError("ALREADY_REQUESTED", "Your request is already pending.", 409)
    notify(db, user_id, "buddy_request", f"{user.name} wants to be study buddies", "", "/buddies?tab=requests", {"request_id": req.id}, dedupe_key=f"buddy_req:{req.id}")
    db.commit()
    return ok({"id": req.id, "status": req.status})


@router.get("/me/buddy-requests")
def my_requests(user: User = Depends(current_user), db: Session = Depends(get_db)):
    hidden = blocked_ids(db, user.id)
    inc = [(r, db.get(User, r.from_id)) for r in db.scalars(select(BuddyRequest).where(BuddyRequest.to_id == user.id, BuddyRequest.status == "pending").order_by(BuddyRequest.created_at.desc())) if r.from_id not in hidden]
    out = [(r, db.get(User, r.to_id)) for r in db.scalars(select(BuddyRequest).where(BuddyRequest.from_id == user.id, BuddyRequest.status == "pending").order_by(BuddyRequest.created_at.desc()))]
    return ok({"incoming": [{"id": r.id, "user": _card(db, u, user.id), "created_at": iso(r.created_at)} for r, u in inc],
               "outgoing": [{"id": r.id, "user": _card(db, u, user.id), "created_at": iso(r.created_at)} for r, u in out]})


class RespondIn(BaseModel):
    action: str = Field(pattern="^(accept|reject|cancel)$")


@router.post("/buddy-requests/{request_id}")
def respond_request(request_id: str, body: RespondIn, user: User = Depends(acting_user), db: Session = Depends(get_db)):
    req = db.get(BuddyRequest, request_id)
    if not req or user.id not in (req.from_id, req.to_id):
        raise not_found("Request")
    if req.status != "pending":
        raise ApiError("INVALID_STATE", f"This request was already {req.status}.", 409)
    if body.action == "cancel":
        if req.from_id != user.id:
            raise forbidden("Only the sender can cancel a request.")
        req.status = "cancelled"
    else:
        if req.to_id != user.id:
            raise forbidden("Only the recipient can answer a request.")
        if body.action == "accept":
            if blocked_either(db, req.from_id, req.to_id):
                raise forbidden()
            a, b = pair(req.from_id, req.to_id)
            try:
                with db.begin_nested():
                    db.add(Buddy(user_a=a, user_b=b))
            except IntegrityError:
                pass
            req.status = "accepted"
            notify(db, req.from_id, "buddy_accepted", f"{user.name} accepted your buddy request", "", f"/u/{user.id}", dedupe_key=f"buddy_acc:{req.id}")
        else:
            req.status = "rejected"
    req.responded_at = utcnow()
    db.commit()
    return ok({"status": req.status})


@router.delete("/users/{user_id}/buddy")
def remove_buddy(user_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    a, b = pair(user.id, user_id)
    db.execute(Buddy.__table__.delete().where(Buddy.user_a == a, Buddy.user_b == b))
    db.commit()
    return ok({"buddies": False})


# ---------------- blocking ----------------

@router.post("/users/{user_id}/block")
def block(user_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user_id == user.id:
        raise ApiError("VALIDATION_ERROR", "You can't block yourself.", 422)
    _user(db, user_id)
    try:
        with db.begin_nested():
            db.add(Block(blocker_id=user.id, blocked_id=user_id))
    except IntegrityError:
        pass
    a, b = pair(user.id, user_id)
    db.execute(Follow.__table__.delete().where(or_((Follow.follower_id == user.id) & (Follow.followee_id == user_id), (Follow.follower_id == user_id) & (Follow.followee_id == user.id))))
    db.execute(Buddy.__table__.delete().where(Buddy.user_a == a, Buddy.user_b == b))
    for r in db.scalars(select(BuddyRequest).where(BuddyRequest.status == "pending", or_((BuddyRequest.from_id == user.id) & (BuddyRequest.to_id == user_id), (BuddyRequest.from_id == user_id) & (BuddyRequest.to_id == user.id)))):
        r.status, r.responded_at = "cancelled", utcnow()
    for inv in db.scalars(select(RoomInvite).where(RoomInvite.status == "pending", or_((RoomInvite.inviter_id == user.id) & (RoomInvite.invitee_id == user_id), (RoomInvite.inviter_id == user_id) & (RoomInvite.invitee_id == user.id)))):
        inv.status, inv.responded_at = "cancelled", utcnow()
    from ..models import Meeting

    for inv in db.scalars(select(MeetingInvite).join(Meeting, Meeting.id == MeetingInvite.meeting_id).where(
            MeetingInvite.status == "pending", or_((Meeting.creator_id == user_id) & (MeetingInvite.user_id == user.id), (Meeting.creator_id == user.id) & (MeetingInvite.user_id == user_id)))):
        inv.status, inv.responded_at = "declined", utcnow()
    db.commit()
    return ok({"blocked": True})


@router.delete("/users/{user_id}/block")
def unblock(user_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.execute(Block.__table__.delete().where(Block.blocker_id == user.id, Block.blocked_id == user_id))
    db.commit()
    return ok({"blocked": False})


@router.get("/me/blocked")
def blocked_list(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.execute(select(User, Block.created_at).join(Block, Block.blocked_id == User.id).where(Block.blocker_id == user.id)).all()
    return ok([{"id": u.id, "name": u.name, "since": iso(t)} for u, t in rows])


# ---------------- nudges ----------------

class NudgeIn(BaseModel):
    message: str = Field(pattern="^(study_together|keep_going|pomodoro|finish_goals)$")


@router.post("/users/{user_id}/nudge")
def nudge(user_id: str, body: NudgeIn, user: User = Depends(acting_user), db: Session = Depends(get_db)):
    target = _user(db, user_id)
    if user_id == user.id or blocked_either(db, user.id, user_id):
        raise forbidden("You can't nudge this student.")
    if not (buddies(db, user.id, user_id) or follows(db, user_id, user.id)):
        raise forbidden("You can nudge your buddies and people who follow you.")
    if not settings_of(db, user_id).get("nudges_enabled", True):
        raise forbidden(f"{target.name} has turned off nudges.")
    if db.scalar(select(Nudge.id).where(Nudge.from_id == user.id, Nudge.to_id == user_id, Nudge.created_at >= utcnow() - timedelta(hours=4))):
        raise ApiError("COOLDOWN", "You've nudged them recently. Give it a few hours.", 429)
    limiter.hit("nudge", user.id)
    db.add(Nudge(from_id=user.id, to_id=user_id, message_key=body.message))
    notify(db, user_id, "nudge", f"{user.name}: {NUDGES[body.message]}", "", f"/u/{user.id}")
    db.commit()
    return ok({"sent": True})


@router.get("/nudges/messages")
def nudge_messages():
    return ok(NUDGES)


# ---------------- discovery ----------------

@router.get("/buddies/recommendations")
def recommendations(user: User = Depends(current_user), db: Session = Depends(get_db)):
    me = db.get(Profile, user.id)
    return ok({"recommendations": matching.recommendations(db, user), "profile_complete": bool(me.subjects and me.questionnaire), "method": matching.__doc__})


@router.get("/buddies/studying-now")
def studying_now(user: User = Depends(current_user), db: Session = Depends(get_db)):
    ids = set(db.scalars(select(Follow.followee_id).where(Follow.follower_id == user.id)))
    for b in db.scalars(select(Buddy).where(or_(Buddy.user_a == user.id, Buddy.user_b == user.id))):
        ids.add(b.user_b if b.user_a == user.id else b.user_a)
    ids -= blocked_ids(db, user.id)
    out = []
    for uid in ids:
        if not can_see_activity(db, uid, user.id):
            continue
        st = activity_status(db, uid)
        if st["state"] != "offline":
            u = db.get(User, uid)
            out.append({**_card(db, u, user.id), "activity": st})
    order = {"studying": 0, "break": 1, "available": 2}
    return ok(sorted(out, key=lambda r: (order.get(r["activity"]["state"], 3), r["name"])))


# ---------------- room invitations ----------------

@router.get("/me/invites")
def my_invites(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.execute(select(RoomInvite, Room, User).join(Room, Room.id == RoomInvite.room_id).join(User, User.id == RoomInvite.inviter_id).where(
        RoomInvite.invitee_id == user.id, RoomInvite.status == "pending", Room.status.in_(("scheduled", "studying"))).order_by(RoomInvite.created_at.desc())).all()
    hidden = blocked_ids(db, user.id)
    return ok([{"id": i.id, "room": room_service.card(db, r, user.id), "inviter": {"id": u.id, "name": u.name}, "created_at": iso(i.created_at)} for i, r, u in rows if u.id not in hidden])


@router.post("/invites/{invite_id}")
def respond_invite(invite_id: str, body: RespondIn, user: User = Depends(acting_user), db: Session = Depends(get_db)):
    inv = db.get(RoomInvite, invite_id)
    if not inv or user.id not in (inv.invitee_id, inv.inviter_id):
        raise not_found("Invitation")
    if inv.status != "pending":
        raise ApiError("INVALID_STATE", f"This invitation was already {inv.status}.", 409)
    room = room_service.get_room(db, inv.room_id)
    if body.action == "cancel":
        if inv.inviter_id != user.id:
            raise forbidden()
        inv.status = "cancelled"
    elif inv.invitee_id != user.id:
        raise forbidden()
    elif body.action == "accept":
        room_service.join(db, room, user, via_invite=True)  # explicit acceptance; capacity and state checked here
        inv.status = "accepted"
        notify(db, inv.inviter_id, "invite_response", f"{user.name} joined {room.title}", "", f"/rooms/{room.id}", dedupe_key=f"invite_resp:{inv.id}")
    else:
        inv.status = "declined"
    inv.responded_at = utcnow()
    db.commit()
    return ok({"status": inv.status, "room_id": room.id})


# ---------------- post-session feedback (private) ----------------

@router.get("/rooms/{room_id}/feedback")
def feedback_targets(room_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    room = room_service.get_room(db, room_id)
    me = room_service.participant(db, room.id, user.id)
    if not me:
        raise forbidden()
    eligible = room.status in ("race", "finished")
    rated = {f.ratee_id: f.tags for f in db.scalars(select(SessionFeedback).where(SessionFeedback.rater_id == user.id, SessionFeedback.room_id == room.id))}
    hidden = blocked_ids(db, user.id)
    others = db.execute(select(User).join(RoomParticipant, RoomParticipant.user_id == User.id).where(RoomParticipant.room_id == room.id, User.id != user.id)).scalars()
    return ok({"eligible": eligible, "tags": FEEDBACK_TAGS, "partners": [{"id": u.id, "name": u.name, "rated": u.id in rated, "my_tags": rated.get(u.id)} for u in others if u.id not in hidden]})


class FeedbackIn(BaseModel):
    ratee_id: str
    tags: list[str] = Field(min_length=1, max_length=5)


@router.post("/rooms/{room_id}/feedback")
def give_feedback(room_id: str, body: FeedbackIn, user: User = Depends(acting_user), db: Session = Depends(get_db)):
    limiter.hit("feedback", user.id)
    room = room_service.get_room(db, room_id)
    if room.status not in ("race", "finished"):
        raise ApiError("NOT_YET", "Feedback opens when the study phase ends.", 409)
    if body.ratee_id == user.id or not room_service.participant(db, room.id, user.id) or not room_service.participant(db, room.id, body.ratee_id):
        raise forbidden("You can only give feedback on people you studied with in this room.")
    tags = sorted(set(body.tags))
    if any(t not in FEEDBACK_TAGS for t in tags) or ("not_fit" in tags and len(tags) > 1):
        raise ApiError("VALIDATION_ERROR", "Choose positive tags, or only 'not a good fit'.", 422)
    try:
        with db.begin_nested():
            db.add(SessionFeedback(rater_id=user.id, ratee_id=body.ratee_id, room_id=room.id, tags=tags))
            db.flush()
    except IntegrityError:
        raise ApiError("ALREADY_GIVEN", "You've already given feedback for this partner in this room.", 409)
    # one update per (room, rater, ratee): a single negative never blocks anyone, it only nudges the estimate
    matching.record_evidence(db, user.id, body.ratee_id, "beta" if tags == ["not_fit"] else "alpha", f"feedback:{room.id}:{user.id}:{body.ratee_id}")
    db.commit()
    return ok({"saved": True})
