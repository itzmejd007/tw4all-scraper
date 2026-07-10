# ToonWorld4All Scraper & Bot

This is a Telegram Bot and Web Scraper built for extracting, searching, and managing animated series/movies content from `toonworld4all.me`.

## Features
- **Fast Search:** Users can search for any cartoon or anime directly from the bot.
- **Dynamic Scraping:** Extracts detailed post information, episodes, ZIP files, qualities (480p, 720p, 1080p), and direct sources (Filepress, MEGA).
- **Background Auto-Scraper:** Checks the website's homepage every 30 minutes for new content and updates the MongoDB database.
- **Language Notifications:** Users can set a preferred language (e.g., `Tamil`, `Hindi`) using `/set_lang` to get instant alerts when matching content is uploaded.
- **Weekly Logs:** Admins can receive automatic weekly stat reports.

## Prerequisites
- Python 3.10+
- A MongoDB cluster

## Installation

1. **Clone the repository** and navigate to the project directory:
   ```bash
   git clone https://github.com/itzmejd007/tw4all-scraper.git
   cd tw4all-scraper
   ```

2. **Install requirements:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment:**
   Open `config.py` and ensure the following variables are set:
   - `BOT_TOKEN`: Your Telegram Bot API Token.
   - `OWNER_ID`: Your Telegram User ID.
   - `DB_URL`: Your MongoDB connection string.
   - `DB_NAME`: The name of the database to use.
   - `LOG_CHANNEL_ID`: (Optional) The channel ID for logs. Set to `None` if not used.

## Usage

1. Start the bot:
   ```bash
   python main.py
   ```
2. Open your bot on Telegram and send `/start`.
3. If you are the owner, send the command `/scrape_initial` to perform the first bulk scrape and populate your database with the latest 20 posts.

## Updating the Bot
If you add or remove features in the codebase, make sure to:
- Test changes locally first.
- Update this `README.md` reflecting the new capabilities.
- Push your changes to GitHub.
