-- D1 schema for the Telegram moderation bot (Cloudflare Workers edition)
-- Apply with:
--   wrangler d1 execute tgmoderation --remote --file=schema.sql

CREATE TABLE IF NOT EXISTS settings (
  chat_id INTEGER PRIMARY KEY,
  data    TEXT NOT NULL DEFAULT '{}'
);

-- Per-chat trigger words
CREATE TABLE IF NOT EXISTS triggers (
  chat_id INTEGER NOT NULL,
  word    TEXT NOT NULL,
  PRIMARY KEY (chat_id, word)
);

CREATE TABLE IF NOT EXISTS warns (
  id      INTEGER PRIMARY KEY AUTOINCREMENT,
  chat_id INTEGER NOT NULL,
  user_id INTEGER NOT NULL,
  reason  TEXT,
  by_user INTEGER,
  date    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_warns_chat_user ON warns (chat_id, user_id, date);

CREATE TABLE IF NOT EXISTS stats (
  chat_id   INTEGER NOT NULL,
  stat_type TEXT NOT NULL,
  count     INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (chat_id, stat_type)
);

-- Anti-spam flood counters (one row per message, pruned by window)
CREATE TABLE IF NOT EXISTS flood (
  id      INTEGER PRIMARY KEY AUTOINCREMENT,
  chat_id INTEGER NOT NULL,
  user_id INTEGER NOT NULL,
  ts      INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_flood_chat_user_ts ON flood (chat_id, user_id, ts);

-- /confirm flow (showing the trigger list requires a triple confirmation)
CREATE TABLE IF NOT EXISTS confirmations (
  key   TEXT PRIMARY KEY,
  count INTEGER NOT NULL DEFAULT 0
);
