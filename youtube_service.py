"""YouTube crawler and downloader service using yt-dlp and imageio-ffmpeg.

Fetches channel videos/shorts, extracts metadata, and downloads video files.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
import imageio_ffmpeg
import yt_dlp
from config import config

# Ensure imageio-ffmpeg binary is available
FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()


class YouTubeService:
    def __init__(self) -> None:
        self.ffmpeg_path = FFMPEG_PATH

    def normalize_channel_url(self, raw_url: str, shorts_only: bool = True) -> str:
        """Normalize channel URL to ensure correct shorts/videos tab."""
        url = raw_url.strip()
        if not url.startswith("http"):
            if url.startswith("@"):
                url = f"https://www.youtube.com/{url}"
            else:
                url = f"https://www.youtube.com/@{url}"

        # Clean trailing slashes
        url = url.rstrip("/")

        if shorts_only and not url.endswith("/shorts") and not url.endswith("/videos"):
            url = f"{url}/shorts"
        return url

    def get_channel_videos(
        self,
        channel_url: str | None = None,
        max_results: int = 50,
        shorts_only: bool | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch video metadata list from a YouTube channel without downloading."""
        target_url = channel_url or config.youtube_channel_url
        is_shorts = shorts_only if shorts_only is not None else config.shorts_only
        normalized_url = self.normalize_channel_url(target_url, shorts_only=is_shorts)

        # Pure unauthenticated, public fetch - absolutely NO YouTube/Google login needed
        ydl_opts: dict[str, Any] = {
            "extract_flat": True,
            "quiet": True,
            "no_warnings": True,
            "playlistend": max_results,
            "ffmpeg_location": self.ffmpeg_path,
            "cookiefile": None,
        }

        videos = []
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(normalized_url, download=False)
            if not result:
                return []

            entries = result.get("entries", [])
            for entry in entries:
                if not entry:
                    continue
                vid_id = entry.get("id")
                if not vid_id:
                    continue

                videos.append(
                    {
                        "id": vid_id,
                        "title": entry.get("title", ""),
                        "duration": entry.get("duration"),
                        "url": f"https://www.youtube.com/watch?v={vid_id}",
                        "view_count": entry.get("view_count"),
                        "upload_date": entry.get("upload_date"),
                    }
                )

        return videos

    def get_video_details(self, video_id_or_url: str) -> dict[str, Any]:
        """Fetch complete metadata for a specific YouTube video."""
        url = (
            video_id_or_url
            if video_id_or_url.startswith("http")
            else f"https://www.youtube.com/watch?v={video_id_or_url}"
        )

        ydl_opts: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "ffmpeg_location": self.ffmpeg_path,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                raise ValueError(f"Could not retrieve details for {url}")

            return {
                "id": info.get("id", ""),
                "title": info.get("title", ""),
                "description": info.get("description", ""),
                "duration": info.get("duration", 0),
                "tags": info.get("tags", []),
                "thumbnail": info.get("thumbnail", ""),
                "url": info.get("webpage_url", url),
            }

    def download_video(
        self,
        video_id_or_url: str,
        output_dir: Path | None = None,
    ) -> tuple[Path, Path | None, dict[str, Any]]:
        """Download YouTube video as MP4 and return (video_path, thumbnail_path, metadata)."""
        target_dir = output_dir or config.downloads_dir
        target_dir.mkdir(parents=True, exist_ok=True)

        url = (
            video_id_or_url
            if video_id_or_url.startswith("http")
            else f"https://www.youtube.com/watch?v={video_id_or_url}"
        )

        out_template = str(target_dir / "%(id)s.%(ext)s")

        ydl_opts: dict[str, Any] = {
            "quiet": False,
            "no_warnings": True,
            "ffmpeg_location": self.ffmpeg_path,
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "merge_output_format": "mp4",
            "outtmpl": out_template,
            "writethumbnail": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not info:
                raise RuntimeError(f"Failed to download video from {url}")

            vid_id = info.get("id")
            video_path = target_dir / f"{vid_id}.mp4"

            # Check if thumbnail was saved
            thumbnail_path = None
            for ext in ("jpg", "webp", "png"):
                thumb_candidate = target_dir / f"{vid_id}.{ext}"
                if thumb_candidate.exists():
                    thumbnail_path = thumb_candidate
                    break

            meta = {
                "id": vid_id,
                "title": info.get("title", ""),
                "description": info.get("description", ""),
                "duration": int(info.get("duration") or 0),
                "url": info.get("webpage_url", url),
            }

            return video_path, thumbnail_path, meta

    def cleanup_files(self, *paths: Path | str | None) -> None:
        """Safely delete downloaded files after upload."""
        for p in paths:
            if not p:
                continue
            try:
                path_obj = Path(p)
                if path_obj.exists():
                    path_obj.unlink()
            except Exception:
                pass


# Global youtube service instance
youtube_service = YouTubeService()
