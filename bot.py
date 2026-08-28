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

ANONYMOUS_ADMIN_ID = 1087968824  # GroupAnonymousBot — сообщения от анонимных админов

# ================================
# Конфигурация
# ================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TOKEN_PATH = os.path.join(BASE_DIR, "token.txt")
TRIGGER_PATH = os.path.join(BASE_DIR, "trigger.txt")
LOG_PATH = os.path.join(BASE_DIR, "log.txt")
WARNS_PATH = os.path.join(BASE_DIR, "warns.json")
STATS_PATH = os.path.join(BASE_DIR, "stats.json")
SETTINGS_PATH = os.path.join(BASE_DIR, "settings.json")

# Настройки по умолчанию
DEFAULT_SETTINGS = {
    "max_warns": 3,
    "warn_expire_days": 30,
    "antispam_enabled": True,
    "antispam_messages": 5,
    "antispam_seconds": 10,
    "antilink_enabled": False,
    "welcome_enabled": False,
    "welcome_message": "👋 Добро пожаловать, {user}!",
    "goodbye_enabled": False,
    "goodbye_message": "👋 {user} покинул(а) чат",
}

# ================================
# Загрузка токена
# ================================
def load_token() -> str:
    try:
        with open(TOKEN_PATH, "r", encoding="utf-8") as f:
            token = f.read().strip()
    except FileNotFoundError:
        raise FileNotFoundError(f"❌ Файл токена не найден: {TOKEN_PATH}")
    # ИСПРАВЛЕНИЕ: понятная ошибка вместо загадочного 401 Unauthorized от API
    if not token or token == "PASTE_YOUR_BOT_TOKEN_HERE":
        raise ValueError(
            "❌ В token.txt не указан токен бота.\n"
            "   Получите токен у @BotFather и вставьте его в token.txt"
        )
    return token

TOKEN = load_token()
bot = telebot.TeleBot(TOKEN, parse_mode=None)

# ================================
# JSON Storage Manager
# ================================
class JsonStorage:
    """Потокобезопасное хранилище JSON"""
    
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
            # ИСПРАВЛЕНИЕ: пустой файл — не ошибка, используем значения по умолчанию
            if not content:
                return self.default.copy() if isinstance(self.default, dict) else self.default
            return json.loads(content)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            print(f"⚠️ Ошибка загрузки {self.filepath}: {e}")
            return self.default.copy() if isinstance(self.default, dict) else self.default
    
    def _save(self) -> None:
        # ИСПРАВЛЕНИЕ: атомарная запись (tmp + os.replace), файл не повредится при сбое
        tmp_path = self.filepath + ".tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self.filepath)
        except Exception as e:
            print(f"❌ Ошибка сохранения {self.filepath}: {e}")
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
    
    def mutate(self, key: str, fn) -> Any:
        """ИСПРАВЛЕНИЕ: атомарное чтение-изменение-запись под общей блокировкой"""
        with self._lock:
            result = fn(self._data.get(str(key)))
            self._data[str(key)] = result
            self._save()
            return result
    
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
    
    def all(self) -> dict:
        with self._lock:
            return self._data.copy()

# ================================
# Менеджер триггер-слов
# ================================
class TriggerManager:
    """Потокобезопасный менеджер триггер-слов"""
    
    def __init__(self, filepath: str):
        self.filepath = filepath
        self._lock = threading.RLock()
        self._words: Set[str] = self._load()
        self._patterns: List[tuple] = []
        self._rebuild_cache()
    
    def _load(self) -> Set[str]:
        if not os.path.exists(self.filepath):
            return set()
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                return {line.strip().lower() for line in f if line.strip()}
        except Exception as e:
            print(f"⚠️ Ошибка загрузки триггеров: {e}")
            return set()
    
    def _save(self) -> None:
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                f.write("\n".join(sorted(self._words)))
        except Exception as e:
            print(f"❌ Ошибка сохранения триггеров: {e}")
    
    def _rebuild_cache(self) -> None:
        # ИСПРАВЛЕНИЕ: поиск по границам слова (подстрока давала ложные срабатывания:
        # триггер "cat" удалял сообщения со словом "education")
        self._patterns = [
            (w, re.compile(r"(?<!\w)" + re.escape(w) + r"(?!\w)"))
            for w in self._words
        ]
    
    def add(self, word: str) -> bool:
        word = word.lower().strip()
        if not word:
            return False
        with self._lock:
            if word in self._words:
                return False
            self._words.add(word)
            self._save()
            self._rebuild_cache()
            return True
    
    def add_many(self, words: List[str]) -> int:
        added = 0
        with self._lock:
            for word in words:
                word = word.lower().strip()
                if word and word not in self._words:
                    self._words.add(word)
                    added += 1
            if added:
                self._save()
                self._rebuild_cache()
        return added
    
    def remove(self, word: str) -> bool:
        word = word.lower().strip()
        with self._lock:
            if word not in self._words:
                return False
            self._words.discard(word)
            self._save()
            self._rebuild_cache()
            return True
    
    def clear(self) -> int:
        with self._lock:
            count = len(self._words)
            self._words.clear()
            self._save()
            self._rebuild_cache()
            return count
    
    def find_in_text(self, text: str) -> List[str]:
        text_lower = text.lower()
        with self._lock:
            return [w for w, pattern in self._patterns if pattern.search(text_lower)]
    
    def get_all(self) -> List[str]:
        with self._lock:
            return sorted(self._words)
    
    def count(self) -> int:
        with self._lock:
            return len(self._words)
    
    def is_empty(self) -> bool:
        with self._lock:
            return len(self._words) == 0

# ================================
# Менеджер анти-спама
# ================================
class AntiSpamManager:
    """Защита от спама/флуда"""
    
    def __init__(self):
        self._lock = threading.Lock()
        self._messages: Dict[str, List[float]] = defaultdict(list)
    
    def check(self, chat_id: int, user_id: int, max_messages: int, seconds: int) -> bool:
        key = f"{chat_id}:{user_id}"
        now = time.time()
        
        with self._lock:
            # ИСПРАВЛЕНИЕ: периодическая чистка неактивных ключей —
            # раньше словарь рос бесконечно (утечка памяти)
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
# Менеджер предупреждений
# ================================
class WarnsManager:
    """Управление предупреждениями пользователей"""
    
    def __init__(self, storage: JsonStorage):
        self.storage = storage
    
    def _active(self, chat_id: int, warns_list: Optional[List[dict]]) -> List[dict]:
        """ИСПРАВЛЕНИЕ: учитываем настройку warn_expire_days — старые варны сгорают"""
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
                active.append(w)  # повреждённая дата — оставляем
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
        
        # ИСПРАВЛЕНИЕ: атомарно под блокировкой хранилища (раньше была гонка get/set)
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
# Менеджер статистики
# ================================
# Менеджер статистики
# ================================
class StatsManager:
    """Статистика модерации"""
    
    def __init__(self, storage: JsonStorage):
        self.storage = storage
    
    def increment(self, chat_id: int, stat_type: str, count: int = 1) -> None:
        # ИСПРАВЛЕНИЕ: атомарный инкремент под блокировкой (раньше терялись значения при гонке)
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
# Менеджер настроек чата
# ================================
class SettingsManager:
    """Настройки чатов"""
    
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
# Менеджер состояний пользователей
# ================================
class UserStateManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._states: dict = {}
    
    def set_state(self, user_id: int, state: str, data: dict = None) -> None:
        with self._lock:
            self._states[user_id] = {"state": state, "data": data or {}}
    
    def get_state(self, user_id: int) -> Optional[dict]:
        with self._lock:
            return self._states.get(user_id)
    
    def clear(self, user_id: int) -> None:
        with self._lock:
            self._states.pop(user_id, None)
    
    def start_confirmation(self, user_id: int) -> None:
        self.set_state(user_id, "confirm", {"count": 0})
    
    def confirm(self, user_id: int) -> Optional[int]:
        with self._lock:
            if user_id not in self._states or self._states[user_id]["state"] != "confirm":
                return None
            self._states[user_id]["data"]["count"] += 1
            return self._states[user_id]["data"]["count"]

# ================================
# Инициализация менеджеров
# ================================
triggers = TriggerManager(TRIGGER_PATH)
warns_storage = JsonStorage(WARNS_PATH, {})
stats_storage = JsonStorage(STATS_PATH, {})
settings_storage = JsonStorage(SETTINGS_PATH, {})

warns = WarnsManager(warns_storage)
stats = StatsManager(stats_storage)
settings = SettingsManager(settings_storage)
antispam = AntiSpamManager()
user_states = UserStateManager()

# ================================
# Логирование
# ================================
_log_lock = threading.Lock()

MAX_LOG_SIZE = 5 * 1024 * 1024  # 5 МБ

def write_log(text: str) -> None:
    try:
        with _log_lock:
            # ИСПРАВЛЕНИЕ: простая ротация — log.txt не растёт бесконечно
            try:
                if os.path.exists(LOG_PATH) and os.path.getsize(LOG_PATH) > MAX_LOG_SIZE:
                    os.replace(LOG_PATH, LOG_PATH + ".old")
            except OSError:
                pass
            with open(LOG_PATH, "a", encoding="utf-8") as f:
                f.write(f"{text}\n")
    except Exception as e:
        print(f"⚠️ Ошибка записи лога: {e}")

# ================================
# Утилиты
# ================================
def md_escape(text: Any) -> str:
    """ИСПРАВЛЕНИЕ: экранирование спецсимволов Markdown в пользовательских данных
    (имя или причина с _ * [ раньше ломали отправку сообщений с parse_mode=Markdown)"""
    return re.sub(r"([_*`\[])", r"\\\1", str(text))

def censor_word(word: str) -> str:
    length = len(word)
    if length <= 1:
        return "*"
    if length == 2:
        return word[0] + "*"
    return word[0] + "*" * (length - 2) + word[-1]

def is_chat_admin(chat_id: int, user_id: int) -> bool:
    """Проверяет, является ли пользователь админом ЧАТА"""
    try:
        member = bot.get_chat_member(chat_id, user_id)
        return member.status in ("creator", "administrator")
    except Exception:
        return False

def can_moderate(chat_id: int, user_id: int) -> bool:
    """Права модератора: анонимный админ группы, админ или создатель чата"""
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
    return value * multipliers.get(unit, 60)

def format_duration(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds} сек"
    if seconds < 3600:
        return f"{seconds // 60} мин"
    if seconds < 86400:
        return f"{seconds // 3600} ч"
    return f"{seconds // 86400} дн"

def extract_user_from_message(message) -> tuple:
    """Извлекает пользователя из reply или аргументов команды"""
    # Из reply
    if message.reply_to_message and message.reply_to_message.from_user:
        parts = message.text.split(maxsplit=2) if message.text else []
        reason = parts[1] if len(parts) > 1 else None
        return message.reply_to_message.from_user, reason
    
    parts = message.text.split(maxsplit=2) if message.text else []
    if len(parts) < 2:
        return None, None
    
    user_arg = parts[1]
    reason = parts[2] if len(parts) > 2 else None
    
    # По ID
    if user_arg.isdigit():
        try:
            member = bot.get_chat_member(message.chat.id, int(user_arg))
            return member.user, reason
        except Exception:
            pass
    
    # По @username - убираем @ если есть
    if user_arg.startswith("@"):
        user_arg = user_arg[1:]
    
    # Пытаемся найти через entities (text_mention — упоминание юзера без @username).
    # Обычный @username разрешить нельзя: Bot API не позволяет найти ID по имени.
    if message.entities:
        for entity in message.entities:
            if entity.type == "text_mention" and entity.user:
                return entity.user, reason
    
    return None, reason

LINK_PATTERNS = [
    r'https?://\S+',
    r'tg://\S+',
    r'(?<![\w.])www\.\S+',
    r'(?<![\w.])t\.me/\S+',
    r'(?<![\w.])telegram\.me/\S+',
    r'(?<![\w.])telegram\.dog/\S+',
    r'(?<![\w.])joinchat\.to/\S+',
    # домен без протокола, включая поддомены: site.ru, sub.site.online и т.п.
    r'(?:(?<=\s)|^)(?:[a-z0-9-]+\.)+(?:com|net|org|ru|su|ua|by|kz|io|me|info|biz|xyz|top|site|online|store|app|dev|pro|tv|рф)(?![\w-])',
]

def has_links(text: str) -> bool:
    # ИСПРАВЛЕНИЕ: расширенный список шаблонов (раньше обходилось через
    # "www.", "tg://", домен без протокола и telegram.dog)
    for pattern in LINK_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False

# ================================
# ИСПРАВЛЕНИЕ: Функция для создания ChatPermissions
# ================================
def get_mute_permissions() -> types.ChatPermissions:
    """Создает объект ChatPermissions для мута (совместимо с разными версиями API)"""
    try:
        # Новая версия API (Bot API 6.3+)
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
        # Старая версия API
        return types.ChatPermissions(
            can_send_messages=False,
            can_send_media_messages=False,
            can_send_other_messages=False,
            can_add_web_page_previews=False
        )

def get_unmute_permissions() -> types.ChatPermissions:
    """Создает объект ChatPermissions для размута (совместимо с разными версиями API)"""
    try:
        # Новая версия API (Bot API 6.3+)
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
        # Старая версия API
        return types.ChatPermissions(
            can_send_messages=True,
            can_send_media_messages=True,
            can_send_other_messages=True,
            can_add_web_page_previews=True
        )

# ================================
# Декораторы
# ================================
def admin_only(func):
    """Для админов чата (включая анонимных админов группы)"""
    @wraps(func)
    def wrapper(message, *args, **kwargs):
        user_id = message.from_user.id
        
        # Анонимный админ группы — точно админ чата
        if user_id == ANONYMOUS_ADMIN_ID:
            return func(message, *args, **kwargs)
        
        # В личке команды модерации недоступны
        if is_private(message):
            bot.reply_to(message, "⛔ Нет доступа")
            return
        
        # Админ чата
        if is_chat_admin(message.chat.id, user_id):
            return func(message, *args, **kwargs)
        
        bot.reply_to(message, "⛔ Только для админов")
    return wrapper

def creator_only(func):
    """Только для создателя чата"""
    @wraps(func)
    def wrapper(message, *args, **kwargs):
        user_id = message.from_user.id
        
        # Анонимный — не можем проверить, создатель ли он
        if user_id == ANONYMOUS_ADMIN_ID:
            bot.reply_to(message, "⛔ Отключите анонимность для этой команды")
            return
        
        if is_private(message):
            bot.reply_to(message, "⛔ Только в группах")
            return
        
        if is_creator(message.chat.id, user_id):
            return func(message, *args, **kwargs)
        
        bot.reply_to(message, "⛔ Только для создателя чата")
    return wrapper

def group_only(func):
    @wraps(func)
    def wrapper(message, *args, **kwargs):
        if is_group(message):
            return func(message, *args, **kwargs)
        bot.reply_to(message, "⛔ Эта команда работает только в группах")
    return wrapper

# ================================
# Клавиатуры
# ================================
def get_main_keyboard() -> types.InlineKeyboardMarkup:
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("➕ Добавить слово", callback_data="help_add"),
        types.InlineKeyboardButton("➖ Удалить слово", callback_data="help_del"),
        types.InlineKeyboardButton("📄 Список слов", callback_data="list_words"),
        types.InlineKeyboardButton("📊 Статистика", callback_data="show_stats"),
        types.InlineKeyboardButton("⚙️ Настройки", callback_data="show_settings"),
        types.InlineKeyboardButton("❓ Все команды", callback_data="all_commands")
    )
    return keyboard

def get_settings_keyboard(chat_id: int) -> types.InlineKeyboardMarkup:
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    
    antispam_status = "✅" if settings.get(chat_id, "antispam_enabled") else "❌"
    antilink_status = "✅" if settings.get(chat_id, "antilink_enabled") else "❌"
    welcome_status = "✅" if settings.get(chat_id, "welcome_enabled") else "❌"
    goodbye_status = "✅" if settings.get(chat_id, "goodbye_enabled") else "❌"
    
    keyboard.add(
        types.InlineKeyboardButton(f"🔄 Анти-спам: {antispam_status}", callback_data="toggle_antispam"),
        types.InlineKeyboardButton(f"🔗 Анти-ссылки: {antilink_status}", callback_data="toggle_antilink"),
        types.InlineKeyboardButton(f"👋 Приветствия: {welcome_status}", callback_data="toggle_welcome"),
        types.InlineKeyboardButton(f"🚪 Прощания: {goodbye_status}", callback_data="toggle_goodbye"),
        types.InlineKeyboardButton("🔙 Назад", callback_data="back_main")
    )
    return keyboard

# ================================
# /myid
# ================================
@bot.message_handler(commands=["myid"])
def cmd_myid(message):
    """Получить свой Telegram ID"""
    bot.reply_to(
        message, 
        f"🆔 Твой ID: `{message.from_user.id}`\n"
        f"💬 ID чата: `{message.chat.id}`",
        parse_mode="Markdown"
    )

# ================================
# Команды /start и /help
# ================================
@bot.message_handler(commands=["start", "help"])
def cmd_help(message):
    text = (
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
        "🆔 `/myid` — узнать свой ID\n"
        "❓ `/commands` — все команды"
    )
    
    bot.send_message(
        message.chat.id,
        text,
        parse_mode="Markdown",
        # ИСПРАВЛЕНИЕ: клавиатура имеет смысл только в группах
        reply_markup=get_main_keyboard() if is_group(message) else None
    )

# ================================
# Все команды
# ================================
@bot.message_handler(commands=["commands"])
def cmd_all_commands(message):
    text = """
📋 *Полный список команд:*

*Триггер-слова:*
• `/addword <слово>` — добавить
• `/addwords <слова>` — добавить несколько
• `/delword <слово>` — удалить
• `/listwords` — показать список
• `/clearwords` — очистить все

*Модерация пользователей:*
• `/warn [user] [причина]` — предупреждение
• `/unwarn [user]` — снять предупреждение
• `/warns [user]` — список предупреждений
• `/clearwarns [user]` — очистить предупреждения
• `/mute [user] [время]` — мут (1h, 30m, 1d)
• `/unmute [user]` — размут
• `/ban [user] [причина]` — бан
• `/unban [user_id]` — разбан
• `/kick [user]` — кик

*Информация:*
• `/userinfo [user]` — инфо о пользователе
• `/chatinfo` — инфо о чате
• `/stats` — статистика модерации
• `/myid` — ваш Telegram ID

*Утилиты:*
• `/clear <N>` — удалить N сообщений
• `/pin` — закрепить сообщение
• `/unpin` — открепить сообщение

*Настройки:*
• `/settings` — настройки чата
• `/setwelcome <текст>` — текст приветствия
• `/setgoodbye <текст>` — текст прощания
• `/setmaxwarns <N>` — макс. предупреждений
"""
    
    text += "\n_Используйте reply или укажите ID пользователя_"
    
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

# ================================
# Callback обработчик
# ================================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    
    # Проверка прав: админ чата (включая анонимного админа группы)
    if is_private(call.message):
        has_access = False
    else:
        has_access = can_moderate(chat_id, user_id)
    
    if not has_access:
        bot.answer_callback_query(call.id, "⛔ Нет доступа", show_alert=True)
        return
    
    try:
        if call.data == "help_add":
            bot.answer_callback_query(call.id)
            bot.send_message(chat_id, "📝 Используй: `/addword <слово>`", parse_mode="Markdown")
        
        elif call.data == "help_del":
            bot.answer_callback_query(call.id)
            bot.send_message(chat_id, "📝 Используй: `/delword <слово>`", parse_mode="Markdown")
        
        elif call.data == "list_words":
            bot.answer_callback_query(call.id)
            user_states.start_confirmation(user_id)
            bot.send_message(
                chat_id,
                f"⚠️ *Подтверждение*\n\nСлов: {triggers.count()}\nПодтвердите 3 раза: /confirm",
                parse_mode="Markdown"
            )
        
        elif call.data == "show_stats":
            bot.answer_callback_query(call.id)
            if is_group(call.message):
                send_stats(chat_id)
            else:
                bot.send_message(chat_id, "📊 Статистика доступна только в группах")
        
        elif call.data == "show_settings":
            bot.answer_callback_query(call.id)
            if is_group(call.message):
                bot.send_message(
                    chat_id,
                    "⚙️ *Настройки чата:*",
                    parse_mode="Markdown",
                    reply_markup=get_settings_keyboard(chat_id)
                )
            else:
                bot.send_message(chat_id, "⚙️ Настройки доступны только в группах")
        
        elif call.data == "toggle_antispam":
            current = settings.get(chat_id, "antispam_enabled")
            settings.set(chat_id, "antispam_enabled", not current)
            status = 'включен' if not current else 'выключен'
            bot.answer_callback_query(call.id, f"Анти-спам {status}")
            bot.edit_message_reply_markup(
                chat_id, call.message.message_id,
                reply_markup=get_settings_keyboard(chat_id)
            )
        
        elif call.data == "toggle_antilink":
            current = settings.get(chat_id, "antilink_enabled")
            settings.set(chat_id, "antilink_enabled", not current)
            status = 'включен' if not current else 'выключен'
            bot.answer_callback_query(call.id, f"Анти-ссылки {status}")
            bot.edit_message_reply_markup(
                chat_id, call.message.message_id,
                reply_markup=get_settings_keyboard(chat_id)
            )
        
        elif call.data == "toggle_welcome":
            current = settings.get(chat_id, "welcome_enabled")
            settings.set(chat_id, "welcome_enabled", not current)
            status = 'включены' if not current else 'выключены'
            bot.answer_callback_query(call.id, f"Приветствия {status}")
            bot.edit_message_reply_markup(
                chat_id, call.message.message_id,
                reply_markup=get_settings_keyboard(chat_id)
            )
        
        elif call.data == "toggle_goodbye":
            current = settings.get(chat_id, "goodbye_enabled")
            settings.set(chat_id, "goodbye_enabled", not current)
            status = 'включены' if not current else 'выключены'
            bot.answer_callback_query(call.id, f"Прощания {status}")
            bot.edit_message_reply_markup(
                chat_id, call.message.message_id,
                reply_markup=get_settings_keyboard(chat_id)
            )
        
        elif call.data == "back_main":
            bot.answer_callback_query(call.id)
            bot.edit_message_text(
                "🤖 Главное меню",
                chat_id, call.message.message_id,
                reply_markup=get_main_keyboard()
            )
        
        elif call.data == "all_commands":
            bot.answer_callback_query(call.id)
            cmd_all_commands(call.message)
            
    except Exception as e:
        print(f"❌ Callback error: {e}")
        bot.answer_callback_query(call.id, "Ошибка обработки")

# ================================
# /confirm
# ================================
@bot.message_handler(commands=["confirm"])
def cmd_confirm(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    count = user_states.confirm(user_id)
    
    if count is None:
        bot.reply_to(message, "❓ Сначала запросите список слов")
        return
    
    if count < 3:
        bot.reply_to(message, f"✅ Подтверждено {count}/3")
        return
    
    words = triggers.get_all()
    
    if not words:
        bot.send_message(chat_id, "📭 Список триггеров пуст")
        user_states.clear(user_id)
        return
    
    temp_file = os.path.join(BASE_DIR, f"triggers_{user_id}.txt")
    
    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write("\n".join(words))
        
        with open(temp_file, "rb") as f:
            bot.send_document(chat_id, f, caption=f"📄 Триггер-слова ({len(words)} шт.)")
    finally:
        if os.path.exists(temp_file):
            os.remove(temp_file)
        user_states.clear(user_id)

# ================================
# Команды триггер-слов
# ================================
@bot.message_handler(commands=["addword"])
@admin_only
def cmd_addword(message):
    parts = message.text.split(maxsplit=1) if message.text else []
    if len(parts) < 2:
        bot.reply_to(message, "📝 Использование: `/addword <слово>`", parse_mode="Markdown")
        return
    
    word = parts[1].strip()
    if len(word) > 100:
        bot.reply_to(message, "⚠️ Слово слишком длинное (макс. 100 символов)")
        return
    
    if triggers.add(word):
        bot.reply_to(message, f"✅ Добавлено: `{md_escape(word.lower())}`", parse_mode="Markdown")
    else:
        bot.reply_to(message, "⚠️ Это слово уже в списке")

@bot.message_handler(commands=["addwords"])
@admin_only
def cmd_addwords(message):
    parts = message.text.split()[1:] if message.text else []
    if not parts:
        bot.reply_to(message, "📝 Использование: `/addwords слово1 слово2 слово3`", parse_mode="Markdown")
        return
    
    added = triggers.add_many(parts)
    bot.reply_to(message, f"✅ Добавлено слов: {added}")

@bot.message_handler(commands=["delword"])
@admin_only
def cmd_delword(message):
    parts = message.text.split(maxsplit=1) if message.text else []
    if len(parts) < 2:
        bot.reply_to(message, "📝 Использование: `/delword <слово>`", parse_mode="Markdown")
        return
    
    word = parts[1].strip()
    if triggers.remove(word):
        bot.reply_to(message, f"✅ Удалено: `{md_escape(word.lower())}`", parse_mode="Markdown")
    else:
        bot.reply_to(message, "⚠️ Слово не найдено в списке")

@bot.message_handler(commands=["clearwords"])
@creator_only
def cmd_clearwords(message):
    count = triggers.clear()
    bot.reply_to(message, f"🗑️ Удалено триггер-слов: {count}")

@bot.message_handler(commands=["listwords"])
@admin_only
def cmd_listwords(message):
    user_states.start_confirmation(message.from_user.id)
    bot.send_message(
        message.chat.id,
        f"⚠️ В списке: {triggers.count()} слов\nПодтвердите 3 раза: /confirm"
    )

# ================================
# Модерация: /warn, /unwarn, /warns
# ================================
# ИСПРАВЛЕНИЕ: Порядок декораторов - @group_only должен быть ближе к функции
@bot.message_handler(commands=["warn"])
@group_only
@admin_only
def cmd_warn(message):
    user, reason = extract_user_from_message(message)
    
    if not user:
        bot.reply_to(message, "📝 Ответьте на сообщение или: `/warn <user_id> причина`", parse_mode="Markdown")
        return
    
    if user.id == ANONYMOUS_ADMIN_ID or is_chat_admin(message.chat.id, user.id):
        bot.reply_to(message, "⚠️ Нельзя выдать предупреждение админу чата")
        return
    
    reason = reason or "Не указана"
    count = warns.add_warn(message.chat.id, user.id, reason, message.from_user.id)
    max_warns = settings.get(message.chat.id, "max_warns")
    
    stats.increment(message.chat.id, "warns_given")
    
    text = (
        f"⚠️ *Предупреждение*\n\n"
        f"👤 Пользователь: {md_escape(get_user_display(user))}\n"
        f"📛 Причина: {md_escape(reason)}\n"
        f"📊 Предупреждений: {count}/{max_warns}"
    )
    
    bot.send_message(message.chat.id, text, parse_mode="Markdown")
    
    if count >= max_warns:
        try:
            bot.ban_chat_member(message.chat.id, user.id)
            bot.send_message(
                message.chat.id,
                f"🔨 {get_user_display(user)} забанен (достигнут лимит предупреждений)"
            )
            stats.increment(message.chat.id, "bans")
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Ошибка бана: {e}")

@bot.message_handler(commands=["unwarn"])
@group_only
@admin_only
def cmd_unwarn(message):
    user, _ = extract_user_from_message(message)
    
    if not user:
        bot.reply_to(message, "📝 Ответьте на сообщение или: `/unwarn <user_id>`", parse_mode="Markdown")
        return
    
    if warns.remove_warn(message.chat.id, user.id):
        count = warns.count_warns(message.chat.id, user.id)
        bot.reply_to(message, f"✅ Предупреждение снято. Осталось: {count}")
    else:
        bot.reply_to(message, "⚠️ У пользователя нет предупреждений")

@bot.message_handler(commands=["warns"])
@group_only
@admin_only
def cmd_warns(message):
    user, _ = extract_user_from_message(message)
    
    if not user:
        bot.reply_to(message, "📝 Ответьте на сообщение или: `/warns <user_id>`", parse_mode="Markdown")
        return
    
    user_warns = warns.get_warns(message.chat.id, user.id)
    
    if not user_warns:
        bot.reply_to(message, f"✅ У {get_user_display(user)} нет предупреждений")
        return
    
    text = f"📋 *Предупреждения {md_escape(get_user_display(user))}:*\n\n"
    for i, w in enumerate(user_warns, 1):
        date = datetime.fromisoformat(w['date']).strftime("%d.%m.%Y")
        text += f"{i}. {md_escape(w['reason'])} ({date})\n"
    
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(commands=["clearwarns"])
@group_only
@admin_only
def cmd_clearwarns(message):
    user, _ = extract_user_from_message(message)
    
    if not user:
        bot.reply_to(message, "📝 Ответьте на сообщение или: `/clearwarns <user_id>`", parse_mode="Markdown")
        return
    
    count = warns.clear_warns(message.chat.id, user.id)
    bot.reply_to(message, f"✅ Снято предупреждений: {count}")

# ================================
# Модерация: /mute, /unmute
# ================================
@bot.message_handler(commands=["mute"])
@group_only
@admin_only
def cmd_mute(message):
    parts = message.text.split() if message.text else []
    duration_str = None
    user = None
    
    if message.reply_to_message and message.reply_to_message.from_user:
        user = message.reply_to_message.from_user
        if len(parts) > 1:
            duration_str = parts[1]
    else:
        if len(parts) < 2:
            bot.reply_to(
                message, 
                "📝 Ответьте на сообщение или: `/mute <user_id> [время]`\n"
                "Время: 1m, 1h, 1d, 1w",
                parse_mode="Markdown"
            )
            return
        user, _ = extract_user_from_message(message)
        if len(parts) > 2:
            duration_str = parts[2]
    
    if not user:
        bot.reply_to(message, "❌ Пользователь не найден")
        return
    
    if user.id == ANONYMOUS_ADMIN_ID or is_chat_admin(message.chat.id, user.id):
        bot.reply_to(message, "⚠️ Нельзя замутить админа чата")
        return
    
    if duration_str:
        duration = parse_duration(duration_str)
        if not duration:
            bot.reply_to(message, "⚠️ Неверный формат времени. Примеры: 30m, 1h, 1d")
            return
        until_date = datetime.now() + timedelta(seconds=duration)
        duration_text = format_duration(duration)
    else:
        until_date = None
        duration_text = "навсегда"
    
    try:
        # ИСПРАВЛЕНИЕ: Используем функцию для совместимости с разными версиями API
        bot.restrict_chat_member(
            message.chat.id,
            user.id,
            until_date=until_date,
            permissions=get_mute_permissions()
        )
        
        bot.send_message(
            message.chat.id,
            f"🔇 {get_user_display(user)} замучен на {duration_text}"
        )
        stats.increment(message.chat.id, "mutes")
        
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=["unmute"])
@group_only
@admin_only
def cmd_unmute(message):
    user, _ = extract_user_from_message(message)
    
    if not user:
        bot.reply_to(message, "📝 Ответьте на сообщение или: `/unmute <user_id>`", parse_mode="Markdown")
        return
    
    try:
        # ИСПРАВЛЕНИЕ: Используем функцию для совместимости с разными версиями API
        bot.restrict_chat_member(
            message.chat.id,
            user.id,
            permissions=get_unmute_permissions()
        )
        bot.reply_to(message, f"🔊 {get_user_display(user)} размучен")
        
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

# ================================
# Модерация: /ban, /unban, /kick
# ================================
@bot.message_handler(commands=["ban"])
@group_only
@admin_only
def cmd_ban(message):
    user, reason = extract_user_from_message(message)
    
    if not user:
        bot.reply_to(message, "📝 Ответьте на сообщение или: `/ban <user_id> [причина]`", parse_mode="Markdown")
        return
    
    if user.id == ANONYMOUS_ADMIN_ID or is_chat_admin(message.chat.id, user.id):
        bot.reply_to(message, "⚠️ Нельзя забанить админа чата")
        return
    
    try:
        bot.ban_chat_member(message.chat.id, user.id)
        
        text = f"🔨 {get_user_display(user)} забанен"
        if reason:
            text += f"\n📛 Причина: {reason}"
        
        bot.send_message(message.chat.id, text)
        stats.increment(message.chat.id, "bans")
        
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=["unban"])
@group_only
@admin_only
def cmd_unban(message):
    # ИСПРАВЛЕНИЕ: работает как остальные команды — reply, ID или text_mention
    user, _ = extract_user_from_message(message)
    
    if not user:
        bot.reply_to(message, "📝 Ответьте на сообщение или: `/unban <user_id>`", parse_mode="Markdown")
        return
    
    try:
        bot.unban_chat_member(message.chat.id, user.id, only_if_banned=True)
        bot.reply_to(message, f"✅ Пользователь `{user.id}` разбанен", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=["kick"])
@group_only
@admin_only
def cmd_kick(message):
    user, _ = extract_user_from_message(message)
    
    if not user:
        bot.reply_to(message, "📝 Ответьте на сообщение или: `/kick <user_id>`", parse_mode="Markdown")
        return
    
    if user.id == ANONYMOUS_ADMIN_ID or is_chat_admin(message.chat.id, user.id):
        bot.reply_to(message, "⚠️ Нельзя кикнуть админа чата")
        return
    
    try:
        bot.ban_chat_member(message.chat.id, user.id)
        bot.unban_chat_member(message.chat.id, user.id)
        
        bot.send_message(message.chat.id, f"👢 {get_user_display(user)} кикнут")
        stats.increment(message.chat.id, "kicks")
        
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

# ================================
# Информация
# ================================
@bot.message_handler(commands=["userinfo"])
@group_only
@admin_only
def cmd_userinfo(message):
    user, _ = extract_user_from_message(message)
    
    if not user:
        user = message.from_user
    
    try:
        member = bot.get_chat_member(message.chat.id, user.id)
        
        status_map = {
            "creator": "👑 Создатель",
            "administrator": "⭐ Админ",
            "member": "👤 Участник",
            "restricted": "🔇 Ограничен",
            "left": "🚪 Покинул",
            "kicked": "🚫 Забанен"
        }
        
        user_warns_count = warns.count_warns(message.chat.id, user.id)
        
        text = (
            f"👤 *Информация о пользователе*\n\n"
            f"├ ID: `{user.id}`\n"
            f"├ Имя: {md_escape(user.first_name or 'N/A')}\n"
            f"├ Фамилия: {md_escape(user.last_name or 'N/A')}\n"
            f"├ Username: @{md_escape(user.username or 'N/A')}\n"
            f"├ Статус в чате: {status_map.get(member.status, member.status)}\n"
            f"├ Бот: {'Да' if user.is_bot else 'Нет'}\n"
            f"└ Предупреждений: {user_warns_count}"
        )
        
        bot.send_message(message.chat.id, text, parse_mode="Markdown")
        
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=["chatinfo"])
@group_only
def cmd_chatinfo(message):
    chat = message.chat
    
    try:
        member_count = bot.get_chat_member_count(chat.id)
        
        text = (
            f"💬 *Информация о чате*\n\n"
            f"├ ID: `{chat.id}`\n"
            f"├ Название: {chat.title}\n"
            f"├ Тип: {chat.type}\n"
            f"├ Username: @{chat.username or 'N/A'}\n"
            f"└ Участников: {member_count}"
        )
        
        bot.send_message(chat.id, text, parse_mode="Markdown")
        
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

# ================================
# Статистика
# ================================
def send_stats(chat_id: int):
    chat_stats = stats.get_stats(chat_id)
    
    text = (
        f"📊 *Статистика модерации*\n\n"
        f"├ 🗑️ Удалено сообщений: {chat_stats.get('deleted_messages', 0)}\n"
        f"├ ⚠️ Предупреждений: {chat_stats.get('warns_given', 0)}\n"
        f"├ 🔇 Мутов: {chat_stats.get('mutes', 0)}\n"
        f"├ 🔨 Банов: {chat_stats.get('bans', 0)}\n"
        f"├ 👢 Киков: {chat_stats.get('kicks', 0)}\n"
        f"├ 🔄 Заблокировано спама: {chat_stats.get('spam_blocked', 0)}\n"
        f"└ 🔗 Заблокировано ссылок: {chat_stats.get('links_blocked', 0)}"
    )
    
    bot.send_message(chat_id, text, parse_mode="Markdown")

@bot.message_handler(commands=["stats"])
@admin_only
def cmd_stats(message):
    if is_private(message):
        bot.reply_to(message, "📊 Статистика доступна только в группах")
        return
    send_stats(message.chat.id)

# ================================
# Утилиты: /clear, /pin, /unpin
# ================================
@bot.message_handler(commands=["clear"])
@group_only
@admin_only
def cmd_clear(message):
    parts = message.text.split() if message.text else []
    if len(parts) < 2:
        bot.reply_to(message, "📝 Использование: `/clear <количество>`", parse_mode="Markdown")
        return
    
    try:
        count = int(parts[1])
        if count < 1 or count > 100:
            bot.reply_to(message, "⚠️ Укажите число от 1 до 100")
            return
        
        deleted = 0
        for i in range(count + 1):
            try:
                bot.delete_message(message.chat.id, message.message_id - i)
                deleted += 1
            except Exception:
                continue
        
        # ИСПРАВЛЕНИЕ: учитываем удалённые сообщения в статистике
        stats.increment(message.chat.id, "deleted_messages", deleted)
        
        msg = bot.send_message(message.chat.id, f"🗑️ Удалено сообщений: {deleted}")
        # ИСПРАВЛЕНИЕ: удаление уведомления в отдельном таймере (было time.sleep(3),
        # блокировавшее поток обработки)
        def _delete_notification():
            try:
                bot.delete_message(message.chat.id, msg.message_id)
            except Exception:
                pass
        threading.Timer(3.0, _delete_notification).start()
        
    except ValueError:
        bot.reply_to(message, "⚠️ Укажите число")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=["pin"])
@group_only
@admin_only
def cmd_pin(message):
    if not message.reply_to_message:
        bot.reply_to(message, "📝 Ответьте на сообщение для закрепления")
        return
    
    try:
        bot.pin_chat_message(message.chat.id, message.reply_to_message.message_id)
        bot.reply_to(message, "📌 Сообщение закреплено")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=["unpin"])
@group_only
@admin_only
def cmd_unpin(message):
    try:
        bot.unpin_chat_message(message.chat.id)
        bot.reply_to(message, "📌 Сообщение откреплено")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

# ================================
# Настройки
# ================================
@bot.message_handler(commands=["settings"])
@group_only
@admin_only
def cmd_settings(message):
    chat_settings = settings.get_all(message.chat.id)
    
    text = (
        f"⚙️ *Настройки чата*\n\n"
        f"├ Макс. предупреждений: {chat_settings['max_warns']}\n"
        f"├ Анти-спам: {'✅' if chat_settings['antispam_enabled'] else '❌'}\n"
        f"├ Анти-ссылки: {'✅' if chat_settings['antilink_enabled'] else '❌'}\n"
        f"├ Приветствия: {'✅' if chat_settings['welcome_enabled'] else '❌'}\n"
        f"└ Прощания: {'✅' if chat_settings['goodbye_enabled'] else '❌'}"
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
    parts = message.text.split() if message.text else []
    if len(parts) < 2:
        bot.reply_to(message, "📝 Использование: `/setmaxwarns <число>`", parse_mode="Markdown")
        return
    
    try:
        value = int(parts[1])
        if value < 1 or value > 10:
            bot.reply_to(message, "⚠️ Укажите число от 1 до 10")
            return
        
        settings.set(message.chat.id, "max_warns", value)
        bot.reply_to(message, f"✅ Максимум предупреждений: {value}")
        
    except ValueError:
        bot.reply_to(message, "⚠️ Укажите число")

@bot.message_handler(commands=["setwelcome"])
@group_only
@admin_only
def cmd_setwelcome(message):
    parts = message.text.split(maxsplit=1) if message.text else []
    if len(parts) < 2:
        bot.reply_to(
            message,
            "📝 Использование: `/setwelcome <текст>`\n\n"
            "Переменные:\n"
            "• `{user}` — имя пользователя\n"
            "• `{chat}` — название чата",
            parse_mode="Markdown"
        )
        return
    
    settings.set(message.chat.id, "welcome_message", parts[1])
    settings.set(message.chat.id, "welcome_enabled", True)
    bot.reply_to(message, "✅ Приветствие обновлено и включено")

@bot.message_handler(commands=["setgoodbye"])
@group_only
@admin_only
def cmd_setgoodbye(message):
    parts = message.text.split(maxsplit=1) if message.text else []
    if len(parts) < 2:
        bot.reply_to(
            message,
            "📝 Использование: `/setgoodbye <текст>`\n\n"
            "Переменные:\n"
            "• `{user}` — имя пользователя\n"
            "• `{chat}` — название чата",
            parse_mode="Markdown"
        )
        return
    
    settings.set(message.chat.id, "goodbye_message", parts[1])
    settings.set(message.chat.id, "goodbye_enabled", True)
    bot.reply_to(message, "✅ Текст прощания обновлён и включён")

# ================================
# Обработка новых/ушедших участников
# ================================
@bot.message_handler(content_types=["new_chat_members"])
def handle_new_member(message):
    if not settings.get(message.chat.id, "welcome_enabled"):
        return
    
    for user in message.new_chat_members:
        if user.is_bot:
            continue
        
        welcome_text = settings.get(message.chat.id, "welcome_message")
        welcome_text = welcome_text.replace("{user}", get_user_display(user))
        welcome_text = welcome_text.replace("{chat}", message.chat.title or "чат")
        
        bot.send_message(message.chat.id, welcome_text)

@bot.message_handler(content_types=["left_chat_member"])
def handle_left_member(message):
    if not settings.get(message.chat.id, "goodbye_enabled"):
        return
    
    user = message.left_chat_member
    if user.is_bot:
        return
    
    goodbye_text = settings.get(message.chat.id, "goodbye_message")
    goodbye_text = goodbye_text.replace("{user}", get_user_display(user))
    goodbye_text = goodbye_text.replace("{chat}", message.chat.title or "чат")
    
    bot.send_message(message.chat.id, goodbye_text)

# ================================
# Обработка сообщений
# ================================
@bot.message_handler(func=lambda m: True, content_types=["text"])
def handle_message(message):
    # Личные сообщения
    if is_private(message):
        text = (
            "👋 Привет! Я бот модерации для групп.\n\n"
            "📌 Добавьте меня в группу и дайте права администратора.\n\n"
            "/help — список команд\n"
            "/myid — узнать свой ID"
        )
        bot.send_message(message.chat.id, text)
        return
    
    if not is_group(message) or not message.text:
        return
    
    chat_id = message.chat.id
    user_id = message.from_user.id
    text = message.text.strip()
    
    # Тест работоспособности
    if text.lower() == "бот":
        bot.send_message(chat_id, "✅ Работаю!")
        return
    
    # Пропуск админов чата (включая анонимных)
    if can_moderate(chat_id, user_id):
        return
    
    # Анти-спам
    if settings.get(chat_id, "antispam_enabled"):
        max_msg = settings.get(chat_id, "antispam_messages")
        seconds = settings.get(chat_id, "antispam_seconds")
        
        if antispam.check(chat_id, user_id, max_msg, seconds):
            try:
                bot.delete_message(chat_id, message.message_id)
                
                # ИСПРАВЛЕНИЕ: Используем функцию для совместимости
                bot.restrict_chat_member(
                    chat_id, user_id,
                    until_date=datetime.now() + timedelta(minutes=5),
                    permissions=get_mute_permissions()
                )
                
                bot.send_message(
                    chat_id,
                    f"🔇 {get_user_display(message.from_user)} замучен на 5 мин (спам)"
                )
                stats.increment(chat_id, "spam_blocked")
                stats.increment(chat_id, "mutes")
                return
                
            except Exception as e:
                print(f"❌ Anti-spam error: {e}")
    
    # Анти-ссылки
    if settings.get(chat_id, "antilink_enabled") and has_links(text):
        try:
            bot.delete_message(chat_id, message.message_id)
            bot.send_message(
                chat_id,
                f"🔗 Сообщение {get_user_display(message.from_user)} удалено (ссылки запрещены)"
            )
            stats.increment(chat_id, "links_blocked")
            stats.increment(chat_id, "deleted_messages")
            return
        except Exception as e:
            print(f"❌ Anti-link error: {e}")
    
    # Триггер-слова
    found_words = triggers.find_in_text(text)
    
    if not found_words:
        return
    
    try:
        bot.delete_message(chat_id, message.message_id)
        
        censored = ", ".join(censor_word(w) for w in found_words)
        user_display = get_user_display(message.from_user)
        
        bot.send_message(
            chat_id,
            f"🚫 Сообщение от {user_display} удалено\n"
            f"📛 Причина: {censored}"
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
            bot.send_message(chat_id, "⚠️ Нет прав на удаление сообщений!")
    except Exception as e:
        print(f"❌ Error: {e}")

# ================================
# Запуск
# ================================
def main():
    print("=" * 50)
    print("🤖 Бот модерации запущен!")
    print(f"📁 Триггер-слова: {triggers.count()}")
    print(f"📁 Логи: {LOG_PATH}")
    print("=" * 50)
    
    while True:
        try:
            bot.infinity_polling(
                timeout=60,
                long_polling_timeout=60,
                allowed_updates=["message", "callback_query"]
            )
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            print("🔄 Перезапуск через 5 секунд...")
            time.sleep(5)

if __name__ == "__main__":
    main()
