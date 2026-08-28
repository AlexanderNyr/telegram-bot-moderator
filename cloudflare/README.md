# Cloudflare Workers edition (free tier)

A webhook-based port of the Python bot (`bot.py`) to a single Cloudflare Worker
(`worker.js`, plain JavaScript, no build step) with **D1** (SQLite) storage.
Same commands, same RU/EN localization, same behaviour — including all the
bug fixes (per-chat trigger words, caption filtering, gap-tolerant `/clear`,
`/mute` with reason, triple-confirm `/listwords`, bounded durations).

Everything runs on the **free** Cloudflare plan:

| Resource | Free limit | What the bot uses |
|---|---|---|
| Workers requests | 100,000 / day | 1 per Telegram update |
| Workers CPU | 10 ms / request | a few ms at most |
| D1 rows read | 5,000,000 / day | a few per update |
| D1 rows written | 100,000 / day | ~1–3 per message |
| D1 storage | 5 GB | kilobytes for a small chat |

## Setup (5 minutes)

```bash
cd cloudflare
npx wrangler login

# 1. Create the D1 database and paste the printed database_id into wrangler.toml
npx wrangler d1 create tgmoderation

# 2. Create the tables
npx wrangler d1 execute tgmoderation --remote --file=schema.sql

# 3. Secrets
npx wrangler secret put BOT_TOKEN       # token from @BotFather
npx wrangler secret put WEBHOOK_SECRET  # any long random string, e.g. from: openssl rand -hex 24

# 4. Deploy
npx wrangler deploy
```

Then register the Telegram webhook (one click — the Worker does it for you):

```
https://<your-worker>.<your-subdomain>.workers.dev/setup?key=<WEBHOOK_SECRET>
```

or manually:

```bash
curl "https://api.telegram.org/bot<BOT_TOKEN>/setWebhook?url=https://<worker>/webhook&secret_token=<WEBHOOK_SECRET>"
```

Finally: add the bot to a group and **promote it to administrator**
(the bot reminds you itself if you forget).

## Endpoints

- `POST /webhook` — Telegram updates (verified with `X-Telegram-Bot-Api-Secret-Token`)
- `GET /setup?key=...` — registers the webhook via the Bot API
- `GET /health` — liveness probe
- `GET /` — short info

## Configuration

`wrangler.toml`:

- `DEFAULT_LANG` — `ru` (default) or `en`; per-chat override via `/lang`
- `SEED_TRIGGER_WORDS` — optional comma/newline-separated words used as the
  initial trigger list of every new chat (like `trigger.txt` in the Python version)

## Local tests

```bash
node test.mjs
```

The tests emulate D1 with a local SQLite (Node 22.5+ `node:sqlite`, or
`npm i better-sqlite3`) and mock the Telegram API. They cover per-chat
triggers, word boundaries, anti-links with captions/entities, anti-spam,
warns → auto-ban, `/mute` with reason, gap-tolerant `/clear`, the
`/listwords` → `/confirm` ×3 flow and the language switch.

## Why a separate JavaScript version?

The Python bot uses long polling and threads (`pyTelegramBotAPI`), which the
Workers runtime does not support (no sockets, no threads, 10 ms CPU).
A webhook worker is the standard way to run Telegram bots on Cloudflare;
the Python version remains for VPS/local use.
