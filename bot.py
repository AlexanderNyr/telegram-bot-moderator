import telebot
import os
from datetime import datetime

# ================================
# Определяем папку, где лежит bot.py
# Get the directory where bot.py is located
# ================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ================================
# Чтение токена
# Read token
# ================================
token_path = os.path.join(BASE_DIR, "token.txt")
with open(token_path, "r", encoding="utf-8") as f:
    TOKEN = f.read().strip()

bot = telebot.TeleBot(TOKEN)

# ================================
# Пути к файлам
# File paths
# ================================
trigger_path = os.path.join(BASE_DIR, "trigger.txt")
log_path = os.path.join(BASE_DIR, "log.txt")

# ================================
# Загрузка триггер-слов
# Load trigger words
# ================================
def load_triggers():
    if os.path.exists(trigger_path):
        with open(trigger_path, "r", encoding="utf-8") as f:
            return [line.strip().lower() for line in f if line.strip()]
    return []

trigger_words = load_triggers()

# ================================
# Сохранение логов
# Save logs
# ================================
def write_log(text):
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(text + "\n")

# ================================
# Цензура слова
# Word censoring
# ================================
def censor_word(word):
    if len(word) <= 2:
        return word[0] + "*" if len(word) == 2 else word
    return word[0] + "*" * (len(word) - 2) + word[-1]

# ================================
# Команда /addword
# Add new trigger word
# ================================
@bot.message_handler(commands=["addword"])
def add_word(message):
    global trigger_words
    parts = message.text.split(maxsplit=1)

    if len(parts) < 2:
        bot.reply_to(message, "Используй: /addword слово\nUse: /addword word")
        return

    word = parts[1].lower().strip()

    if word in trigger_words:
        bot.reply_to(message, "Это слово уже есть.\nThis word already exists.")
        return

    trigger_words.append(word)

    with open(trigger_path, "a", encoding="utf-8") as f:
        f.write(word + "\n")

    bot.reply_to(message, f"Слово добавлено: {word}\nWord added: {word}")

# ================================
# Команда /delword
# Delete trigger word
# ================================
@bot.message_handler(commands=["delword"])
def del_word(message):
    global trigger_words
    parts = message.text.split(maxsplit=1)

    if len(parts) < 2:
        bot.reply_to(message, "Используй: /delword слово\nUse: /delword word")
        return

    word = parts[1].lower().strip()

    if word not in trigger_words:
        bot.reply_to(message, "Такого слова нет.\nThis word does not exist.")
        return

    trigger_words.remove(word)

    with open(trigger_path, "w", encoding="utf-8") as f:
        for w in trigger_words:
            f.write(w + "\n")

    bot.reply_to(message, f"Слово удалено: {word}\nWord removed: {word}")

# ================================
# Обработка всех сообщений
# Handle all messages
# ================================
@bot.message_handler(func=lambda message: True)
def handle_message(message):

    # Личка
    # Private chat
    if message.chat.type == "private":
        bot.send_message(
            message.chat.id,
            "Привет! 👋\n"
            "Я удаляю сообщения с запрещёнными словами в группах.\n"
            "Команды:\n"
            "/addword слово — добавить слово\n"
            "/delword слово — удалить слово\n\n"
            "Hi! 👋\n"
            "I delete messages with forbidden words in groups.\n"
            "Commands:\n"
            "/addword word — add word\n"
            "/delword word — delete word"
        )
        return

    # Группы
    # Groups
    if message.chat.type in ["group", "supergroup"]:
        if not message.text:
            return

        text = message.text.lower()

        # Если написали "бот"
        # If someone wrote "bot"
        if text.strip() == "бот":
            bot.send_message(message.chat.id, "на месте ✅")
            return

        found_words = []

        for word in trigger_words:
            if word in text:
                found_words.append(word)

        if found_words:
            try:
                bot.delete_message(message.chat.id, message.message_id)

                censored = [censor_word(w) for w in found_words]

                bot.send_message(
                    message.chat.id,
                    f"Сообщение удалено из-за слов: {', '.join(censored)}\n"
                    f"Message deleted because of: {', '.join(censored)}"
                )

                log_text = (
                    f"[{datetime.now()}] "
                    f"Chat: {message.chat.title} | "
                    f"User: {message.from_user.username} | "
                    f"Text: {message.text}"
                )

                write_log(log_text)

                print("Удалено | Deleted:", message.text)

            except Exception as e:
                print("Ошибка | Error:", e)

# ================================
# Запуск
# Start bot
# ================================
print("Бот запущен | Bot is running!")
bot.polling(none_stop=True)
