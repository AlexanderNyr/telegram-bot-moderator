import telebot
import os

# --- Путь к директории бота ---
BASE_DIR = r"C:\bot"  # <-- твоя директория с bot.py, token.txt, trigger.txt

# --- Чтение токена ---
token_path = os.path.join(BASE_DIR, "token.txt")
with open(token_path, "r", encoding="utf-8") as f:
    TOKEN = f.read().strip()

bot = telebot.TeleBot(TOKEN)

# --- Чтение триггер-слов ---
trigger_path = os.path.join(BASE_DIR, "trigger.txt")
if os.path.exists(trigger_path):
    with open(trigger_path, "r", encoding="utf-8") as f:
        trigger_words = [line.strip().lower() for line in f if line.strip()]
else:
    trigger_words = []
    print("Файл trigger.txt не найден. Список триггер-слов пуст.")

# --- Функция цензуры слова ---
def censor_word(word):
    if len(word) <= 2:
        return word[0] + "*" if len(word) == 2 else word
    return word[0] + "*" * (len(word) - 2) + word[-1]

# --- Обработка сообщений ---
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    # Личка
    if message.chat.type == "private":
        bot.send_message(
            message.chat.id,
            "Привет! Я бот, который удаляет сообщения с нежелательными словами в группах.\n"
            "В личных сообщениях я могу объяснить свой функционал.\n"
            "В группах я автоматически удаляю сообщения с триггерными словами и уведомляю об этом."
        )
        return

    # Группа
    if message.chat.type in ["group", "supergroup"]:
        if not message.text:
            return

        text = message.text.lower()
        found_words = []

        for word in trigger_words:
            if word in text:
                found_words.append(word)

        if found_words:
            try:
                bot.delete_message(message.chat.id, message.message_id)
                # Цензурируем найденные слова
                censored = [censor_word(w) for w in found_words]
                bot.send_message(
                    message.chat.id,
                    f"Сообщение было удалено из-за нежелательных слов: {', '.join(censored)}"
                )
                print(f"Удалено сообщение: {message.text}")
            except Exception as e:
                print(f"Не удалось удалить сообщение: {e}")

# --- Запуск бота ---
print("Бот запущен!")
bot.polling(none_stop=True)