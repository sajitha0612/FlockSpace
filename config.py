"""All tunable rules live here so they can be changed from backend/.env without touching the logic."""
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


def _default_database_url() -> str:
    # The app used to be called NestUp. Keep using an existing nestup.db so renaming never loses anyone's data.
    if not Path("flockspace.db").exists() and Path("nestup.db").exists():
        return "sqlite:///./nestup.db"
    return "sqlite:///./flockspace.db"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8-sig", extra="ignore")

    database_url: str = Field(default_factory=_default_database_url)
    # dev_mode: verification/reset codes are written to the server log when SMTP is not configured
    dev_mode: bool = True

    # --- AI (Groq, backend only) ---
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    ai_timeout_seconds: float = 60
    ai_max_retries: int = 2
    ai_user_daily_quota: int = 40
    ai_room_daily_quota: int = 150
    ai_user_per_minute: int = 4
    ai_max_question_chars: int = 2000
    ai_chunk_chars: int = 12000
    ai_max_source_chars: int = 120000
    ai_max_chat_messages: int = 400

    # --- auth ---
    jwt_secret: str = "change-me-in-.env"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7
    admin_emails: str = ""  # comma-separated; these accounts can review reports and flags
    require_verified_email_for_rewards: bool = True
    verification_code_minutes: int = 30

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""

    frontend_url: str = "http://localhost:5173"

    # --- uploads ---
    upload_dir: str = "uploads"
    max_upload_size_mb: int = 15
    max_extracted_chars: int = 400000

    # --- rooms ---
    room_min_minutes: int = 15
    room_max_minutes: int = 360
    room_max_participants: int = 50
    room_max_topics: int = 30

    # --- study sessions / streaks ---
    min_counted_focus_minutes: int = 10  # a focus block shorter than this never counts toward analytics
    default_daily_goal_minutes: int = 25

    # --- quizzes and rewards ---
    halfway_question_count: int = 5
    halfway_minutes: int = 10
    twigs_per_correct: int = 1
    race_question_count: int = 10
    race_min_questions: int = 4
    race_minutes: int = 10
    race_countdown_seconds: int = 20
    race_nest_target_ratio: float = 0.7  # nest completes at this share of the maximum possible twigs
    race_min_eligible: int = 2
    placement_bonuses: str = "3,2,1"
    golden_nest_daily_cap: int = 3
    personal_nest_target: int = 50
    milestones: str = "5:accessory_scarf,10:nest_golden,25:crown_royal,50:nest_legendary"

    # --- matching ---
    bayes_prior_alpha: float = 2
    bayes_prior_beta: float = 2
    bayes_confidence_k: float = 5
    bayes_max_adjustment: float = 30

    # --- presence ---
    presence_stale_seconds: int = 90

    @field_validator("groq_api_key", "jwt_secret", "smtp_password", mode="before")
    @classmethod
    def _clean_secret(cls, v):
        return str(v or "").strip().strip('"').strip("'").strip()

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.frontend_url.split(",") if o.strip()]

    @property
    def admins(self) -> set[str]:
        return {e.strip().lower() for e in self.admin_emails.split(",") if e.strip()}

    @property
    def bonuses(self) -> list[int]:
        return [int(x) for x in self.placement_bonuses.split(",") if x.strip()]

    @property
    def milestone_list(self) -> list[tuple[int, str]]:
        out = []
        for part in self.milestones.split(","):
            if ":" in part:
                n, item = part.split(":", 1)
                out.append((int(n), item.strip()))
        return sorted(out)


@lru_cache
def get_settings() -> Settings:
    return Settings()
