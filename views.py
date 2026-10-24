"""Shared response shapes for users and profiles."""
from sqlalchemy.orm import Session

from ..core.db import iso
from ..core.security import active_restriction
from ..models import Profile, User
from ..services import rewards


def me_view(db: Session, user: User) -> dict:
    p = db.get(Profile, user.id)
    return {
        "id": user.id, "email": user.email, "name": user.name, "role": user.role, "email_verified": user.email_verified,
        "created_at": iso(user.created_at), "timezone": p.timezone if p else "UTC", "bird": p.bird if p else {},
        "onboarded": bool(p and p.subjects and p.questionnaire), "suspended": bool(active_restriction(db, user.id, "suspended")),
    }


def profile_view(p: Profile) -> dict:
    return {
        "bio": p.bio, "subjects": p.subjects, "courses": p.courses, "year": p.year, "goals": p.goals, "interests": p.interests,
        "study_times": p.study_times, "study_style": {k: v for k, v in (p.study_style or {}).items() if k != "vector"},
        "timezone": p.timezone, "daily_goal_minutes": p.daily_goal_minutes, "bird": p.bird,
    }


def reward_summary(db: Session, user_id: str) -> dict:
    return {
        "twigs": rewards.balance(db, user_id), "nest": rewards.personal_nest(db, user_id), "golden_nests": rewards.golden_count(db, user_id),
        "next_milestone": rewards.next_milestone(db, user_id),
    }
