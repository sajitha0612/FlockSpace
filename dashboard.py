from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.db import get_db, iso, utcnow
from ..core.errors import ok
from ..core.security import current_user
from ..models import AIJob, BuddyRequest, Note, PomodoroState, QuizAttempt, Room, RoomInvite, StudySession, User
from ..services import analytics, matching, meetings, quiz, race, rewards
from ..services import rooms as room_service
from .views import me_view, reward_summary

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard")
def dashboard(user: User = Depends(current_user), db: Session = Depends(get_db)):
    active = room_service.joined_rooms(db, user.id, ("scheduled", "studying", "race"))
    for r in active:
        room_service.sync_room(db, r)
    rooms_out, progress_out, halfway_out = [], [], []
    for r in active:
        card = room_service.card(db, r, user.id)
        st = db.scalar(select(PomodoroState).where(PomodoroState.room_id == r.id, PomodoroState.user_id == user.id))
        card["pomodoro"] = room_service.pomodoro_view(st, r)
        card["progress"] = room_service.progress(db, r.id, user.id)
        rooms_out.append(card)
        if r.status == "studying":
            hs = quiz.halfway_status(db, r, user.id)
            progress_out.append({"room_id": r.id, "title": r.title, **card["progress"]})
            halfway_out.append({"room_id": r.id, "title": r.title, "unlocked": hs["unlocked"], "can_start": hs["can_start"],
                                "attempt": {k: hs["attempt"][k] for k in ("submitted", "score", "total", "twigs")} if hs["attempt"] else None})
    recent_halfway = [{"room_id": a.room_id, "title": t, "score": a.score, "total": a.total, "twigs": a.twigs, "at": iso(a.submitted_at)}
                      for a, t in db.execute(select(QuizAttempt, Room.title).join(Room, Room.id == QuizAttempt.room_id).where(
                          QuizAttempt.user_id == user.id, QuizAttempt.submitted_at.is_not(None)).order_by(QuizAttempt.submitted_at.desc()).limit(5)).all()]
    recommended_rooms = []
    from ..api.rooms import discover  # reuse the same filtering rules as the Discover page

    found = discover(q="", subject="", course="", topic="", year=None, when="week", available=True, interests=True, sort="soonest", user=user, db=db)["data"]["rooms"]
    recommended_rooms = [r for r in found if not r.get("my_status") == "active"][:4]
    joined_ids = [r.id for r in room_service.joined_rooms(db, user.id, ("scheduled", "studying", "race", "finished"))]
    notes = [{"id": n.id, "room_id": n.room_id, "title": n.title, "kind": n.kind, "status": n.status, "created_at": iso(n.created_at)}
             for n in db.scalars(select(Note).where(Note.room_id.in_(joined_ids or [""])).order_by(Note.created_at.desc()).limit(6))]
    pending_ai = [{"id": j.id, "kind": j.kind, "status": j.status, "room_id": j.room_id} for j in db.scalars(select(AIJob).where(
        AIJob.user_id == user.id, AIJob.status.in_(("queued", "validating", "extracting", "processing")), AIJob.kind != "extract"))]
    recent_sessions = [{"room_id": s.room_id, "subject": s.subject, "minutes": s.minutes, "status": s.status, "ended_at": iso(s.ended_at)}
                       for s in db.scalars(select(StudySession).where(StudySession.user_id == user.id, StudySession.ended_at.is_not(None)).order_by(StudySession.ended_at.desc()).limit(8))]
    return ok({
        "user": me_view(db, user),
        "server_time": iso(utcnow()),
        "rewards": reward_summary(db, user.id),
        "rooms": rooms_out,
        "recommended_rooms": recommended_rooms,
        "buddy_recommendations": matching.recommendations(db, user, 3),
        "progress": progress_out,
        "halfway": halfway_out,
        "recent_halfway": recent_halfway,
        "races": race.history(db, user.id, 5),
        "golden_history": rewards.golden_history(db, user.id)[:5],
        "pending_requests": len(list(db.scalars(select(BuddyRequest.id).where(BuddyRequest.to_id == user.id, BuddyRequest.status == "pending")))),
        "pending_invites": len(list(db.scalars(select(RoomInvite.id).where(RoomInvite.invitee_id == user.id, RoomInvite.status == "pending")))),
        "meetings": [meetings.view(db, m, user.id) for m in meetings.list_for(db, user.id, past=False)[:5]],
        "notes": notes,
        "pending_ai": pending_ai,
        "recent_sessions": recent_sessions,
        "streak": analytics.streak(db, user.id),
    })


@router.get("/me/analytics")
def my_analytics(range: str = Query("week", pattern="^(week|month|all)$"), user: User = Depends(current_user), db: Session = Depends(get_db)):  # noqa: A002
    return ok(analytics.analytics(db, user.id, range))


@router.get("/me/streak")
def my_streak(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return ok(analytics.streak(db, user.id))
