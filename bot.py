import telebot
from telebot import types
import os
import json
import re
import time
from datetime import datetime, timedelta
from collections import defaultdict
import threading
from functools import wraps
from typing import Optional, List, Set, Dict, Any

ANONYMOUS_ADMIN_ID = 1087968824  # GroupAnonymousBot: messages sent by anonymous group admins

# ================================
# Configuration
# ================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TOKEN_PATH = os.path.join(BASE_DIR, "token.txt")
TRIGGER_PATH = os.path.join(BASE_DIR, "trigger.txt")
TRIGGERS_PATH = os.path.join(BASE_DIR, "triggers.json")  # per-chat trigger lists
LOG_PATH = os.path.join(BASE_DIR, "log.txt")
WARNS_PATH = os.path.join(BASE_DIR, "warns.json")
STATS_PATH = os.path.join(BASE_DIR, "stats.json")
SETTINGS_PATH = os.path.join(BASE_DIR, "settings.json")
LANG_PATH = os.path.join(BASE_DIR, "lang.txt")

FALLBACK_LANGUAGE = "ru"  # used when lang.txt is missing or invalid

# Default chat settings ("welcome_message"/"goodbye_message" defaults are
# localized, so they are resolved through tr() at usage time)
DEFAULT_SETTINGS = {
    "max_warns": 3,
    "warn_expire_days": 30,
    "antispam_enabled": True,
    "antispam_messages": 5,
    "antispam_seconds": 10,
    "antilink_enabled": False,
    "welcome_enabled": False,
    "goodbye_enabled": False,
}

# ================================
# Localization
# ================================
# Two interface languages are supported: Russian (ru) and English (en).
# The default language is read from lang.txt ("ru" or "en"); each chat can
# override it via /lang or the settings keyboard.
LANGUAGES: Dict[str, Dict[str, str]] = {
    "ru": {
        # Access control
        "no_access": "⛔ Нет доступа",
        "admins_only": "⛔ Только для админов",
        "groups_only": "⛔ Эта команда работает только в группах",
        "groups_only_short": "⛔ Только в группах",
        "disable_anonymity": "⛔ Отключите анонимность для этой команды",
        "creator_only": "⛔ Только для создателя чата",
        # /myid
        "myid": "🆔 Твой ID: `{id}`\n💬 ID чата: `{chat}`",
        # Help
        "help_text": (
            "🤖 *Бот модерации*\n\n"
            "📋 *Основные команды:*\n"
            "• `/addword <слово>` — добавить триггер\n"
            "• `/delword <слово>` — удалить триггер\n"
            "• `/listwords` — список триггеров\n\n"
            "👮 *Модерация:*\n"
            "• `/warn` — предупреждение\n"
            "• `/mute` — мут пользователя\n"
            "• `/ban` — бан пользователя\n"
            "• `/kick` — кик пользователя\n\n"
            "📊 `/stats` — статистика\n"
            "⚙️ `/settings` — настройки\n"
            "🌐 `/lang` — язык бота\n"
            "🆔 `/myid` — узнать свой ID\n"
            "❓ `/commands` — все команды"
        ),
        "commands_text": (
            "\n📋 *Полный список команд:*\n\n"
            "*Триггер-слова:*\n"
            "• `/addword <слово>` — добавить\n"
            "• `/addwords <слова>` — добавить несколько\n"
            "• `/delword <слово>` — удалить\n"
            "• `/listwords` — показать список\n"
            "• `/clearwords` — очистить все\n\n"
            "*Модерация пользователей:*\n"
            "• `/warn [user] [причина]` — предупреждение\n"
            "• `/unwarn [user]` — снять предупреждение\n"
            "• `/warns [user]` — список предупреждений\n"
            "• `/clearwarns [user]` — очистить предупреждения\n"
            "• `/mute [user] [время]` — мут (1h, 30m, 1d)\n"
            "• `/unmute [user]` — размут\n"
            "• `/ban [user] [причина]` — бан\n"
            "• `/unban [user_id]` — разбан\n"
            "• `/kick [user]` — кик\n\n"
            "*Информация:*\n"
            "• `/userinfo [user]` — инфо о пользователе\n"
            "• `/chatinfo` — инфо о чате\n"
            "• `/stats` — статистика модерации\n"
            "• `/myid` — ваш Telegram ID\n\n"
            "*Утилиты:*\n"
            "• `/clear <N>` — удалить N сообщений\n"
            "• `/pin` — закрепить сообщение\n"
            "• `/unpin` — открепить сообщение\n\n"
            "*Настройки:*\n"
            "• `/settings` — настройки чата\n"
            "• `/setwelcome <текст>` — текст приветствия\n"
            "• `/setgoodbye <текст>` — текст прощания\n"
            "• `/setmaxwarns <N>` — макс. предупреждений\n"
            "• `/lang` — язык бота\n"
        ),
        "commands_footer": "_Используйте reply или укажите ID пользователя_",
        # Callbacks
        "cb_error": "Ошибка обработки",
        "confirm_title": "⚠️ *Подтверждение*\n\nСлов: {count}\nПодтвердите 3 раза: /confirm",
        "stats_groups_only": "📊 Статистика доступна только в группах",
        "settings_groups_only": "⚙️ Настройки доступны только в группах",
        "antispam_name": "Анти-спам",
        "antilink_name": "Анти-ссылки",
        "welcome_name": "Приветствия",
        "goodbye_name": "Прощания",
        "toggle_on_m": "включен",
        "toggle_off_m": "выключен",
        "toggle_on_f": "включены",
        "toggle_off_f": "выключены",
        "main_menu": "🤖 Главное меню",
        # /confirm
        "confirm_not_started": "❓ Сначала запросите список слов",
        "confirm_progress": "✅ Подтверждено {count}/3",
        "triggers_empty": "📭 Список триггеров пуст",
        "triggers_file_caption": "📄 Триггер-слова ({count} шт.)",
        # Trigger word commands
        "addword_usage": "📝 Использование: `/addword <слово>`",
        "word_too_long": "⚠️ Слово слишком длинное (макс. 100 символов)",
        "word_added": "✅ Добавлено: `{word}`",
        "word_exists": "⚠️ Это слово уже в списке",
        "addwords_usage": "📝 Использование: `/addwords слово1 слово2 слово3`",
        "addwords_done": "✅ Добавлено слов: {count}",
        "delword_usage": "📝 Использование: `/delword <слово>`",
        "word_deleted": "✅ Удалено: `{word}`",
        "word_not_found": "⚠️ Слово не найдено в списке",
        "clearwords_done": "🗑️ Удалено триггер-слов: {count}",
        "listwords_confirm": "⚠️ В списке: {count} слов\nПодтвердите 3 раза: /confirm",
        # Moderation
        "warn_usage": "📝 Ответьте на сообщение или: `/warn <user_id> причина`",
        "target_admin_warn": "⚠️ Нельзя выдать предупреждение админу чата",
        "reason_not_set": "Не указана",
        "warn_header": "⚠️ *Предупреждение*\n\n👤 Пользователь: {user}\n📛 Причина: {reason}\n📊 Предупреждений: {count}/{max}",
        "warn_limit_ban": "🔨 {user} забанен (достигнут лимит предупреждений)",
        "ban_error": "❌ Ошибка бана: {error}",
        "unwarn_usage": "📝 Ответьте на сообщение или: `/unwarn <user_id>`",
        "unwarn_done": "✅ Предупреждение снято. Осталось: {count}",
        "no_warns_user": "⚠️ У пользователя нет предупреждений",
        "warns_usage": "📝 Ответьте на сообщение или: `/warns <user_id>`",
        "user_no_warns": "✅ У {user} нет предупреждений",
        "warns_list_header": "📋 *Предупреждения {user}:*\n\n",
        "clearwarns_usage": "📝 Ответьте на сообщение или: `/clearwarns <user_id>`",
        "clearwarns_done": "✅ Снято предупреждений: {count}",
        "mute_usage": "📝 Ответьте на сообщение или: `/mute <user_id> [время]`\nВремя: 1m, 1h, 1d, 1w",
        "user_not_found": "❌ Пользователь не найден",
        "target_admin_mute": "⚠️ Нельзя замутить админа чата",
        "bad_duration": "⚠️ Неверный формат времени. Примеры: 30m, 1h, 1d",
        "muted_forever": "навсегда",
        "muted": "🔇 {user} замучен на {duration}",
        "unmute_usage": "📝 Ответьте на сообщение или: `/unmute <user_id>`",
        "unmuted": "🔊 {user} размучен",
        "action_error": "❌ Ошибка: {error}",
        "ban_usage": "📝 Ответьте на сообщение или: `/ban <user_id> [причина]`",
        "target_admin_ban": "⚠️ Нельзя забанить админа чата",
        "banned": "🔨 {user} забанен",
        "ban_reason_line": "\n📛 Причина: {reason}",
        "unban_usage": "📝 Ответьте на сообщение или: `/unban <user_id>`",
        "unbanned": "✅ Пользователь `{id}` разбанен",
        "kick_usage": "📝 Ответьте на сообщение или: `/kick <user_id>`",
        "target_admin_kick": "⚠️ Нельзя кикнуть админа чата",
        "kicked": "👢 {user} кикнут",
        # Durations
        "dur_sec": "{n} сек",
        "dur_min": "{n} мин",
        "dur_hour": "{n} ч",
        "dur_day": "{n} дн",
        # /userinfo
        "userinfo_title": "👤 *Информация о пользователе*\n\n",
        "ui_name": "├ Имя: {value}",
        "ui_surname": "├ Фамилия: {value}",
        "ui_status": "├ Статус в чате: {value}",
        "ui_bot": "├ Бот: {value}",
        "ui_warns": "└ Предупреждений: {count}",
        "status_creator": "👑 Создатель",
        "status_admin": "⭐ Админ",
        "status_member": "👤 Участник",
        "status_restricted": "🔇 Ограничен",
        "status_left": "🚪 Покинул",
        "status_kicked": "🚫 Забанен",
        "yes": "Да",
        "no": "Нет",
        # /chatinfo
        "chatinfo_title": "💬 *Информация о чате*\n\n",
        "ci_title": "├ Название: {value}",
        "ci_type": "├ Тип: {value}",
        "ci_members": "└ Участников: {count}",
        # /stats
        "stats_title": "📊 *Статистика модерации*\n\n",
        "st_deleted": "├ 🗑️ Удалено сообщений: {count}",
        "st_warns": "├ ⚠️ Предупреждений: {count}",
        "st_mutes": "├ 🔇 Мутов: {count}",
        "st_bans": "├ 🔨 Банов: {count}",
        "st_kicks": "├ 👢 Киков: {count}",
        "st_spam": "├ 🔄 Заблокировано спама: {count}",
        "st_links": "└ 🔗 Заблокировано ссылок: {count}",
        # Utilities
        "clear_usage": "📝 Использование: `/clear <количество>`",
        "clear_range": "⚠️ Укажите число от 1 до 100",
        "clear_done": "🗑️ Удалено сообщений: {count}",
        "not_a_number": "⚠️ Укажите число",
        "pin_usage": "📝 Ответьте на сообщение для закрепления",
        "pinned": "📌 Сообщение закреплено",
        "unpinned": "📌 Сообщение откреплено",
        # Settings
        "settings_title": "⚙️ *Настройки чата*\n\n",
        "set_max_warns": "├ Макс. предупреждений: {value}",
        "set_antispam": "├ Анти-спам: {value}",
        "set_antilink": "├ Анти-ссылки: {value}",
        "set_welcome": "├ Приветствия: {value}",
        "set_goodbye": "├ Прощания: {value}",
        "set_language": "└ Язык: {value}",
        "setmaxwarns_usage": "📝 Использование: `/setmaxwarns <число>`",
        "setmaxwarns_range": "⚠️ Укажите число от 1 до 10",
        "setmaxwarns_done": "✅ Максимум предупреждений: {value}",
        "setwelcome_usage": "📝 Использование: `/setwelcome <текст>`\n\nПеременные:\n• `{user}` — имя пользователя\n• `{chat}` — название чата",
        "setwelcome_done": "✅ Приветствие обновлено и включено",
        "setgoodbye_usage": "📝 Использование: `/setgoodbye <текст>`\n\nПеременные:\n• `{user}` — имя пользователя\n• `{chat}` — название чата",
        "setgoodbye_done": "✅ Текст прощания обновлён и включён",
        # Language
        "lang_text": "🌐 Язык: {current}",
        "lang_set": "✅ Язык установлен: {value}",
        "kb_lang": "🌐 Язык: {value}",
        # Welcome / goodbye
        "default_welcome": "👋 Добро пожаловать, {user}!",
        "default_goodbye": "👋 {user} покинул(а) чат",
        "chat_word": "чат",
        # Message handling
        "private_hello": "👋 Привет! Я бот модерации для групп.\n\n📌 Добавьте меня в группу и дайте права администратора.\n\n/help — список команд\n/myid — узнать свой ID",
        "im_working": "✅ Работаю!",
        "spam_muted": "🔇 {user} замучен на 5 мин (спам)",
        "links_removed": "🔗 Сообщение {user} удалено (ссылки запрещены)",
        "msg_deleted": "🚫 Сообщение от {user} удалено\n📛 Причина: {censored}",
        "no_delete_rights": "⚠️ Нет прав на удаление сообщений!",
"need_admin_rights": "⚠️ Сделайте меня администратором группы (с правом удаления сообщений и блокировки), иначе модерация работать не будет",
    },
    "en": {
        # Access control
        "no_access": "⛔ No access",
        "admins_only": "⛔ Admins only",
        "groups_only": "⛔ This command works only in groups",
        "groups_only_short": "⛔ Groups only",
        "disable_anonymity": "⛔ Disable anonymity to use this command",
        "creator_only": "⛔ Chat creator only",
        # /myid
        "myid": "🆔 Your ID: `{id}`\n💬 Chat ID: `{chat}`",
        # Help
        "help_text": (
            "🤖 *Moderation bot*\n\n"
            "📋 *Basic commands:*\n"
            "• `/addword <word>` — add a trigger word\n"
            "• `/delword <word>` — remove a trigger word\n"
            "• `/listwords` — list trigger words\n\n"
            "👮 *Moderation:*\n"
            "• `/warn` — warn a user\n"
            "• `/mute` — mute a user\n"
            "• `/ban` — ban a user\n"
            "• `/kick` — kick a user\n\n"
            "📊 `/stats` — statistics\n"
            "⚙️ `/settings` — settings\n"
            "🌐 `/lang` — bot language\n"
            "🆔 `/myid` — get your ID\n"
            "❓ `/commands` — all commands"
        ),
        "commands_text": (
            "\n📋 *Full command list:*\n\n"
            "*Trigger words:*\n"
            "• `/addword <word>` — add\n"
            "• `/addwords <words>` — add several\n"
            "• `/delword <word>` — remove\n"
            "• `/listwords` — show the list\n"
            "• `/clearwords` — remove all\n\n"
            "*User moderation:*\n"
            "• `/warn [user] [reason]` — warning\n"
            "• `/unwarn [user]` — remove a warning\n"
            "• `/warns [user]` — list warnings\n"
            "• `/clearwarns [user]` — clear warnings\n"
            "• `/mute [user] [time]` — mute (1h, 30m, 1d)\n"
            "• `/unmute [user]` — unmute\n"
            "• `/ban [user] [reason]` — ban\n"
            "• `/unban [user_id]` — unban\n"
            "• `/kick [user]` — kick\n\n"
            "*Information:*\n"
            "• `/userinfo [user]` — user info\n"
            "• `/chatinfo` — chat info\n"
            "• `/stats` — moderation statistics\n"
            "• `/myid` — your Telegram ID\n\n"
            "*Utilities:*\n"
            "• `/clear <N>` — delete N messages\n"
            "• `/pin` — pin a message\n"
            "• `/unpin` — unpin a message\n\n"
            "*Settings:*\n"
            "• `/settings` — chat settings\n"
            "• `/setwelcome <text>` — welcome text\n"
            "• `/setgoodbye <text>` — farewell text\n"
            "• `/setmaxwarns <N>` — max warnings\n"
            "• `/lang` — bot language\n"
        ),
        "commands_footer": "_Use a reply or specify a user ID_",
        # Callbacks
        "cb_error": "Processing error",
        "confirm_title": "⚠️ *Confirmation*\n\nWords: {count}\nConfirm 3 times: /confirm",
        "stats_groups_only": "📊 Statistics are available only in groups",
        "settings_groups_only": "⚙️ Settings are available only in groups",
        "antispam_name": "Anti-spam",
        "antilink_name": "Anti-links",
        "welcome_name": "Welcome messages",
        "goodbye_name": "Farewell messages",
        "toggle_on_m": "enabled",
        "toggle_off_m": "disabled",
        "toggle_on_f": "enabled",
        "toggle_off_f": "disabled",
        "main_menu": "🤖 Main menu",
        # /confirm
        "confirm_not_started": "❓ Request the word list first",
        "confirm_progress": "✅ Confirmed {count}/3",
        "triggers_empty": "📭 The trigger word list is empty",
        "triggers_file_caption": "📄 Trigger words ({count})",
        # Trigger word commands
        "addword_usage": "📝 Usage: `/addword <word>`",
        "word_too_long": "⚠️ The word is too long (max. 100 characters)",
        "word_added": "✅ Added: `{word}`",
        "word_exists": "⚠️ This word is already in the list",
        "addwords_usage": "📝 Usage: `/addwords word1 word2 word3`",
        "addwords_done": "✅ Words added: {count}",
        "delword_usage": "📝 Usage: `/delword <word>`",
        "word_deleted": "✅ Removed: `{word}`",
        "word_not_found": "⚠️ Word not found in the list",
        "clearwords_done": "🗑️ Trigger words removed: {count}",
        "listwords_confirm": "⚠️ In the list: {count} words\nConfirm 3 times: /confirm",
        # Moderation
        "warn_usage": "📝 Reply to a message or: `/warn <user_id> reason`",
        "target_admin_warn": "⚠️ Cannot warn a chat admin",
        "reason_not_set": "Not specified",
        "warn_header": "⚠️ *Warning*\n\n👤 User: {user}\n📛 Reason: {reason}\n📊 Warnings: {count}/{max}",
        "warn_limit_ban": "🔨 {user} banned (warning limit reached)",
        "ban_error": "❌ Ban error: {error}",
        "unwarn_usage": "📝 Reply to a message or: `/unwarn <user_id>`",
        "unwarn_done": "✅ Warning removed. Remaining: {count}",
        "no_warns_user": "⚠️ The user has no warnings",
        "warns_usage": "📝 Reply to a message or: `/warns <user_id>`",
        "user_no_warns": "✅ {user} has no warnings",
        "warns_list_header": "📋 *Warnings for {user}:*\n\n",
        "clearwarns_usage": "📝 Reply to a message or: `/clearwarns <user_id>`",
        "clearwarns_done": "✅ Warnings removed: {count}",
        "mute_usage": "📝 Reply to a message or: `/mute <user_id> [time]`\nTime: 1m, 1h, 1d, 1w",
        "user_not_found": "❌ User not found",
        "target_admin_mute": "⚠️ Cannot mute a chat admin",
        "bad_duration": "⚠️ Invalid time format. Examples: 30m, 1h, 1d",
        "muted_forever": "forever",
        "muted": "🔇 {user} muted for {duration}",
        "unmute_usage": "📝 Reply to a message or: `/unmute <user_id>`",
        "unmuted": "🔊 {user} unmuted",
        "action_error": "❌ Error: {error}",
        "ban_usage": "📝 Reply to a message or: `/ban <user_id> [reason]`",
        "target_admin_ban": "⚠️ Cannot ban a chat admin",
        "banned": "🔨 {user} banned",
        "ban_reason_line": "\n📛 Reason: {reason}",
        "unban_usage": "📝 Reply to a message or: `/unban <user_id>`",
        "unbanned": "✅ User `{id}` unbanned",
        "kick_usage": "📝 Reply to a message or: `/kick <user_id>`",
        "target_admin_kick": "⚠️ Cannot kick a chat admin",
        "kicked": "👢 {user} kicked",
        # Durations
        "dur_sec": "{n} sec",
        "dur_min": "{n} min",
        "dur_hour": "{n} h",
        "dur_day": "{n} d",
        # /userinfo
        "userinfo_title": "👤 *User info*\n\n",
        "ui_name": "├ Name: {value}",
        "ui_surname": "├ Last name: {value}",
        "ui_status": "├ Chat status: {value}",
        "ui_bot": "├ Bot: {value}",
        "ui_warns": "└ Warnings: {count}",
        "status_creator": "👑 Creator",
        "status_admin": "⭐ Admin",
        "status_member": "👤 Member",
        "status_restricted": "🔇 Restricted",
        "status_left": "🚪 Left",
        "status_kicked": "🚫 Banned",
        "yes": "Yes",
        "no": "No",
        # /chatinfo
        "chatinfo_title": "💬 *Chat info*\n\n",
        "ci_title": "├ Title: {value}",
        "ci_type": "├ Type: {value}",
        "ci_members": "└ Members: {count}",
        # /stats
        "stats_title": "📊 *Moderation statistics*\n\n",
        "st_deleted": "├ 🗑️ Messages deleted: {count}",
        "st_warns": "├ ⚠️ Warnings issued: {count}",
        "st_mutes": "├ 🔇 Mutes: {count}",
        "st_bans": "├ 🔨 Bans: {count}",
        "st_kicks": "├ 👢 Kicks: {count}",
        "st_spam": "├ 🔄 Spam blocked: {count}",
        "st_links": "└ 🔗 Links blocked: {count}",
        # Utilities
        "clear_usage": "📝 Usage: `/clear <count>`",
        "clear_range": "⚠️ Specify a number from 1 to 100",
        "clear_done": "🗑️ Messages deleted: {count}",
        "not_a_number": "⚠️ Specify a number",
        "pin_usage": "📝 Reply to a message to pin it",
        "pinned": "📌 Message pinned",
        "unpinned": "📌 Message unpinned",
        # Settings
        "settings_title": "⚙️ *Chat settings*\n\n",
        "set_max_warns": "├ Max warnings: {value}",
        "set_antispam": "├ Anti-spam: {value}",
        "set_antilink": "├ Anti-links: {value}",
        "set_welcome": "├ Welcome messages: {value}",
        "set_goodbye": "├ Farewell messages: {value}",
        "set_language": "└ Language: {value}",
        "setmaxwarns_usage": "📝 Usage: `/setmaxwarns <number>`",
        "setmaxwarns_range": "⚠️ Specify a number from 1 to 10",
        "setmaxwarns_done": "✅ Max warnings: {value}",
        "setwelcome_usage": "📝 Usage: `/setwelcome <text>`\n\nVariables:\n• `{user}` — user name\n• `{chat}` — chat title",
        "setwelcome_done": "✅ Welcome message updated and enabled",
        "setgoodbye_usage": "📝 Usage: `/setgoodbye <text>`\n\nVariables:\n• `{user}` — user name\n• `{chat}` — chat title",
        "setgoodbye_done": "✅ Farewell message updated and enabled",
        # Language
        "lang_text": "🌐 Language: {current}",
        "lang_set": "✅ Language set: {value}",
        "kb_lang": "🌐 Language: {value}",
        # Welcome / goodbye
        "default_welcome": "👋 Welcome, {user}!",
        "default_goodbye": "👋 {user} left the chat",
        "chat_word": "chat",
        # Message handling
        "private_hello": "👋 Hi! I'm a group moderation bot.\n\n📌 Add me to a group and grant me administrator rights.\n\n/help — command list\n/myid — get your ID",
        "im_working": "✅ I'm working!",
        "spam_muted": "🔇 {user} muted for 5 min (spam)",
        "links_removed": "🔗 Message from {user} deleted (links are not allowed)",
        "msg_deleted": "🚫 Message from {user} deleted\n📛 Reason: {censored}",
        "no_delete_rights": "⚠️ Not enough rights to delete messages!",
"need_admin_rights": "⚠️ Please make me a group administrator (with rights to delete messages and ban users), otherwise moderation will not work",
    },
}

# Language names shown to users (always in the language itself)
LANG_NAMES: Dict[str, str] = {"ru": "Русский", "en": "English"}


def tr(lang: str, key: str, **kwargs) -> str:
    """Return a localized string; falls back to FALLBACK_LANGUAGE, then to the key."""
    text = LANGUAGES.get(lang, {}).get(key)
    if text is None:
        text = LANGUAGES[FALLBACK_LANGUAGE].get(key, key)
    if kwargs:
        text = text.format(**kwargs)
    return text


def load_default_language() -> str:
    """Read the default language from lang.txt ("ru" or "en")."""
    try:
        with open(LANG_PATH, "r", encoding="utf-8") as f:
            value = f.read().strip().lower()
        if value in LANGUAGES:
            return value
    except OSError:
        pass
    return FALLBACK_LANGUAGE


# ================================
# Token loading
# ================================
def load_token() -> str:
    try:
        with open(TOKEN_PATH, "r", encoding="utf-8") as f:
            token = f.read().strip()
    except FileNotFoundError:
        raise FileNotFoundError(f"❌ Token file not found: {TOKEN_PATH}")
    # FIX: clear error instead of a cryptic 401 Unauthorized from the API
    if not token or token == "PASTE_YOUR_BOT_TOKEN_HERE":
        raise ValueError(
            "❌ token.txt does not contain a bot token.\n"
            "   Get a token from @BotFather and paste it into token.txt"
        )
    return token


TOKEN = load_token()
bot = telebot.TeleBot(TOKEN, parse_mode=None)

# ================================
# JSON Storage Manager
# ================================
class JsonStorage:
    """Thread-safe JSON storage"""

    def __init__(self, filepath: str, default: Any = None):
        self.filepath = filepath
        self.default = default if default is not None else {}
        self._lock = threading.RLock()
        self._data = self._load()

    def _load(self) -> Any:
        if not os.path.exists(self.filepath):
            return self.default.copy() if isinstance(self.default, dict) else self.default
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                content = f.read().strip()
            # FIX: an empty file is not an error, fall back to defaults
            if not content:
                return self.default.copy() if isinstance(self.default, dict) else self.default
            return json.loads(content)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            print(f"⚠️ Failed to load {self.filepath}: {e}")
            return self.default.copy() if isinstance(self.default, dict) else self.default

    def _save(self) -> None:
        # FIX: atomic write (tmp + os.replace) so the file cannot be corrupted by a crash
        tmp_path = self.filepath + ".tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self.filepath)
        except Exception as e:
            print(f"❌ Failed to save {self.filepath}: {e}")
            try:
                os.remove(tmp_path)
            except OSError:
                pass

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._data.get(str(key), default)

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._data[str(key)] = value
            self._save()

    def delete(self, key: str) -> bool:
        with self._lock:
            if str(key) in self._data:
                del self._data[str(key)]
                self._save()
                return True
            return False

    def get_nested(self, *keys, default: Any = None) -> Any:
        with self._lock:
            data = self._data
            for key in keys:
                if isinstance(data, dict) and str(key) in data:
                    data = data[str(key)]
                else:
                    return default
            return data

    def set_nested(self, *keys, value: Any) -> None:
        with self._lock:
            if len(keys) < 1:
                return
            data = self._data
            for key in keys[:-1]:
                key = str(key)
                if key not in data:
                    data[key] = {}
                data = data[key]
            data[str(keys[-1])] = value
            self._save()

    def mutate(self, key: str, fn) -> Any:
        """FIX: atomic read-modify-write under a single lock"""
        with self._lock:
            result = fn(self._data.get(str(key)))
            self._data[str(key)] = result
            self._save()
            return result

    def all(self) -> dict:
        with self._lock:
            return self._data.copy()

# ================================
# Trigger word manager
# ================================
class TriggerManager:
    """Thread-safe per-chat trigger word manager.

    FIX: trigger words used to be one global list shared by every chat.
    Now every chat has its own list; the words from trigger.txt are used
    as the initial list the first time a chat is seen.
    """

    def __init__(self, filepath: str, storage_path: str):
        self.filepath = filepath  # seed words for new chats
        self._lock = threading.RLock()
        self._storage = JsonStorage(storage_path, {})
        self._seed: Set[str] = self._load_seed()
        self._words: Dict[int, Set[str]] = self._load_all()
        self._patterns: Dict[int, List[tuple]] = {}
        self._rebuild_all()

    def _load_seed(self) -> Set[str]:
        """Seed words from trigger.txt (applied to new chats)."""
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                return {line.strip().lower() for line in f if line.strip()}
        except OSError:
            return set()

    def _load_all(self) -> Dict[int, Set[str]]:
        data = {}
        for chat_id, words in self._storage.all().items():
            try:
                data[int(chat_id)] = {str(w).lower() for w in words}
            except (TypeError, ValueError):
                continue
        return data

    def _save_chat(self, chat_id: int) -> None:
        self._storage.set(chat_id, sorted(self._words.get(chat_id, ())))

    def _ensure_chat(self, chat_id: int) -> Set[str]:
        # FIX: a new chat starts from a copy of the trigger.txt seed words
        if chat_id not in self._words:
            self._words[chat_id] = set(self._seed)
            self._save_chat(chat_id)
            self._rebuild(chat_id)
        return self._words[chat_id]

    def seed_count(self) -> int:
        return len(self._seed)

    def _rebuild_all(self) -> None:
        for chat_id in self._words:
            self._rebuild(chat_id)

    def _rebuild(self, chat_id: int) -> None:
        # FIX: match on word boundaries (plain substring matching caused false
        # positives: the trigger "cat" deleted messages containing "education")
        words = self._words.get(chat_id, ())
        self._patterns[chat_id] = [
            (w, re.compile(r"(?<!\w)" + re.escape(w) + r"(?!\w)"))
            for w in words
        ]

    def add(self, chat_id: int, word: str) -> bool:
        word = word.lower().strip()
        if not word:
            return False
        with self._lock:
            words = self._ensure_chat(chat_id)
            if word in words:
                return False
            words.add(word)
            self._save_chat(chat_id)
            self._rebuild(chat_id)
            return True

    def add_many(self, chat_id: int, words: List[str]) -> int:
        added = 0
        with self._lock:
            chat_words = self._ensure_chat(chat_id)
            for word in words:
                word = word.lower().strip()
                if word and word not in chat_words:
                    chat_words.add(word)
                    added += 1
            if added:
                self._save_chat(chat_id)
                self._rebuild(chat_id)
        return added

    def remove(self, chat_id: int, word: str) -> bool:
        word = word.lower().strip()
        with self._lock:
            words = self._ensure_chat(chat_id)
            if word not in words:
                return False
            words.discard(word)
            self._save_chat(chat_id)
            self._rebuild(chat_id)
            return True

    def clear(self, chat_id: int) -> int:
        with self._lock:
            self._ensure_chat(chat_id)
            count = len(self._words[chat_id])
            self._words[chat_id].clear()
            self._save_chat(chat_id)
            self._rebuild(chat_id)
            return count

    def find_in_text(self, chat_id: int, text: str) -> List[str]:
        text_lower = text.lower()
        with self._lock:
            self._ensure_chat(chat_id)
            return [w for w, pattern in self._patterns.get(chat_id, []) if pattern.search(text_lower)]

    def get_all(self, chat_id: int) -> List[str]:
        with self._lock:
            self._ensure_chat(chat_id)
            return sorted(self._words[chat_id])

    def count(self, chat_id: int) -> int:
        with self._lock:
            self._ensure_chat(chat_id)
            return len(self._words[chat_id])

    def is_empty(self, chat_id: int) -> bool:
        with self._lock:
            self._ensure_chat(chat_id)
            return len(self._words[chat_id]) == 0

# ================================
# Anti-spam manager
# ================================
class AntiSpamManager:
    """Spam/flood protection"""

    def __init__(self):
        self._lock = threading.Lock()
        self._messages: Dict[str, List[float]] = defaultdict(list)

    def check(self, chat_id: int, user_id: int, max_messages: int, seconds: int) -> bool:
        key = f"{chat_id}:{user_id}"
        now = time.time()

        with self._lock:
            # FIX: periodic sweep of stale keys — the dict used to grow forever (memory leak)
            if len(self._messages) > 512:
                cleaned = {}
                for k, timestamps in self._messages.items():
                    fresh = [t for t in timestamps if now - t < seconds]
                    if fresh:
                        cleaned[k] = fresh
                self._messages = defaultdict(list, cleaned)

            history = [t for t in self._messages[key] if now - t < seconds]
            history.append(now)
            self._messages[key] = history
            return len(history) > max_messages

# ================================
# Warnings manager
# ================================
class WarnsManager:
    """User warning management"""

    def __init__(self, storage: JsonStorage):
        self.storage = storage

    def _active(self, chat_id: int, warns_list: Optional[List[dict]]) -> List[dict]:
        """FIX: honour the warn_expire_days setting — old warnings expire"""
        days = settings.get(chat_id, "warn_expire_days") or 0
        if days <= 0 or not warns_list:
            return warns_list or []
        limit = datetime.now() - timedelta(days=days)
        active = []
        for w in warns_list:
            try:
                if datetime.fromisoformat(w.get("date", "")) >= limit:
                    active.append(w)
            except (ValueError, TypeError):
                active.append(w)  # damaged date — keep the warning
        return active

    def add_warn(self, chat_id: int, user_id: int, reason: str, by_user_id: int) -> int:
        key = f"{chat_id}:{user_id}"
        holder = {"count": 0}

        def _add(current: Optional[List[dict]]) -> List[dict]:
            items = self._active(chat_id, current or [])
            items.append({
                "reason": reason,
                "by": by_user_id,
                "date": datetime.now().isoformat()
            })
            holder["count"] = len(items)
            return items

        # FIX: atomic under the storage lock (get/set used to race)
        self.storage.mutate(key, _add)
        return holder["count"]

    def remove_warn(self, chat_id: int, user_id: int, index: int = -1) -> bool:
        key = f"{chat_id}:{user_id}"
        holder = {"removed": False}

        def _remove(current: Optional[List[dict]]) -> List[dict]:
            items = self._active(chat_id, current or [])
            if items:
                items.pop(index)
                holder["removed"] = True
            return items

        self.storage.mutate(key, _remove)
        return holder["removed"]

    def clear_warns(self, chat_id: int, user_id: int) -> int:
        count = len(self.get_warns(chat_id, user_id))
        if count:
            self.storage.delete(f"{chat_id}:{user_id}")
        return count

    def get_warns(self, chat_id: int, user_id: int) -> List[dict]:
        raw = self.storage.get(f"{chat_id}:{user_id}", [])
        return self._active(chat_id, raw)

    def count_warns(self, chat_id: int, user_id: int) -> int:
        return len(self.get_warns(chat_id, user_id))

# ================================
# Statistics manager
# ================================
class StatsManager:
    """Moderation statistics"""

    def __init__(self, storage: JsonStorage):
        self.storage = storage

    def increment(self, chat_id: int, stat_type: str, count: int = 1) -> None:
        # FIX: atomic increment under the lock (values used to be lost in races)
        def _inc(current: Optional[dict]) -> dict:
            current = current or {}
            current[stat_type] = current.get(stat_type, 0) + count
            return current
        self.storage.mutate(str(chat_id), _inc)

    def get_stats(self, chat_id: int) -> dict:
        return self.storage.get(str(chat_id), {
            "deleted_messages": 0,
            "warns_given": 0,
            "mutes": 0,
            "bans": 0,
            "kicks": 0,
            "spam_blocked": 0,
            "links_blocked": 0
        })

# ================================
# Chat settings manager
# ================================
class SettingsManager:
    """Per-chat settings"""

    def __init__(self, storage: JsonStorage):
        self.storage = storage

    def get(self, chat_id: int, key: str) -> Any:
        chat_settings = self.storage.get(str(chat_id), {})
        return chat_settings.get(key, DEFAULT_SETTINGS.get(key))

    def set(self, chat_id: int, key: str, value: Any) -> None:
        chat_settings = self.storage.get(str(chat_id), {})
        chat_settings[key] = value
        self.storage.set(str(chat_id), chat_settings)

    def get_all(self, chat_id: int) -> dict:
        default = DEFAULT_SETTINGS.copy()
        default.update(self.storage.get(str(chat_id), {}))
        return default

    def reset(self, chat_id: int) -> None:
        self.storage.delete(str(chat_id))

# ================================
# User state manager
# ================================
class UserStateManager:
    # FIX: states are keyed by (chat_id, user_id) — the /confirm flow used
    # to leak between chats
    def __init__(self):
        self._lock = threading.Lock()
        self._states: dict = {}

    def _key(self, chat_id: int, user_id: int) -> str:
        return f"{chat_id}:{user_id}"

    def set_state(self, chat_id: int, user_id: int, state: str, data: dict = None) -> None:
        with self._lock:
            self._states[self._key(chat_id, user_id)] = {"state": state, "data": data or {}}

    def get_state(self, chat_id: int, user_id: int) -> Optional[dict]:
        with self._lock:
            return self._states.get(self._key(chat_id, user_id))

    def clear(self, chat_id: int, user_id: int) -> None:
        with self._lock:
            self._states.pop(self._key(chat_id, user_id), None)

    def start_confirmation(self, chat_id: int, user_id: int) -> None:
        self.set_state(chat_id, user_id, "confirm", {"count": 0})

    def confirm(self, chat_id: int, user_id: int) -> Optional[int]:
        with self._lock:
            state = self._states.get(self._key(chat_id, user_id))
            if not state or state["state"] != "confirm":
                return None
            state["data"]["count"] += 1
            return state["data"]["count"]

# ================================
# Manager initialization
# ================================
triggers = TriggerManager(TRIGGER_PATH, TRIGGERS_PATH)
warns_storage = JsonStorage(WARNS_PATH, {})
stats_storage = JsonStorage(STATS_PATH, {})
settings_storage = JsonStorage(SETTINGS_PATH, {})

warns = WarnsManager(warns_storage)
stats = StatsManager(stats_storage)
settings = SettingsManager(settings_storage)
antispam = AntiSpamManager()
user_states = UserStateManager()

DEFAULT_LANG = load_default_language()


def get_lang(chat_id: int) -> str:
    """Interface language for a chat: per-chat override or the global default."""
    lang = settings.get(chat_id, "language")
    return lang if lang in LANGUAGES else DEFAULT_LANG


def lang_name(lang: str) -> str:
    """Language name in its own language (Русский / English)."""
    return LANG_NAMES.get(lang, lang)

# ================================
# Logging
# ================================
_log_lock = threading.Lock()
MAX_LOG_SIZE = 5 * 1024 * 1024  # 5 MB

def write_log(text: str) -> None:
    try:
        with _log_lock:
            # FIX: simple rotation — log.txt no longer grows forever
            try:
                if os.path.exists(LOG_PATH) and os.path.getsize(LOG_PATH) > MAX_LOG_SIZE:
                    os.replace(LOG_PATH, LOG_PATH + ".old")
            except OSError:
                pass
            with open(LOG_PATH, "a", encoding="utf-8") as f:
                f.write(f"{text}\n")
    except Exception as e:
        print(f"⚠️ Failed to write log: {e}")

# ================================
# Utilities
# ================================
def md_escape(text: Any) -> str:
    """FIX: escape Markdown specials in user data (a name or reason with _ * [
    used to break replies sent with parse_mode=Markdown)"""
    return re.sub(r"([_*`\[])", r"\\\1", str(text))

def censor_word(word: str) -> str:
    length = len(word)
    if length <= 1:
        return "*"
    if length == 2:
        return word[0] + "*"
    return word[0] + "*" * (length - 2) + word[-1]

def is_chat_admin(chat_id: int, user_id: int) -> bool:
    """Checks whether the user is an admin of the CHAT"""
    try:
        member = bot.get_chat_member(chat_id, user_id)
        return member.status in ("creator", "administrator")
    except Exception:
        return False

def can_moderate(chat_id: int, user_id: int) -> bool:
    """Moderator rights: anonymous group admin, chat admin or chat creator"""
    if user_id == ANONYMOUS_ADMIN_ID:
        return True
    return is_chat_admin(chat_id, user_id)

def is_creator(chat_id: int, user_id: int) -> bool:
    try:
        member = bot.get_chat_member(chat_id, user_id)
        return member.status == "creator"
    except Exception:
        return False

def is_private(message) -> bool:
    return message.chat.type == "private"

def is_group(message) -> bool:
    return message.chat.type in ("group", "supergroup")

def get_user_display(user) -> str:
    if user.username:
        return f"@{user.username}"
    return user.first_name or f"ID:{user.id}"

def parse_duration(text: str) -> Optional[int]:
    match = re.match(r'^(\d+)([mhdw])$', text.lower())
    if not match:
        return None
    value = int(match.group(1))
    unit = match.group(2)
    multipliers = {'m': 60, 'h': 3600, 'd': 86400, 'w': 604800}
    seconds = value * multipliers.get(unit, 60)
    # FIX: reject zero durations ("0m" used to "mute" for 0 seconds) and
    # values Telegram cannot accept (until_date must be under ~366 days)
    if seconds < 60 or seconds > 365 * 86400:
        return None
    return seconds

def format_duration(seconds: int, lang: str) -> str:
    if seconds < 60:
        return tr(lang, "dur_sec", n=seconds)
    if seconds < 3600:
        return tr(lang, "dur_min", n=seconds // 60)
    if seconds < 86400:
        return tr(lang, "dur_hour", n=seconds // 3600)
    return tr(lang, "dur_day", n=seconds // 86400)

def extract_user_from_message(message) -> tuple:
    """Extracts the target user from a reply or command arguments"""
    # From a reply
    if message.reply_to_message and message.reply_to_message.from_user:
        parts = message.text.split(maxsplit=2) if message.text else []
        reason = parts[1] if len(parts) > 1 else None
        return message.reply_to_message.from_user, reason

    parts = message.text.split(maxsplit=2) if message.text else []
    if len(parts) < 2:
        return None, None

    user_arg = parts[1]
    reason = parts[2] if len(parts) > 2 else None

    # By numeric ID
    if user_arg.isdigit():
        try:
            member = bot.get_chat_member(message.chat.id, int(user_arg))
            return member.user, reason
        except Exception:
            pass

    # By @username — strip the @ if present
    if user_arg.startswith("@"):
        user_arg = user_arg[1:]

    # Try text_mention entities (a mention of a user without @username).
    # A plain @username cannot be resolved: the Bot API has no way to look up
    # a user ID by username.
    if message.entities:
        for entity in message.entities:
            if entity.type == "text_mention" and entity.user:
                return entity.user, reason

    return None, reason

LINK_TLDS = (
    # FIX: a much wider curated TLD list (the old short list was bypassed
    # with e.g. .de, .fr or .pl links)
    "com", "net", "org", "ru", "su", "ua", "by", "kz", "io", "me", "info",
    "biz", "xyz", "top", "site", "online", "store", "app", "dev", "pro",
    "tv", "рф",
    "de", "fr", "it", "es", "pl", "nl", "se", "cz", "sk", "fi", "no", "dk",
    "pt", "gr", "ro", "bg", "hu", "at", "ch", "be", "lt", "lv", "ee", "md",
    "ge", "am", "az", "uz", "tj", "tm", "kg", "il", "tr", "cn", "jp", "kr",
    "in", "id", "th", "vn", "ph", "my", "sg", "hk", "tw", "br", "ar", "cl",
    "co", "mx", "pe", "ve", "ca", "us", "uk", "au", "nz", "za", "ng", "eg",
    "ma", "club", "life", "live", "world", "today", "email", "link", "icu",
    "cam", "fun", "pw", "cc", "ws", "fm", "ai", "tech", "space", "vip", "one",
)

LINK_PATTERNS = [
    r'https?://\S+',
    r'tg://\S+',
    r'(?<![\w.])www\.\S+',
    r'(?<![\w.])t\.me/\S+',
    r'(?<![\w.])telegram\.me/\S+',
    r'(?<![\w.])telegram\.dog/\S+',
    r'(?<![\w.])joinchat\.to/\S+',
    # a domain without a protocol, including subdomains: site.ru, sub.site.online, etc.
    r'(?:(?<=\s)|^)(?:[a-z0-9-]+\.)+(?:' + "|".join(sorted(LINK_TLDS)) + r')(?![\w-])',
]

def has_links(text: str) -> bool:
    # FIX: extended pattern list (it used to be bypassed via "www.", "tg://",
    # a bare domain, and telegram.dog)
    for pattern in LINK_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False

def message_has_link_entities(message) -> bool:
    """FIX: detect links via Telegram entities as well — covers captions and
    inline links (text_link) that the plain-text regex cannot see."""
    for entities in (message.entities, message.caption_entities):
        if not entities:
            continue
        for entity in entities:
            if entity.type in ("url", "text_link"):
                return True
    return False

# ================================
# ChatPermissions helpers
# ================================
def get_mute_permissions() -> types.ChatPermissions:
    """Builds ChatPermissions for muting (compatible with different API versions)"""
    try:
        # Newer API (Bot API 6.3+)
        return types.ChatPermissions(
            can_send_messages=False,
            can_send_audios=False,
            can_send_documents=False,
            can_send_photos=False,
            can_send_videos=False,
            can_send_video_notes=False,
            can_send_voice_notes=False,
            can_send_polls=False,
            can_send_other_messages=False,
            can_add_web_page_previews=False,
            can_change_info=False,
            can_invite_users=False,
            can_pin_messages=False,
            can_manage_topics=False
        )
    except TypeError:
        # Older API
        return types.ChatPermissions(
            can_send_messages=False,
            can_send_media_messages=False,
            can_send_other_messages=False,
            can_add_web_page_previews=False
        )

def get_unmute_permissions() -> types.ChatPermissions:
    """Builds ChatPermissions for unmuting (compatible with different API versions)"""
    try:
        # Newer API (Bot API 6.3+)
        return types.ChatPermissions(
            can_send_messages=True,
            can_send_audios=True,
            can_send_documents=True,
            can_send_photos=True,
            can_send_videos=True,
            can_send_video_notes=True,
            can_send_voice_notes=True,
            can_send_polls=True,
            can_send_other_messages=True,
            can_add_web_page_previews=True,
            can_change_info=False,
            can_invite_users=True,
            can_pin_messages=False,
            can_manage_topics=False
        )
    except TypeError:
        # Older API
        return types.ChatPermissions(
            can_send_messages=True,
            can_send_media_messages=True,
            can_send_other_messages=True,
            can_add_web_page_previews=True
        )

# ================================
# Decorators
# ================================
def admin_only(func):
    """For chat admins (including anonymous group admins)"""
    @wraps(func)
    def wrapper(message, *args, **kwargs):
        user_id = message.from_user.id
        lang = get_lang(message.chat.id)

        # Anonymous group admin — definitely a chat admin
        if user_id == ANONYMOUS_ADMIN_ID:
            return func(message, *args, **kwargs)

        # Moderation commands are unavailable in private chats
        if is_private(message):
            bot.reply_to(message, tr(lang, "no_access"))
            return

        # Chat admin
        if is_chat_admin(message.chat.id, user_id):
            return func(message, *args, **kwargs)

        bot.reply_to(message, tr(lang, "admins_only"))
    return wrapper

def creator_only(func):
    """For the chat creator only"""
    @wraps(func)
    def wrapper(message, *args, **kwargs):
        user_id = message.from_user.id
        lang = get_lang(message.chat.id)

        # Anonymous — cannot verify creator status
        if user_id == ANONYMOUS_ADMIN_ID:
            bot.reply_to(message, tr(lang, "disable_anonymity"))
            return

        if is_private(message):
            bot.reply_to(message, tr(lang, "groups_only_short"))
            return

        if is_creator(message.chat.id, user_id):
            return func(message, *args, **kwargs)

        bot.reply_to(message, tr(lang, "creator_only"))
    return wrapper

def group_only(func):
    @wraps(func)
    def wrapper(message, *args, **kwargs):
        lang = get_lang(message.chat.id)
        if is_group(message):
            return func(message, *args, **kwargs)
        bot.reply_to(message, tr(lang, "groups_only"))
    return wrapper

# ================================
# Keyboards
# ================================
def get_main_keyboard(lang: str) -> types.InlineKeyboardMarkup:
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    if lang == "en":
        keyboard.add(
            types.InlineKeyboardButton("➕ Add word", callback_data="help_add"),
            types.InlineKeyboardButton("➖ Remove word", callback_data="help_del"),
            types.InlineKeyboardButton("📄 Word list", callback_data="list_words"),
            types.InlineKeyboardButton("📊 Statistics", callback_data="show_stats"),
            types.InlineKeyboardButton("⚙️ Settings", callback_data="show_settings"),
            types.InlineKeyboardButton("❓ All commands", callback_data="all_commands")
        )
    else:
        keyboard.add(
            types.InlineKeyboardButton("➕ Добавить слово", callback_data="help_add"),
            types.InlineKeyboardButton("➖ Удалить слово", callback_data="help_del"),
            types.InlineKeyboardButton("📄 Список слов", callback_data="list_words"),
            types.InlineKeyboardButton("📊 Статистика", callback_data="show_stats"),
            types.InlineKeyboardButton("⚙️ Настройки", callback_data="show_settings"),
            types.InlineKeyboardButton("❓ Все команды", callback_data="all_commands")
        )
    return keyboard

def get_lang_keyboard() -> types.InlineKeyboardMarkup:
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("🇷🇺 Русский", callback_data="set_lang:ru"),
        types.InlineKeyboardButton("🇬🇧 English", callback_data="set_lang:en")
    )
    return keyboard

def get_settings_keyboard(chat_id: int) -> types.InlineKeyboardMarkup:
    lang = get_lang(chat_id)
    keyboard = types.InlineKeyboardMarkup(row_width=1)

    antispam_status = "✅" if settings.get(chat_id, "antispam_enabled") else "❌"
    antilink_status = "✅" if settings.get(chat_id, "antilink_enabled") else "❌"
    welcome_status = "✅" if settings.get(chat_id, "welcome_enabled") else "❌"
    goodbye_status = "✅" if settings.get(chat_id, "goodbye_enabled") else "❌"

    keyboard.add(
        types.InlineKeyboardButton(f"🔄 {tr(lang, 'antispam_name')}: {antispam_status}", callback_data="toggle_antispam"),
        types.InlineKeyboardButton(f"🔗 {tr(lang, 'antilink_name')}: {antilink_status}", callback_data="toggle_antilink"),
        types.InlineKeyboardButton(f"👋 {tr(lang, 'welcome_name')}: {welcome_status}", callback_data="toggle_welcome"),
        types.InlineKeyboardButton(f"🚪 {tr(lang, 'goodbye_name')}: {goodbye_status}", callback_data="toggle_goodbye"),
        types.InlineKeyboardButton(tr(lang, "kb_lang", value=lang_name(lang)), callback_data="cycle_lang"),
        types.InlineKeyboardButton("🔙 " + ("Back" if lang == "en" else "Назад"), callback_data="back_main")
    )
    return keyboard

# ================================
# /myid
# ================================
@bot.message_handler(commands=["myid"])
def cmd_myid(message):
    """Get your Telegram ID"""
    lang = get_lang(message.chat.id)
    bot.reply_to(
        message,
        tr(lang, "myid", id=message.from_user.id, chat=message.chat.id),
        parse_mode="Markdown"
    )

# ================================
# /start and /help
# ================================
@bot.message_handler(commands=["start", "help"])
def cmd_help(message):
    lang = get_lang(message.chat.id)
    bot.send_message(
        message.chat.id,
        tr(lang, "help_text"),
        parse_mode="Markdown",
        # the keyboard only makes sense in groups
        reply_markup=get_main_keyboard(lang) if is_group(message) else None
    )

# ================================
# All commands
# ================================
@bot.message_handler(commands=["commands"])
def cmd_all_commands(message):
    lang = get_lang(message.chat.id)
    text = tr(lang, "commands_text") + tr(lang, "commands_footer")
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

# ================================
# Language selection
# ================================
@bot.message_handler(commands=["lang"])
@group_only
@admin_only
def cmd_lang(message):
    lang = get_lang(message.chat.id)
    bot.send_message(
        message.chat.id,
        tr(lang, "lang_text", current=lang_name(lang)),
        reply_markup=get_lang_keyboard()
    )

# ================================
# Callback handler
# ================================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    lang = get_lang(chat_id)

    # Permission check: chat admin (including the anonymous group admin)
    if is_private(call.message):
        has_access = False
    else:
        has_access = can_moderate(chat_id, user_id)

    if not has_access:
        bot.answer_callback_query(call.id, tr(lang, "no_access"), show_alert=True)
        return

    try:
        if call.data == "help_add":
            bot.answer_callback_query(call.id)
            bot.send_message(chat_id, tr(lang, "addword_usage"), parse_mode="Markdown")

        elif call.data == "help_del":
            bot.answer_callback_query(call.id)
            bot.send_message(chat_id, tr(lang, "delword_usage"), parse_mode="Markdown")

        elif call.data == "list_words":
            bot.answer_callback_query(call.id)
            user_states.start_confirmation(chat_id, user_id)
            bot.send_message(
                chat_id,
                tr(lang, "confirm_title", count=triggers.count(chat_id)),
                parse_mode="Markdown"
            )

        elif call.data == "show_stats":
            bot.answer_callback_query(call.id)
            if is_group(call.message):
                send_stats(chat_id)
            else:
                bot.send_message(chat_id, tr(lang, "stats_groups_only"))

        elif call.data == "show_settings":
            bot.answer_callback_query(call.id)
            if is_group(call.message):
                bot.send_message(
                    chat_id,
                    tr(lang, "settings_title"),
                    parse_mode="Markdown",
                    reply_markup=get_settings_keyboard(chat_id)
                )
            else:
                bot.send_message(chat_id, tr(lang, "settings_groups_only"))

        elif call.data == "toggle_antispam":
            current = settings.get(chat_id, "antispam_enabled")
            settings.set(chat_id, "antispam_enabled", not current)
            status = tr(lang, "toggle_on_m") if not current else tr(lang, "toggle_off_m")
            bot.answer_callback_query(call.id, f"{tr(lang, 'antispam_name')} {status}")
            bot.edit_message_reply_markup(
                chat_id, call.message.message_id,
                reply_markup=get_settings_keyboard(chat_id)
            )

        elif call.data == "toggle_antilink":
            current = settings.get(chat_id, "antilink_enabled")
            settings.set(chat_id, "antilink_enabled", not current)
            status = tr(lang, "toggle_on_m") if not current else tr(lang, "toggle_off_m")
            bot.answer_callback_query(call.id, f"{tr(lang, 'antilink_name')} {status}")
            bot.edit_message_reply_markup(
                chat_id, call.message.message_id,
                reply_markup=get_settings_keyboard(chat_id)
            )

        elif call.data == "toggle_welcome":
            current = settings.get(chat_id, "welcome_enabled")
            settings.set(chat_id, "welcome_enabled", not current)
            status = tr(lang, "toggle_on_f") if not current else tr(lang, "toggle_off_f")
            bot.answer_callback_query(call.id, f"{tr(lang, 'welcome_name')} {status}")
            bot.edit_message_reply_markup(
                chat_id, call.message.message_id,
                reply_markup=get_settings_keyboard(chat_id)
            )

        elif call.data == "toggle_goodbye":
            current = settings.get(chat_id, "goodbye_enabled")
            settings.set(chat_id, "goodbye_enabled", not current)
            status = tr(lang, "toggle_on_f") if not current else tr(lang, "toggle_off_f")
            bot.answer_callback_query(call.id, f"{tr(lang, 'goodbye_name')} {status}")
            bot.edit_message_reply_markup(
                chat_id, call.message.message_id,
                reply_markup=get_settings_keyboard(chat_id)
            )

        elif call.data == "cycle_lang":
            new_lang = "en" if lang == "ru" else "ru"
            settings.set(chat_id, "language", new_lang)
            bot.answer_callback_query(call.id, tr(new_lang, "lang_set", value=lang_name(new_lang)))
            bot.edit_message_reply_markup(
                chat_id, call.message.message_id,
                reply_markup=get_settings_keyboard(chat_id)
            )

        elif call.data in ("set_lang:ru", "set_lang:en"):
            new_lang = call.data.split(":")[1]
            settings.set(chat_id, "language", new_lang)
            bot.answer_callback_query(call.id, tr(new_lang, "lang_set", value=lang_name(new_lang)))
            try:
                bot.edit_message_text(
                    tr(new_lang, "lang_text", current=lang_name(new_lang)),
                    chat_id, call.message.message_id,
                    reply_markup=get_lang_keyboard()
                )
            except Exception:
                pass

        elif call.data == "back_main":
            bot.answer_callback_query(call.id)
            bot.edit_message_text(
                tr(lang, "main_menu"),
                chat_id, call.message.message_id,
                reply_markup=get_main_keyboard(lang)
            )

        elif call.data == "all_commands":
            bot.answer_callback_query(call.id)
            cmd_all_commands(call.message)

    except Exception as e:
        print(f"❌ Callback error: {e}")
        bot.answer_callback_query(call.id, tr(lang, "cb_error"))

# ================================
# /confirm
# ================================
@bot.message_handler(commands=["confirm"])
def cmd_confirm(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    lang = get_lang(chat_id)

    count = user_states.confirm(chat_id, user_id)

    if count is None:
        bot.reply_to(message, tr(lang, "confirm_not_started"))
        return

    if count < 3:
        bot.reply_to(message, tr(lang, "confirm_progress", count=count))
        return

    words = triggers.get_all(chat_id)

    if not words:
        bot.send_message(chat_id, tr(lang, "triggers_empty"))
        user_states.clear(chat_id, user_id)
        return

    temp_file = os.path.join(BASE_DIR, f"triggers_{user_id}.txt")

    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write("\n".join(words))

        with open(temp_file, "rb") as f:
            bot.send_document(chat_id, f, caption=tr(lang, "triggers_file_caption", count=len(words)))
    finally:
        if os.path.exists(temp_file):
            os.remove(temp_file)
        user_states.clear(chat_id, user_id)

# ================================
# Trigger word commands
# ================================
@bot.message_handler(commands=["addword"])
@admin_only
def cmd_addword(message):
    lang = get_lang(message.chat.id)
    parts = message.text.split(maxsplit=1) if message.text else []
    if len(parts) < 2:
        bot.reply_to(message, tr(lang, "addword_usage"), parse_mode="Markdown")
        return

    word = parts[1].strip()
    if len(word) > 100:
        bot.reply_to(message, tr(lang, "word_too_long"))
        return

    if triggers.add(message.chat.id, word):
        bot.reply_to(message, tr(lang, "word_added", word=md_escape(word.lower())), parse_mode="Markdown")
    else:
        bot.reply_to(message, tr(lang, "word_exists"))

@bot.message_handler(commands=["addwords"])
@admin_only
def cmd_addwords(message):
    lang = get_lang(message.chat.id)
    parts = message.text.split()[1:] if message.text else []
    if not parts:
        bot.reply_to(message, tr(lang, "addwords_usage"), parse_mode="Markdown")
        return

    added = triggers.add_many(message.chat.id, parts)
    bot.reply_to(message, tr(lang, "addwords_done", count=added))

@bot.message_handler(commands=["delword"])
@admin_only
def cmd_delword(message):
    lang = get_lang(message.chat.id)
    parts = message.text.split(maxsplit=1) if message.text else []
    if len(parts) < 2:
        bot.reply_to(message, tr(lang, "delword_usage"), parse_mode="Markdown")
        return

    word = parts[1].strip()
    if triggers.remove(message.chat.id, word):
        bot.reply_to(message, tr(lang, "word_deleted", word=md_escape(word.lower())), parse_mode="Markdown")
    else:
        bot.reply_to(message, tr(lang, "word_not_found"))

@bot.message_handler(commands=["clearwords"])
@creator_only
def cmd_clearwords(message):
    lang = get_lang(message.chat.id)
    count = triggers.clear(message.chat.id)
    bot.reply_to(message, tr(lang, "clearwords_done", count=count))

@bot.message_handler(commands=["listwords"])
@admin_only
def cmd_listwords(message):
    lang = get_lang(message.chat.id)
    user_states.start_confirmation(message.chat.id, message.from_user.id)
    bot.send_message(
        message.chat.id,
        tr(lang, "listwords_confirm", count=triggers.count(message.chat.id))
    )

# ================================
# Moderation: /warn, /unwarn, /warns
# ================================
@bot.message_handler(commands=["warn"])
@group_only
@admin_only
def cmd_warn(message):
    lang = get_lang(message.chat.id)
    user, reason = extract_user_from_message(message)

    if not user:
        bot.reply_to(message, tr(lang, "warn_usage"), parse_mode="Markdown")
        return

    if user.id == ANONYMOUS_ADMIN_ID or is_chat_admin(message.chat.id, user.id):
        bot.reply_to(message, tr(lang, "target_admin_warn"))
        return

    reason = reason or tr(lang, "reason_not_set")
    count = warns.add_warn(message.chat.id, user.id, reason, message.from_user.id)
    max_warns = settings.get(message.chat.id, "max_warns")

    stats.increment(message.chat.id, "warns_given")

    text = tr(
        lang, "warn_header",
        user=md_escape(get_user_display(user)),
        reason=md_escape(reason),
        count=count, max=max_warns
    )

    bot.send_message(message.chat.id, text, parse_mode="Markdown")

    if count >= max_warns:
        try:
            bot.ban_chat_member(message.chat.id, user.id)
            bot.send_message(
                message.chat.id,
                tr(lang, "warn_limit_ban", user=get_user_display(user))
            )
            stats.increment(message.chat.id, "bans")
        except Exception as e:
            bot.send_message(message.chat.id, tr(lang, "ban_error", error=e))

@bot.message_handler(commands=["unwarn"])
@group_only
@admin_only
def cmd_unwarn(message):
    lang = get_lang(message.chat.id)
    user, _ = extract_user_from_message(message)

    if not user:
        bot.reply_to(message, tr(lang, "unwarn_usage"), parse_mode="Markdown")
        return

    if warns.remove_warn(message.chat.id, user.id):
        count = warns.count_warns(message.chat.id, user.id)
        bot.reply_to(message, tr(lang, "unwarn_done", count=count))
    else:
        bot.reply_to(message, tr(lang, "no_warns_user"))

@bot.message_handler(commands=["warns"])
@group_only
@admin_only
def cmd_warns(message):
    lang = get_lang(message.chat.id)
    user, _ = extract_user_from_message(message)

    if not user:
        bot.reply_to(message, tr(lang, "warns_usage"), parse_mode="Markdown")
        return

    user_warns = warns.get_warns(message.chat.id, user.id)

    if not user_warns:
        bot.reply_to(message, tr(lang, "user_no_warns", user=get_user_display(user)))
        return

    text = tr(lang, "warns_list_header", user=md_escape(get_user_display(user)))
    for i, w in enumerate(user_warns, 1):
        date = datetime.fromisoformat(w['date']).strftime("%d.%m.%Y")
        text += f"{i}. {md_escape(w['reason'])} ({date})\n"

    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(commands=["clearwarns"])
@group_only
@admin_only
def cmd_clearwarns(message):
    lang = get_lang(message.chat.id)
    user, _ = extract_user_from_message(message)

    if not user:
        bot.reply_to(message, tr(lang, "clearwarns_usage"), parse_mode="Markdown")
        return

    count = warns.clear_warns(message.chat.id, user.id)
    bot.reply_to(message, tr(lang, "clearwarns_done", count=count))

# ================================
# Moderation: /mute, /unmute
# ================================
@bot.message_handler(commands=["mute"])
@group_only
@admin_only
def cmd_mute(message):
    lang = get_lang(message.chat.id)
    parts = message.text.split() if message.text else []

    if message.reply_to_message and message.reply_to_message.from_user:
        user = message.reply_to_message.from_user
        rest = parts[1:]
    else:
        if len(parts) < 2:
            bot.reply_to(message, tr(lang, "mute_usage"), parse_mode="Markdown")
            return
        user, _ = extract_user_from_message(message)
        rest = parts[2:]

    if not user:
        bot.reply_to(message, tr(lang, "user_not_found"))
        return

    if user.id == ANONYMOUS_ADMIN_ID or is_chat_admin(message.chat.id, user.id):
        bot.reply_to(message, tr(lang, "target_admin_mute"))
        return

    # FIX: the first argument is a duration only when it looks like one
    # (\d+[mhdw]); with or without a duration the remaining text is the reason
    duration = None
    reason = None
    if rest and re.match(r'^\d+[mhdw]$', rest[0].lower()):
        duration = parse_duration(rest[0])
        if not duration:
            bot.reply_to(message, tr(lang, "bad_duration"))
            return
        reason = " ".join(rest[1:]) or None
    elif rest:
        reason = " ".join(rest) or None

    if duration:
        until_date = datetime.now() + timedelta(seconds=duration)
        duration_text = format_duration(duration, lang)
    else:
        until_date = None
        duration_text = tr(lang, "muted_forever")

    try:
        bot.restrict_chat_member(
            message.chat.id,
            user.id,
            until_date=until_date,
            permissions=get_mute_permissions()
        )

        text = tr(lang, "muted", user=get_user_display(user), duration=duration_text)
        if reason:
            text += tr(lang, "ban_reason_line", reason=reason)

        bot.send_message(message.chat.id, text)
        stats.increment(message.chat.id, "mutes")

    except Exception as e:
        bot.reply_to(message, tr(lang, "action_error", error=e))


@bot.message_handler(commands=["unmute"])
@group_only
@admin_only
def cmd_unmute(message):
    lang = get_lang(message.chat.id)
    user, _ = extract_user_from_message(message)

    if not user:
        bot.reply_to(message, tr(lang, "unmute_usage"), parse_mode="Markdown")
        return

    try:
        bot.restrict_chat_member(
            message.chat.id,
            user.id,
            permissions=get_unmute_permissions()
        )
        bot.reply_to(message, tr(lang, "unmuted", user=get_user_display(user)))

    except Exception as e:
        bot.reply_to(message, tr(lang, "action_error", error=e))

# ================================
# Moderation: /ban, /unban, /kick
# ================================
@bot.message_handler(commands=["ban"])
@group_only
@admin_only
def cmd_ban(message):
    lang = get_lang(message.chat.id)
    user, reason = extract_user_from_message(message)

    if not user:
        bot.reply_to(message, tr(lang, "ban_usage"), parse_mode="Markdown")
        return

    if user.id == ANONYMOUS_ADMIN_ID or is_chat_admin(message.chat.id, user.id):
        bot.reply_to(message, tr(lang, "target_admin_ban"))
        return

    try:
        bot.ban_chat_member(message.chat.id, user.id)

        text = tr(lang, "banned", user=get_user_display(user))
        if reason:
            text += tr(lang, "ban_reason_line", reason=reason)

        bot.send_message(message.chat.id, text)
        stats.increment(message.chat.id, "bans")

    except Exception as e:
        bot.reply_to(message, tr(lang, "action_error", error=e))

@bot.message_handler(commands=["unban"])
@group_only
@admin_only
def cmd_unban(message):
    lang = get_lang(message.chat.id)
    # Works like the other commands: reply, user ID or text_mention
    user, _ = extract_user_from_message(message)

    if not user:
        bot.reply_to(message, tr(lang, "unban_usage"), parse_mode="Markdown")
        return

    try:
        bot.unban_chat_member(message.chat.id, user.id, only_if_banned=True)
        bot.reply_to(message, tr(lang, "unbanned", id=user.id), parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, tr(lang, "action_error", error=e))

@bot.message_handler(commands=["kick"])
@group_only
@admin_only
def cmd_kick(message):
    lang = get_lang(message.chat.id)
    user, _ = extract_user_from_message(message)

    if not user:
        bot.reply_to(message, tr(lang, "kick_usage"), parse_mode="Markdown")
        return

    if user.id == ANONYMOUS_ADMIN_ID or is_chat_admin(message.chat.id, user.id):
        bot.reply_to(message, tr(lang, "target_admin_kick"))
        return

    try:
        bot.ban_chat_member(message.chat.id, user.id)
        bot.unban_chat_member(message.chat.id, user.id)

        bot.send_message(message.chat.id, tr(lang, "kicked", user=get_user_display(user)))
        stats.increment(message.chat.id, "kicks")

    except Exception as e:
        bot.reply_to(message, tr(lang, "action_error", error=e))

# ================================
# Information
# ================================
@bot.message_handler(commands=["userinfo"])
@group_only
@admin_only
def cmd_userinfo(message):
    lang = get_lang(message.chat.id)
    user, _ = extract_user_from_message(message)

    if not user:
        user = message.from_user

    try:
        member = bot.get_chat_member(message.chat.id, user.id)

        status_map = {
            "creator": tr(lang, "status_creator"),
            "administrator": tr(lang, "status_admin"),
            "member": tr(lang, "status_member"),
            "restricted": tr(lang, "status_restricted"),
            "left": tr(lang, "status_left"),
            "kicked": tr(lang, "status_kicked")
        }

        user_warns_count = warns.count_warns(message.chat.id, user.id)

        text = (
            tr(lang, "userinfo_title") +
            f"├ ID: `{user.id}`\n" +
            tr(lang, "ui_name", value=md_escape(user.first_name or 'N/A')) + "\n" +
            tr(lang, "ui_surname", value=md_escape(user.last_name or 'N/A')) + "\n" +
            f"├ Username: @{md_escape(user.username or 'N/A')}\n" +
            tr(lang, "ui_status", value=status_map.get(member.status, member.status)) + "\n" +
            tr(lang, "ui_bot", value=tr(lang, "yes") if user.is_bot else tr(lang, "no")) + "\n" +
            tr(lang, "ui_warns", count=user_warns_count)
        )

        bot.send_message(message.chat.id, text, parse_mode="Markdown")

    except Exception as e:
        bot.reply_to(message, tr(lang, "action_error", error=e))

@bot.message_handler(commands=["chatinfo"])
@group_only
def cmd_chatinfo(message):
    lang = get_lang(message.chat.id)
    chat = message.chat

    try:
        member_count = bot.get_chat_member_count(chat.id)

        text = (
            tr(lang, "chatinfo_title") +
            f"├ ID: `{chat.id}`\n" +
            tr(lang, "ci_title", value=chat.title) + "\n" +
            tr(lang, "ci_type", value=chat.type) + "\n" +
            f"├ Username: @{chat.username or 'N/A'}\n" +
            tr(lang, "ci_members", count=member_count)
        )

        bot.send_message(chat.id, text, parse_mode="Markdown")

    except Exception as e:
        bot.reply_to(message, tr(lang, "action_error", error=e))

# ================================
# Statistics
# ================================
def send_stats(chat_id: int):
    lang = get_lang(chat_id)
    chat_stats = stats.get_stats(chat_id)

    text = (
        tr(lang, "stats_title") +
        tr(lang, "st_deleted", count=chat_stats.get('deleted_messages', 0)) + "\n" +
        tr(lang, "st_warns", count=chat_stats.get('warns_given', 0)) + "\n" +
        tr(lang, "st_mutes", count=chat_stats.get('mutes', 0)) + "\n" +
        tr(lang, "st_bans", count=chat_stats.get('bans', 0)) + "\n" +
        tr(lang, "st_kicks", count=chat_stats.get('kicks', 0)) + "\n" +
        tr(lang, "st_spam", count=chat_stats.get('spam_blocked', 0)) + "\n" +
        tr(lang, "st_links", count=chat_stats.get('links_blocked', 0))
    )

    bot.send_message(chat_id, text, parse_mode="Markdown")

@bot.message_handler(commands=["stats"])
@admin_only
def cmd_stats(message):
    lang = get_lang(message.chat.id)
    if is_private(message):
        bot.reply_to(message, tr(lang, "stats_groups_only"))
        return
    send_stats(message.chat.id)

# ================================
# Utilities: /clear, /pin, /unpin
# ================================
@bot.message_handler(commands=["clear"])
@group_only
@admin_only
def cmd_clear(message):
    lang = get_lang(message.chat.id)
    parts = message.text.split() if message.text else []
    if len(parts) < 2:
        bot.reply_to(message, tr(lang, "clear_usage"), parse_mode="Markdown")
        return

    try:
        count = int(parts[1])
        if count < 1 or count > 100:
            bot.reply_to(message, tr(lang, "clear_range"))
            return

        deleted = 0
        attempts = 0
        consecutive_misses = 0
        # FIX: message IDs in supergroups are not contiguous — keep walking
        # back until enough messages are deleted or a long gap is reached
        while deleted < count + 1 and attempts < count + 100 and consecutive_misses < 10:
            target_id = message.message_id - attempts
            attempts += 1
            if target_id < 1:
                break
            try:
                bot.delete_message(message.chat.id, target_id)
                deleted += 1
                consecutive_misses = 0
            except Exception:
                consecutive_misses += 1

        # FIX: count deleted messages in the statistics
        stats.increment(message.chat.id, "deleted_messages", deleted)

        msg = bot.send_message(message.chat.id, tr(lang, "clear_done", count=deleted))
        # FIX: remove the service message from a separate timer (a blocking
        # time.sleep(3) used to stall the worker thread)
        def _delete_notification():
            try:
                bot.delete_message(message.chat.id, msg.message_id)
            except Exception:
                pass
        threading.Timer(3.0, _delete_notification).start()

    except ValueError:
        bot.reply_to(message, tr(lang, "not_a_number"))
    except Exception as e:
        bot.reply_to(message, tr(lang, "action_error", error=e))

@bot.message_handler(commands=["pin"])
@group_only
@admin_only
def cmd_pin(message):
    lang = get_lang(message.chat.id)
    if not message.reply_to_message:
        bot.reply_to(message, tr(lang, "pin_usage"))
        return

    try:
        bot.pin_chat_message(message.chat.id, message.reply_to_message.message_id)
        bot.reply_to(message, tr(lang, "pinned"))
    except Exception as e:
        bot.reply_to(message, tr(lang, "action_error", error=e))

@bot.message_handler(commands=["unpin"])
@group_only
@admin_only
def cmd_unpin(message):
    lang = get_lang(message.chat.id)
    try:
        bot.unpin_chat_message(message.chat.id)
        bot.reply_to(message, tr(lang, "unpinned"))
    except Exception as e:
        bot.reply_to(message, tr(lang, "action_error", error=e))

# ================================
# Settings
# ================================
@bot.message_handler(commands=["settings"])
@group_only
@admin_only
def cmd_settings(message):
    lang = get_lang(message.chat.id)
    chat_settings = settings.get_all(message.chat.id)

    text = (
        tr(lang, "settings_title") +
        tr(lang, "set_max_warns", value=chat_settings['max_warns']) + "\n" +
        tr(lang, "set_antispam", value='✅' if chat_settings['antispam_enabled'] else '❌') + "\n" +
        tr(lang, "set_antilink", value='✅' if chat_settings['antilink_enabled'] else '❌') + "\n" +
        tr(lang, "set_welcome", value='✅' if chat_settings['welcome_enabled'] else '❌') + "\n" +
        tr(lang, "set_goodbye", value='✅' if chat_settings['goodbye_enabled'] else '❌') + "\n" +
        tr(lang, "set_language", value=lang_name(lang))
    )

    bot.send_message(
        message.chat.id,
        text,
        parse_mode="Markdown",
        reply_markup=get_settings_keyboard(message.chat.id)
    )

@bot.message_handler(commands=["setmaxwarns"])
@group_only
@admin_only
def cmd_setmaxwarns(message):
    lang = get_lang(message.chat.id)
    parts = message.text.split() if message.text else []
    if len(parts) < 2:
        bot.reply_to(message, tr(lang, "setmaxwarns_usage"), parse_mode="Markdown")
        return

    try:
        value = int(parts[1])
        if value < 1 or value > 10:
            bot.reply_to(message, tr(lang, "setmaxwarns_range"))
            return

        settings.set(message.chat.id, "max_warns", value)
        bot.reply_to(message, tr(lang, "setmaxwarns_done", value=value))

    except ValueError:
        bot.reply_to(message, tr(lang, "not_a_number"))

@bot.message_handler(commands=["setwelcome"])
@group_only
@admin_only
def cmd_setwelcome(message):
    lang = get_lang(message.chat.id)
    parts = message.text.split(maxsplit=1) if message.text else []
    if len(parts) < 2:
        bot.reply_to(message, tr(lang, "setwelcome_usage"), parse_mode="Markdown")
        return

    settings.set(message.chat.id, "welcome_message", parts[1])
    settings.set(message.chat.id, "welcome_enabled", True)
    bot.reply_to(message, tr(lang, "setwelcome_done"))

@bot.message_handler(commands=["setgoodbye"])
@group_only
@admin_only
def cmd_setgoodbye(message):
    lang = get_lang(message.chat.id)
    parts = message.text.split(maxsplit=1) if message.text else []
    if len(parts) < 2:
        bot.reply_to(message, tr(lang, "setgoodbye_usage"), parse_mode="Markdown")
        return

    settings.set(message.chat.id, "goodbye_message", parts[1])
    settings.set(message.chat.id, "goodbye_enabled", True)
    bot.reply_to(message, tr(lang, "setgoodbye_done"))

# ================================
# New/left chat members
# ================================
BOT_INFO = None  # cached get_me() result


def get_bot_id() -> Optional[int]:
    """FIX: recognize the bot itself to warn when it lacks admin rights."""
    global BOT_INFO
    if BOT_INFO is None:
        try:
            BOT_INFO = bot.get_me()
        except Exception:
            return None
    return BOT_INFO.id


@bot.message_handler(content_types=["new_chat_members"])
def handle_new_member(message):
    # FIX: warn when the bot is added to a group without admin rights
    bot_id = get_bot_id()
    if bot_id is not None and any(u.is_bot and u.id == bot_id for u in message.new_chat_members):
        try:
            me = bot.get_chat_member(message.chat.id, bot_id)
            if me.status != "administrator":
                bot.send_message(message.chat.id, tr(get_lang(message.chat.id), "need_admin_rights"))
        except Exception:
            pass
    if not settings.get(message.chat.id, "welcome_enabled"):
        return

    lang = get_lang(message.chat.id)
    # a custom message if set, otherwise a localized default
    template = settings.get(message.chat.id, "welcome_message") or tr(lang, "default_welcome")

    for user in message.new_chat_members:
        if user.is_bot:
            continue

        welcome_text = template.replace("{user}", get_user_display(user))
        welcome_text = welcome_text.replace("{chat}", message.chat.title or tr(lang, "chat_word"))

        bot.send_message(message.chat.id, welcome_text)

@bot.message_handler(content_types=["left_chat_member"])
def handle_left_member(message):
    if not settings.get(message.chat.id, "goodbye_enabled"):
        return

    user = message.left_chat_member
    if user.is_bot:
        return

    lang = get_lang(message.chat.id)
    template = settings.get(message.chat.id, "goodbye_message") or tr(lang, "default_goodbye")

    goodbye_text = template.replace("{user}", get_user_display(user))
    goodbye_text = goodbye_text.replace("{chat}", message.chat.title or tr(lang, "chat_word"))

    bot.send_message(message.chat.id, goodbye_text)

# ================================
# Message handling
# ================================
MEDIA_CONTENT_TYPES = [
    # FIX: captions of photos/videos/etc. are moderated too, not only text
    "text", "photo", "video", "document", "audio", "voice",
    "video_note", "sticker", "animation",
]


@bot.message_handler(func=lambda m: True, content_types=MEDIA_CONTENT_TYPES)
def handle_message(message):
    # Private messages
    if is_private(message):
        bot.send_message(message.chat.id, tr(get_lang(message.chat.id), "private_hello"))
        return

    if not is_group(message):
        return

    chat_id = message.chat.id
    user_id = message.from_user.id
    lang = get_lang(chat_id)
    # FIX: captions are checked too, not only plain text
    text = (message.text or message.caption or "").strip()

    # Liveness check
    if message.text and text.lower() in ("бот", "bot"):
        bot.send_message(chat_id, tr(lang, "im_working"))
        return

    # Skip chat admins (including anonymous ones)
    if can_moderate(chat_id, user_id):
        return

    # Anti-spam (any message type counts towards the flood limit)
    if settings.get(chat_id, "antispam_enabled"):
        max_msg = settings.get(chat_id, "antispam_messages")
        seconds = settings.get(chat_id, "antispam_seconds")

        if antispam.check(chat_id, user_id, max_msg, seconds):
            try:
                bot.delete_message(chat_id, message.message_id)

                bot.restrict_chat_member(
                    chat_id, user_id,
                    until_date=datetime.now() + timedelta(minutes=5),
                    permissions=get_mute_permissions()
                )

                bot.send_message(
                    chat_id,
                    tr(lang, "spam_muted", user=get_user_display(message.from_user))
                )
                stats.increment(chat_id, "spam_blocked")
                stats.increment(chat_id, "mutes")
                return

            except Exception as e:
                print(f"❌ Anti-spam error: {e}")

    # Anti-links (regex on the text/caption + Telegram link entities)
    if settings.get(chat_id, "antilink_enabled") and (has_links(text) or message_has_link_entities(message)):
        try:
            bot.delete_message(chat_id, message.message_id)
            bot.send_message(
                chat_id,
                tr(lang, "links_removed", user=get_user_display(message.from_user))
            )
            stats.increment(chat_id, "links_blocked")
            stats.increment(chat_id, "deleted_messages")
            return
        except Exception as e:
            print(f"❌ Anti-link error: {e}")

    # Trigger words
    if not text:
        return

    found_words = triggers.find_in_text(chat_id, text)

    if not found_words:
        return

    try:
        bot.delete_message(chat_id, message.message_id)

        censored = ", ".join(censor_word(w) for w in found_words)
        user_display = get_user_display(message.from_user)

        bot.send_message(
            chat_id,
            tr(lang, "msg_deleted", user=user_display, censored=censored)
        )

        stats.increment(chat_id, "deleted_messages")

        log_entry = (
            f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
            f"Chat: {message.chat.title} ({chat_id}) | "
            f"User: {user_display} ({user_id}) | "
            f"Words: {found_words}"
        )
        write_log(log_entry)

    except telebot.apihelper.ApiTelegramException as e:
        if "not enough rights" in str(e).lower():
            bot.send_message(chat_id, tr(lang, "no_delete_rights"))
    except Exception as e:
        print(f"❌ Error: {e}")


# ================================
# Startup
# ================================
def main():
    print("=" * 50)
    print("🤖 Moderation bot started!")
    print(f"📁 Trigger seed words (trigger.txt): {triggers.seed_count()}")
    print(f"🌐 Default language: {lang_name(DEFAULT_LANG)} ({DEFAULT_LANG})")
    print(f"📁 Logs: {LOG_PATH}")
    print("=" * 50)

    while True:
        try:
            bot.infinity_polling(
                timeout=60,
                long_polling_timeout=60,
                allowed_updates=["message", "callback_query"]
            )
        except Exception as e:
            print(f"❌ Error: {e}")
            print("🔄 Restarting in 5 seconds...")
            time.sleep(5)

if __name__ == "__main__":
    main()
