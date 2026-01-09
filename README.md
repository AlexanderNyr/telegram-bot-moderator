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

### Chat Settings
- Enable/disable anti-spam
- Enable/disable anti-links
- Welcome messages
- Max warnings limit
- Custom messages

### Statistics
- Deleted messages
- Warnings issued
- Mutes, bans, kicks
- Blocked spam and links

### Permission System
- Global bot administrators
- Chat administrators
- Chat creator
- Protection from anonymous admin abuse

### Security
- Confirmation for sensitive actions
- Thread-safe JSON storage
- Logging system

---

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
token.txt

### 4. Add your Telegram id to 
