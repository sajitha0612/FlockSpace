"""
Reports, review, restrictions and appeals.

- Any student can report a user, a message, a room, an invitation or a meeting. The reported person is never told
  who reported them, and reports are visible only to the reporter (status only) and to platform reviewers.
- Reviewers (accounts listed in ADMIN_EMAILS) work the report queue and the risk-flag queue. Consequential actions
  (suspension, chat restriction, reward hold, releasing a withheld Golden Nest) are taken only by a reviewer, are
  audited, and can always be appealed. Nothing is removed or banned automatically.
"""
from datetime import timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.db import get_db, iso, utcnow
from ..core.errors import ApiError, forbidden, not_found, ok
from ..core.ratelimit import limiter
from ..core.security import admin_user, current_user
from ..models import Appeal, ChatMessage, GoldenNest, Meeting, Report, Restriction, RiskFlag, Room, RoomInvite, User
from ..services import rewards, safety
from ..services.notify import notify

router = APIRouter(tags=["safety"])
CATEGORIES = {"harassment", "spam", "cheating", "inappropriate", "privacy", "other"}


class ReportIn(BaseModel):
    target_type: str = Field(pattern="^(user|message|room|invite|meeting)$")
    target_id: str
    category: str
    details: str = Field(default="", max_length=2000)
    also_block: bool = False


@router.post("/reports")
def report(body: ReportIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    limiter.hit("report", user.id)
    if body.category not in CATEGORIES:
        raise ApiError("VALIDATION_ERROR", "Pick a category.", 422)
    target_user, room_id, evidence = None, None, {}
    if body.target_type == "user":
        if not db.get(User, body.target_id):
            raise not_found("Student")
        target_user = body.target_id
    elif body.target_type == "message":
        m = db.get(ChatMessage, body.target_id)
        from ..services.rooms import participant

        if not m or not participant(db, m.room_id, user.id):
            raise not_found("Message")
        target_user, room_id, evidence = m.user_id, m.room_id, {"text": m.body, "sent_at": iso(m.created_at)}
    elif body.target_type == "room":
        r = db.get(Room, body.target_id)
        if not r:
            raise not_found("Room")
        target_user, room_id = r.creator_id, r.id
    elif body.target_type == "invite":
        i = db.get(RoomInvite, body.target_id)
        if not i or i.invitee_id != user.id:
            raise not_found("Invitation")
        target_user, room_id = i.inviter_id, i.room_id
    else:
        mt = db.get(Meeting, body.target_id)
        if not mt:
            raise not_found("Meeting")
        target_user = mt.creator_id
    if target_user == user.id:
        raise ApiError("VALIDATION_ERROR", "You can't report yourself.", 422)
    if db.scalar(select(Report.id).where(Report.reporter_id == user.id, Report.target_type == body.target_type, Report.target_id == body.target_id, Report.status == "open")):
        raise ApiError("ALREADY_REPORTED", "You've already reported this. Reviewers will look at it.", 409)
    r = Report(reporter_id=user.id, target_type=body.target_type, target_id=body.target_id, target_user_id=target_user, room_id=room_id,
               category=body.category, details=body.details.strip(), evidence=evidence)
    db.add(r)
    db.commit()
    if body.also_block and target_user:
        from .social import block

        block(target_user, user, db)
    return ok({"id": r.id, "status": r.status})


@router.get("/me/reports")
def my_reports(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Report).where(Report.reporter_id == user.id).order_by(Report.created_at.desc()).limit(50))
    return ok([{"id": r.id, "target_type": r.target_type, "category": r.category, "status": r.status, "created_at": iso(r.created_at)} for r in rows])


@router.get("/me/restrictions")
def my_restrictions(user: User = Depends(current_user), db: Session = Depends(get_db)):
    now = utcnow()
    rows = db.scalars(select(Restriction).where(Restriction.user_id == user.id).order_by(Restriction.created_at.desc()))
    appeals = {a.restriction_id: a for a in db.scalars(select(Appeal).where(Appeal.user_id == user.id))}
    out = []
    for r in rows:
        active = r.lifted_at is None and (r.expires_at is None or r.expires_at > now)
        a = appeals.get(r.id)
        out.append({"id": r.id, "kind": r.kind, "reason": r.reason, "active": active, "created_at": iso(r.created_at), "expires_at": iso(r.expires_at),
                    "appeal": {"status": a.status, "response": a.response} if a else None})
    withheld = [{"room_id": g.room_id, "placement": g.placement, "awarded_at": iso(g.awarded_at)} for g in db.scalars(select(GoldenNest).where(GoldenNest.user_id == user.id, GoldenNest.status == "withheld"))]
    return ok({"restrictions": out, "withheld_golden_nests": withheld})


class AppealIn(BaseModel):
    restriction_id: str
    text: str = Field(min_length=10, max_length=3000)


@router.post("/appeals")
def appeal(body: AppealIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    r = db.get(Restriction, body.restriction_id)
    if not r or r.user_id != user.id:
        raise not_found("Restriction")
    if db.scalar(select(Appeal.id).where(Appeal.restriction_id == r.id, Appeal.status == "open")):
        raise ApiError("ALREADY_APPEALED", "Your appeal is already waiting for review.", 409)
    a = Appeal(user_id=user.id, restriction_id=r.id, text=body.text.strip())
    db.add(a)
    db.commit()
    return ok({"id": a.id, "status": a.status})


# ---------------- reviewers ----------------

@router.get("/admin/queue")
def queue(user: User = Depends(admin_user), db: Session = Depends(get_db)):
    names = lambda ids: {u.id: u.name for u in db.scalars(select(User).where(User.id.in_([i for i in ids if i])))}
    reports = list(db.scalars(select(Report).where(Report.status == "open").order_by(Report.created_at)))
    flags = list(db.scalars(select(RiskFlag).where(RiskFlag.status == "open").order_by(RiskFlag.created_at)))
    appeals = list(db.scalars(select(Appeal).where(Appeal.status == "open").order_by(Appeal.created_at)))
    n = names([r.reporter_id for r in reports] + [r.target_user_id for r in reports] + [f.subject_user_id for f in flags] + [a.user_id for a in appeals])
    restrictions = {a.restriction_id: db.get(Restriction, a.restriction_id) for a in appeals}
    return ok({
        "reports": [{"id": r.id, "reporter": n.get(r.reporter_id), "target_type": r.target_type, "target_id": r.target_id, "target_user": {"id": r.target_user_id, "name": n.get(r.target_user_id)},
                     "room_id": r.room_id, "category": r.category, "details": r.details, "evidence": r.evidence, "created_at": iso(r.created_at)} for r in reports],
        "flags": [{"id": f.id, "kind": f.kind, "user": {"id": f.subject_user_id, "name": n.get(f.subject_user_id)}, "details": f.details, "created_at": iso(f.created_at)} for f in flags],
        "appeals": [{"id": a.id, "user": {"id": a.user_id, "name": n.get(a.user_id)}, "text": a.text, "restriction": {"kind": restrictions[a.restriction_id].kind, "reason": restrictions[a.restriction_id].reason},
                     "created_at": iso(a.created_at)} for a in appeals],
    })


class ResolveIn(BaseModel):
    status: str = Field(pattern="^(resolved|dismissed)$")
    resolution: str = Field(default="", max_length=2000)


@router.post("/admin/reports/{report_id}")
def resolve_report(report_id: str, body: ResolveIn, user: User = Depends(admin_user), db: Session = Depends(get_db)):
    r = db.get(Report, report_id)
    if not r:
        raise not_found("Report")
    r.status, r.resolution, r.reviewer_id, r.reviewed_at = body.status, body.resolution, user.id, utcnow()
    safety.audit(db, user.id, f"report_{body.status}", r.id)
    notify(db, r.reporter_id, "report_update", "Your report was reviewed", "Thanks for helping keep FlockSpace safe.", "/settings", dedupe_key=f"report_done:{r.id}")
    db.commit()
    return ok({"status": r.status})


class FlagIn(BaseModel):
    status: str = Field(pattern="^(dismissed|actioned)$")
    note: str = Field(default="", max_length=2000)
    release_golden: bool = False


@router.post("/admin/flags/{flag_id}")
def review_flag(flag_id: str, body: FlagIn, user: User = Depends(admin_user), db: Session = Depends(get_db)):
    f = db.get(RiskFlag, flag_id)
    if not f:
        raise not_found("Flag")
    f.status, f.note, f.reviewed_by, f.reviewed_at = body.status, body.note, user.id, utcnow()
    if body.release_golden and f.kind == "golden_withheld":
        g = db.scalar(select(GoldenNest).where(GoldenNest.race_id == f.details.get("race_id"), GoldenNest.user_id == f.subject_user_id))
        if g and g.status == "withheld":
            g.status = "awarded"
            notify(db, g.user_id, "golden_nest", "Your Golden Nest was released", "A reviewer approved your Golden Nest.", "/achievements", dedupe_key=f"golden_release:{g.id}")
            rewards.check_milestones(db, g.user_id)
    safety.audit(db, user.id, f"flag_{body.status}", f.id, {"release_golden": body.release_golden})
    db.commit()
    return ok({"status": f.status})


class RestrictIn(BaseModel):
    user_id: str
    kind: str = Field(pattern="^(suspended|chat_ban|reward_hold)$")
    reason: str = Field(min_length=5, max_length=300)
    days: int | None = Field(default=None, ge=1, le=365)


@router.post("/admin/restrictions")
def restrict(body: RestrictIn, user: User = Depends(admin_user), db: Session = Depends(get_db)):
    if body.user_id == user.id or not db.get(User, body.user_id):
        raise ApiError("VALIDATION_ERROR", "Invalid student.", 422)
    r = Restriction(user_id=body.user_id, kind=body.kind, reason=body.reason, created_by=user.id, expires_at=utcnow() + timedelta(days=body.days) if body.days else None)
    db.add(r)
    safety.audit(db, user.id, f"restrict_{body.kind}", body.user_id, {"days": body.days})
    notify(db, body.user_id, "moderation", "A reviewer placed a restriction on your account", f"{body.reason} You can appeal from Settings.", "/settings")
    db.commit()
    return ok({"id": r.id})


@router.post("/admin/restrictions/{restriction_id}/lift")
def lift(restriction_id: str, user: User = Depends(admin_user), db: Session = Depends(get_db)):
    r = db.get(Restriction, restriction_id)
    if not r:
        raise not_found("Restriction")
    r.lifted_at = r.lifted_at or utcnow()
    safety.audit(db, user.id, "restriction_lifted", r.id)
    db.commit()
    return ok({"lifted": True})


class AppealDecisionIn(BaseModel):
    overturn: bool
    response: str = Field(min_length=3, max_length=2000)


@router.post("/admin/appeals/{appeal_id}")
def decide_appeal(appeal_id: str, body: AppealDecisionIn, user: User = Depends(admin_user), db: Session = Depends(get_db)):
    a = db.get(Appeal, appeal_id)
    if not a or a.status != "open":
        raise not_found("Appeal")
    if a.user_id == user.id:
        raise forbidden("You can't review your own appeal.")
    a.status, a.response, a.reviewer_id, a.reviewed_at = ("overturned" if body.overturn else "upheld"), body.response, user.id, utcnow()
    if body.overturn:
        r = db.get(Restriction, a.restriction_id)
        r.lifted_at = r.lifted_at or utcnow()
    safety.audit(db, user.id, f"appeal_{a.status}", a.id)
    notify(db, a.user_id, "moderation", f"Your appeal was {a.status}", body.response, "/settings", dedupe_key=f"appeal:{a.id}")
    db.commit()
    return ok({"status": a.status})
