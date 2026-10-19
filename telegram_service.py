"""Telegram Bot Service for YouTube to Instagram Automation.

Sends real-time notifications when a Reel is uploaded to Instagram,
including the direct Instagram link and performance analytics (views, likes,
shares, comments) of the previously uploaded Reel.
"""

from __future__ import annotations

import html
import logging
from typing import Any
import requests
from config import config

logger = logging.getLogger("telegram_service")


class TelegramService:
    def __init__(self) -> None:
        self.api_base = "https://api.telegram.org"

    @property
    def token(self) -> str:
        return config.telegram_bot_token

    @property
    def chat_id(self) -> str:
        return config.telegram_chat_id

    def is_configured(self) -> bool:
        """Check if Telegram Bot token and chat ID are configured."""
        return bool(self.token and self.chat_id and "your_bot_token" not in self.token)

    def send_message(
        self,
        text: str,
        parse_mode: str = "HTML",
        disable_web_page_preview: bool = False,
    ) -> bool:
        """Send an HTML-formatted message to the configured Telegram chat."""
        if not self.is_configured():
            logger.debug("Telegram is not configured. Skipping message dispatch.")
            return False

        url = f"{self.api_base}/bot{self.token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": disable_web_page_preview,
        }

        try:
            resp = requests.post(url, json=payload, timeout=15)
            data = resp.json()
            if not data.get("ok"):
                logger.error(f"Telegram API error: {data.get('description')}")
                return False
            return True
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False

    def send_upload_notification(
        self,
        new_video_meta: dict[str, Any],
        new_reel_info: dict[str, Any],
        prev_reel_info: dict[str, Any] | None = None,
        prev_stats: dict[str, Any] | None = None,
    ) -> bool:
        """Send a formatted notification for a newly published Instagram Reel with stats of the previous Reel."""
        if not self.is_configured():
            return False

        new_title = html.escape(new_video_meta.get("title", "Untitled"))
        new_url = new_reel_info.get("url", "")
        new_duration = new_video_meta.get("duration", 0)

        # Build Previous Reel Stats Section
        if prev_reel_info and prev_stats:
            prev_title = html.escape(prev_reel_info.get("title", "Untitled"))
            prev_url = prev_reel_info.get("instagram_url", "")
            views = prev_stats.get("views", 0)
            likes = prev_stats.get("likes", 0)
            comments = prev_stats.get("comments", 0)
            shares = prev_stats.get("shares", "N/A")
            saves = prev_stats.get("saves", "N/A")

            # Format view / like count with commas
            views_str = f"{views:,}" if isinstance(views, (int, float)) else str(views)
            likes_str = f"{likes:,}" if isinstance(likes, (int, float)) else str(likes)
            comments_str = f"{comments:,}" if isinstance(comments, (int, float)) else str(comments)
            shares_str = f"{shares:,}" if isinstance(shares, (int, float)) else str(shares)
            saves_str = f"{saves:,}" if isinstance(saves, (int, float)) else str(saves)

            prev_section = (
                f"📌 <b>Title:</b> {prev_title}\n"
                f"🔗 <b>Link:</b> <a href=\"{prev_url}\">{prev_url}</a>\n"
                f"👀 <b>Views / Plays:</b> {views_str}\n"
                f"❤️ <b>Likes:</b> {likes_str}\n"
                f"💬 <b>Comments:</b> {comments_str}\n"
                f"🔄 <b>Shares:</b> {shares_str}\n"
                f"🔖 <b>Saves:</b> {saves_str}"
            )
        else:
            prev_section = "<i>(First automated upload — no previous reel to report yet.)</i>"

        message = (
            "🚀 <b>New Reel Uploaded to Instagram!</b>\n\n"
            f"🎬 <b>YouTube Title:</b> {new_title}\n"
            f"🔗 <b>Instagram Reel:</b> <a href=\"{new_url}\">{new_url}</a>\n"
            f"⏱ <b>Duration:</b> {new_duration}s\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "📊 <b>Stats of Previous Reel:</b>\n"
            f"{prev_section}\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━"
        )

        return self.send_message(message, disable_web_page_preview=False)

    def test_connection(self) -> dict[str, Any]:
        """Test Telegram Bot credentials and send a test message."""
        if not self.is_configured():
            return {
                "ok": False,
                "error": "TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is missing in configuration.",
            }

        # 1. Verify Bot Token
        try:
            resp = requests.get(f"{self.api_base}/bot{self.token}/getMe", timeout=10)
            data = resp.json()
            if not data.get("ok"):
                return {"ok": False, "error": f"Invalid Bot Token: {data.get('description')}"}
            bot_info = data.get("result", {})
        except Exception as e:
            return {"ok": False, "error": f"Connection error: {e}"}

        # 2. Send Test Message
        test_msg = (
            "🤖 <b>YouTube to Instagram Bot Connected!</b>\n\n"
            "You will receive automatic notifications with reel links and previous reel performance stats "
            "whenever a new video is posted."
        )
        sent = self.send_message(test_msg)
        if not sent:
            return {
                "ok": False,
                "bot_username": bot_info.get("username"),
                "error": f"Bot verified (@{bot_info.get('username')}), but failed to send message to chat_id {self.chat_id}. Ensure you sent /start to the bot first!",
            }

        return {
            "ok": True,
            "bot_username": bot_info.get("username"),
            "chat_id": self.chat_id,
        }


# Global telegram service instance
telegram_service = TelegramService()
