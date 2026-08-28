# Telegram Moderation Bot

A powerful and flexible Telegram moderation bot with advanced admin tools, anti-spam protection, trigger-word filtering, warnings system, and detailed chat statistics.

---

## Features

### Moderation
- `/warn`, `/unwarn`, `/warns`, `/clearwarns`
- `/mute`, `/unmute`
- `/ban`, `/unban`
- `/kick`

### Trigger Words
- `/addword`, `/addwords`
- `/delword`
- `/listwords`
- `/clearwords`
- Trigger lists are **per chat**: `trigger.txt` is used as the initial word list for every new chat, and `/addword`/`/delword`/`/clearwords` only affect the chat where they are used

### Chat Settings
- Enable/disable anti-spam
- Enable/disable anti-links
- Welcome messages
- Max warnings limit
- Custom messages
- Bot language: Russian/English (`/lang` in a chat or `lang.txt` for the default)

### Message filtering
- Anti-spam and anti-links also check **captions** of photos/videos/documents, not only plain text
- Anti-links detect links via Telegram entities and a wide TLD list (`.de`, `.fr`, `.pl`, etc.)
- `/mute` accepts a reason with or without a duration: `/mute 1h flooding` or reply + `/mute be polite`

### Statistics
- Deleted messages
- Warnings issued
- Mutes, bans, kicks
- Blocked spam and links

### Permission System
- Chat administrators
- Chat creator
- Protection from anonymous admin abuse

### Security
- Confirmation for sensitive actions
- Thread-safe JSON storage
- Logging system

---

## Deploy to Cloudflare Workers (free)

The repository includes a webhook-based **Cloudflare Workers edition** (JavaScript + D1) with the same commands, localization (RU/EN) and features. It runs entirely on the free tier:

- Workers Free: 100,000 requests/day (updates), 10 ms CPU per request
- D1 Free: 5 million rows read/day, 100,000 rows written/day, 5 GB storage

```bash
cd cloudflare
npx wrangler login
npx wrangler d1 create tgmoderation     # paste database_id into wrangler.toml
npx wrangler d1 execute tgmoderation --remote --file=schema.sql
npx wrangler secret put BOT_TOKEN       # token from @BotFather
npx wrangler secret put WEBHOOK_SECRET  # any random string
npx wrangler deploy
```

Then open `https://<worker-url>/setup?key=<WEBHOOK_SECRET>` once to register the Telegram webhook. Full instructions: [`cloudflare/README.md`](cloudflare/README.md).

## Installation

### 1. Clone the repository
```bash
git clone https://github.com/AlexanderNyr/telegram-bot-moderator.git
cd telegram-bot-moderator
````
### 2. Install dependencies
```bash
pip install pyTelegramBotAPI
````
### 3. Add your bot token
Paste your token from @BotFather into:
nano token.txt

### 4. Add your trigger words in trigger.txt
nano trigger.txt

### 5. Choose the bot language (optional)
The default language is Russian. To switch the whole bot to English:
```bash
echo en > lang.txt
```
Each chat can also pick its own language with the `/lang` command (chat admins only).

### 6. follow the command line instructions
If it doesn't work, let me know in issues
