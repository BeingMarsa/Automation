# 🚀 YouTube to Instagram Reels Automation

An automated Python bot that monitors **one specific YouTube channel** (zero YouTube login needed!) and automatically crossposts new videos/Shorts to Instagram as Reels, utilizing the YouTube video's **Title and Description** for the Instagram caption.

Includes **real-time Telegram bot alerts** that reply with the uploaded Reel link and performance statistics (views, likes, comments, shares, saves) of your previously uploaded Reel!

Ready for local running on your PC and **1-click cloud deployment on Render** (free tier supported)!

---

## 🌟 Key Highlights

- 🔓 **NO YouTube Login Required**: The bot only needs the public URL or handle of your channel (e.g. `@YourChannel/shorts`). Zero Google APIs, zero tokens, zero logins.
- 🎯 **Only Fetches That One Channel**: Strictly monitors the single YouTube channel URL specified in your configuration.
- 📲 **Instant Telegram Bot Notifications**:
  - Delivers a notification directly to your Telegram chat whenever a Reel is posted.
  - Sends the direct Instagram Reel link.
  - **Reports stats of the previous Reel**: Tracks views/plays, likes, comments, shares, and saves of the reel posted before it!
- 📝 **Title & Description Captioning**: Uses the YouTube video's title as the bold headline and description as the body, with smart word-boundary truncation (respecting Instagram's 2,200 character limit).
- 🏷️ **Hashtag Intelligence**: Preserves existing hashtags from YouTube titles/descriptions, deduplicates them, and allows adding custom hashtags.
- 🧹 **Call-to-Action Cleaning**: Automatically strips YouTube-specific lines (e.g. *"Subscribe to my channel"*, *"Click the bell icon"*) to keep Instagram captions native.
- 💾 **Duplicate Prevention (SQLite)**: Records all processed videos in SQLite so no video is ever reposted twice.
- ☁️ **Cloud Ready for Render**: Includes built-in HTTP health-check server (`server.py`), `render.yaml` blueprint, `Procfile`, `Dockerfile`, and base64 headless session exporting.

---

## 📁 Project Architecture

```
Automation/
├── .env                  # Your active configuration (channel URL, Instagram, Telegram)
├── .env.example          # Reference configuration template
├── config.py             # Strongly typed settings loader and validator
├── database.py           # SQLite persistence layer (tracks posted vs skipped videos)
├── formatter.py          # Formats YouTube title + description into Instagram captions
├── youtube_service.py    # Zero-login yt-dlp crawler and video/thumbnail downloader
├── instagram_service.py  # instagrapi client with session caching, 2FA, Reel upload, and stats fetcher
├── telegram_service.py   # Telegram bot notification and stats dispatcher
├── server.py             # Render Web Service HTTP server + background scheduler
├── main.py               # Main CLI orchestrator
├── render.yaml           # Render deployment blueprint (Infrastructure as Code)
├── Procfile              # Process manager definitions for PaaS
├── Dockerfile            # Container deployment image
└── requirements.txt      # Python dependencies
```

---

## 🤖 Telegram Bot Setup (Takes 2 Minutes)

Get notified on your phone with direct Reel links and previous Reel performance:

1. **Create your Bot**:
   - Open Telegram and search for [`@BotFather`](https://t.me/BotFather).
   - Send `/newbot` and follow the prompts to choose a name and username.
   - Copy the **HTTP API Token** (e.g. `123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ`).
2. **Find your Chat ID**:
   - Open Telegram and search for [`@userinfobot`](https://t.me/userinfobot).
   - Send `/start` and copy your numerical **Id** (e.g. `987654321`).
3. **Start a conversation with your bot**:
   - Open your newly created bot on Telegram and tap **Start** (or send `/start`).
4. **Add to `.env`**:
   ```ini
   TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ
   TELEGRAM_CHAT_ID=987654321
   ```
5. **Verify Telegram Connection**:
   ```bash
   .\.venv\Scripts\python.exe main.py test-telegram
   ```

---

### 📩 What the Telegram Notification Looks Like

```text
🚀 New Reel Uploaded to Instagram!

🎬 YouTube Title: 5 Python Automation Hacks in 2026! 🚀
🔗 Instagram Reel: https://www.instagram.com/reel/C8xYz123/
⏱ Duration: 34s

━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 Stats of Previous Reel:
📌 Title: Top AI Productivity Tools 🔥
🔗 Link: https://www.instagram.com/reel/C7aBc456/
👀 Views / Plays: 14,850
❤️ Likes: 1,230
💬 Comments: 48
🔄 Shares: 92
🔖 Saves: 215
━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## ⚡ Quick Start (Running Locally)

### 1. Configure `.env`
Open `.env` and fill in your details:
```ini
# YouTube Channel (NO LOGIN REQUIRED)
YOUTUBE_CHANNEL_URL=https://www.youtube.com/@YourChannel/shorts

# Instagram Login
INSTAGRAM_USERNAME=your_instagram_username
INSTAGRAM_PASSWORD=your_instagram_password

# Telegram Bot
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
```

### 2. Verify Connections
```bash
# Verify your YouTube channel connection (prints discovered videos)
.\.venv\Scripts\python.exe main.py fetch-yt

# Log in to Instagram once and cache session cookies (handles 2FA)
.\.venv\Scripts\python.exe main.py test-login

# Test Telegram bot notification
.\.venv\Scripts\python.exe main.py test-telegram

# Run a safe dry-run (previews video detection & caption formatting without uploading)
.\.venv\Scripts\python.exe main.py dry-run
```

### 3. Run or Watch
```bash
# Upload unposted backlog videos:
.\.venv\Scripts\python.exe main.py run

# Keep running in watch mode (checks every 60 mins):
.\.venv\Scripts\python.exe main.py watch
```

---

## ☁️ Deploying to Render (render.com)

Render allows you to run this automation 24/7 in the cloud.

### Step 1: Export Your Instagram Session Locally
On your local PC (where you already logged in with `test-login`):
```bash
.\.venv\Scripts\python.exe main.py export-session
```
Copy the Base64 string from the terminal.

### Step 2: Push Your Code to GitHub
```bash
git init
git add .
git commit -m "YouTube to Instagram automation bot with Telegram"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

### Step 3: Create Web Service on Render
1. Go to [dashboard.render.com](https://dashboard.render.com) -> **New +** -> **Web Service**.
2. Connect your GitHub repository.
3. Configure settings:
   - **Name**: `youtube-to-instagram-bot`
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python main.py server`
   - **Plan**: `Free`
4. Under **Environment Variables**, add:
   - `YOUTUBE_CHANNEL_URL`: Your channel URL (e.g. `https://www.youtube.com/@YourChannel/shorts`)
   - `INSTAGRAM_SESSION_BASE64`: The Base64 string from Step 1.
   - `TELEGRAM_BOT_TOKEN`: Your Telegram Bot Token from `@BotFather`.
   - `TELEGRAM_CHAT_ID`: Your Telegram Chat ID from `@userinfobot`.
   - `SHORTS_ONLY`: `true`
   - `CHECK_INTERVAL_MINUTES`: `60`
   - `INITIAL_SYNC_ONLY_NEW`: `true`
   - `MAX_VIDEOS_PER_RUN`: `2`
   - `DELAY_BETWEEN_POSTS_SECONDS`: `90`
5. Click **Create Web Service**!

---

## 🛠️ CLI Command Reference

| Command | Description |
|---|---|
| `python main.py run` | Scans channel and uploads unposted videos (up to batch limit) |
| `python main.py watch` | Runs locally in a continuous background loop |
| `python main.py server` | Starts Render Web Service HTTP server + background scheduler |
| `python main.py test-telegram` | Verifies Telegram Bot and sends a test message to your chat |
| `python main.py dry-run` | Simulates video detection and caption generation without uploading |
| `python main.py test-login` | Logs in to Instagram and caches session to `instagram_session.json` |
| `python main.py export-session` | Exports Instagram session as Base64 for Render cloud deployment |
| `python main.py fetch-yt` | Inspects channel videos and displays posted vs pending status |
| `python main.py mark-all-posted` | Marks all current channel videos as posted in DB (baseline) |
| `python main.py status` | Displays total posted count and recent Instagram links |
| `python main.py post-url --url <URL>` | Cross-posts a specific YouTube video immediately |
