from zoneinfo import available_timezones

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core.db import get_db, iso, utcnow
from ..core.errors import ApiError, not_found, ok
from ..core.security import acting_user, current_user
from ..models import BuddyRequest, Follow, Profile, User
from ..services import analytics, matching, race, rewards
from ..services.relations import blocked_either, blocked_ids, buddies, can_see_activity, follows, users_i_blocked
from ..services.social_status import activity_status
from .views import me_view, profile_view, reward_summary

router = APIRouter(tags=["profile"])


def _clean_list(xs: list[str], limit: int, size: int = 60) -> list[str]:
    out, seen = [], set()
    for x in xs or []:
        x = " ".join(str(x).split())[:size]
        if x and x.lower() not in seen:
            seen.add(x.lower())
            out.append(x)
    return out[:limit]


class ProfileIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    bio: str | None = Field(default=None, max_length=300)
    subjects: list[str] | None = None
    courses: list[str] | None = None
    year: int | None = Field(default=None, ge=1, le=8)
    goals: list[str] | None = None
    interests: list[str] | None = None
    study_times: list[str] | None = None
    timezone: str | None = None
    daily_goal_minutes: int | None = Field(default=None, ge=10, le=600)


@router.get("/me/profile")
def my_profile(user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = db.get(Profile, user.id)
    return ok({"user": me_view(db, user), "profile": profile_view(p), "rewards": reward_summary(db, user.id), "goals_catalog": matching.GOALS,
               "time_slots": matching.TIME_SLOTS, "golden_history": rewards.golden_history(db, user.id), "races": race.history(db, user.id),
               "streak": {k: v for k, v in analytics.streak(db, user.id).items() if k != "heatmap"}})


@router.patch("/me/profile")
def update_profile(body: ProfileIn, user: User = Depends(acting_user), db: Session = Depends(get_db)):
    p = db.get(Profile, user.id)
    if body.name is not None:
        user.name = " ".join(body.name.split())
    if body.bio is not None:
        p.bio = body.bio.strip()
    for field, limit in (("subjects", 12), ("courses", 8), ("interests", 12)):
        v = getattr(body, field)
        if v is not None:
            setattr(p, field, _clean_list(v, limit))
    if body.goals is not None:
        p.goals = [g for g in _clean_list(body.goals, 9, 40) if g in matching.GOALS]
    if body.study_times is not None:
        p.study_times = [t for t in body.study_times if t in matching.TIME_SLOTS]
    if body.year is not None:
        p.year = body.year
    if body.timezone is not None:
        if body.timezone not in available_timezones():
            raise ApiError("VALIDATION_ERROR", "Unknown timezone.", 422)
        p.timezone = body.timezone
    if body.daily_goal_minutes is not None:
        p.daily_goal_minutes = body.daily_goal_minutes
    db.commit()
    return ok(profile_view(p))


@router.get("/me/questionnaire")
def questionnaire(user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = db.get(Profile, user.id)
    return ok({"questions": matching.QUESTIONNAIRE, "answers": p.questionnaire or {}, "answered_at": iso(p.questionnaire_at)})


class AnswersIn(BaseModel):
    answers: dict


@router.put("/me/questionnaire")
def save_questionnaire(body: AnswersIn, user: User = Depends(acting_user), db: Session = Depends(get_db)):
    clean = matching.validate_answers(body.answers)
    p = db.get(Profile, user.id)
    p.questionnaire, p.questionnaire_at = clean, utcnow()
    p.study_style = matching.derive_style(clean)
    p.study_times = clean["q4"]
    db.commit()
    return ok(profile_view(p))


class SettingsIn(BaseModel):
    discoverable: bool | None = None
    activity_visibility: str | None = None
    who_can_request: str | None = None
    who_can_invite: str | None = None
    nudges_enabled: bool | None = None
    notify: dict | None = None


@router.get("/me/settings")
def get_settings_(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return ok(db.get(Profile, user.id).settings)


@router.patch("/me/settings")
def update_settings(body: SettingsIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    p = db.get(Profile, user.id)
    s = dict(p.settings or {})
    choices = {"activity_visibility": {"everyone", "followers", "buddies", "nobody"}, "who_can_request": {"everyone", "nobody"},
               "who_can_invite": {"everyone", "followers", "buddies", "nobody"}}
    for k, allowed in choices.items():
        v = getattr(body, k)
        if v is not None:
            if v not in allowed:
                raise ApiError("VALIDATION_ERROR", f"{k} must be one of {', '.join(sorted(allowed))}.", 422)
            s[k] = v
    for k in ("discoverable", "nudges_enabled"):
        if getattr(body, k) is not None:
            s[k] = getattr(body, k)
    if body.notify is not None:
        s["notify"] = {**s.get("notify", {}), **{k: bool(v) for k, v in body.notify.items() if k in s.get("notify", {})}}
    p.settings = s
    db.commit()
    return ok(s)


@router.get("/me/items")
def items(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return ok({"items": rewards.catalog_view(db, user.id), "bird": db.get(Profile, user.id).bird, "twigs": rewards.balance(db, user.id)})


@router.post("/me/items/{item_id}/buy")
def buy(item_id: str, user: User = Depends(acting_user), db: Session = Depends(get_db)):
    rewards.buy(db, user.id, item_id)
    db.commit()
    return ok({"items": rewards.catalog_view(db, user.id), "twigs": rewards.balance(db, user.id)})


class EquipIn(BaseModel):
    slot: str
    item_id: str | None = None


@router.put("/me/bird")
def equip(body: EquipIn, user: User = Depends(acting_user), db: Session = Depends(get_db)):
    bird = rewards.equip(db, user.id, body.slot, body.item_id)
    db.commit()
    return ok(bird)


@router.get("/me/ledger")
def ledger(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return ok({"entries": rewards.ledger_view(db, user.id, 100), "balance": rewards.balance(db, user.id)})


@router.get("/me/achievements")
def achievements(user: User = Depends(current_user), db: Session = Depends(get_db)):
    from ..core.config import get_settings

    count = rewards.golden_count(db, user.id)
    owned = rewards.owned(db, user.id)
    milestones = [{"at": n, "item": i, "name": rewards.ITEMS.get(i, {}).get("name", i), "unlocked": i in owned, "progress": min(count, n)} for n, i in get_settings().milestone_list]
    return ok({"golden_nests": count, "history": rewards.golden_history(db, user.id), "milestones": milestones, "next_milestone": rewards.next_milestone(db, user.id),
               "races": race.history(db, user.id, 50)})


# ---------------- other students ----------------

@router.get("/users")
def search_users(q: str = Query("", max_length=60), user: User = Depends(current_user), db: Session = Depends(get_db)):
    hidden = blocked_ids(db, user.id) | {user.id}
    stmt = select(User, Profile).join(Profile, Profile.user_id == User.id).where(User.id.notin_(hidden))
    if q.strip():
        stmt = stmt.where(func.lower(User.name).contains(q.strip().lower()))
    out = []
    for u, p in db.execute(stmt.order_by(User.name).limit(40)).all():
        if (p.settings or {}).get("discoverable", True) or follows(db, user.id, u.id) or buddies(db, user.id, u.id):
            out.append({"id": u.id, "name": u.name, "year": p.year, "subjects": p.subjects[:3], "bird": p.bird})
    return ok(out)


@router.get("/users/{user_id}")
def public_profile(user_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    other = db.get(User, user_id)
    if not other or blocked_either(db, user.id, user_id):
        raise not_found("Student")
    p = db.get(Profile, user_id)
    pending_out = db.scalar(select(BuddyRequest.id).where(BuddyRequest.from_id == user.id, BuddyRequest.to_id == user_id, BuddyRequest.status == "pending"))
    pending_in = db.scalar(select(BuddyRequest.id).where(BuddyRequest.from_id == user_id, BuddyRequest.to_id == user.id, BuddyRequest.status == "pending"))
    followers = db.scalar(select(func.count(Follow.id)).where(Follow.followee_id == user_id)) or 0
    following = db.scalar(select(func.count(Follow.id)).where(Follow.follower_id == user_id)) or 0
    data = {
        "id": other.id, "name": other.name, "bio": p.bio, "year": p.year, "subjects": p.subjects, "courses": p.courses, "interests": p.interests,
        "goals": p.goals, "bird": p.bird, "study_style": {k: v for k, v in (p.study_style or {}).items() if k != "vector"},
        "golden_nests": rewards.golden_count(db, user_id), "achievements": rewards.golden_history(db, user_id)[:10],
        "races": [{k: r[k] for k in ("room", "placement", "eligible_count", "finished_at", "status")} for r in race.history(db, user_id, 10)],
        "followers": followers, "following": following,
        "relationship": {"following": follows(db, user.id, user_id), "follows_you": follows(db, user_id, user.id), "buddies": buddies(db, user.id, user_id),
                         "request_sent": pending_out, "request_received": pending_in, "blocked_by_you": user_id in users_i_blocked(db, user.id)},
        "activity": activity_status(db, user_id) if can_see_activity(db, user_id, user.id) else None,
        "match": matching.profile_score(db.get(Profile, user.id), p) if user_id != user.id else None,
    }
    return ok(data)

