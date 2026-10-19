"""Instagram service utilizing instagrapi for authentication and Reel uploading.

Handles session caching, 2FA challenges, image conversion, and clip uploads.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from PIL import Image
from instagrapi import Client
from instagrapi.exceptions import (
    ChallengeRequired,
    LoginRequired,
    PleaseWaitFewMinutes,
    TwoFactorRequired,
)
from config import config

logger = logging.getLogger("instagram_service")


class InstagramService:
    def __init__(self) -> None:
        self.client = Client()
        self.session_file = config.instagram_session_file
        self._is_authenticated = False

    def _prepare_thumbnail(self, thumbnail_path: Path | None) -> Path | None:
        """Ensure thumbnail is in compatible JPEG format."""
        if not thumbnail_path or not thumbnail_path.exists():
            return None

        # If already jpg/jpeg, return as-is
        if thumbnail_path.suffix.lower() in (".jpg", ".jpeg"):
            return thumbnail_path

        # Convert webp or png to jpg
        try:
            jpg_path = thumbnail_path.with_suffix(".jpg")
            with Image.open(thumbnail_path) as img:
                rgb_img = img.convert("RGB")
                rgb_img.save(jpg_path, "JPEG", quality=90)
            return jpg_path
        except Exception as e:
            logger.warning(f"Could not convert thumbnail {thumbnail_path}: {e}")
            return None

    def export_session_base64(self) -> str:
        """Export the current Instagram session as a base64 string for cloud environments."""
        import base64
        import json

        if self.session_file.exists():
            data = self.session_file.read_text(encoding="utf-8")
        else:
            settings = self.client.get_settings()
            if not settings:
                raise ValueError("No active session found. Please run 'python main.py test-login' first.")
            data = json.dumps(settings)

        return base64.b64encode(data.encode("utf-8")).decode("utf-8")

    def authenticate(self, username: str | None = None, password: str | None = None) -> bool:
        """Authenticate with Instagram using base64 session, cached session file, or credentials."""
        import base64
        import json

        user = username or config.instagram_username
        pwd = password or config.instagram_password

        # 1. Attempt to load from base64 environment variable (Render / Cloud deployment)
        if config.instagram_session_base64:
            try:
                decoded_json = base64.b64decode(config.instagram_session_base64.encode("utf-8")).decode("utf-8")
                settings_dict = json.loads(decoded_json)
                self.client.set_settings(settings_dict)
                self.client.get_timeline_feed()
                self._is_authenticated = True
                logger.info("Successfully authenticated via INSTAGRAM_SESSION_BASE64!")
                return True
            except Exception as e:
                logger.warning(f"Failed to authenticate via INSTAGRAM_SESSION_BASE64 ({e}). Trying next method...")

        # 2. Attempt to load existing session file
        if self.session_file.exists():
            try:
                self.client.load_settings(self.session_file)
                # Verify session validity
                self.client.get_timeline_feed()
                self._is_authenticated = True
                logger.info("Successfully authenticated via session file!")
                return True
            except Exception as e:
                logger.info(f"Existing session invalid or expired ({e}). Proceeding to fresh login...")

        # 3. Fresh login with credentials (if provided)
        if not user or not pwd:
            raise ValueError(
                "Instagram credentials (username and password) or INSTAGRAM_SESSION_BASE64 must be provided."
            )

        try:
            logged_in = self.client.login(user, pwd)
            if logged_in:
                self.client.dump_settings(self.session_file)
                self._is_authenticated = True
                return True
        except TwoFactorRequired:
            code = input("\n[2FA Required] Enter the 6-digit 2FA verification code sent to your phone/authenticator: ").strip()
            self.client.login(user, pwd, verification_code=code)
            self.client.dump_settings(self.session_file)
            self._is_authenticated = True
            return True
        except ChallengeRequired:
            raise RuntimeError(
                "Instagram checkpoint / challenge required. Please log into the Instagram app "
                "or website on this device/network once and verify 'This Was Me', then rerun."
            )
        except PleaseWaitFewMinutes:
            raise RuntimeError(
                "Instagram has temporarily rate-limited login requests. Please wait a few minutes before retrying."
            )

        return False

    def upload_reel(
        self,
        video_path: Path,
        caption: str,
        thumbnail_path: Path | None = None,
        share_to_feed: bool | None = None,
    ) -> dict[str, Any]:
        """Upload a video file as an Instagram Reel."""
        if not self._is_authenticated:
            self.authenticate()

        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found at {video_path}")

        show_in_feed = share_to_feed if share_to_feed is not None else config.share_to_feed
        prepared_thumb = self._prepare_thumbnail(thumbnail_path)

        media = self.client.clip_upload(
            path=video_path,
            caption=caption,
            thumbnail=prepared_thumb,
            show_preview_in_feed=show_in_feed,
        )

        media_id = str(getattr(media, "id", ""))
        code = getattr(media, "code", "")
        url = f"https://www.instagram.com/reel/{code}/" if code else ""

        return {
            "media_id": media_id,
            "code": code,
            "url": url,
            "media": media,
        }

    def get_media_stats(
        self,
        media_id: str | None = None,
        code: str | None = None,
        url: str | None = None,
    ) -> dict[str, Any]:
        """Fetch views, likes, comments, shares, and saves for an Instagram Reel."""
        if not self._is_authenticated:
            try:
                self.authenticate()
            except Exception as e:
                logger.warning(f"Could not authenticate to fetch media stats: {e}")
                return {"error": str(e), "views": 0, "likes": 0, "comments": 0, "shares": "N/A", "saves": "N/A"}

        pk = None
        if media_id:
            try:
                clean_id = str(media_id).split("_")[0]
                if clean_id.isdigit():
                    pk = int(clean_id)
            except Exception:
                pass

        if not pk and code:
            try:
                pk = self.client.media_pk_from_code(code)
            except Exception:
                pass

        if not pk and url:
            try:
                pk = self.client.media_pk_from_url(url)
            except Exception:
                pass

        if not pk:
            return {
                "error": "Could not determine media ID/code",
                "views": 0,
                "likes": 0,
                "comments": 0,
                "shares": "N/A",
                "saves": "N/A",
            }

        stats: dict[str, Any] = {
            "views": 0,
            "likes": 0,
            "comments": 0,
            "shares": "N/A",
            "saves": "N/A",
        }

        try:
            info = self.client.media_info(pk)
            stats["views"] = max(getattr(info, "view_count", 0) or 0, getattr(info, "play_count", 0) or 0)
            stats["likes"] = getattr(info, "like_count", 0) or 0
            stats["comments"] = getattr(info, "comment_count", 0) or 0
        except Exception as e:
            logger.warning(f"Failed to fetch media_info for pk {pk}: {e}")

        # Attempt to fetch insights (shares, saves) if professional account
        try:
            insights = self.client.insights_media(pk)
            if isinstance(insights, dict):
                for metric in ("shares", "saves", "reshare_count", "saved_count"):
                    if metric in insights:
                        val = insights[metric]
                        if "share" in metric:
                            stats["shares"] = val
                        elif "save" in metric:
                            stats["saves"] = val
        except Exception:
            pass

        return stats


# Global instagram service instance
instagram_service = InstagramService()
