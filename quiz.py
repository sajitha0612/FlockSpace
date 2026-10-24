from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base, new_id, utcnow


class Question(Base):
    """A multiple-choice question in a room's bank. Only 'approved' questions are ever used in a quiz."""
    __tablename__ = "questions"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    room_id: Mapped[str] = mapped_column(ForeignKey("rooms.id", ondelete="CASCADE"), index=True)
    topic_id: Mapped[str | None] = mapped_column(ForeignKey("room_topics.id", ondelete="SET NULL"), nullable=True)
    prompt: Mapped[str] = mapped_column(Text)
    options: Mapped[list] = mapped_column(JSON)
    correct_index: Mapped[int] = mapped_column(Integer)
    explanation: Mapped[str] = mapped_column(Text, default="")
    difficulty: Mapped[int] = mapped_column(Integer, default=2)
    status: Mapped[str] = mapped_column(String(10), default="approved")  # approved | draft
    source: Mapped[str] = mapped_column(String(10), default="manual")  # manual | bank | ai
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class QuizAttempt(Base):
    """The personal halfway quiz. One attempt per student per room; the question set is frozen when it starts."""
    __tablename__ = "quiz_attempts"
    __table_args__ = (UniqueConstraint("room_id", "user_id", "kind"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    room_id: Mapped[str] = mapped_column(ForeignKey("rooms.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(10), default="halfway")
    question_ids: Mapped[list] = mapped_column(JSON)
    seed: Mapped[str] = mapped_column(String(32))
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    deadline: Mapped[datetime] = mapped_column(DateTime)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    score: Mapped[int] = mapped_column(Integer, default=0)
    total: Mapped[int] = mapped_column(Integer, default=0)
    twigs: Mapped[int] = mapped_column(Integer, default=0)


class QuizAnswer(Base):
    __tablename__ = "quiz_answers"
    __table_args__ = (UniqueConstraint("attempt_id", "question_id"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    attempt_id: Mapped[str] = mapped_column(ForeignKey("quiz_attempts.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[str] = mapped_column(String(32))
    chosen_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    correct: Mapped[bool] = mapped_column(Boolean, default=False)
    answered_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Race(Base):
    """The Nest Race. config holds the rules, locked when the race is created and never changed afterwards."""
    __tablename__ = "races"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    room_id: Mapped[str] = mapped_column(ForeignKey("rooms.id", ondelete="CASCADE"), unique=True)
    status: Mapped[str] = mapped_column(String(10), default="countdown")  # countdown | live | finished | void
    starts_at: Mapped[datetime] = mapped_column(DateTime)
    deadline: Mapped[datetime] = mapped_column(DateTime)
    config: Mapped[dict] = mapped_column(JSON)
    question_ids: Mapped[list] = mapped_column(JSON)
    eligible_count: Mapped[int] = mapped_column(Integer, default=0)
    void_reason: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class RaceEntry(Base):
    __tablename__ = "race_entries"
    __table_args__ = (UniqueConstraint("race_id", "user_id"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    race_id: Mapped[str] = mapped_column(ForeignKey("races.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    twigs: Mapped[int] = mapped_column(Integer, default=0)
    correct: Mapped[int] = mapped_column(Integer, default=0)
    answered: Mapped[int] = mapped_column(Integer, default=0)
    nest_completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_answer_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    withdrew_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    placement: Mapped[int | None] = mapped_column(Integer, nullable=True)
    eligible: Mapped[bool] = mapped_column(Boolean, default=False)


class RaceAnswer(Base):
    __tablename__ = "race_answers"
    __table_args__ = (UniqueConstraint("entry_id", "question_id"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    entry_id: Mapped[str] = mapped_column(ForeignKey("race_entries.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[str] = mapped_column(String(32))
    chosen_index: Mapped[int] = mapped_column(Integer)
    correct: Mapped[bool] = mapped_column(Boolean)
    answered_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class TwigLedger(Base):
    """Every twig ever earned or spent. dedupe_key makes each reward claimable exactly once."""
    __tablename__ = "twig_ledger"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    amount: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(20))  # halfway_correct | race_correct | placement_bonus | purchase
    ref: Mapped[str] = mapped_column(String(64), default="")
    note: Mapped[str] = mapped_column(String(160), default="")
    dedupe_key: Mapped[str] = mapped_column(String(160), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class GoldenNest(Base):
    __tablename__ = "golden_nests"
    __table_args__ = (UniqueConstraint("user_id", "race_id"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    race_id: Mapped[str] = mapped_column(ForeignKey("races.id"))
    room_id: Mapped[str] = mapped_column(String(32))
    placement: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(10), default="awarded")  # awarded | withheld (pending review)
    awarded_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class UserItem(Base):
    __tablename__ = "user_items"
    __table_args__ = (UniqueConstraint("user_id", "item_id"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    item_id: Mapped[str] = mapped_column(String(40))
    source: Mapped[str] = mapped_column(String(40), default="")
    unlocked_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class RiskFlag(Base):
    """A pattern worth a human look. Never a verdict, never acted on automatically."""
    __tablename__ = "risk_flags"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(32))
    subject_user_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(10), default="open")  # open | dismissed | actioned
    dedupe_key: Mapped[str] = mapped_column(String(160), unique=True)
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    reviewed_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
