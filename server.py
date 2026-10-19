"""Render Web Service & Health-Check Server.

Runs a lightweight HTTP server that binds to the Render $PORT, provides a /health
status endpoint, and runs the automated YouTube-to-Instagram scheduler in a
background thread.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

# Reconfigure stdout/stderr to UTF-8 on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from config import config
from database import db
from main import process_unposted_videos

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("render_server")

# Server state
START_TIME = time.time()
LAST_CHECK_TIME: str | None = None
LAST_RUN_RESULT: str = "Waiting for initial run"
IS_RUNNING_JOB = False


def run_automation_cycle() -> None:
    """Execute one scan and upload cycle."""
    global LAST_CHECK_TIME, LAST_RUN_RESULT, IS_RUNNING_JOB

    if IS_RUNNING_JOB:
        logger.warning("Job already running, skipping overlapping execution.")
        return

    IS_RUNNING_JOB = True
    LAST_CHECK_TIME = datetime.now().isoformat()
    logger.info("Starting automation cycle...")

    try:
        count = process_unposted_videos(dry_run=False)
        LAST_RUN_RESULT = f"Success. Processed {count} video(s)."
        logger.info(LAST_RUN_RESULT)
    except Exception as e:
        LAST_RUN_RESULT = f"Error: {e}"
        logger.error(f"Automation cycle encountered error: {e}", exc_info=True)
    finally:
        IS_RUNNING_JOB = False


def scheduler_worker() -> None:
    """Background worker that executes the check periodically."""
    logger.info(f"Scheduler worker started. Interval: {config.check_interval_minutes} minute(s).")

    # Initial run upon server boot
    time.sleep(5)  # Brief delay to allow HTTP server to bind first
    run_automation_cycle()

    interval_seconds = max(config.check_interval_minutes * 60, 60)
    while True:
        time.sleep(interval_seconds)
        run_automation_cycle()


class AutomationHTTPHandler(BaseHTTPRequestHandler):
    """HTTP request handler for Render health checks and webhooks."""

    def _send_json(self, status_code: int, data: dict[str, Any]) -> None:
        payload = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        path = self.path.split("?")[0].rstrip("/") or "/"

        if path in ("/", "/health", "/status"):
            stats = db.get_stats()
            uptime = int(time.time() - START_TIME)
            data = {
                "status": "healthy",
                "service": "YouTube to Instagram Reels Automation",
                "uptime_seconds": uptime,
                "youtube_channel": config.youtube_channel_url,
                "shorts_only": config.shorts_only,
                "interval_minutes": config.check_interval_minutes,
                "last_check_time": LAST_CHECK_TIME,
                "last_run_result": LAST_RUN_RESULT,
                "is_processing_now": IS_RUNNING_JOB,
                "stats": stats,
            }
            self._send_json(200, data)

        elif path in ("/trigger", "/run-now"):
            # Trigger immediate run in background thread
            t = threading.Thread(target=run_automation_cycle, daemon=True)
            t.start()
            self._send_json(202, {
                "status": "triggered",
                "message": "Automation cycle initiated in background.",
                "triggered_at": datetime.now().isoformat(),
            })

        elif path == "/history":
            recent = db.get_recent_posts(limit=25)
            self._send_json(200, {"recent_posts": recent})

        else:
            self._send_json(404, {"error": "Not Found", "available_endpoints": ["/health", "/trigger", "/history"]})

    def do_POST(self) -> None:
        path = self.path.split("?")[0].rstrip("/") or "/"
        if path in ("/trigger", "/run-now"):
            t = threading.Thread(target=run_automation_cycle, daemon=True)
            t.start()
            self._send_json(202, {
                "status": "triggered",
                "message": "Automation cycle initiated in background.",
                "triggered_at": datetime.now().isoformat(),
            })
        else:
            self._send_json(404, {"error": "Not Found"})

    def log_message(self, format: str, *args: Any) -> None:
        """Quiet HTTP server logging for routine health checks."""
        pass


def start_server(port: int | None = None) -> None:
    """Start the Render Web Service HTTP server and scheduler thread."""
    bind_port = port or config.port
    server_address = ("0.0.0.0", bind_port)

    logger.info(f"Binding HTTP health check server on 0.0.0.0:{bind_port}...")
    httpd = ThreadingHTTPServer(server_address, AutomationHTTPHandler)
    logger.info(f"Render Web Service is LIVE and listening on port {bind_port}!")

    # Start background scheduler
    worker_thread = threading.Thread(target=scheduler_worker, daemon=True)
    worker_thread.start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Server shutting down...")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    start_server()
