"""Configuration manager for YouTube to Instagram Automation.

Loads environment variables from .env and provides strongly typed settings
suitable for both local operation and cloud deployments (e.g., Render).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

# Base directory for the automation project
BASE_DIR = Path(__file__).resolve().parent

# Load .env file
load_dotenv(dotenv_path=BASE_DIR / ".env")


def _get_bool(key: str, default: bool = False) -> bool:
    val = os.getenv(key)
    if val is None:
        return default
    return val.strip().lower() in ("true", "1", "yes", "on")


def _get_int(key: str, default: int) -> int:
    val = os.getenv(key)
    if val is None:
        return default
    try:
        return int(val.strip())
    except ValueError:
        return default


@dataclass
class Config:
    # -------------------------------------------------------------------------
    # YouTube Settings (NO LOGIN REQUIRED - PUBLIC CHANNEL URL ONLY)
    # -------------------------------------------------------------------------
    youtube_channel_url: str = os.getenv("YOUTUBE_CHANNEL_URL", "").strip()
    shorts_only: bool = _get_bool("SHORTS_ONLY", True)

    # -------------------------------------------------------------------------
    # Instagram Credentials & Headless Cloud Session (for Render)
    # -------------------------------------------------------------------------
    instagram_username: str = os.getenv("INSTAGRAM_USERNAME", "").strip()
    instagram_password: str = os.getenv("INSTAGRAM_PASSWORD", "").strip()
    instagram_session_file: Path = BASE_DIR / os.getenv("INSTAGRAM_SESSION_FILE", "instagram_session.json")
    # Base64-encoded session string (ideal for headless deployments like Render)
    instagram_session_base64: str = os.getenv("INSTAGRAM_SESSION_BASE64", "").strip()

    # -------------------------------------------------------------------------
    # Posting Controls & Account Safety
    # -------------------------------------------------------------------------
    max_videos_per_run: int = _get_int("MAX_VIDEOS_PER_RUN", 2)
    delay_between_posts_seconds: int = _get_int("DELAY_BETWEEN_POSTS_SECONDS", 90)
    post_order: str = os.getenv("POST_ORDER", "oldest_first").strip().lower()
    share_to_feed: bool = _get_bool("SHARE_TO_FEED", True)

    # -------------------------------------------------------------------------
    # Caption Settings
    # -------------------------------------------------------------------------
    max_caption_length: int = _get_int("MAX_CAPTION_LENGTH", 2200)
    custom_hashtags: str = os.getenv("CUSTOM_HASHTAGS", "").strip()
    clean_youtube_links: bool = _get_bool("CLEAN_YOUTUBE_LINKS", True)

    # -------------------------------------------------------------------------
    # Telegram Bot Notifications & Stats Reporting
    # -------------------------------------------------------------------------
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    @property
    def has_telegram(self) -> bool:
        return bool(self.telegram_bot_token and self.telegram_chat_id and "your_bot_token" not in self.telegram_bot_token)

    # -------------------------------------------------------------------------
    # Scheduler & Server Settings (Render Web Service)
    # -------------------------------------------------------------------------
    check_interval_minutes: int = _get_int("CHECK_INTERVAL_MINUTES", 60)
    port: int = _get_int("PORT", 10000)

    # -------------------------------------------------------------------------
    # Storage Paths & Database Synchronization
    # -------------------------------------------------------------------------
    downloads_dir: Path = BASE_DIR / "temp_videos"
    data_dir: Path = BASE_DIR / "data"

    # Database file path (configurable for Render persistent disk, e.g. /var/data/posted_videos.db)
    @property
    def db_file(self) -> Path:
        custom_path = os.getenv("DATABASE_PATH", "").strip()
        if custom_path:
            return Path(custom_path)
        return self.data_dir / "posted_videos.db"

    # If true, on fresh startup with an empty DB, all existing channel videos are marked baseline
    initial_sync_only_new: bool = _get_bool("INITIAL_SYNC_ONLY_NEW", False)
    # Optional comma-separated list of known posted video IDs to seed the database
    posted_ids_list: str = os.getenv("POSTED_IDS_LIST", "").strip()

    def ensure_directories(self) -> None:
        """Ensure runtime directories exist."""
        self.downloads_dir.mkdir(parents=True, exist_ok=True)
        self.db_file.parent.mkdir(parents=True, exist_ok=True)

    def validate_youtube_config(self) -> list[str]:
        """Check if YouTube configuration is valid."""
        errors = []
        if not self.youtube_channel_url or "YourChannel" in self.youtube_channel_url:
            errors.append("YOUTUBE_CHANNEL_URL is not set or still has default placeholder.")
        return errors

    def validate_instagram_config(self) -> list[str]:
        """Check if Instagram configuration is valid."""
        errors = []
        # If an exported session is provided, credentials are not strictly mandatory
        has_session = bool(self.instagram_session_base64) or self.instagram_session_file.exists()

        if not has_session:
            if not self.instagram_username or "your_instagram_username" in self.instagram_username:
                errors.append("INSTAGRAM_USERNAME is not set (and no INSTAGRAM_SESSION_BASE64 provided).")
            if not self.instagram_password or "your_instagram_password" in self.instagram_password:
                errors.append("INSTAGRAM_PASSWORD is not set (and no INSTAGRAM_SESSION_BASE64 provided).")
        return errors

    def print_summary(self) -> dict[str, str | int | bool]:
        """Return masked settings summary."""
        has_b64 = "Yes (Configured)" if self.instagram_session_base64 else "No"
        masked_pass = "*" * len(self.instagram_password) if self.instagram_password else "[NOT SET]"
        return {
            "YouTube Channel URL": self.youtube_channel_url or "[NOT SET]",
            "YouTube Authentication": "None (Public Channel Fetch)",
            "Shorts Only": self.shorts_only,
            "Instagram Username": self.instagram_username or "[NOT SET]",
            "Instagram Password": masked_pass,
            "Render Cloud Session (B64)": has_b64,
            "Database File": str(self.db_file),
            "Max Videos Per Run": self.max_videos_per_run,
            "Delay Between Posts": f"{self.delay_between_posts_seconds}s",
            "Watch Interval": f"{self.check_interval_minutes} mins",
            "Telegram Notifications": "Configured" if self.has_telegram else "Disabled / Not Set",
            "Web Service Port": self.port,
        }


# Global config instance
config = Config()
config.ensure_directories()
