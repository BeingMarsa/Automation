"""Database tracking system for processed and posted videos.

Uses SQLite to ensure persistent record-keeping so videos are never duplicated.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any
from config import config


class Database:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or config.db_file
        self.init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        """Create tables if they do not exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS posted_videos (
                    youtube_id TEXT PRIMARY KEY,
                    title TEXT,
                    description TEXT,
                    duration INTEGER,
                    youtube_url TEXT,
                    instagram_media_id TEXT,
                    instagram_code TEXT,
                    instagram_url TEXT,
                    posted_at TEXT,
                    status TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS skipped_videos (
                    youtube_id TEXT PRIMARY KEY,
                    title TEXT,
                    reason TEXT,
                    skipped_at TEXT
                )
            """)
            conn.commit()

            # Seed pre-configured posted IDs if provided in environment
            if config.posted_ids_list:
                for raw_id in config.posted_ids_list.split(","):
                    vid_id = raw_id.strip()
                    if vid_id:
                        cursor.execute(
                            """
                            INSERT OR IGNORE INTO posted_videos (
                                youtube_id, title, description, duration, youtube_url,
                                instagram_media_id, instagram_code, instagram_url, posted_at, status
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (vid_id, "Seeded from config", "", 0, f"https://www.youtube.com/watch?v={vid_id}", "seeded", "", "", datetime.now().isoformat(), "seeded"),
                        )
                conn.commit()

    def is_processed(self, youtube_id: str) -> bool:
        """Check whether a video has already been posted or explicitly skipped."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM posted_videos WHERE youtube_id = ? UNION SELECT 1 FROM skipped_videos WHERE youtube_id = ?",
                (youtube_id, youtube_id),
            )
            return cursor.fetchone() is not None

    def get_processed_ids(self) -> set[str]:
        """Return a set of all processed (posted or skipped) YouTube video IDs."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT youtube_id FROM posted_videos UNION SELECT youtube_id FROM skipped_videos")
            rows = cursor.fetchall()
            return {row["youtube_id"] for row in rows}

    def record_posted(
        self,
        youtube_id: str,
        title: str,
        description: str,
        duration: int,
        youtube_url: str,
        instagram_media_id: str = "",
        instagram_code: str = "",
        instagram_url: str = "",
        status: str = "posted",
    ) -> None:
        """Record a successfully posted video."""
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO posted_videos (
                    youtube_id, title, description, duration, youtube_url,
                    instagram_media_id, instagram_code, instagram_url, posted_at, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    youtube_id,
                    title,
                    description,
                    duration,
                    youtube_url,
                    instagram_media_id,
                    instagram_code,
                    instagram_url,
                    now,
                    status,
                ),
            )
            conn.commit()

    def record_skipped(self, youtube_id: str, title: str, reason: str) -> None:
        """Record a video that was intentionally skipped (e.g. over 90s, broken format)."""
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO skipped_videos (youtube_id, title, reason, skipped_at)
                VALUES (?, ?, ?, ?)
                """,
                (youtube_id, title, reason, now),
            )
            conn.commit()

    def get_stats(self) -> dict[str, int]:
        """Get summary statistics from the database."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) AS total FROM posted_videos")
            posted_count = cursor.fetchone()["total"]
            cursor.execute("SELECT COUNT(*) AS total FROM skipped_videos")
            skipped_count = cursor.fetchone()["total"]
            return {"posted_count": posted_count, "skipped_count": skipped_count}

    def get_recent_posts(self, limit: int = 10) -> list[dict[str, Any]]:
        """Retrieve recent posts from the database."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT youtube_id, title, instagram_url, posted_at, status
                FROM posted_videos
                ORDER BY posted_at DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def mark_all_as_posted(self, videos: list[dict[str, Any]]) -> int:
        """Bulk mark a list of YouTube videos as posted without uploading (for initial baseline)."""
        now = datetime.now().isoformat()
        count = 0
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for v in videos:
                vid_id = v.get("id") or v.get("youtube_id")
                if not vid_id:
                    continue
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO posted_videos (
                        youtube_id, title, description, duration, youtube_url,
                        instagram_media_id, instagram_code, instagram_url, posted_at, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        vid_id,
                        v.get("title", ""),
                        v.get("description", ""),
                        v.get("duration", 0),
                        f"https://www.youtube.com/watch?v={vid_id}",
                        "marked_existing",
                        "",
                        "",
                        now,
                        "marked_baseline",
                    ),
                )
                if cursor.rowcount > 0:
                    count += 1
            conn.commit()
        return count

    def get_last_posted_reel(self) -> dict[str, Any] | None:
        """Retrieve the most recently posted Instagram Reel from the database."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT youtube_id, title, description, duration, youtube_url,
                       instagram_media_id, instagram_code, instagram_url, posted_at, status
                FROM posted_videos
                WHERE status = 'posted'
                  AND instagram_media_id != ''
                  AND instagram_media_id NOT IN ('seeded', 'marked_existing')
                ORDER BY posted_at DESC
                LIMIT 1
                """
            )
            row = cursor.fetchone()
            return dict(row) if row else None


# Global database instance
db = Database()
