"""
Quiz endpoints. The question bank (with answers) is visible only to the room creator; other participants only
ever receive questions with opaque, per-person option tokens, and correct answers only after the quiz closes.
"""
import json
from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.db import get_db
from ..core.errors import ApiError, not_found, ok
from ..core.ratelimit import limiter
from ..core.security import acting_user, current_user
from ..models import Question, Race, RoomTopic, User
from ..services import quiz as qs
from ..services import race as race_service
from ..services import rooms as svc

router = APIRouter(tags=["quiz"])
SEED = Path(__file__).resolve().parents[1] / "seed" / "bank.json"


def _creator_room(db: Session, room_id: str, user: User):
    room = svc.get_room(db, room_id)
    svc.require_creator(room, user.id)
    return room


def _unlocked_bank(db: Session, room) -> None:
    if qs.bank_locked(db, room):
        raise ApiError("BANK_LOCKED", "The question set is locked: the Nest Race has been created.", 409)


@router.get("/rooms/{room_id}/questions")
def bank(room_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    room = _creator_room(db, room_id, user)
    return ok({"questions": qs.bank_view(db, room), "locked": qs.bank_locked(db, room)})


class QuestionIn(BaseModel):
    topic_id: str | None = None
    prompt: str = Field(min_length=5, max_length=1000)
    options: list[str] = Field(min_length=2, max_length=6)
    correct_index: int
    explanation: str = Field(default="", max_length=1000)
    difficulty: int = Field(default=2, ge=1, le=3)


def _check_topic(db: Session, room, topic_id: str | None) -> None:
    if topic_id:
        t = db.get(RoomTopic, topic_id)
        if not t or t.room_id != room.id:
            raise ApiError("VALIDATION_ERROR", "Unknown topic.", 422)


@router.post("/rooms/{room_id}/questions")
def add_question(room_id: str, body: QuestionIn, user: User = Depends(acting_user), db: Session = Depends(get_db)):
    room = _creator_room(db, room_id, user)
    _unlocked_bank(db, room)
    qs.validate_question(body.prompt, body.options, body.correct_index)
    _check_topic(db, room, body.topic_id)
    q = Question(room_id=room.id, topic_id=body.topic_id, prompt=body.prompt.strip(), options=[o.strip() for o in body.options], correct_index=body.correct_index,
                 explanation=body.explanation.strip(), difficulty=body.difficulty, status="approved", source="manual", created_by=user.id)
    db.add(q)
    db.commit()
    return ok({"id": q.id})


@router.put("/questions/{question_id}")
def edit_question(question_id: str, body: QuestionIn, user: User = Depends(acting_user), db: Session = Depends(get_db)):
    q = db.get(Question, question_id)
    if not q:
        raise not_found("Question")
    room = _creator_room(db, q.room_id, user)
    _unlocked_bank(db, room)
    qs.validate_question(body.prompt, body.options, body.correct_index)
    _check_topic(db, room, body.topic_id)
    q.topic_id, q.prompt, q.options, q.correct_index = body.topic_id, body.prompt.strip(), [o.strip() for o in body.options], body.correct_index
    q.explanation, q.difficulty = body.explanation.strip(), body.difficulty
    db.commit()
    return ok({"id": q.id})


@router.post("/questions/{question_id}/approve")
def approve_question(question_id: str, user: User = Depends(acting_user), db: Session = Depends(get_db)):
    q = db.get(Question, question_id)
    if not q:
        raise not_found("Question")
    room = _creator_room(db, q.room_id, user)
    _unlocked_bank(db, room)
    q.status = "approved"
    db.commit()
    return ok({"status": q.status})


@router.delete("/questions/{question_id}")
def delete_question(question_id: str, user: User = Depends(acting_user), db: Session = Depends(get_db)):
    q = db.get(Question, question_id)
    if not q:
        raise not_found("Question")
    room = _creator_room(db, q.room_id, user)
    _unlocked_bank(db, room)
    db.delete(q)
    db.commit()
    return ok({"deleted": True})


@router.post("/rooms/{room_id}/questions/import-bank")
def import_bank(room_id: str, user: User = Depends(acting_user), db: Session = Depends(get_db)):
    """Copies starter-bank questions whose topic matches one of the room's topics (by name). Skips ones already imported."""
    room = _creator_room(db, room_id, user)
    _unlocked_bank(db, room)
    seed = json.loads(SEED.read_text(encoding="utf-8"))
    have = {q.prompt for q in db.scalars(select(Question).where(Question.room_id == room.id))}
    added = 0
    for t in svc.topics(db, room.id):
        name = t.title.lower()
        for item in seed:
            if (item["topic"] in name or name in item["topic"]) and item["prompt"] not in have:
                db.add(Question(room_id=room.id, topic_id=t.id, prompt=item["prompt"], options=item["options"], correct_index=item["correct_index"],
                                explanation=item.get("explanation", ""), status="approved", source="bank", created_by=user.id))
                have.add(item["prompt"])
                added += 1
    db.commit()
    return ok({"added": added})


# ---------------- halfway quiz ----------------

@router.get("/rooms/{room_id}/halfway")
def halfway(room_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    room = svc.get_room(db, room_id)
    svc.sync_room(db, room)
    svc.require_participant(db, room, user.id)
    return ok(qs.halfway_status(db, room, user.id))


@router.post("/rooms/{room_id}/halfway/start")
def start_halfway(room_id: str, user: User = Depends(acting_user), db: Session = Depends(get_db)):
    room = svc.get_room(db, room_id)
    return ok(qs.start_halfway(db, room, user.id))


class AnswerIn(BaseModel):
    question_id: str
    option: str = Field(min_length=6, max_length=32)


@router.post("/rooms/{room_id}/halfway/answer")
def answer_halfway(room_id: str, body: AnswerIn, user: User = Depends(acting_user), db: Session = Depends(get_db)):
    limiter.hit("quiz_submit", user.id)
    room = svc.get_room(db, room_id)
    return ok(qs.answer_halfway(db, room, user.id, body.question_id, body.option))


@router.post("/rooms/{room_id}/halfway/finish")
def finish_halfway(room_id: str, user: User = Depends(acting_user), db: Session = Depends(get_db)):
    room = svc.get_room(db, room_id)
    return ok(qs.finish_halfway(db, room, user.id))


# ---------------- Nest Race ----------------

@router.get("/rooms/{room_id}/race")
def get_race(room_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    room = svc.get_room(db, room_id)
    svc.sync_room(db, room)
    if not svc.can_view(db, room, user.id):
        raise not_found("Room")
    race = db.scalar(select(Race).where(Race.room_id == room.id))
    if not race:
        return ok(None)
    return ok(race_service.race_view(db, room, race, user.id))


@router.post("/races/{race_id}/answer")
def race_answer(race_id: str, body: AnswerIn, user: User = Depends(acting_user), db: Session = Depends(get_db)):
    limiter.hit("quiz_submit", user.id)
    race = race_service.get_race(db, race_id)
    room = svc.get_room(db, race.room_id)
    svc.sync_room(db, room)
    db.refresh(race)
    result = race_service.answer(db, room, race, user, body.question_id, body.option)
    svc.sync_room(db, room)  # finalizes immediately if this was the last answer
    return ok(result)


@router.post("/races/{race_id}/withdraw")
def race_withdraw(race_id: str, user: User = Depends(acting_user), db: Session = Depends(get_db)):
    race = race_service.get_race(db, race_id)
    room = svc.get_room(db, race.room_id)
    race_service.withdraw(db, room, race, user)
    svc.sync_room(db, room)
    return ok({"withdrawn": True})
