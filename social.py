from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base, new_id, utcnow


class Follow(Base):
    __tablename__ = "follows"
    __table_args__ = (UniqueConstraint("follower_id", "followee_id"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    follower_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    followee_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class BuddyRequest(Base):
    __tablename__ = "buddy_requests"
    # at most one pending request per direction, enforced by the database
    __table_args__ = (Index("uq_pending_buddy_request", "from_id", "to_id", unique=True, sqlite_where=text("status = 'pending'")),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    from_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    to_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(10), default="pending")  # pending | accepted | rejected | cancelled
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Buddy(Base):
    """A mutual buddy link, stored once with user_a < user_b."""
    __tablename__ = "buddies"
    __table_args__ = (UniqueConstraint("user_a", "user_b"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_a: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    user_b: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Block(Base):
    __tablename__ = "blocks"
    __table_args__ = (UniqueConstraint("blocker_id", "blocked_id"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    blocker_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    blocked_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Nudge(Base):
    __tablename__ = "nudges"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    from_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    to_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    message_key: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class PairModel(Base):
    """Beta-Bernoulli compatibility belief for a pair (user_a < user_b). Starts at the configured prior."""
    __tablename__ = "pair_models"
    __table_args__ = (UniqueConstraint("user_a", "user_b"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_a: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    user_b: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    alpha: Mapped[float] = mapped_column(Float)
    beta: Mapped[float] = mapped_column(Float)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class InteractionEvent(Base):
    """Each piece of evidence updates a pair model at most once: event_key is unique."""
    __tablename__ = "interaction_events"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    event_key: Mapped[str] = mapped_column(String(160), unique=True)
    user_a: Mapped[str] = mapped_column(String(32))
    user_b: Mapped[str] = mapped_column(String(32))
    effect: Mapped[str] = mapped_column(String(8))  # alpha | beta
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class SessionFeedback(Base):
    """Private by default: only the rater sees what they wrote; the ratee sees nothing."""
    __tablename__ = "session_feedback"
    __table_args__ = (UniqueConstraint("rater_id", "ratee_id", "room_id"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    rater_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    ratee_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    room_id: Mapped[str] = mapped_column(ForeignKey("rooms.id", ondelete="CASCADE"))
    tags: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Meeting(Base):
    __tablename__ = "meetings"
    __table_args__ = (UniqueConstraint("creator_id", "idempotency_key", "occurrence_index"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    creator_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(120))
    subject: Mapped[str] = mapped_column(String(80))
    topics: Mapped[list] = mapped_column(JSON, default=list)
    starts_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    duration_minutes: Mapped[int] = mapped_column(Integer)
    max_participants: Mapped[int] = mapped_column(Integer)
    visibility: Mapped[str] = mapped_column(String(10), default="private")
    room_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    series_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    recurrence: Mapped[str] = mapped_column(String(10), default="none")  # none | daily | weekly
    occurrence_index: Mapped[int] = mapped_column(Integer, default=0)
    reminder_minutes: Mapped[list] = mapped_column(JSON, default=lambda: [60, 10])
    status: Mapped[str] = mapped_column(String(10), default="scheduled")  # scheduled | cancelled | completed
    idempotency_key: Mapped[str] = mapped_column(String(64))
    cancel_reason: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class MeetingInvite(Base):
    __tablename__ = "meeting_invites"
    __table_args__ = (UniqueConstraint("meeting_id", "user_id"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    meeting_id: Mapped[str] = mapped_column(ForeignKey("meetings.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    invited_by: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(10), default="pending")  # pending | accepted | declined
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Report(Base):
    __tablename__ = "reports"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    reporter_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    target_type: Mapped[str] = mapped_column(String(12))  # user | message | room | invite | meeting
    target_id: Mapped[str] = mapped_column(String(32))
    target_user_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    room_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    category: Mapped[str] = mapped_column(String(20))  # harassment | spam | cheating | inappropriate | privacy | other
    details: Mapped[str] = mapped_column(Text, default="")
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)  # e.g. the reported message text at report time
    status: Mapped[str] = mapped_column(String(10), default="open")  # open | resolved | dismissed
    resolution: Mapped[str] = mapped_column(Text, default="")  # internal; never shown to the reported user
    reviewer_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Restriction(Base):
    """Created only by a reviewer. Every restriction can be appealed."""
    __tablename__ = "restrictions"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(12))  # suspended | chat_ban | reward_hold
    reason: Mapped[str] = mapped_column(String(300))
    created_by: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    lifted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Appeal(Base):
    __tablename__ = "appeals"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    restriction_id: Mapped[str] = mapped_column(ForeignKey("restrictions.id"))
    text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(10), default="open")  # open | upheld | overturned
    response: Mapped[str] = mapped_column(Text, default="")
    reviewer_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Counter(Base):
    """Small named counters (per-room chat sequence numbers)."""
    __tablename__ = "counters"
    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[int] = mapped_column(Integer, default=0)
