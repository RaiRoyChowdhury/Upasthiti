"""
Centralized application configuration.

All configurable values MUST be read from here (and ultimately from the .env
file) rather than hardcoded anywhere else in the codebase. This is what lets
thresholds, secrets, and connection strings change per-environment without
touching application code.
"""

from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/config/settings.py -> backend/config -> backend -> project root
BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_FILE = BASE_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ---- App ----
    APP_NAME: str = "SmartAttend AI"
    APP_ENV: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    # ---- API ----
    API_V1_PREFIX: str = "/api"
    CORS_ORIGINS: str = "http://localhost:8000,http://127.0.0.1:8000"

    # ---- Database ----
    MONGODB_URI: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "smartattend_ai"

    # ---- Auth ----
    JWT_SECRET: str = "insecure-dev-secret-change-me"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 120

    # ---- CV / Attendance policy ----
    # Now actively used by the Phase 2/3 CV pipeline. Values are placeholders
    # until calibrated against the real enrollment data on the deploying
    # institution's hardware/lighting — see docs/computer-vision.md.
    FACE_RECOGNITION_THRESHOLD: float = 0.60
    LOW_CONFIDENCE_THRESHOLD: float = 0.45  # below this: UNKNOWN. Between this and
    # FACE_RECOGNITION_THRESHOLD: LOW_CONFIDENCE (teacher verification required).
    LIVENESS_THRESHOLD: float = 0.50
    RECOGNITION_COOLDOWN_SECONDS: int = 30

    # Face detection/quality
    INSIGHTFACE_MODEL_PACK: str = "buffalo_l"
    INSIGHTFACE_PROVIDERS: str = "CPUExecutionProvider"
    INSIGHTFACE_DET_SIZE: int = 640
    MIN_FACE_QUALITY_SCORE: float = 0.55  # 0-1, composite of size/blur/brightness/pose
    MIN_FACE_SIZE_RATIO: float = 0.12  # face bbox width / frame width, minimum
    MAX_BLUR_VARIANCE_FLOOR: float = 60.0  # Laplacian variance below this = too blurry
    MAX_YAW_DEGREES_FOR_ENROLLMENT: float = 20.0  # frontal-ness requirement for enrollment

    # Liveness (heuristic head-turn challenge — see docs/computer-vision.md
    # for why this is NOT certified anti-spoofing)
    LIVENESS_YAW_DELTA_DEGREES: float = 12.0  # minimum head-turn to count as an action
    LIVENESS_TIMEOUT_SECONDS: int = 20
    LIVENESS_SESSION_TTL_SECONDS: int = 60

    # Attendance
    DEFAULT_LATE_THRESHOLD_MINUTES: int = 10  # used only if a session doesn't set its own

    # ---- Retention (Phase 10) ----
    # How often the background purge loop checks whether it should run.
    # Actual deletion still requires policy.retention_enforcement_enabled
    # to be True — see services/retention_service.py and docs/retention.md.
    RETENTION_CHECK_INTERVAL_HOURS: int = 24

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance — .env is read once per process."""
    return Settings()
