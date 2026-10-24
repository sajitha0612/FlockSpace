"""
Shared room workspace: chat, resources, AI notes, shared tasks, and the AI study agent.

Chat rules
- Only active participants can read or post. Messages are 1-2000 characters, rendered as plain text by the
  client (no HTML is ever interpreted); only http(s) links are allowed, other URL schemes are rejected.
- Rate limits: 8 messages per 10 s and 40 per minute; the same text can't be re-sent within 60 s.
- Chat is paused while the Nest Race is running, so answers can't be shared in the room.
- Authors can edit within 15 minutes and delete any time. The room creator can hide messages; muted
  participants can read but not post. Messages from people you blocked are filtered out on the server.

Task permissions
- Any participant can add a task; the creator's tasks are active immediately, others' start as proposed.
- AI-generated tasks always start as proposed. The room creator adopts (makes active), edits or archives tasks;
  authors can edit or delete their own proposed tasks.
- Completion is personal: ticking a task records it for you only.
- Connecting a task to the topic checklist changes the syllabus and the final quiz scope, so only the room
  creator can do it, with explicit confirmation, before the study phase ends.
"""
import re
from datetime import timedelta

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core.db import get_db, iso, new_id, utcnow
from ..core.errors import ApiError, forbidden, not_found, ok
from ..core.ratelimit import limiter
from ..core.security import acting_user, active_restriction, current_user
from ..models import AgentMessage, AIJob, Block, ChatMessage, ModerationAction, Note, Profile, Resource, Room, RoomTopic, Task, TaskProgress, User
from ..services import ai_jobs, documents
from ..services import rooms as svc
from ..services.realtime import publish_after_commit
from ..services.relations import users_i_blocked

router = APIRouter(tags=["workspace"])
UNSAFE_URL = re.compile(r"\b(?:javascript|data|vbscript|file):", re.I)
URL = re.compile(r"^https?://[^\s<>\"']{3,490}$", re.I)


def _room_for_participant(db: Session, room_id: str, user: User) -> Room:
    room = svc.get_room(db, room_id)
    svc.require_participant(db, room, user.id)
    return room


# ---------------- chat ----------------

def message_view(m: ChatMessage, users: dict[str, User], birds: dict[str, dict]) -> dict:
    u = users.get(m.user_id) if m.user_id else None
    removed = m.deleted_at or m.hidden_at
    return {"id": m.id, "seq": m.seq, "kind": m.kind, "body": None if removed else m.body, "resource_id": m.resource_id,
            "user": {"id": u.id, "name": u.name, "bird": birds.get(u.id, {})} if u else None,
            "created_at": iso(m.created_at), "edited": m.edited_at is not None, "deleted": m.deleted_at is not None, "hidden": m.hidden_at is not None}


def _views(db: Session, msgs: list[ChatMessage]) -> list[dict]:
    ids = {m.user_id for m in msgs if m.user_id}
    users = {u.id: u for u in db.scalars(select(User).where(User.id.in_(ids)))} if ids else {}
    birds = {p.user_id: p.bird for p in db.scalars(select(Profile).where(Profile.user_id.in_(ids)))} if ids else {}
    return [message_view(m, users, birds) for m in msgs]


@router.get("/rooms/{room_id}/messages")
def messages(room_id: str, before_seq: int | None = None, limit: int = Query(50, ge=1, le=200), user: User = Depends(current_user), db: Session = Depends(get_db)):
    _room_for_participant(db, room_id, user)
    q = select(ChatMessage).where(ChatMessage.room_id == room_id)
    hidden = users_i_blocked(db, user.id)
    if hidden:
        q = q.where((ChatMessage.user_id.is_(None)) | (ChatMessage.user_id.notin_(hidden)))
    if before_seq:
        q = q.where(ChatMessage.seq < before_seq)
    msgs = list(reversed(db.scalars(q.order_by(ChatMessage.seq.desc()).limit(limit)).all()))
    return ok({"messages": _views(db, msgs), "has_more": len(msgs) == limit})


class MessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


def _clean_body(text: str) -> str:
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text).strip()
    if not text:
        raise ApiError("VALIDATION_ERROR", "Message is empty.", 422)
    if UNSAFE_URL.search(text):
        raise ApiError("UNSAFE_LINK", "Only http(s) links are allowed in chat.", 422)
    return text


@router.post("/rooms/{room_id}/messages")
def send_message(room_id: str, body: MessageIn, user: User = Depends(acting_user), db: Session = Depends(get_db)):
    room = _room_for_participant(db, room_id, user)
    p = svc.participant(db, room.id, user.id)
    if p.muted_until and p.muted_until > utcnow():
        raise ApiError("MUTED", "You're muted in this room for now.", 403, {"until": iso(p.muted_until)})
    if active_restriction(db, user.id, "chat_ban"):
        raise ApiError("CHAT_RESTRICTED", "Your chat access is restricted pending review. You can appeal from Settings.", 403)
    svc.sync_room(db, room)
    if room.status == "race":
        raise ApiError("CHAT_PAUSED", "Chat is paused during the Nest Race so everyone races fairly.", 409)
    if room.status == "cancelled":
        raise ApiError("ROOM_CLOSED", "This room was cancelled.", 409)
    limiter.hit("chat", user.id)
    limiter.hit("chat_minute", user.id)
    text = _clean_body(body.body)
    recent = db.scalar(select(ChatMessage.id).where(ChatMessage.room_id == room.id, ChatMessage.user_id == user.id, ChatMessage.body == text,
                                                     ChatMessage.created_at >= utcnow() - timedelta(seconds=60)))
    if recent:
        raise ApiError("DUPLICATE_MESSAGE", "You just sent that.", 409)
    m = ChatMessage(room_id=room.id, user_id=user.id, body=text, seq=svc.next_seq(db, room.id))
    db.add(m)
    db.flush()
    view = _views(db, [m])[0]
    blockers = list(db.scalars(select(Block.blocker_id).where(Block.blocked_id == user.id)))
    publish_after_commit(db, "room", room.id, "chat_message", {**view, "_exclude": blockers})
    db.commit()
    return ok(view)


@router.patch("/messages/{message_id}")
def edit_message(message_id: str, body: MessageIn, user: User = Depends(acting_user), db: Session = Depends(get_db)):
    m = db.get(ChatMessage, message_id)
    if not m or m.user_id != user.id:
        raise not_found("Message")
    if m.deleted_at or m.hidden_at:
        raise ApiError("MESSAGE_REMOVED", "This message was removed.", 409)
    if utcnow() - m.created_at > timedelta(minutes=15):
        raise ApiError("EDIT_WINDOW", "Messages can be edited for 15 minutes.", 409)
    m.body, m.edited_at = _clean_body(body.body), utcnow()
    publish_after_commit(db, "room", m.room_id, "chat_updated", _views(db, [m])[0])
    db.commit()
    return ok(_views(db, [m])[0])


@router.delete("/messages/{message_id}")
def delete_message(message_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    m = db.get(ChatMessage, message_id)
    if not m or m.user_id != user.id:
        raise not_found("Message")
    m.deleted_at = m.deleted_at or utcnow()
    publish_after_commit(db, "room", m.room_id, "chat_updated", _views(db, [m])[0])
    db.commit()
    return ok({"deleted": True})


class HideIn(BaseModel):
    reason: str = Field(default="", max_length=300)


@router.post("/messages/{message_id}/hide")
def hide_message(message_id: str, body: HideIn, user: User = Depends(acting_user), db: Session = Depends(get_db)):
    m = db.get(ChatMessage, message_id)
    if not m:
        raise not_found("Message")
    room = svc.get_room(db, m.room_id)
    svc.require_creator(room, user.id)
    m.hidden_at, m.hidden_by = utcnow(), user.id
    db.add(ModerationAction(room_id=room.id, actor_id=user.id, target_user_id=m.user_id, message_id=m.id, action="hide_message", reason=body.reason))
    publish_after_commit(db, "room", room.id, "chat_updated", _views(db, [m])[0])
    db.commit()
    return ok({"hidden": True})


# ---------------- resources ----------------

def resource_view(r: Resource, names: dict[str, str]) -> dict:
    return {"id": r.id, "kind": r.kind, "title": r.title, "url": r.url, "body": r.body if r.kind == "note" else None, "filename": r.filename, "ext": r.ext,
            "size": r.size, "status": r.status, "error": r.error, "image_only": r.image_only, "truncated": r.truncated, "chars": len(r.text or ""),
            "uploader": {"id": r.uploader_id, "name": names.get(r.uploader_id)}, "created_at": iso(r.created_at)}


def _names(db: Session, ids) -> dict[str, str]:
    ids = set(ids)
    return {u.id: u.name for u in db.scalars(select(User).where(User.id.in_(ids)))} if ids else {}


@router.get("/rooms/{room_id}/resources")
def resources(room_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _room_for_participant(db, room_id, user)
    rs = list(db.scalars(select(Resource).where(Resource.room_id == room_id, Resource.deleted_at.is_(None)).order_by(Resource.created_at.desc())))
    names = _names(db, [r.uploader_id for r in rs])
    return ok([resource_view(r, names) for r in rs])


def _announce(db: Session, room: Room, user: User, r: Resource) -> None:
    m = ChatMessage(room_id=room.id, user_id=user.id, kind="resource", body=f"shared {r.title}", resource_id=r.id, seq=svc.next_seq(db, room.id))
    db.add(m)
    db.flush()
    publish_after_commit(db, "room", room.id, "chat_message", _views(db, [m])[0])
    publish_after_commit(db, "room", room.id, "resource_updated", {"id": r.id, "status": r.status})


@router.post("/rooms/{room_id}/resources/file")
async def upload(room_id: str, file: UploadFile = File(...), title: str = Form(""), user: User = Depends(acting_user), db: Session = Depends(get_db)):
    room = _room_for_participant(db, room_id, user)
    limiter.hit("upload", user.id)
    from ..core.config import get_settings

    limit = get_settings().max_upload_size_mb * 1024 * 1024
    data = await file.read(limit + 1)
    name = documents.safe_name(file.filename or "file")
    ext = documents.validate(name, data)
    r = Resource(room_id=room.id, uploader_id=user.id, kind="file", title=(title.strip() or name)[:200], filename=name, ext=ext, mime=documents.ALLOWED[ext],
                 size=len(data), sha256=documents.sha256(data), stored_name=f"{new_id()}{ext}", status="uploaded")
    documents.store(room.id, r.stored_name, data)
    db.add(r)
    db.flush()
    _announce(db, room, user, r)
    db.commit()
    ai_jobs.enqueue(db, room, user, "extract", {"resource_id": r.id}, f"extract:{r.id}")
    return ok(resource_view(r, {user.id: user.name}))


class LinkIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    url: str = Field(max_length=500)


@router.post("/rooms/{room_id}/resources/link")
def add_link(room_id: str, body: LinkIn, user: User = Depends(acting_user), db: Session = Depends(get_db)):
    room = _room_for_participant(db, room_id, user)
    limiter.hit("upload", user.id)
    url = body.url.strip()
    if not URL.match(url):
        raise ApiError("VALIDATION_ERROR", "Links must start with http:// or https://.", 422)
    r = Resource(room_id=room.id, uploader_id=user.id, kind="link", title=body.title.strip(), url=url, status="ready")
    db.add(r)
    db.flush()
    _announce(db, room, user, r)
    db.commit()
    return ok(resource_view(r, {user.id: user.name}))


class TextNoteIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=50000)


@router.post("/rooms/{room_id}/resources/note")
def add_text_note(room_id: str, body: TextNoteIn, user: User = Depends(acting_user), db: Session = Depends(get_db)):
    room = _room_for_participant(db, room_id, user)
    limiter.hit("upload", user.id)
    r = Resource(room_id=room.id, uploader_id=user.id, kind="note", title=body.title.strip(), body=body.body, text=body.body, status="ready")
    db.add(r)
    db.flush()
    _announce(db, room, user, r)
    db.commit()
    return ok(resource_view(r, {user.id: user.name}))


def _resource_for(db: Session, resource_id: str, user: User) -> Resource:
    r = db.get(Resource, resource_id)
    if not r or r.deleted_at:
        raise not_found("Resource")
    _room_for_participant(db, r.room_id, user)
    return r


@router.get("/resources/{resource_id}/download")
def download(resource_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    r = _resource_for(db, resource_id, user)
    if r.kind != "file":
        raise not_found("File")
    path = documents.path_of(r.room_id, r.stored_name)
    if not path.exists():
        raise not_found("File")
    return FileResponse(path, media_type=documents.ALLOWED.get(r.ext, "application/octet-stream"), filename=r.filename,
                        headers={"X-Content-Type-Options": "nosniff", "Content-Security-Policy": "default-src 'none'; sandbox", "Cache-Control": "private, no-store"})


@router.get("/resources/{resource_id}/text")
def resource_text(resource_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    r = _resource_for(db, resource_id, user)
    return ok({"title": r.title, "status": r.status, "error": r.error, "text": (r.text or "")[:20000], "truncated_preview": len(r.text or "") > 20000})


@router.delete("/resources/{resource_id}")
def delete_resource(resource_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    r = _resource_for(db, resource_id, user)
    room = svc.get_room(db, r.room_id)
    if r.uploader_id != user.id and room.creator_id != user.id:
        raise forbidden()
    r.deleted_at = utcnow()
    if r.kind == "file":
        try:
            documents.path_of(r.room_id, r.stored_name).unlink(missing_ok=True)
        except OSError:
            pass
    publish_after_commit(db, "room", room.id, "resource_updated", {"id": r.id, "deleted": True})
    db.commit()
    return ok({"deleted": True})


# ---------------- AI jobs ----------------

class AIRequest(BaseModel):
    idempotency_key: str = Field(min_length=8, max_length=64)
    detail: str = Field(default="standard", pattern="^(brief|standard|detailed)$")
    regenerate_group: str | None = None
    # chat notes
    mode: str | None = Field(default=None, pattern="^(recent|all|range)$")
    purpose: str | None = Field(default=None, pattern="^(notes|key_points|revision|questions)$")
    from_seq: int | None = None
    to_seq: int | None = None
    from_time: str | None = None
    to_time: str | None = None
    # documents
    resource_id: str | None = None
    resource_ids: list[str] | None = Field(default=None, max_length=8)
    # material
    subject: str | None = Field(default=None, max_length=80)
    topic: str | None = Field(default=None, max_length=120)
    level: str | None = Field(default=None, max_length=60)
    objectives: str | None = Field(default=None, max_length=1000)
    depth: str | None = Field(default=None, pattern="^(brief|standard|detailed)$")
    subtopics: list[str] | None = Field(default=None, max_length=12)
    # tasks
    note_id: str | None = None
    objective: str | None = Field(default=None, max_length=1000)
    # questions
    topics: list[str] | None = None
    count: int | None = Field(default=None, ge=1, le=20)


KIND_FIELDS = {
    "chat_notes": ("mode", "purpose", "from_seq", "to_seq", "from_time", "to_time", "detail", "regenerate_group"),
    "doc_notes": ("resource_id", "detail", "regenerate_group"),
    "consolidated": ("resource_ids", "detail", "regenerate_group"),
    "material": ("subject", "topic", "level", "objectives", "depth", "subtopics", "detail", "regenerate_group"),
    "tasks": ("note_id", "objective", "resource_ids"),
    "questions": ("topics", "count"),
}


@router.post("/rooms/{room_id}/ai/{kind}")
def request_ai(room_id: str, kind: str, body: AIRequest, user: User = Depends(acting_user), db: Session = Depends(get_db)):
    if kind not in KIND_FIELDS:
        raise not_found("AI action")
    room = _room_for_participant(db, room_id, user)
    params = {k: getattr(body, k) for k in KIND_FIELDS[kind] if getattr(body, k) is not None}
    if kind == "doc_notes" and not body.resource_id:
        raise ApiError("VALIDATION_ERROR", "Pick a document.", 422)
    if kind == "consolidated" and len(body.resource_ids or []) < 2:
        raise ApiError("VALIDATION_ERROR", "Pick at least two documents to consolidate.", 422)
    if kind == "material" and not (body.subject and body.topic):
        raise ApiError("VALIDATION_ERROR", "Give a subject and a topic.", 422)
    if kind == "tasks" and not (body.note_id or body.objective or body.resource_ids):
        raise ApiError("VALIDATION_ERROR", "Choose notes, documents or write a learning objective.", 422)
    if kind == "chat_notes":
        params.setdefault("mode", "recent")
    job = ai_jobs.enqueue(db, room, user, kind, params, body.idempotency_key)
    return ok(ai_jobs.job_view(job, user.name))


@router.get("/rooms/{room_id}/ai/jobs")
def ai_jobs_list(room_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _room_for_participant(db, room_id, user)
    rows = db.execute(select(AIJob, User.name).join(User, User.id == AIJob.user_id).where(AIJob.room_id == room_id, AIJob.kind != "extract").order_by(AIJob.created_at.desc()).limit(30)).all()
    return ok([ai_jobs.job_view(j, n) for j, n in rows])


@router.post("/ai/jobs/{job_id}/retry")
def retry_job(job_id: str, user: User = Depends(acting_user), db: Session = Depends(get_db)):
    job = db.get(AIJob, job_id)
    if not job or job.user_id != user.id:
        raise not_found("AI request")
    if job.status != "failed":
        raise ApiError("NOT_FAILED", "Only failed requests can be retried.", 409)
    _room_for_participant(db, job.room_id, user)
    if job.counts_quota:
        limiter.hit("ai", user.id)
    if job.kind == "extract":
        r = db.get(Resource, job.params.get("resource_id"))
        if r:
            r.status, r.error = "uploaded", ""
    job.status, job.error, job.finished_at = "queued", "", None
    db.commit()
    ai_jobs.worker.wake()
    return ok(ai_jobs.job_view(job, user.name))


# ---------------- notes ----------------

def note_view(n: Note, names: dict[str, str], versions: int = 1) -> dict:
    return {"id": n.id, "group_id": n.group_id, "version": n.version, "versions": versions, "kind": n.kind, "title": n.title, "content": n.content,
            "ai_generated": n.ai_generated, "sources": n.sources, "detail_level": n.detail_level, "status": n.status,
            "created_by": {"id": n.created_by, "name": names.get(n.created_by)}, "created_at": iso(n.created_at),
            "edited_by": names.get(n.edited_by) if n.edited_by else None, "edited_at": iso(n.edited_at)}


@router.get("/rooms/{room_id}/notes")
def notes(room_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _room_for_participant(db, room_id, user)
    all_notes = list(db.scalars(select(Note).where(Note.room_id == room_id).order_by(Note.created_at.desc())))
    latest, counts = {}, {}
    for n in all_notes:
        counts[n.group_id] = counts.get(n.group_id, 0) + 1
        if n.group_id not in latest or n.version > latest[n.group_id].version:
            latest[n.group_id] = n
    names = _names(db, [n.created_by for n in latest.values()] + [n.edited_by for n in latest.values() if n.edited_by])
    return ok([note_view(n, names, counts[n.group_id]) for n in sorted(latest.values(), key=lambda n: n.created_at, reverse=True)])


def _note_for(db: Session, note_id: str, user: User) -> tuple[Note, Room]:
    n = db.get(Note, note_id)
    if not n:
        raise not_found("Note")
    return n, _room_for_participant(db, n.room_id, user)


@router.get("/notes/{note_id}")
def get_note(note_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    n, _ = _note_for(db, note_id, user)
    versions = list(db.scalars(select(Note).where(Note.group_id == n.group_id).order_by(Note.version)))
    names = _names(db, [v.created_by for v in versions] + [v.edited_by for v in versions if v.edited_by])
    return ok({**note_view(n, names, len(versions)), "history": [{"id": v.id, "version": v.version, "detail_level": v.detail_level, "created_at": iso(v.created_at), "status": v.status} for v in versions]})


class NoteEditIn(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    content: dict | None = None


@router.patch("/notes/{note_id}")
def edit_note(note_id: str, body: NoteEditIn, user: User = Depends(acting_user), db: Session = Depends(get_db)):
    n, room = _note_for(db, note_id, user)
    if user.id not in (n.created_by, room.creator_id):
        raise forbidden("Only the note's author or the room creator can edit it.")
    if body.content is not None:
        if len(str(body.content)) > 200000:
            raise ApiError("VALIDATION_ERROR", "Note is too long.", 422)
        n.content = body.content
    if body.title is not None:
        n.title = body.title.strip()
    n.edited_by, n.edited_at = user.id, utcnow()
    publish_after_commit(db, "room", room.id, "notes_changed", {"note_id": n.id})
    db.commit()
    return ok(note_view(n, _names(db, [n.created_by, user.id])))


@router.post("/notes/{note_id}/share")
def share_note(note_id: str, user: User = Depends(acting_user), db: Session = Depends(get_db)):
    """The explicit confirmation step: AI drafts become shared room notes only when a person chooses so."""
    n, room = _note_for(db, note_id, user)
    if user.id not in (n.created_by, room.creator_id):
        raise forbidden("Only the person who requested these notes or the room creator can share them.")
    n.status = "shared"
    publish_after_commit(db, "room", room.id, "notes_changed", {"note_id": n.id})
    db.commit()
    return ok({"status": n.status})


class ManualNoteIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=20000)
    kind: str = Field(default="findings", pattern="^(findings|manual)$")


@router.post("/rooms/{room_id}/notes")
def add_note(room_id: str, body: ManualNoteIn, user: User = Depends(acting_user), db: Session = Depends(get_db)):
    room = _room_for_participant(db, room_id, user)
    n = Note(room_id=room.id, group_id=new_id(), kind=body.kind, title=body.title.strip(), content={"text": body.text}, ai_generated=False, status="shared",
             sources={"type": "manual"}, created_by=user.id)
    db.add(n)
    publish_after_commit(db, "room", room.id, "notes_changed", {})
    db.commit()
    return ok(note_view(n, {user.id: user.name}))


@router.delete("/notes/{note_id}")
def delete_note(note_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    n, room = _note_for(db, note_id, user)
    if user.id not in (n.created_by, room.creator_id):
        raise forbidden()
    db.delete(n)
    publish_after_commit(db, "room", room.id, "notes_changed", {})
    db.commit()
    return ok({"deleted": True})


def note_markdown(n: Note) -> str:
    c, out = n.content or {}, [f"# {n.title}", ""]
    if n.ai_generated:
        out += ["> AI-generated study notes: a study aid, not verified content. Check important facts against your sources.", ""]
    if c.get("text"):
        out += [c["text"], ""]
    for key, label in (("summary", "Summary"), ("overview", "Overview")):
        if c.get(key):
            out += [f"## {label}", c[key], ""]
    for s in c.get("sections", []):
        out.append(f"## {s.get('heading', '')}")
        out += [f"- {p}" for p in s.get("points", [])]
        if s.get("sources"):
            out.append(f"*Sources: {', '.join(s['sources'])}*")
        out.append("")
    for key, label in (("key_points", "Key points"), ("examples", "Examples"), ("questions_raised", "Questions raised"), ("conclusions", "Conclusions"),
                       ("unresolved", "Unresolved questions"), ("misconceptions", "Possible misconceptions to check"), ("revision_points", "Revision points"),
                       ("practice_questions", "Practice questions"), ("verify_with_sources", "Verify with a trusted source")):
        if c.get(key):
            out += [f"## {label}"] + [f"- {x}" for x in c[key]] + [""]
    for key, label in (("definitions", "Definitions"), ("key_concepts", "Key concepts"), ("glossary", "Glossary")):
        if c.get(key):
            out += [f"## {label}"] + [f"- **{d.get('term')}**: {d.get('definition')}" for d in c[key]] + [""]
    if c.get("disagreements"):
        out.append("## Where sources disagree")
        for d in c["disagreements"]:
            out += [f"- **{d.get('topic')}**"] + [f"  - {p}" for p in d.get("positions", [])]
        out.append("")
    if c.get("revision_summary"):
        out += ["## Revision summary", c["revision_summary"], ""]
    src = n.sources or {}
    if src.get("type") == "documents":
        out += ["---", "Sources: " + "; ".join(d["title"] for d in src.get("documents", []))]
    elif src.get("type") == "chat":
        out += ["---", f"Source: room chat messages #{src.get('first_seq')}–#{src.get('last_seq')} ({src.get('message_count')} messages)"]
    return "\n".join(out)


@router.get("/notes/{note_id}/export")
def export_note(note_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    n, _ = _note_for(db, note_id, user)
    safe = re.sub(r"[^A-Za-z0-9 _-]", "", n.title)[:60] or "notes"
    return PlainTextResponse(note_markdown(n), media_type="text/markdown; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{safe}.md"'})


# ---------------- tasks ----------------

def task_view(t: Task, mine: set[str], counts: dict[str, int], names: dict[str, str]) -> dict:
    return {"id": t.id, "title": t.title, "description": t.description, "topic": t.topic, "priority": t.priority, "position": t.position,
            "est_minutes": t.est_minutes, "source": t.source, "note_id": t.note_id, "status": t.status, "created_by": {"id": t.created_by, "name": names.get(t.created_by)},
            "assignee": {"id": t.assignee_id, "name": names.get(t.assignee_id)} if t.assignee_id else None, "created_at": iso(t.created_at),
            "done_by_me": t.id in mine, "done_count": counts.get(t.id, 0)}


@router.get("/rooms/{room_id}/tasks")
def tasks(room_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    room = _room_for_participant(db, room_id, user)
    ts = list(db.scalars(select(Task).where(Task.room_id == room_id, Task.status != "archived").order_by(Task.priority, Task.position)))
    ids = [t.id for t in ts]
    mine = set(db.scalars(select(TaskProgress.task_id).where(TaskProgress.user_id == user.id, TaskProgress.task_id.in_(ids or [""]))))
    counts = dict(db.execute(select(TaskProgress.task_id, func.count()).where(TaskProgress.task_id.in_(ids or [""])).group_by(TaskProgress.task_id)).all())
    names = _names(db, [t.created_by for t in ts] + [t.assignee_id for t in ts if t.assignee_id])
    return ok({"tasks": [task_view(t, mine, counts, names) for t in ts], "participants": room.participant_count, "is_creator": room.creator_id == user.id})


class TaskIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    topic: str = Field(default="", max_length=100)
    priority: int = Field(default=2, ge=1, le=3)
    est_minutes: int | None = Field(default=None, ge=1, le=600)


@router.post("/rooms/{room_id}/tasks")
def add_task(room_id: str, body: TaskIn, user: User = Depends(acting_user), db: Session = Depends(get_db)):
    room = _room_for_participant(db, room_id, user)
    pos = (db.scalar(select(func.max(Task.position)).where(Task.room_id == room.id)) or 0) + 1
    t = Task(room_id=room.id, title=body.title.strip(), description=body.description.strip(), topic=body.topic.strip(), priority=body.priority,
             est_minutes=body.est_minutes, position=pos, source="manual", status="active" if room.creator_id == user.id else "proposed", created_by=user.id)
    db.add(t)
    publish_after_commit(db, "room", room.id, "tasks_changed", {})
    db.commit()
    return ok(task_view(t, set(), {}, {user.id: user.name}))


def _task_for(db: Session, task_id: str, user: User) -> tuple[Task, Room]:
    t = db.get(Task, task_id)
    if not t:
        raise not_found("Task")
    return t, _room_for_participant(db, t.room_id, user)


class TaskEditIn(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    topic: str | None = Field(default=None, max_length=100)
    priority: int | None = Field(default=None, ge=1, le=3)
    est_minutes: int | None = Field(default=None, ge=1, le=600)
    position: int | None = None
    status: str | None = Field(default=None, pattern="^(active|archived)$")


@router.patch("/tasks/{task_id}")
def edit_task(task_id: str, body: TaskEditIn, user: User = Depends(acting_user), db: Session = Depends(get_db)):
    t, room = _task_for(db, task_id, user)
    own_proposal = t.created_by == user.id and t.status == "proposed"
    if room.creator_id != user.id and not own_proposal:
        raise forbidden("Only the room creator can change the shared task list.")
    if body.status and room.creator_id != user.id:
        raise forbidden("Only the room creator can adopt or archive tasks.")
    for k in ("title", "description", "topic", "priority", "est_minutes", "position", "status"):
        v = getattr(body, k)
        if v is not None:
            setattr(t, k, v.strip() if isinstance(v, str) and k not in ("status",) else v)
    publish_after_commit(db, "room", room.id, "tasks_changed", {})
    db.commit()
    return ok({"id": t.id, "status": t.status})


class AdoptIn(BaseModel):
    task_ids: list[str] = Field(min_length=1, max_length=50)


@router.post("/rooms/{room_id}/tasks/adopt")
def adopt(room_id: str, body: AdoptIn, user: User = Depends(acting_user), db: Session = Depends(get_db)):
    room = _room_for_participant(db, room_id, user)
    svc.require_creator(room, user.id)
    n = 0
    for t in db.scalars(select(Task).where(Task.id.in_(body.task_ids), Task.room_id == room.id, Task.status == "proposed")):
        t.status, n = "active", n + 1
    publish_after_commit(db, "room", room.id, "tasks_changed", {})
    db.commit()
    return ok({"adopted": n})


@router.delete("/tasks/{task_id}")
def delete_task(task_id: str, user: User = Depends(acting_user), db: Session = Depends(get_db)):
    t, room = _task_for(db, task_id, user)
    if room.creator_id != user.id and not (t.created_by == user.id and t.status == "proposed"):
        raise forbidden()
    db.delete(t)
    publish_after_commit(db, "room", room.id, "tasks_changed", {})
    db.commit()
    return ok({"deleted": True})


class DoneIn(BaseModel):
    done: bool


@router.put("/tasks/{task_id}/progress")
def task_progress(task_id: str, body: DoneIn, user: User = Depends(acting_user), db: Session = Depends(get_db)):
    t, room = _task_for(db, task_id, user)
    if t.status != "active":
        raise ApiError("TASK_NOT_ACTIVE", "Only adopted tasks can be ticked off.", 409)
    row = db.scalar(select(TaskProgress).where(TaskProgress.task_id == t.id, TaskProgress.user_id == user.id))
    if body.done and not row:
        db.add(TaskProgress(task_id=t.id, user_id=user.id))
    elif not body.done and row:
        db.delete(row)
    publish_after_commit(db, "room", room.id, "tasks_changed", {})
    db.commit()
    return ok({"done": body.done})


@router.post("/tasks/{task_id}/claim")
def claim(task_id: str, user: User = Depends(acting_user), db: Session = Depends(get_db)):
    """For research mode: a participant takes a subtopic. Claiming again releases it."""
    t, room = _task_for(db, task_id, user)
    if t.assignee_id and t.assignee_id != user.id:
        raise ApiError("TAKEN", "Someone else is already on this one.", 409)
    t.assignee_id = None if t.assignee_id == user.id else user.id
    publish_after_commit(db, "room", room.id, "tasks_changed", {})
    db.commit()
    return ok({"assignee": t.assignee_id})


class LinkTopicIn(BaseModel):
    confirm_syllabus_change: bool = False


@router.post("/tasks/{task_id}/link-topic")
def link_topic(task_id: str, body: LinkTopicIn, user: User = Depends(acting_user), db: Session = Depends(get_db)):
    t, room = _task_for(db, task_id, user)
    svc.require_creator(room, user.id)
    svc.sync_room(db, room)
    if room.status not in ("scheduled", "studying"):
        raise ApiError("SYLLABUS_LOCKED", "The syllabus is locked once the study phase ends.", 409)
    if not body.confirm_syllabus_change:
        raise ApiError("CONFIRM_REQUIRED", "Adding this to the topic checklist changes everyone's progress and the final quiz scope. Confirm to continue.", 409)
    title = (t.topic or t.title).strip()[:100]
    existing = svc.topics(db, room.id)
    if any(x.title.lower() == title.lower() for x in existing):
        return ok({"added": False, "topic": title})
    from ..core.config import get_settings

    if len(existing) >= get_settings().room_max_topics:
        raise ApiError("TOO_MANY_TOPICS", "The checklist is full.", 409)
    db.add(RoomTopic(room_id=room.id, position=len(existing), title=title))
    svc.system_message(db, room.id, f"The room creator added '{title}' to the topic checklist.")
    publish_after_commit(db, "room", room.id, "room_updated", {})
    db.commit()
    return ok({"added": True, "topic": title})


# ---------------- AI study agent ----------------

def agent_view(m: AgentMessage, names: dict[str, str]) -> dict:
    return {"id": m.id, "role": m.role, "mode": m.mode, "text": m.text, "content": m.content, "context": m.context, "user": {"id": m.user_id, "name": names.get(m.user_id)},
            "created_at": iso(m.created_at), "job_id": m.job_id}


@router.get("/rooms/{room_id}/agent")
def agent_thread(room_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _room_for_participant(db, room_id, user)
    msgs = list(reversed(db.scalars(select(AgentMessage).where(AgentMessage.room_id == room_id).order_by(AgentMessage.created_at.desc()).limit(60)).all()))
    names = _names(db, [m.user_id for m in msgs])
    pending = db.scalar(select(func.count(AIJob.id)).where(AIJob.room_id == room_id, AIJob.kind == "agent", AIJob.status.in_(ai_jobs.ACTIVE))) or 0
    return ok({"messages": [agent_view(m, names) for m in msgs], "pending": pending})


class AgentIn(BaseModel):
    question: str = Field(min_length=2)
    mode: str = Field(default="explain", pattern="^(explain|breakdown|compare|solve|gaps|plan|revision|research|summarize)$")
    context: str = Field(default="question", pattern="^(question|documents|room)$")
    resource_ids: list[str] = Field(default_factory=list, max_length=5)
    level: str = Field(default="", max_length=60)
    idempotency_key: str = Field(min_length=8, max_length=64)


@router.post("/rooms/{room_id}/agent")
def ask_agent(room_id: str, body: AgentIn, user: User = Depends(acting_user), db: Session = Depends(get_db)):
    from ..core.config import get_settings

    room = _room_for_participant(db, room_id, user)
    if len(body.question) > get_settings().ai_max_question_chars:
        raise ApiError("VALIDATION_ERROR", f"Questions can be at most {get_settings().ai_max_question_chars} characters.", 422)
    if body.context == "documents" and not body.resource_ids:
        raise ApiError("VALIDATION_ERROR", "Select the documents to use.", 422)
    params = {"question": body.question.strip(), "mode": body.mode, "context": body.context, "resource_ids": body.resource_ids, "level": body.level}
    job = ai_jobs.enqueue(db, room, user, "agent", params, body.idempotency_key)
    if not db.scalar(select(AgentMessage.id).where(AgentMessage.job_id == job.id, AgentMessage.role == "user")):
        db.add(AgentMessage(room_id=room.id, user_id=user.id, role="user", mode=body.mode, text=body.question.strip(), context={"mode": body.context}, job_id=job.id))
        publish_after_commit(db, "room", room.id, "agent_message", {})
        db.commit()
    return ok(ai_jobs.job_view(job, user.name))


@router.post("/agent/{message_id}/to-notes")
def agent_to_notes(message_id: str, user: User = Depends(acting_user), db: Session = Depends(get_db)):
    m = db.get(AgentMessage, message_id)
    if not m or m.role != "assistant":
        raise not_found("Answer")
    room = _room_for_participant(db, m.room_id, user)
    c = m.content or {}
    n = Note(room_id=room.id, group_id=new_id(), kind="agent", title=f"Study agent: {m.mode}", ai_generated=True, status="shared", created_by=user.id,
             content={"text": c.get("answer", m.text), "key_points": [r.get("text") for r in c.get("from_material", []) if r.get("text")],
                      "unresolved": [c["uncertainty"]] if c.get("uncertainty") else [], "practice_questions": c.get("follow_up_questions", [])},
             sources={"type": "agent", "context": m.context, "message_id": m.id})
    db.add(n)
    publish_after_commit(db, "room", room.id, "notes_changed", {})
    db.commit()
    return ok({"note_id": n.id})


@router.post("/agent/{message_id}/tasks")
def agent_tasks(message_id: str, user: User = Depends(acting_user), db: Session = Depends(get_db)):
    m = db.get(AgentMessage, message_id)
    if not m or m.role != "assistant":
        raise not_found("Answer")
    room = _room_for_participant(db, m.room_id, user)
    proposed = (m.content or {}).get("tasks") or [{"title": s, "topic": s, "description": "Research this subtopic and add findings to the room notes."} for s in (m.content or {}).get("subtopics", [])]
    if not proposed:
        raise ApiError("NO_TASKS", "This answer has no tasks or subtopics to add.", 409)
    pos = db.scalar(select(func.max(Task.position)).where(Task.room_id == room.id)) or 0
    for i, t in enumerate(proposed[:10], 1):
        db.add(Task(room_id=room.id, title=str(t.get("title", ""))[:200] or "Task", description=str(t.get("description", ""))[:2000], topic=str(t.get("topic", ""))[:100],
                    priority=min(3, max(1, int(t.get("priority") or 2))), est_minutes=t.get("est_minutes"), position=pos + i, source="ai", status="proposed", created_by=user.id))
    publish_after_commit(db, "room", room.id, "tasks_changed", {})
    db.commit()
    return ok({"proposed": min(10, len(proposed))})
