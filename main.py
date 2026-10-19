"""Main CLI and Orchestrator for YouTube to Instagram Automation.

Monitors YouTube channel uploads, downloads videos, formats captions,
and uploads them as Instagram Reels with persistent tracking and rate limiting.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from rich import print as rprint
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Reconfigure stdout/stderr to UTF-8 on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from config import config
from database import db
from formatter import format_caption
from instagram_service import instagram_service
from telegram_service import telegram_service
from youtube_service import youtube_service

console = Console()


def display_banner() -> None:
    """Print welcome header."""
    banner_text = (
        "[bold cyan]YouTube to Instagram Reels Automation[/bold cyan]\n"
        "[dim]Automatically crosspost YouTube Shorts to Instagram with Title & Description[/dim]"
    )
    console.print(Panel(banner_text, border_style="cyan"))


def process_unposted_videos(dry_run: bool = False, max_count: int | None = None) -> int:
    """Check for unposted videos on YouTube channel and post them to Instagram."""
    limit = max_count or config.max_videos_per_run

    # 1. Validate YouTube configuration
    yt_errors = config.validate_youtube_config()
    if yt_errors:
        for err in yt_errors:
            console.print(f"[bold red]Configuration Error:[/bold red] {err}")
        console.print("[yellow]Please update your .env file with your YouTube channel URL.[/yellow]")
        return 0

    if not dry_run:
        ig_errors = config.validate_instagram_config()
        if ig_errors:
            for err in ig_errors:
                console.print(f"[bold red]Configuration Error:[/bold red] {err}")
            console.print("[yellow]Please update your .env file with your Instagram credentials.[/yellow]")
            return 0

    console.print(f"[cyan]Scanning YouTube channel:[/cyan] {config.youtube_channel_url}")
    try:
        channel_videos = youtube_service.get_channel_videos()
    except Exception as e:
        console.print(f"[bold red]Failed to fetch channel videos:[/bold red] {e}")
        return 0

    if not channel_videos:
        console.print("[yellow]No videos found on the channel.[/yellow]")
        return 0

    console.print(f"[green]Found {len(channel_videos)} videos/shorts on channel.[/green]")

    # 2. Filter out already processed videos
    processed_ids = db.get_processed_ids()

    # Safety check for fresh cloud deployments: if INITIAL_SYNC_ONLY_NEW is active and DB is empty, baseline all current videos
    if config.initial_sync_only_new and len(processed_ids) == 0:
        console.print("[cyan]INITIAL_SYNC_ONLY_NEW is enabled and database is empty. Marking existing channel videos as baseline...[/cyan]")
        count = db.mark_all_as_posted(channel_videos)
        console.print(f"[bold green]Marked {count} existing videos as baseline. Only new future uploads will be posted.[/bold green]")
        return 0

    unposted = [v for v in channel_videos if v["id"] not in processed_ids]

    if not unposted:
        console.print("[bold green]All channel videos have already been posted! Everything up to date.[/bold green]")
        return 0

    console.print(f"[bold yellow]{len(unposted)} unposted video(s) found.[/bold yellow]")

    # 3. Sort by configured order
    if config.post_order == "oldest_first":
        unposted = list(reversed(unposted))

    # Limit to maximum batch size
    batch = unposted[:limit]
    console.print(f"[cyan]Processing batch of {len(batch)} video(s) (Limit: {limit})...[/cyan]\n")

    posted_count = 0
    for idx, item in enumerate(batch, 1):
        vid_id = item["id"]
        console.print(f"[bold blue][{idx}/{len(batch)}] Processing YouTube video ID: {vid_id}[/bold blue]")

        # Fetch detailed video metadata
        try:
            details = youtube_service.get_video_details(vid_id)
        except Exception as e:
            console.print(f"[red]Error fetching metadata for {vid_id}: {e}[/red]")
            continue

        title = details.get("title", "")
        description = details.get("description", "")
        duration = details.get("duration", 0)
        yt_url = details.get("url", f"https://www.youtube.com/watch?v={vid_id}")

        console.print(f"  [bold]Title:[/bold] {title}")
        console.print(f"  [dim]Duration:[/dim] {duration}s")

        # Check duration if shorts only
        if config.shorts_only and duration > 95:
            console.print(f"  [yellow]Skipping {vid_id} because duration ({duration}s) exceeds 90s limit.[/yellow]")
            db.record_skipped(vid_id, title, f"Duration ({duration}s) exceeds 90s limit")
            continue

        # Format Instagram Caption
        caption = format_caption(title=title, description=description)

        if dry_run:
            console.print("\n  [bold magenta]--- PREVIEW CAPTION (DRY RUN) ---[/bold magenta]")
            console.print(Panel(caption, title="Instagram Caption Preview", border_style="magenta"))
            console.print(f"  [cyan]Caption length: {len(caption)} / {config.max_caption_length} chars[/cyan]\n")
            posted_count += 1
            continue

        # Download Video & Thumbnail
        console.print("  [cyan]Downloading video file...[/cyan]")
        try:
            video_path, thumb_path, _ = youtube_service.download_video(vid_id)
        except Exception as e:
            console.print(f"  [bold red]Download failed:[/bold red] {e}")
            continue

        # Fetch previous reel info and its live performance stats (before recording this new one)
        prev_reel = db.get_last_posted_reel()
        prev_stats = None
        if prev_reel:
            console.print(f"  [dim]Fetching stats for previously uploaded Reel: {prev_reel.get('title')[:35]}...[/dim]")
            try:
                prev_stats = instagram_service.get_media_stats(
                    media_id=prev_reel.get("instagram_media_id"),
                    code=prev_reel.get("instagram_code"),
                    url=prev_reel.get("instagram_url"),
                )
            except Exception as e:
                console.print(f"  [yellow]Notice: Could not retrieve previous reel stats: {e}[/yellow]")

        # Upload to Instagram
        console.print("  [cyan]Uploading to Instagram Reels...[/cyan]")
        try:
            result = instagram_service.upload_reel(
                video_path=video_path,
                caption=caption,
                thumbnail_path=thumb_path,
            )
            ig_url = result.get("url", "")
            media_id = result.get("media_id", "")
            code = result.get("code", "")

            console.print(f"  [bold green]Successfully uploaded Reel![/bold green] Link: [underline]{ig_url}[/underline]")

            # Record in database
            db.record_posted(
                youtube_id=vid_id,
                title=title,
                description=description,
                duration=duration,
                youtube_url=yt_url,
                instagram_media_id=media_id,
                instagram_code=code,
                instagram_url=ig_url,
            )
            posted_count += 1

            # Dispatch Telegram notification with new Reel link and previous Reel stats
            if telegram_service.is_configured():
                console.print("  [cyan]Sending Telegram notification...[/cyan]")
                sent = telegram_service.send_upload_notification(
                    new_video_meta=details,
                    new_reel_info=result,
                    prev_reel_info=prev_reel,
                    prev_stats=prev_stats,
                )
                if sent:
                    console.print("  [bold green]Telegram notification sent successfully![/bold green]")
                else:
                    console.print("  [yellow]Failed to send Telegram notification.[/yellow]")

        except Exception as e:
            console.print(f"  [bold red]Instagram upload failed:[/bold red] {e}")
        finally:
            # Clean up temporary downloads
            youtube_service.cleanup_files(video_path, thumb_path)

        # Rate-limiting delay between posts
        if idx < len(batch) and config.delay_between_posts_seconds > 0:
            console.print(f"  [dim]Waiting {config.delay_between_posts_seconds}s before next upload to protect account...[/dim]")
            time.sleep(config.delay_between_posts_seconds)

    return posted_count


def post_single_url(url: str, dry_run: bool = False) -> None:
    """Manually post a single YouTube video URL to Instagram."""
    console.print(f"[cyan]Fetching single video:[/cyan] {url}")
    try:
        details = youtube_service.get_video_details(url)
    except Exception as e:
        console.print(f"[bold red]Failed to fetch video details:[/bold red] {e}")
        return

    vid_id = details["id"]
    title = details["title"]
    desc = details["description"]
    duration = details["duration"]

    caption = format_caption(title=title, description=desc)

    console.print(f"  [bold]Title:[/bold] {title}")
    console.print(f"  [dim]Duration:[/dim] {duration}s")

    if dry_run:
        console.print(Panel(caption, title="Caption Preview", border_style="magenta"))
        return

    prev_reel = db.get_last_posted_reel()
    prev_stats = None
    if prev_reel:
        try:
            prev_stats = instagram_service.get_media_stats(
                media_id=prev_reel.get("instagram_media_id"),
                code=prev_reel.get("instagram_code"),
                url=prev_reel.get("instagram_url"),
            )
        except Exception:
            pass

    console.print("  [cyan]Downloading...[/cyan]")
    video_path, thumb_path, _ = youtube_service.download_video(url)
    try:
        console.print("  [cyan]Uploading to Instagram...[/cyan]")
        result = instagram_service.upload_reel(video_path=video_path, caption=caption, thumbnail_path=thumb_path)
        console.print(f"  [bold green]Uploaded successfully![/bold green] {result.get('url')}")
        db.record_posted(
            youtube_id=vid_id,
            title=title,
            description=desc,
            duration=duration,
            youtube_url=url,
            instagram_media_id=result.get("media_id", ""),
            instagram_code=result.get("code", ""),
            instagram_url=result.get("url", ""),
        )

        if telegram_service.is_configured():
            telegram_service.send_upload_notification(
                new_video_meta=details,
                new_reel_info=result,
                prev_reel_info=prev_reel,
                prev_stats=prev_stats,
            )
    finally:
        youtube_service.cleanup_files(video_path, thumb_path)


def cmd_watch() -> None:
    """Run continuously on interval."""
    interval_sec = config.check_interval_minutes * 60
    console.print(f"[bold green]Starting Watch Mode (checking every {config.check_interval_minutes} minutes)...[/bold green]")
    try:
        while True:
            console.print(f"\n[cyan]--- Checking at {time.strftime('%Y-%m-%d %H:%M:%S')} ---[/cyan]")
            process_unposted_videos()
            console.print(f"[dim]Sleeping for {config.check_interval_minutes} minutes... (Press Ctrl+C to stop)[/dim]")
            time.sleep(interval_sec)
    except KeyboardInterrupt:
        console.print("\n[yellow]Watch mode stopped by user.[/yellow]")


def cmd_status() -> None:
    """Show database statistics and recent posts."""
    stats = db.get_stats()
    console.print(Panel(
        f"[bold]Total Videos Posted:[/bold] {stats['posted_count']}\n"
        f"[bold]Total Videos Skipped:[/bold] {stats['skipped_count']}",
        title="Automation Status",
        border_style="green",
    ))

    recent = db.get_recent_posts(limit=10)
    if recent:
        table = Table(title="Recent Instagram Posts")
        table.add_column("YouTube ID", style="cyan")
        table.add_column("Title", style="white")
        table.add_column("Instagram Link", style="green")
        table.add_column("Posted Date", style="dim")

        for r in recent:
            table.add_row(
                r["youtube_id"],
                r["title"][:40] + ("..." if len(r["title"]) > 40 else ""),
                r["instagram_url"] or "[N/A]",
                r["posted_at"][:19] if r.get("posted_at") else "",
            )
        console.print(table)


def cmd_fetch_yt() -> None:
    """Test YouTube channel fetch without downloading."""
    videos = youtube_service.get_channel_videos()
    processed_ids = db.get_processed_ids()

    table = Table(title=f"Videos on Channel ({config.youtube_channel_url})")
    table.add_column("ID", style="cyan")
    table.add_column("Title", style="white")
    table.add_column("Status", style="bold")

    for v in videos[:15]:
        is_done = v["id"] in processed_ids
        status_text = "[green]POSTED[/green]" if is_done else "[yellow]PENDING[/yellow]"
        table.add_row(v["id"], v["title"][:50], status_text)

    console.print(table)


def cmd_mark_all_posted() -> None:
    """Mark all current YouTube videos as posted in DB."""
    videos = youtube_service.get_channel_videos()
    count = db.mark_all_as_posted(videos)
    console.print(f"[bold green]Marked {count} existing videos as posted in database.[/bold green]")


def cmd_test_login() -> None:
    """Test Instagram authentication and save session."""
    console.print("[cyan]Testing Instagram login...[/cyan]")
    try:
        ok = instagram_service.authenticate()
        if ok:
            console.print("[bold green]Instagram Login Successful! Session saved.[/bold green]")
        else:
            console.print("[bold red]Instagram Login Failed.[/bold red]")
    except Exception as e:
        console.print(f"[bold red]Login Error:[/bold red] {e}")


def cmd_export_session() -> None:
    """Export Instagram session as a Base64 string for cloud environments like Render."""
    try:
        b64_str = instagram_service.export_session_base64()
        console.print(Panel(
            "[bold green]Instagram Session Exported Successfully![/bold green]\n\n"
            "Copy the string below and paste it into your [bold cyan]Render Environment Variables[/bold cyan] under:\n"
            "[bold yellow]INSTAGRAM_SESSION_BASE64[/bold yellow]\n\n"
            f"[white]{b64_str}[/white]",
            title="Render Cloud Deployment Variable",
            border_style="green",
        ))
    except Exception as e:
        console.print(f"[bold red]Failed to export session:[/bold red] {e}")
        console.print("[yellow]Please run 'python main.py test-login' first on your local computer to authenticate and create a session.[/yellow]")


def cmd_server() -> None:
    """Run Render Web Service with health check server and background scheduler."""
    from server import start_server
    start_server()


def cmd_test_telegram() -> None:
    """Test Telegram bot connection and send a test notification."""
    console.print("[cyan]Testing Telegram Bot configuration...[/cyan]")
    res = telegram_service.test_connection()
    if res.get("ok"):
        console.print(Panel(
            f"[bold green]Telegram Bot Connected Successfully![/bold green]\n\n"
            f"Bot Username: @{res.get('bot_username')}\n"
            f"Chat ID: {res.get('chat_id')}\n\n"
            "A test message was dispatched to your Telegram app.",
            title="Telegram Status",
            border_style="green",
        ))
    else:
        console.print(Panel(
            f"[bold red]Telegram Test Failed:[/bold red]\n{res.get('error')}",
            title="Telegram Error",
            border_style="red",
        ))


def main() -> None:
    display_banner()

    parser = argparse.ArgumentParser(description="YouTube to Instagram Reels Automation")
    parser.add_argument("command", nargs="?", default="run", choices=[
        "run", "watch", "server", "dry-run", "test-login", "export-session", "test-telegram", "fetch-yt", "mark-all-posted", "status", "post-url"
    ], help="Action to execute")
    parser.add_argument("--url", help="YouTube video URL for post-url command")
    parser.add_argument("--limit", type=int, help="Override maximum videos to process")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without posting")

    args = parser.parse_args()

    if args.command == "run":
        process_unposted_videos(dry_run=args.dry_run, max_count=args.limit)
    elif args.command == "dry-run":
        process_unposted_videos(dry_run=True, max_count=args.limit)
    elif args.command == "watch":
        cmd_watch()
    elif args.command == "server":
        cmd_server()
    elif args.command == "test-login":
        cmd_test_login()
    elif args.command == "export-session":
        cmd_export_session()
    elif args.command == "test-telegram":
        cmd_test_telegram()
    elif args.command == "fetch-yt":
        cmd_fetch_yt()
    elif args.command == "mark-all-posted":
        cmd_mark_all_posted()
    elif args.command == "status":
        cmd_status()
    elif args.command == "post-url":
        if not args.url:
            console.print("[red]Please provide a video URL using --url <link>[/red]")
            return
        post_single_url(args.url, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
