/**
 * Telegram moderation bot — Cloudflare Workers edition.
 *
 * Webhook-based port of bot.py (pyTelegramBotAPI) with full feature parity:
 * all 28 commands, RU/EN localization, per-chat trigger words, warnings with
 * expiry, anti-spam, anti-links, welcome/goodbye, stats and inline keyboards.
 *
 * Storage: Cloudflare D1 (SQLite) — free tier friendly:
 *   Workers Free: 100,000 requests/day, 10 ms CPU per request
 *   D1 Free:      5,000,000 rows read/day, 100,000 rows written/day, 5 GB
 *
 * Secrets (wrangler secret put BOT_TOKEN / WEBHOOK_SECRET).
 * GET /setup?key=<WEBHOOK_SECRET> registers the Telegram webhook.
 * POST /webhook receives updates (verified via X-Telegram-Bot-Api-Secret-Token).
 */

const ANONYMOUS_ADMIN_ID = 1087968824; // GroupAnonymousBot
const FALLBACK_LANGUAGE = "ru";

const DEFAULT_SETTINGS = {
  max_warns: 3,
  warn_expire_days: 30,
  antispam_enabled: true,
  antispam_messages: 5,
  antispam_seconds: 10,
  antilink_enabled: false,
  welcome_enabled: false,
  goodbye_enabled: false,
};

const LANG_NAMES = { ru: "Русский", en: "English" };

const LANGUAGES = {
  ru: {
    // Access control
    no_access: "⛔ Нет доступа",
    admins_only: "⛔ Только для админов",
    groups_only: "⛔ Эта команда работает только в группах",
    groups_only_short: "⛔ Только в группах",
    disable_anonymity: "⛔ Отключите анонимность для этой команды",
    creator_only: "⛔ Только для создателя чата",
    // /myid
    myid: "🆔 Твой ID: `{id}`\n💬 ID чата: `{chat}`",
    // Help
    help_text:
      "🤖 *Бот модерации*\n\n" +
      "📋 *Основные команды:*\n" +
      "• `/addword <слово>` — добавить триггер\n" +
      "• `/delword <слово>` — удалить триггер\n" +
      "• `/listwords` — список триггеров\n\n" +
      "👮 *Модерация:*\n" +
      "• `/warn` — предупреждение\n" +
      "• `/mute` — мут пользователя\n" +
      "• `/ban` — бан пользователя\n" +
      "• `/kick` — кик пользователя\n\n" +
      "📊 `/stats` — статистика\n" +
      "⚙️ `/settings` — настройки\n" +
      "🌐 `/lang` — язык бота\n" +
      "🆔 `/myid` — узнать свой ID\n" +
      "❓ `/commands` — все команды",
    commands_text:
      "\n📋 *Полный список команд:*\n\n" +
      "*Триггер-слова:*\n" +
      "• `/addword <слово>` — добавить\n" +
      "• `/addwords <слова>` — добавить несколько\n" +
      "• `/delword <слово>` — удалить\n" +
      "• `/listwords` — показать список\n" +
      "• `/clearwords` — очистить все\n\n" +
      "*Модерация пользователей:*\n" +
      "• `/warn [user] [причина]` — предупреждение\n" +
      "• `/unwarn [user]` — снять предупреждение\n" +
      "• `/warns [user]` — список предупреждений\n" +
      "• `/clearwarns [user]` — очистить предупреждения\n" +
      "• `/mute [user] [время]` — мут (1h, 30m, 1d)\n" +
      "• `/unmute [user]` — размут\n" +
      "• `/ban [user] [причина]` — бан\n" +
      "• `/unban [user_id]` — разбан\n" +
      "• `/kick [user]` — кик\n\n" +
      "*Информация:*\n" +
      "• `/userinfo [user]` — инфо о пользователе\n" +
      "• `/chatinfo` — инфо о чате\n" +
      "• `/stats` — статистика модерации\n" +
      "• `/myid` — ваш Telegram ID\n\n" +
      "*Утилиты:*\n" +
      "• `/clear <N>` — удалить N сообщений\n" +
      "• `/pin` — закрепить сообщение\n" +
      "• `/unpin` — открепить сообщение\n\n" +
      "*Настройки:*\n" +
      "• `/settings` — настройки чата\n" +
      "• `/setwelcome <текст>` — текст приветствия\n" +
      "• `/setgoodbye <текст>` — текст прощания\n" +
      "• `/setmaxwarns <N>` — макс. предупреждений\n" +
      "• `/lang` — язык бота\n",
    commands_footer: "_Используйте reply или укажите ID пользователя_",
    // Callbacks
    cb_error: "Ошибка обработки",
    confirm_title: "⚠️ *Подтверждение*\n\nСлов: {count}\nПодтвердите 3 раза: /confirm",
    stats_groups_only: "📊 Статистика доступна только в группах",
    settings_groups_only: "⚙️ Настройки доступны только в группах",
    antispam_name: "Анти-спам",
    antilink_name: "Анти-ссылки",
    welcome_name: "Приветствия",
    goodbye_name: "Прощания",
    toggle_on_m: "включен",
    toggle_off_m: "выключен",
    toggle_on_f: "включены",
    toggle_off_f: "выключены",
    main_menu: "🤖 Главное меню",
    // /confirm
    confirm_not_started: "❓ Сначала запросите список слов",
    confirm_progress: "✅ Подтверждено {count}/3",
    triggers_empty: "📭 Список триггеров пуст",
    triggers_file_caption: "📄 Триггер-слова ({count} шт.)",
    // Trigger word commands
    addword_usage: "📝 Использование: `/addword <слово>`",
    word_too_long: "⚠️ Слово слишком длинное (макс. 100 символов)",
    word_added: "✅ Добавлено: `{word}`",
    word_exists: "⚠️ Это слово уже в списке",
    addwords_usage: "📝 Использование: `/addwords слово1 слово2 слово3`",
    addwords_done: "✅ Добавлено слов: {count}",
    delword_usage: "📝 Использование: `/delword <слово>`",
    word_deleted: "✅ Удалено: `{word}`",
    word_not_found: "⚠️ Слово не найдено в списке",
    clearwords_done: "🗑️ Удалено триггер-слов: {count}",
    listwords_confirm: "⚠️ В списке: {count} слов\nПодтвердите 3 раза: /confirm",
    // Moderation
    warn_usage: "📝 Ответьте на сообщение или: `/warn <user_id> причина`",
    target_admin_warn: "⚠️ Нельзя выдать предупреждение админу чата",
    reason_not_set: "Не указана",
    warn_header: "⚠️ *Предупреждение*\n\n👤 Пользователь: {user}\n📛 Причина: {reason}\n📊 Предупреждений: {count}/{max}",
    warn_limit_ban: "🔨 {user} забанен (достигнут лимит предупреждений)",
    ban_error: "❌ Ошибка бана: {error}",
    unwarn_usage: "📝 Ответьте на сообщение или: `/unwarn <user_id>`",
    unwarn_done: "✅ Предупреждение снято. Осталось: {count}",
    no_warns_user: "⚠️ У пользователя нет предупреждений",
    warns_usage: "📝 Ответьте на сообщение или: `/warns <user_id>`",
    user_no_warns: "✅ У {user} нет предупреждений",
    warns_list_header: "📋 *Предупреждения {user}:*\n\n",
    clearwarns_usage: "📝 Ответьте на сообщение или: `/clearwarns <user_id>`",
    clearwarns_done: "✅ Снято предупреждений: {count}",
    mute_usage: "📝 Ответьте на сообщение или: `/mute <user_id> [время]`\nВремя: 1m, 1h, 1d, 1w",
    user_not_found: "❌ Пользователь не найден",
    target_admin_mute: "⚠️ Нельзя замутить админа чата",
    bad_duration: "⚠️ Неверный формат времени. Примеры: 30m, 1h, 1d",
    muted_forever: "навсегда",
    muted: "🔇 {user} замучен на {duration}",
    unmute_usage: "📝 Ответьте на сообщение или: `/unmute <user_id>`",
    unmuted: "🔊 {user} размучен",
    action_error: "❌ Ошибка: {error}",
    ban_usage: "📝 Ответьте на сообщение или: `/ban <user_id> [причина]`",
    target_admin_ban: "⚠️ Нельзя забанить админа чата",
    banned: "🔨 {user} забанен",
    ban_reason_line: "\n📛 Причина: {reason}",
    unban_usage: "📝 Ответьте на сообщение или: `/unban <user_id>`",
    unbanned: "✅ Пользователь `{id}` разбанен",
    kick_usage: "📝 Ответьте на сообщение или: `/kick <user_id>`",
    target_admin_kick: "⚠️ Нельзя кикнуть админа чата",
    kicked: "👢 {user} кикнут",
    // Durations
    dur_sec: "{n} сек",
    dur_min: "{n} мин",
    dur_hour: "{n} ч",
    dur_day: "{n} дн",
    // /userinfo
    userinfo_title: "👤 *Информация о пользователе*\n\n",
    ui_name: "├ Имя: {value}",
    ui_surname: "├ Фамилия: {value}",
    ui_status: "├ Статус в чате: {value}",
    ui_bot: "├ Бот: {value}",
    ui_warns: "└ Предупреждений: {count}",
    status_creator: "👑 Создатель",
    status_admin: "⭐ Админ",
    status_member: "👤 Участник",
    status_restricted: "🔇 Ограничен",
    status_left: "🚪 Покинул",
    status_kicked: "🚫 Забанен",
    yes: "Да",
    no: "Нет",
    // /chatinfo
    chatinfo_title: "💬 *Информация о чате*\n\n",
    ci_title: "├ Название: {value}",
    ci_type: "├ Тип: {value}",
    ci_members: "└ Участников: {count}",
    // /stats
    stats_title: "📊 *Статистика модерации*\n\n",
    st_deleted: "├ 🗑️ Удалено сообщений: {count}",
    st_warns: "├ ⚠️ Предупреждений: {count}",
    st_mutes: "├ 🔇 Мутов: {count}",
    st_bans: "├ 🔨 Банов: {count}",
    st_kicks: "├ 👢 Киков: {count}",
    st_spam: "├ 🔄 Заблокировано спама: {count}",
    st_links: "└ 🔗 Заблокировано ссылок: {count}",
    // Utilities
    clear_usage: "📝 Использование: `/clear <количество>`",
    clear_range: "⚠️ Укажите число от 1 до 100",
    clear_done: "🗑️ Удалено сообщений: {count}",
    not_a_number: "⚠️ Укажите число",
    pin_usage: "📝 Ответьте на сообщение для закрепления",
    pinned: "📌 Сообщение закреплено",
    unpinned: "📌 Сообщение откреплено",
    // Settings
    settings_title: "⚙️ *Настройки чата*\n\n",
    set_max_warns: "├ Макс. предупреждений: {value}",
    set_antispam: "├ Анти-спам: {value}",
    set_antilink: "├ Анти-ссылки: {value}",
    set_welcome: "├ Приветствия: {value}",
    set_goodbye: "├ Прощания: {value}",
    set_language: "└ Язык: {value}",
    setmaxwarns_usage: "📝 Использование: `/setmaxwarns <число>`",
    setmaxwarns_range: "⚠️ Укажите число от 1 до 10",
    setmaxwarns_done: "✅ Максимум предупреждений: {value}",
    setwelcome_usage: "📝 Использование: `/setwelcome <текст>`\n\nПеременные:\n• `{user}` — имя пользователя\n• `{chat}` — название чата",
    setwelcome_done: "✅ Приветствие обновлено и включено",
    setgoodbye_usage: "📝 Использование: `/setgoodbye <текст>`\n\nПеременные:\n• `{user}` — имя пользователя\n• `{chat}` — название чата",
    setgoodbye_done: "✅ Текст прощания обновлён и включён",
    // Language
    lang_text: "🌐 Язык: {current}",
    lang_set: "✅ Язык установлен: {value}",
    kb_lang: "🌐 Язык: {value}",
    // Welcome / goodbye
    default_welcome: "👋 Добро пожаловать, {user}!",
    default_goodbye: "👋 {user} покинул(а) чат",
    chat_word: "чат",
    // Message handling
    private_hello: "👋 Привет! Я бот модерации для групп.\n\n📌 Добавьте меня в группу и дайте права администратора.\n\n/help — список команд\n/myid — узнать свой ID",
    im_working: "✅ Работаю!",
    spam_muted: "🔇 {user} замучен на 5 мин (спам)",
    links_removed: "🔗 Сообщение {user} удалено (ссылки запрещены)",
    msg_deleted: "🚫 Сообщение от {user} удалено\n📛 Причина: {censored}",
    no_delete_rights: "⚠️ Нет прав на удаление сообщений!",
    // Bot self-check
    need_admin_rights: "⚠️ Сделайте меня администратором группы (с правом удаления сообщений и блокировки), иначе модерация работать не будет",
  },
  en: {
    // Access control
    no_access: "⛔ No access",
    admins_only: "⛔ Admins only",
    groups_only: "⛔ This command works only in groups",
    groups_only_short: "⛔ Groups only",
    disable_anonymity: "⛔ Disable anonymity to use this command",
    creator_only: "⛔ Chat creator only",
    // /myid
    myid: "🆔 Your ID: `{id}`\n💬 Chat ID: `{chat}`",
    // Help
    help_text:
      "🤖 *Moderation bot*\n\n" +
      "📋 *Basic commands:*\n" +
      "• `/addword <word>` — add a trigger word\n" +
      "• `/delword <word>` — remove a trigger word\n" +
      "• `/listwords` — list trigger words\n\n" +
      "👮 *Moderation:*\n" +
      "• `/warn` — warn a user\n" +
      "• `/mute` — mute a user\n" +
      "• `/ban` — ban a user\n" +
      "• `/kick` — kick a user\n\n" +
      "📊 `/stats` — statistics\n" +
      "⚙️ `/settings` — settings\n" +
      "🌐 `/lang` — bot language\n" +
      "🆔 `/myid` — get your ID\n" +
      "❓ `/commands` — all commands",
    commands_text:
      "\n📋 *Full command list:*\n\n" +
      "*Trigger words:*\n" +
      "• `/addword <word>` — add\n" +
      "• `/addwords <words>` — add several\n" +
      "• `/delword <word>` — remove\n" +
      "• `/listwords` — show the list\n" +
      "• `/clearwords` — remove all\n\n" +
      "*User moderation:*\n" +
      "• `/warn [user] [reason]` — warning\n" +
      "• `/unwarn [user]` — remove a warning\n" +
      "• `/warns [user]` — list warnings\n" +
      "• `/clearwarns [user]` — clear warnings\n" +
      "• `/mute [user] [time]` — mute (1h, 30m, 1d)\n" +
      "• `/unmute [user]` — unmute\n" +
      "• `/ban [user] [reason]` — ban\n" +
      "• `/unban [user_id]` — unban\n" +
      "• `/kick [user]` — kick\n\n" +
      "*Information:*\n" +
      "• `/userinfo [user]` — user info\n" +
      "• `/chatinfo` — chat info\n" +
      "• `/stats` — moderation statistics\n" +
      "• `/myid` — your Telegram ID\n\n" +
      "*Utilities:*\n" +
      "• `/clear <N>` — delete N messages\n" +
      "• `/pin` — pin a message\n" +
      "• `/unpin` — unpin a message\n\n" +
      "*Settings:*\n" +
      "• `/settings` — chat settings\n" +
      "• `/setwelcome <text>` — welcome text\n" +
      "• `/setgoodbye <text>` — farewell text\n" +
      "• `/setmaxwarns <N>` — max warnings\n" +
      "• `/lang` — bot language\n",
    commands_footer: "_Use a reply or specify a user ID_",
    // Callbacks
    cb_error: "Processing error",
    confirm_title: "⚠️ *Confirmation*\n\nWords: {count}\nConfirm 3 times: /confirm",
    stats_groups_only: "📊 Statistics are available only in groups",
    settings_groups_only: "⚙️ Settings are available only in groups",
    antispam_name: "Anti-spam",
    antilink_name: "Anti-links",
    welcome_name: "Welcome messages",
    goodbye_name: "Farewell messages",
    toggle_on_m: "enabled",
    toggle_off_m: "disabled",
    toggle_on_f: "enabled",
    toggle_off_f: "disabled",
    main_menu: "🤖 Main menu",
    // /confirm
    confirm_not_started: "❓ Request the word list first",
    confirm_progress: "✅ Confirmed {count}/3",
    triggers_empty: "📭 The trigger word list is empty",
    triggers_file_caption: "📄 Trigger words ({count})",
    // Trigger word commands
    addword_usage: "📝 Usage: `/addword <word>`",
    word_too_long: "⚠️ The word is too long (max. 100 characters)",
    word_added: "✅ Added: `{word}`",
    word_exists: "⚠️ This word is already in the list",
    addwords_usage: "📝 Usage: `/addwords word1 word2 word3`",
    addwords_done: "✅ Words added: {count}",
    delword_usage: "📝 Usage: `/delword <word>`",
    word_deleted: "✅ Removed: `{word}`",
    word_not_found: "⚠️ Word not found in the list",
    clearwords_done: "🗑️ Trigger words removed: {count}",
    listwords_confirm: "⚠️ In the list: {count} words\nConfirm 3 times: /confirm",
    // Moderation
    warn_usage: "📝 Reply to a message or: `/warn <user_id> reason`",
    target_admin_warn: "⚠️ Cannot warn a chat admin",
    reason_not_set: "Not specified",
    warn_header: "⚠️ *Warning*\n\n👤 User: {user}\n📛 Reason: {reason}\n📊 Warnings: {count}/{max}",
    warn_limit_ban: "🔨 {user} banned (warning limit reached)",
    ban_error: "❌ Ban error: {error}",
    unwarn_usage: "📝 Reply to a message or: `/unwarn <user_id>`",
    unwarn_done: "✅ Warning removed. Remaining: {count}",
    no_warns_user: "⚠️ The user has no warnings",
    warns_usage: "📝 Reply to a message or: `/warns <user_id>`",
    user_no_warns: "✅ {user} has no warnings",
    warns_list_header: "📋 *Warnings for {user}:*\n\n",
    clearwarns_usage: "📝 Reply to a message or: `/clearwarns <user_id>`",
    clearwarns_done: "✅ Warnings removed: {count}",
    mute_usage: "📝 Reply to a message or: `/mute <user_id> [time]`\nTime: 1m, 1h, 1d, 1w",
    user_not_found: "❌ User not found",
    target_admin_mute: "⚠️ Cannot mute a chat admin",
    bad_duration: "⚠️ Invalid time format. Examples: 30m, 1h, 1d",
    muted_forever: "forever",
    muted: "🔇 {user} muted for {duration}",
    unmute_usage: "📝 Reply to a message or: `/unmute <user_id>`",
    unmuted: "🔊 {user} unmuted",
    action_error: "❌ Error: {error}",
    ban_usage: "📝 Reply to a message or: `/ban <user_id> [reason]`",
    target_admin_ban: "⚠️ Cannot ban a chat admin",
    banned: "🔨 {user} banned",
    ban_reason_line: "\n📛 Reason: {reason}",
    unban_usage: "📝 Reply to a message or: `/unban <user_id>`",
    unbanned: "✅ User `{id}` unbanned",
    kick_usage: "📝 Reply to a message or: `/kick <user_id>`",
    target_admin_kick: "⚠️ Cannot kick a chat admin",
    kicked: "👢 {user} kicked",
    // Durations
    dur_sec: "{n} sec",
    dur_min: "{n} min",
    dur_hour: "{n} h",
    dur_day: "{n} d",
    // /userinfo
    userinfo_title: "👤 *User info*\n\n",
    ui_name: "├ Name: {value}",
    ui_surname: "├ Last name: {value}",
    ui_status: "├ Chat status: {value}",
    ui_bot: "├ Bot: {value}",
    ui_warns: "└ Warnings: {count}",
    status_creator: "👑 Creator",
    status_admin: "⭐ Admin",
    status_member: "👤 Member",
    status_restricted: "🔇 Restricted",
    status_left: "🚪 Left",
    status_kicked: "🚫 Banned",
    yes: "Yes",
    no: "No",
    // /chatinfo
    chatinfo_title: "💬 *Chat info*\n\n",
    ci_title: "├ Title: {value}",
    ci_type: "├ Type: {value}",
    ci_members: "└ Members: {count}",
    // /stats
    stats_title: "📊 *Moderation statistics*\n\n",
    st_deleted: "├ 🗑️ Messages deleted: {count}",
    st_warns: "├ ⚠️ Warnings issued: {count}",
    st_mutes: "├ 🔇 Mutes: {count}",
    st_bans: "├ 🔨 Bans: {count}",
    st_kicks: "├ 👢 Kicks: {count}",
    st_spam: "├ 🔄 Spam blocked: {count}",
    st_links: "└ 🔗 Links blocked: {count}",
    // Utilities
    clear_usage: "📝 Usage: `/clear <count>`",
    clear_range: "⚠️ Specify a number from 1 to 100",
    clear_done: "🗑️ Messages deleted: {count}",
    not_a_number: "⚠️ Specify a number",
    pin_usage: "📝 Reply to a message to pin it",
    pinned: "📌 Message pinned",
    unpinned: "📌 Message unpinned",
    // Settings
    settings_title: "⚙️ *Chat settings*\n\n",
    set_max_warns: "├ Max warnings: {value}",
    set_antispam: "├ Anti-spam: {value}",
    set_antilink: "├ Anti-links: {value}",
    set_welcome: "├ Welcome messages: {value}",
    set_goodbye: "├ Farewell messages: {value}",
    set_language: "└ Language: {value}",
    setmaxwarns_usage: "📝 Usage: `/setmaxwarns <number>`",
    setmaxwarns_range: "⚠️ Specify a number from 1 to 10",
    setmaxwarns_done: "✅ Max warnings: {value}",
    setwelcome_usage: "📝 Usage: `/setwelcome <text>`\n\nVariables:\n• `{user}` — user name\n• `{chat}` — chat title",
    setwelcome_done: "✅ Welcome message updated and enabled",
    setgoodbye_usage: "📝 Usage: `/setgoodbye <text>`\n\nVariables:\n• `{user}` — user name\n• `{chat}` — chat title",
    setgoodbye_done: "✅ Farewell message updated and enabled",
    // Language
    lang_text: "🌐 Language: {current}",
    lang_set: "✅ Language set: {value}",
    kb_lang: "🌐 Language: {value}",
    // Welcome / goodbye
    default_welcome: "👋 Welcome, {user}!",
    default_goodbye: "👋 {user} left the chat",
    chat_word: "chat",
    // Message handling
    private_hello: "👋 Hi! I'm a group moderation bot.\n\n📌 Add me to a group and grant me administrator rights.\n\n/help — command list\n/myid — get your ID",
    im_working: "✅ I'm working!",
    spam_muted: "🔇 {user} muted for 5 min (spam)",
    links_removed: "🔗 Message from {user} deleted (links are not allowed)",
    msg_deleted: "🚫 Message from {user} deleted\n📛 Reason: {censored}",
    no_delete_rights: "⚠️ Not enough rights to delete messages!",
    // Bot self-check
    need_admin_rights: "⚠️ Please make me a group administrator (with rights to delete messages and ban users), otherwise moderation will not work",
  },
};

// ================================
// Small helpers
// ================================
function tr(lang, key, kwargs) {
  let text = (LANGUAGES[lang] || {})[key];
  if (text === undefined) text = (LANGUAGES[FALLBACK_LANGUAGE] || {})[key];
  if (text === undefined) text = key;
  if (kwargs) {
    text = text.replace(/\{(\w+)\}/g, (m, k) => (Object.prototype.hasOwnProperty.call(kwargs, k) ? String(kwargs[k]) : m));
  }
  return text;
}

// FIX: escape Markdown specials in user data (legacy Markdown parse mode)
function mdEscape(text) {
  return String(text).replace(/([_*`[])/g, "\\$1");
}

function censorWord(word) {
  const length = word.length;
  if (length <= 1) return "*";
  if (length === 2) return word[0] + "*";
  return word[0] + "*".repeat(length - 2) + word[length - 1];
}

function parseDuration(text) {
  const match = /^(\d+)([mhdw])$/.exec(String(text || "").toLowerCase());
  if (!match) return null;
  const value = parseInt(match[1], 10);
  const multipliers = { m: 60, h: 3600, d: 86400, w: 604800 };
  const seconds = value * multipliers[match[2]];
  // FIX: reject zero durations and values Telegram cannot accept
  if (seconds < 60 || seconds > 365 * 86400) return null;
  return seconds;
}

// looks like a duration token but may still be invalid ("0m", "99w")
function looksLikeDuration(text) {
  return /^\d+[mhdw]$/.test(String(text || "").toLowerCase());
}

function formatDuration(seconds, lang) {
  if (seconds < 60) return tr(lang, "dur_sec", { n: seconds });
  if (seconds < 3600) return tr(lang, "dur_min", { n: Math.floor(seconds / 60) });
  if (seconds < 86400) return tr(lang, "dur_hour", { n: Math.floor(seconds / 3600) });
  return tr(lang, "dur_day", { n: Math.floor(seconds / 86400) });
}

function userDisplay(user) {
  if (!user) return "ID:?";
  if (user.username) return "@" + user.username;
  return user.first_name || "ID:" + user.id;
}

function escapeRegExp(s) {
  return String(s).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

// FIX: a much wider curated TLD list (the old short list was bypassed
// with e.g. .de, .fr or .pl links)
const LINK_TLDS = [
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
];

const LINK_PATTERNS = [
  /https?:\/\/\S+/i,
  /tg:\/\/\S+/i,
  /(?<![\w.])www\.\S+/i,
  /(?<![\w.])t\.me\/\S+/i,
  /(?<![\w.])telegram\.me\/\S+/i,
  /(?<![\w.])telegram\.dog\/\S+/i,
  /(?<![\w.])joinchat\.to\/\S+/i,
  // a domain without a protocol, including subdomains: site.ru, sub.site.online
  new RegExp("(?:(?<=\\s)|^)(?:[a-z0-9-]+\\.)+(?:" + [...LINK_TLDS].sort().join("|") + ")(?![\\w-])", "i"),
];

function hasLinks(text) {
  if (!text) return false;
  for (const pattern of LINK_PATTERNS) {
    if (pattern.test(text)) return true;
  }
  return false;
}

// FIX: detect links via Telegram entities as well — covers captions and
// inline links (text_link) that the plain-text regex cannot see
function messageHasLinkEntities(m) {
  for (const list of [m.entities, m.caption_entities]) {
    if (!Array.isArray(list)) continue;
    for (const entity of list) {
      if (entity && (entity.type === "url" || entity.type === "text_link")) return true;
    }
  }
  return false;
}

function mutePermissions() {
  return {
    can_send_messages: false,
    can_send_audios: false,
    can_send_documents: false,
    can_send_photos: false,
    can_send_videos: false,
    can_send_video_notes: false,
    can_send_voice_notes: false,
    can_send_polls: false,
    can_send_other_messages: false,
    can_add_web_page_previews: false,
    can_change_info: false,
    can_invite_users: false,
    can_pin_messages: false,
    can_manage_topics: false,
  };
}

function unmutePermissions() {
  return {
    can_send_messages: true,
    can_send_audios: true,
    can_send_documents: true,
    can_send_photos: true,
    can_send_videos: true,
    can_send_video_notes: true,
    can_send_voice_notes: true,
    can_send_polls: true,
    can_send_other_messages: true,
    can_add_web_page_previews: true,
    can_change_info: false,
    can_invite_users: true,
    can_pin_messages: false,
    can_manage_topics: false,
  };
}

function isGroup(m) {
  return m.chat && (m.chat.type === "group" || m.chat.type === "supergroup");
}

function isPrivate(m) {
  return m.chat && m.chat.type === "private";
}

// ================================
// Telegram API wrapper
// ================================
class Bot {
  constructor(env) {
    this.env = env;
    this._settingsCache = new Map(); // chatId -> settings object
    this._triggersCache = new Map(); // chatId -> string[] words
    this._regexCache = new Map(); // chatId -> {src, regexes}
  }

  async tg(method, payload) {
    const url = "https://api.telegram.org/bot" + this.env.BOT_TOKEN + "/" + method;
    const opts = { method: "POST" };
    if (payload instanceof FormData) {
      opts.body = payload;
    } else {
      opts.headers = { "Content-Type": "application/json" };
      opts.body = JSON.stringify(payload || {});
    }
    const resp = await fetch(url, opts);
    let data;
    try {
      data = await resp.json();
    } catch (e) {
      throw new Error("Telegram API: bad response for " + method);
    }
    if (!data.ok) {
      const err = new Error(data.description || "Telegram API error (" + method + ")");
      err.code = data.error_code;
      throw err;
    }
    return data.result;
  }

  sendMessage(chatId, text, extra) {
    return this.tg("sendMessage", Object.assign({ chat_id: chatId, text: text }, extra || {}));
  }

  replyTo(m, text, extra) {
    return this.sendMessage(m.chat.id, text, Object.assign({ reply_to_message_id: m.message_id }, extra || {}));
  }

  deleteMessage(chatId, messageId) {
    return this.tg("deleteMessage", { chat_id: chatId, message_id: messageId });
  }

  restrictChatMember(chatId, userId, untilDateSec, permissions) {
    const params = { chat_id: chatId, user_id: userId, permissions: permissions };
    if (untilDateSec) params.until_date = untilDateSec;
    return this.tg("restrictChatMember", params);
  }

  banChatMember(chatId, userId) {
    return this.tg("banChatMember", { chat_id: chatId, user_id: userId });
  }

  unbanChatMember(chatId, userId, onlyIfBanned) {
    return this.tg("unbanChatMember", { chat_id: chatId, user_id: userId, only_if_banned: !!onlyIfBanned });
  }

  getChatMember(chatId, userId) {
    return this.tg("getChatMember", { chat_id: chatId, user_id: userId });
  }

  answerCallbackQuery(id, text, showAlert) {
    return this.tg("answerCallbackQuery", { callback_query_id: id, text: text || "", show_alert: !!showAlert });
  }

  editMessageReplyMarkup(chatId, messageId, replyMarkup) {
    return this.tg("editMessageReplyMarkup", { chat_id: chatId, message_id: messageId, reply_markup: replyMarkup });
  }

  editMessageText(text, chatId, messageId, extra) {
    return this.tg("editMessageText", Object.assign({ chat_id: chatId, message_id: messageId, text: text }, extra || {}));
  }

  async sendDocument(chatId, filename, content, caption) {
    const fd = new FormData();
    fd.append("chat_id", String(chatId));
    if (caption) fd.append("caption", caption);
    fd.append("document", new Blob([content], { type: "text/plain" }), filename);
    return this.tg("sendDocument", fd);
  }
}

let _meCache = null; // module-level get_me() cache (per isolate)
async function getMe(bot) {
  if (!_meCache) _meCache = await bot.tg("getMe");
  return _meCache;
}

// ================================
// Chat member cache (60 s TTL)
// ================================
const _memberCache = new Map(); // "chat:user" -> {status, exp}

async function getMemberCached(bot, chatId, userId) {
  const key = chatId + ":" + userId;
  const hit = _memberCache.get(key);
  if (hit && hit.exp > Date.now()) return hit.status;
  let status = null;
  try {
    const member = await bot.getChatMember(chatId, userId);
    status = member.status;
  } catch (e) {
    status = null;
  }
  _memberCache.set(key, { status: status, exp: Date.now() + 60000 });
  return status;
}

async function isChatAdmin(bot, chatId, userId) {
  const status = await getMemberCached(bot, chatId, userId);
  return status === "creator" || status === "administrator";
}

async function isCreator(bot, chatId, userId) {
  return (await getMemberCached(bot, chatId, userId)) === "creator";
}

async function canModerate(bot, chatId, userId) {
  if (userId === ANONYMOUS_ADMIN_ID) return true;
  return isChatAdmin(bot, chatId, userId);
}

// ================================
// D1 storage
// ================================
function parseSeed(env) {
  return String(env.SEED_TRIGGER_WORDS || "")
    .split(/[\n,;]+/)
    .map((s) => s.trim().toLowerCase())
    .filter(Boolean);
}

function defaultLang(env) {
  return LANGUAGES[env.DEFAULT_LANG] ? env.DEFAULT_LANG : FALLBACK_LANGUAGE;
}

async function getSettings(bot, chatId) {
  if (bot._settingsCache.has(chatId)) return bot._settingsCache.get(chatId);
  const row = await bot.env.DB.prepare("SELECT data FROM settings WHERE chat_id = ?").bind(chatId).first();
  let data = {};
  if (row && row.data) {
    try {
      data = JSON.parse(row.data);
    } catch (e) {
      data = {};
    }
  }
  const merged = Object.assign({}, DEFAULT_SETTINGS, data);
  bot._settingsCache.set(chatId, merged);
  return merged;
}

async function setSetting(bot, chatId, key, value) {
  const settings = Object.assign({}, await getSettings(bot, chatId));
  settings[key] = value;
  await bot.env.DB
    .prepare("INSERT INTO settings (chat_id, data) VALUES (?, ?) ON CONFLICT(chat_id) DO UPDATE SET data = excluded.data")
    .bind(chatId, JSON.stringify(settings))
    .run();
  bot._settingsCache.set(chatId, settings);
  return settings;
}

async function getLang(bot, chatId) {
  const settings = await getSettings(bot, chatId);
  return LANGUAGES[settings.language] ? settings.language : defaultLang(bot.env);
}

function langName(lang) {
  return LANG_NAMES[lang] || lang;
}

// Per-chat trigger words. FIX: the Python bot used to keep ONE global list;
// here every chat has its own list, seeded from SEED_TRIGGER_WORDS on first use.
async function getTriggerWords(bot, chatId) {
  if (bot._triggersCache.has(chatId)) return bot._triggersCache.get(chatId);
  const db = bot.env.DB;
  let rows = (await db.prepare("SELECT word FROM triggers WHERE chat_id = ?").bind(chatId).all()).results.map((r) => r.word);
  const settings = await getSettings(bot, chatId);
  if (!settings.triggers_seeded) {
    const seed = parseSeed(bot.env);
    if (seed.length) {
      await db.batch(
        seed.map((w) => db.prepare("INSERT OR IGNORE INTO triggers (chat_id, word) VALUES (?, ?)").bind(chatId, w))
      );
      rows = Array.from(new Set(rows.concat(seed))).sort();
    }
    await setSetting(bot, chatId, "triggers_seeded", true);
  }
  bot._triggersCache.set(chatId, rows);
  return rows;
}

async function triggersAdd(bot, chatId, word) {
  word = String(word || "").toLowerCase().trim();
  if (!word) return false;
  const words = await getTriggerWords(bot, chatId);
  if (words.includes(word)) return false;
  await bot.env.DB.prepare("INSERT OR IGNORE INTO triggers (chat_id, word) VALUES (?, ?)").bind(chatId, word).run();
  const next = words.concat([word]).sort();
  bot._triggersCache.set(chatId, next);
  return true;
}

async function triggersAddMany(bot, chatId, wordList) {
  let added = 0;
  const words = await getTriggerWords(bot, chatId);
  const next = words.slice();
  for (const raw of wordList) {
    const word = String(raw || "").toLowerCase().trim();
    if (word && !next.includes(word)) {
      next.push(word);
      added++;
    }
  }
  if (added) {
    await bot.env.DB.batch(
      next
        .filter((w) => !words.includes(w))
        .map((w) => bot.env.DB.prepare("INSERT OR IGNORE INTO triggers (chat_id, word) VALUES (?, ?)").bind(chatId, w))
    );
    next.sort();
    bot._triggersCache.set(chatId, next);
  }
  return added;
}

async function triggersRemove(bot, chatId, word) {
  word = String(word || "").toLowerCase().trim();
  const words = await getTriggerWords(bot, chatId);
  if (!words.includes(word)) return false;
  await bot.env.DB.prepare("DELETE FROM triggers WHERE chat_id = ? AND word = ?").bind(chatId, word).run();
  bot._triggersCache.set(chatId, words.filter((w) => w !== word));
  return true;
}

async function triggersClear(bot, chatId) {
  const words = await getTriggerWords(bot, chatId);
  if (words.length) {
    await bot.env.DB.prepare("DELETE FROM triggers WHERE chat_id = ?").bind(chatId).run();
  }
  bot._triggersCache.set(chatId, []);
  return words.length;
}

// FIX: match on word boundaries with Unicode-aware classes (works for Cyrillic)
async function findTriggers(bot, chatId, text) {
  const words = await getTriggerWords(bot, chatId);
  if (!words.length || !text) return [];
  let entry = bot._regexCache.get(chatId);
  if (!entry || entry.src !== words) {
    entry = {
      src: words,
      regexes: words.map((w) => [w, new RegExp("(?<![\\p{L}\\p{N}_])" + escapeRegExp(w) + "(?![\\p{L}\\p{N}_])", "iu")]),
    };
    bot._regexCache.set(chatId, entry);
  }
  const lower = text.toLowerCase();
  return entry.regexes.filter(([, re]) => re.test(lower)).map(([w]) => w);
}

// ================================
// Warnings (with expiry)
// ================================
async function warnsCutoff(bot, chatId) {
  const days = (await getSettings(bot, chatId)).warn_expire_days || 0;
  return days > 0 ? new Date(Date.now() - days * 86400000).toISOString() : null;
}

async function warnsCount(bot, chatId, userId) {
  const cutoff = await warnsCutoff(bot, chatId);
  const row = await bot.env.DB
    .prepare("SELECT COUNT(*) AS c FROM warns WHERE chat_id = ? AND user_id = ?" + (cutoff ? " AND date >= ?" : ""))
    .bind(...(cutoff ? [chatId, userId, cutoff] : [chatId, userId]))
    .first();
  return row ? row.c : 0;
}

async function warnsList(bot, chatId, userId) {
  const cutoff = await warnsCutoff(bot, chatId);
  const res = await bot.env.DB
    .prepare("SELECT reason, date FROM warns WHERE chat_id = ? AND user_id = ?" + (cutoff ? " AND date >= ?" : "") + " ORDER BY date, id")
    .bind(...(cutoff ? [chatId, userId, cutoff] : [chatId, userId]))
    .all();
  return res.results || [];
}

async function warnsAdd(bot, chatId, userId, reason, byUserId) {
  await bot.env.DB
    .prepare("INSERT INTO warns (chat_id, user_id, reason, by_user, date) VALUES (?, ?, ?, ?, ?)")
    .bind(chatId, userId, reason, byUserId, new Date().toISOString())
    .run();
  return warnsCount(bot, chatId, userId);
}

async function warnsRemoveLast(bot, chatId, userId) {
  const cutoff = await warnsCutoff(bot, chatId);
  const row = await bot.env.DB
    .prepare("SELECT id FROM warns WHERE chat_id = ? AND user_id = ?" + (cutoff ? " AND date >= ?" : "") + " ORDER BY date DESC, id DESC LIMIT 1")
    .bind(...(cutoff ? [chatId, userId, cutoff] : [chatId, userId]))
    .first();
  if (!row) return false;
  await bot.env.DB.prepare("DELETE FROM warns WHERE id = ?").bind(row.id).run();
  return true;
}

async function warnsClear(bot, chatId, userId) {
  const count = await warnsCount(bot, chatId, userId);
  if (count) {
    await bot.env.DB.prepare("DELETE FROM warns WHERE chat_id = ? AND user_id = ?").bind(chatId, userId).run();
  }
  return count;
}

// ================================
// Statistics
// ================================
async function statsIncrement(bot, chatId, statType, n) {
  await bot.env.DB
    .prepare("INSERT INTO stats (chat_id, stat_type, count) VALUES (?, ?, ?) ON CONFLICT(chat_id, stat_type) DO UPDATE SET count = count + excluded.count")
    .bind(chatId, statType, n || 1)
    .run();
}

async function statsGet(bot, chatId) {
  const res = await bot.env.DB.prepare("SELECT stat_type, count FROM stats WHERE chat_id = ?").bind(chatId).all();
  const out = {
    deleted_messages: 0,
    warns_given: 0,
    mutes: 0,
    bans: 0,
    kicks: 0,
    spam_blocked: 0,
    links_blocked: 0,
  };
  for (const row of res.results || []) out[row.stat_type] = row.count;
  return out;
}

// ================================
// Anti-spam (D1-backed, correct across isolates)
// ================================
async function antispamCheck(bot, chatId, userId, maxMessages, seconds) {
  const now = Date.now();
  const windowMs = (seconds || 10) * 1000;
  const res = await bot.env.DB.batch([
    bot.env.DB.prepare("DELETE FROM flood WHERE chat_id = ? AND user_id = ? AND ts < ?").bind(chatId, userId, now - windowMs),
    bot.env.DB.prepare("INSERT INTO flood (chat_id, user_id, ts) VALUES (?, ?, ?)").bind(chatId, userId, now),
    bot.env.DB.prepare("SELECT COUNT(*) AS c FROM flood WHERE chat_id = ? AND user_id = ?").bind(chatId, userId),
  ]);
  const rows = (res && res[2] && res[2].results) || [];
  return (rows[0] ? rows[0].c : 0) > maxMessages;
}

async function antispamReset(bot, chatId, userId) {
  await bot.env.DB.prepare("DELETE FROM flood WHERE chat_id = ? AND user_id = ?").bind(chatId, userId).run();
}

// ================================
// /confirm flow (D1-backed)
// ================================
async function confirmStart(bot, chatId, userId) {
  await bot.env.DB
    .prepare("INSERT INTO confirmations (key, count) VALUES (?, 0) ON CONFLICT(key) DO UPDATE SET count = 0")
    .bind(chatId + ":" + userId)
    .run();
}

async function confirmStep(bot, chatId, userId) {
  const key = chatId + ":" + userId;
  const row = await bot.env.DB.prepare("SELECT count FROM confirmations WHERE key = ?").bind(key).first();
  if (!row) return null;
  await bot.env.DB.prepare("UPDATE confirmations SET count = count + 1 WHERE key = ?").bind(key).run();
  return row.count + 1;
}

async function confirmClear(bot, chatId, userId) {
  await bot.env.DB.prepare("DELETE FROM confirmations WHERE key = ?").bind(chatId + ":" + userId).run();
}

// ================================
// Access-control guards
// ================================
async function guardGroup(bot, m) {
  const lang = await getLang(bot, m.chat.id);
  if (isGroup(m)) return true;
  await bot.replyTo(m, tr(lang, "groups_only"));
  return false;
}

async function guardAdmin(bot, m) {
  const lang = await getLang(bot, m.chat.id);
  // Anonymous group admin — definitely a chat admin
  if (m.from.id === ANONYMOUS_ADMIN_ID) return true;
  // Moderation commands are unavailable in private chats
  if (isPrivate(m)) {
    await bot.replyTo(m, tr(lang, "no_access"));
    return false;
  }
  if (await isChatAdmin(bot, m.chat.id, m.from.id)) return true;
  await bot.replyTo(m, tr(lang, "admins_only"));
  return false;
}

async function guardCreator(bot, m) {
  const lang = await getLang(bot, m.chat.id);
  // Anonymous — cannot verify creator status
  if (m.from.id === ANONYMOUS_ADMIN_ID) {
    await bot.replyTo(m, tr(lang, "disable_anonymity"));
    return false;
  }
  if (isPrivate(m)) {
    await bot.replyTo(m, tr(lang, "groups_only_short"));
    return false;
  }
  if (await isCreator(bot, m.chat.id, m.from.id)) return true;
  await bot.replyTo(m, tr(lang, "creator_only"));
  return false;
}

// ================================
// Keyboards
// ================================
function mainKeyboard(lang) {
  const ru = lang !== "en";
  const b = (text, data) => ({ text: text, callback_data: data });
  return {
    inline_keyboard: [
      [b(ru ? "➕ Добавить слово" : "➕ Add word", "help_add"), b(ru ? "➖ Удалить слово" : "➖ Remove word", "help_del")],
      [b(ru ? "📄 Список слов" : "📄 Word list", "list_words"), b(ru ? "📊 Статистика" : "📊 Statistics", "show_stats")],
      [b(ru ? "⚙️ Настройки" : "⚙️ Settings", "show_settings"), b(ru ? "❓ Все команды" : "❓ All commands", "all_commands")],
    ],
  };
}

function langKeyboard() {
  return {
    inline_keyboard: [[{ text: "🇷🇺 Русский", callback_data: "set_lang:ru" }, { text: "🇬🇧 English", callback_data: "set_lang:en" }]],
  };
}

async function settingsKeyboard(bot, chatId) {
  const lang = await getLang(bot, chatId);
  const s = await getSettings(bot, chatId);
  const b = (text, data) => ({ text: text, callback_data: data });
  return {
    inline_keyboard: [
      [b("🔄 " + tr(lang, "antispam_name") + ": " + (s.antispam_enabled ? "✅" : "❌"), "toggle_antispam")],
      [b("🔗 " + tr(lang, "antilink_name") + ": " + (s.antilink_enabled ? "✅" : "❌"), "toggle_antilink")],
      [b("👋 " + tr(lang, "welcome_name") + ": " + (s.welcome_enabled ? "✅" : "❌"), "toggle_welcome")],
      [b("🚪 " + tr(lang, "goodbye_name") + ": " + (s.goodbye_enabled ? "✅" : "❌"), "toggle_goodbye")],
      [b(tr(lang, "kb_lang", { value: langName(lang) }), "cycle_lang")],
      [b("🔙 " + (lang === "en" ? "Back" : "Назад"), "back_main")],
    ],
  };
}

// ================================
// User extraction from a command
// ================================
async function extractUserFromMessage(bot, m) {
  const parts = m.text ? m.text.trim().split(/\s+/) : [];
  // From a reply
  if (m.reply_to_message && m.reply_to_message.from) {
    return { user: m.reply_to_message.from, reason: parts.length > 1 ? parts.slice(1).join(" ") : null };
  }
  if (parts.length < 2) return { user: null, reason: null };
  const userArg = parts[1];
  const reason = parts.length > 2 ? parts.slice(2).join(" ") : null;
  // By numeric ID
  if (/^\d+$/.test(userArg)) {
    try {
      const member = await bot.getChatMember(m.chat.id, parseInt(userArg, 10));
      if (member && member.user) return { user: member.user, reason: reason };
    } catch (e) {
      /* fall through */
    }
  }
  // Try text_mention entities (a mention of a user without @username).
  // A plain @username cannot be resolved: the Bot API has no lookup by username.
  if (Array.isArray(m.entities)) {
    for (const entity of m.entities) {
      if (entity.type === "text_mention" && entity.user) return { user: entity.user, reason: reason };
    }
  }
  return { user: null, reason: reason };
}

// ================================
// Commands
// ================================
async function cmdMyId(bot, m) {
  const lang = await getLang(bot, m.chat.id);
  await bot.replyTo(m, tr(lang, "myid", { id: m.from.id, chat: m.chat.id }), { parse_mode: "Markdown" });
}

async function cmdHelp(bot, m) {
  const lang = await getLang(bot, m.chat.id);
  await bot.sendMessage(m.chat.id, tr(lang, "help_text"), {
    parse_mode: "Markdown",
    // the keyboard only makes sense in groups
    reply_markup: isGroup(m) ? mainKeyboard(lang) : undefined,
  });
}

async function cmdAllCommands(bot, m) {
  const lang = await getLang(bot, m.chat.id);
  await bot.sendMessage(m.chat.id, tr(lang, "commands_text") + tr(lang, "commands_footer"), { parse_mode: "Markdown" });
}

async function cmdLang(bot, m) {
  if (!(await guardGroup(bot, m))) return;
  if (!(await guardAdmin(bot, m))) return;
  const lang = await getLang(bot, m.chat.id);
  await bot.sendMessage(m.chat.id, tr(lang, "lang_text", { current: langName(lang) }), { reply_markup: langKeyboard() });
}

async function cmdConfirm(bot, m) {
  const chatId = m.chat.id;
  const userId = m.from.id;
  const lang = await getLang(bot, chatId);
  const count = await confirmStep(bot, chatId, userId);
  if (count === null) {
    await bot.replyTo(m, tr(lang, "confirm_not_started"));
    return;
  }
  if (count < 3) {
    await bot.replyTo(m, tr(lang, "confirm_progress", { count: count }));
    return;
  }
  const words = await getTriggerWords(bot, chatId);
  if (!words.length) {
    await bot.sendMessage(chatId, tr(lang, "triggers_empty"));
    await confirmClear(bot, chatId, userId);
    return;
  }
  try {
    await bot.sendDocument(chatId, "triggers_" + userId + ".txt", words.join("\n"), tr(lang, "triggers_file_caption", { count: words.length }));
  } finally {
    await confirmClear(bot, chatId, userId);
  }
}

async function cmdAddword(bot, m) {
  if (!(await guardAdmin(bot, m))) return;
  const lang = await getLang(bot, m.chat.id);
  const parts = m.text ? m.text.trim().split(/\s+/) : [];
  if (parts.length < 2) {
    await bot.replyTo(m, tr(lang, "addword_usage"), { parse_mode: "Markdown" });
    return;
  }
  const word = parts.slice(1).join(" ").trim();
  if (word.length > 100) {
    await bot.replyTo(m, tr(lang, "word_too_long"));
    return;
  }
  if (await triggersAdd(bot, m.chat.id, word)) {
    await bot.replyTo(m, tr(lang, "word_added", { word: mdEscape(word.toLowerCase()) }), { parse_mode: "Markdown" });
  } else {
    await bot.replyTo(m, tr(lang, "word_exists"));
  }
}

async function cmdAddwords(bot, m) {
  if (!(await guardAdmin(bot, m))) return;
  const lang = await getLang(bot, m.chat.id);
  const parts = m.text ? m.text.trim().split(/\s+/).slice(1) : [];
  if (!parts.length) {
    await bot.replyTo(m, tr(lang, "addwords_usage"), { parse_mode: "Markdown" });
    return;
  }
  const added = await triggersAddMany(bot, m.chat.id, parts);
  await bot.replyTo(m, tr(lang, "addwords_done", { count: added }));
}

async function cmdDelword(bot, m) {
  if (!(await guardAdmin(bot, m))) return;
  const lang = await getLang(bot, m.chat.id);
  const parts = m.text ? m.text.trim().split(/\s+/) : [];
  if (parts.length < 2) {
    await bot.replyTo(m, tr(lang, "delword_usage"), { parse_mode: "Markdown" });
    return;
  }
  const word = parts.slice(1).join(" ").trim();
  if (await triggersRemove(bot, m.chat.id, word)) {
    await bot.replyTo(m, tr(lang, "word_deleted", { word: mdEscape(word.toLowerCase()) }), { parse_mode: "Markdown" });
  } else {
    await bot.replyTo(m, tr(lang, "word_not_found"));
  }
}

async function cmdClearwords(bot, m) {
  if (!(await guardCreator(bot, m))) return;
  const lang = await getLang(bot, m.chat.id);
  const count = await triggersClear(bot, m.chat.id);
  await bot.replyTo(m, tr(lang, "clearwords_done", { count: count }));
}

async function cmdListwords(bot, m) {
  if (!(await guardAdmin(bot, m))) return;
  const lang = await getLang(bot, m.chat.id);
  await confirmStart(bot, m.chat.id, m.from.id);
  await bot.sendMessage(m.chat.id, tr(lang, "listwords_confirm", { count: (await getTriggerWords(bot, m.chat.id)).length }));
}

// ---- Moderation: warnings ----
async function cmdWarn(bot, m) {
  if (!(await guardGroup(bot, m))) return;
  if (!(await guardAdmin(bot, m))) return;
  const lang = await getLang(bot, m.chat.id);
  const { user, reason } = await extractUserFromMessage(bot, m);
  if (!user) {
    await bot.replyTo(m, tr(lang, "warn_usage"), { parse_mode: "Markdown" });
    return;
  }
  if (user.id === ANONYMOUS_ADMIN_ID || (await isChatAdmin(bot, m.chat.id, user.id))) {
    await bot.replyTo(m, tr(lang, "target_admin_warn"));
    return;
  }
  const finalReason = reason || tr(lang, "reason_not_set");
  const count = await warnsAdd(bot, m.chat.id, user.id, finalReason, m.from.id);
  const s = await getSettings(bot, m.chat.id);
  await statsIncrement(bot, m.chat.id, "warns_given");
  const text = tr(lang, "warn_header", {
    user: mdEscape(userDisplay(user)),
    reason: mdEscape(finalReason),
    count: count,
    max: s.max_warns,
  });
  await bot.sendMessage(m.chat.id, text, { parse_mode: "Markdown" });
  if (count >= s.max_warns) {
    try {
      await bot.banChatMember(m.chat.id, user.id);
      await bot.sendMessage(m.chat.id, tr(lang, "warn_limit_ban", { user: userDisplay(user) }));
      await statsIncrement(bot, m.chat.id, "bans");
    } catch (e) {
      await bot.sendMessage(m.chat.id, tr(lang, "ban_error", { error: e.message || String(e) }));
    }
  }
}

async function cmdUnwarn(bot, m) {
  if (!(await guardGroup(bot, m))) return;
  if (!(await guardAdmin(bot, m))) return;
  const lang = await getLang(bot, m.chat.id);
  const { user } = await extractUserFromMessage(bot, m);
  if (!user) {
    await bot.replyTo(m, tr(lang, "unwarn_usage"), { parse_mode: "Markdown" });
    return;
  }
  if (await warnsRemoveLast(bot, m.chat.id, user.id)) {
    const count = await warnsCount(bot, m.chat.id, user.id);
    await bot.replyTo(m, tr(lang, "unwarn_done", { count: count }));
  } else {
    await bot.replyTo(m, tr(lang, "no_warns_user"));
  }
}

async function cmdWarns(bot, m) {
  if (!(await guardGroup(bot, m))) return;
  if (!(await guardAdmin(bot, m))) return;
  const lang = await getLang(bot, m.chat.id);
  const { user } = await extractUserFromMessage(bot, m);
  if (!user) {
    await bot.replyTo(m, tr(lang, "warns_usage"), { parse_mode: "Markdown" });
    return;
  }
  const list = await warnsList(bot, m.chat.id, user.id);
  if (!list.length) {
    await bot.replyTo(m, tr(lang, "user_no_warns", { user: userDisplay(user) }));
    return;
  }
  let text = tr(lang, "warns_list_header", { user: mdEscape(userDisplay(user)) });
  list.forEach((w, i) => {
    const date = String(w.date || "").slice(0, 10).split("-").reverse().join(".");
    text += i + 1 + ". " + mdEscape(w.reason || "") + " (" + date + ")\n";
  });
  await bot.sendMessage(m.chat.id, text, { parse_mode: "Markdown" });
}

async function cmdClearwarns(bot, m) {
  if (!(await guardGroup(bot, m))) return;
  if (!(await guardAdmin(bot, m))) return;
  const lang = await getLang(bot, m.chat.id);
  const { user } = await extractUserFromMessage(bot, m);
  if (!user) {
    await bot.replyTo(m, tr(lang, "clearwarns_usage"), { parse_mode: "Markdown" });
    return;
  }
  const count = await warnsClear(bot, m.chat.id, user.id);
  await bot.replyTo(m, tr(lang, "clearwarns_done", { count: count }));
}

// ---- Moderation: mute ----
async function cmdMute(bot, m) {
  if (!(await guardGroup(bot, m))) return;
  if (!(await guardAdmin(bot, m))) return;
  const lang = await getLang(bot, m.chat.id);
  const parts = m.text ? m.text.trim().split(/\s+/) : [];
  let user = null;
  let rest = [];

  if (m.reply_to_message && m.reply_to_message.from) {
    user = m.reply_to_message.from;
    rest = parts.slice(1);
  } else {
    if (parts.length < 2) {
      await bot.replyTo(m, tr(lang, "mute_usage"), { parse_mode: "Markdown" });
      return;
    }
    const extracted = await extractUserFromMessage(bot, m);
    user = extracted.user;
    rest = parts.slice(2);
  }

  if (!user) {
    await bot.replyTo(m, tr(lang, "user_not_found"));
    return;
  }
  if (user.id === ANONYMOUS_ADMIN_ID || (await isChatAdmin(bot, m.chat.id, user.id))) {
    await bot.replyTo(m, tr(lang, "target_admin_mute"));
    return;
  }

  // FIX: the first argument is a duration only when it looks like one
  // (\d+[mhdw]); with or without a duration the remaining text is the reason
  let duration = null;
  let reason = null;
  if (rest.length && looksLikeDuration(rest[0])) {
    duration = parseDuration(rest[0]);
    if (!duration) {
      await bot.replyTo(m, tr(lang, "bad_duration"));
      return;
    }
    reason = rest.slice(1).join(" ") || null;
  } else if (rest.length) {
    reason = rest.join(" ") || null;
  }

  let untilDate = null;
  let durationText = tr(lang, "muted_forever");
  if (duration) {
    untilDate = Math.floor(Date.now() / 1000) + duration;
    durationText = formatDuration(duration, lang);
  }

  try {
    await bot.restrictChatMember(m.chat.id, user.id, untilDate, mutePermissions());
    let text = tr(lang, "muted", { user: userDisplay(user), duration: durationText });
    if (reason) text += tr(lang, "ban_reason_line", { reason: reason });
    await bot.sendMessage(m.chat.id, text);
    await statsIncrement(bot, m.chat.id, "mutes");
  } catch (e) {
    await bot.replyTo(m, tr(lang, "action_error", { error: e.message || String(e) }));
  }
}

async function cmdUnmute(bot, m) {
  if (!(await guardGroup(bot, m))) return;
  if (!(await guardAdmin(bot, m))) return;
  const lang = await getLang(bot, m.chat.id);
  const { user } = await extractUserFromMessage(bot, m);
  if (!user) {
    await bot.replyTo(m, tr(lang, "unmute_usage"), { parse_mode: "Markdown" });
    return;
  }
  try {
    await bot.restrictChatMember(m.chat.id, user.id, null, unmutePermissions());
    await bot.replyTo(m, tr(lang, "unmuted", { user: userDisplay(user) }));
  } catch (e) {
    await bot.replyTo(m, tr(lang, "action_error", { error: e.message || String(e) }));
  }
}

// ---- Moderation: ban / unban / kick ----
async function cmdBan(bot, m) {
  if (!(await guardGroup(bot, m))) return;
  if (!(await guardAdmin(bot, m))) return;
  const lang = await getLang(bot, m.chat.id);
  const { user, reason } = await extractUserFromMessage(bot, m);
  if (!user) {
    await bot.replyTo(m, tr(lang, "ban_usage"), { parse_mode: "Markdown" });
    return;
  }
  if (user.id === ANONYMOUS_ADMIN_ID || (await isChatAdmin(bot, m.chat.id, user.id))) {
    await bot.replyTo(m, tr(lang, "target_admin_ban"));
    return;
  }
  try {
    await bot.banChatMember(m.chat.id, user.id);
    let text = tr(lang, "banned", { user: userDisplay(user) });
    if (reason) text += tr(lang, "ban_reason_line", { reason: reason });
    await bot.sendMessage(m.chat.id, text);
    await statsIncrement(bot, m.chat.id, "bans");
  } catch (e) {
    await bot.replyTo(m, tr(lang, "action_error", { error: e.message || String(e) }));
  }
}

async function cmdUnban(bot, m) {
  if (!(await guardGroup(bot, m))) return;
  if (!(await guardAdmin(bot, m))) return;
  const lang = await getLang(bot, m.chat.id);
  const { user } = await extractUserFromMessage(bot, m);
  if (!user) {
    await bot.replyTo(m, tr(lang, "unban_usage"), { parse_mode: "Markdown" });
    return;
  }
  try {
    await bot.unbanChatMember(m.chat.id, user.id, true);
    await bot.replyTo(m, tr(lang, "unbanned", { id: user.id }), { parse_mode: "Markdown" });
  } catch (e) {
    await bot.replyTo(m, tr(lang, "action_error", { error: e.message || String(e) }));
  }
}

async function cmdKick(bot, m) {
  if (!(await guardGroup(bot, m))) return;
  if (!(await guardAdmin(bot, m))) return;
  const lang = await getLang(bot, m.chat.id);
  const { user } = await extractUserFromMessage(bot, m);
  if (!user) {
    await bot.replyTo(m, tr(lang, "kick_usage"), { parse_mode: "Markdown" });
    return;
  }
  if (user.id === ANONYMOUS_ADMIN_ID || (await isChatAdmin(bot, m.chat.id, user.id))) {
    await bot.replyTo(m, tr(lang, "target_admin_kick"));
    return;
  }
  try {
    await bot.banChatMember(m.chat.id, user.id);
    await bot.unbanChatMember(m.chat.id, user.id, true);
    await bot.sendMessage(m.chat.id, tr(lang, "kicked", { user: userDisplay(user) }));
    await statsIncrement(bot, m.chat.id, "kicks");
  } catch (e) {
    await bot.replyTo(m, tr(lang, "action_error", { error: e.message || String(e) }));
  }
}

// ---- Information ----
async function cmdUserinfo(bot, m) {
  if (!(await guardGroup(bot, m))) return;
  if (!(await guardAdmin(bot, m))) return;
  const lang = await getLang(bot, m.chat.id);
  const { user: extracted } = await extractUserFromMessage(bot, m);
  const user = extracted || m.from;
  try {
    const member = await bot.getChatMember(m.chat.id, user.id);
    const statusMap = {
      creator: tr(lang, "status_creator"),
      administrator: tr(lang, "status_admin"),
      member: tr(lang, "status_member"),
      restricted: tr(lang, "status_restricted"),
      left: tr(lang, "status_left"),
      kicked: tr(lang, "status_kicked"),
    };
    const warnsCountVal = await warnsCount(bot, m.chat.id, user.id);
    const text =
      tr(lang, "userinfo_title") +
      "├ ID: `" + user.id + "`\n" +
      tr(lang, "ui_name", { value: mdEscape(user.first_name || "N/A") }) + "\n" +
      tr(lang, "ui_surname", { value: mdEscape(user.last_name || "N/A") }) + "\n" +
      "├ Username: @" + mdEscape(user.username || "N/A") + "\n" +
      tr(lang, "ui_status", { value: statusMap[member.status] || member.status }) + "\n" +
      tr(lang, "ui_bot", { value: user.is_bot ? tr(lang, "yes") : tr(lang, "no") }) + "\n" +
      tr(lang, "ui_warns", { count: warnsCountVal });
    await bot.sendMessage(m.chat.id, text, { parse_mode: "Markdown" });
  } catch (e) {
    await bot.replyTo(m, tr(lang, "action_error", { error: e.message || String(e) }));
  }
}

async function cmdChatinfo(bot, m) {
  if (!(await guardGroup(bot, m))) return;
  const lang = await getLang(bot, m.chat.id);
  const chat = m.chat;
  try {
    const memberCount = await bot.tg("getChatMemberCount", { chat_id: chat.id });
    const text =
      tr(lang, "chatinfo_title") +
      "├ ID: `" + chat.id + "`\n" +
      tr(lang, "ci_title", { value: chat.title || "N/A" }) + "\n" +
      tr(lang, "ci_type", { value: chat.type }) + "\n" +
      "├ Username: @" + (chat.username || "N/A") + "\n" +
      tr(lang, "ci_members", { count: memberCount });
    await bot.sendMessage(chat.id, text, { parse_mode: "Markdown" });
  } catch (e) {
    await bot.replyTo(m, tr(lang, "action_error", { error: e.message || String(e) }));
  }
}

async function sendStats(bot, chatId) {
  const lang = await getLang(bot, chatId);
  const st = await statsGet(bot, chatId);
  const text =
    tr(lang, "stats_title") +
    tr(lang, "st_deleted", { count: st.deleted_messages }) + "\n" +
    tr(lang, "st_warns", { count: st.warns_given }) + "\n" +
    tr(lang, "st_mutes", { count: st.mutes }) + "\n" +
    tr(lang, "st_bans", { count: st.bans }) + "\n" +
    tr(lang, "st_kicks", { count: st.kicks }) + "\n" +
    tr(lang, "st_spam", { count: st.spam_blocked }) + "\n" +
    tr(lang, "st_links", { count: st.links_blocked });
  await bot.sendMessage(chatId, text, { parse_mode: "Markdown" });
}

async function cmdStats(bot, m) {
  if (!(await guardAdmin(bot, m))) return;
  const lang = await getLang(bot, m.chat.id);
  if (isPrivate(m)) {
    await bot.replyTo(m, tr(lang, "stats_groups_only"));
    return;
  }
  await sendStats(bot, m.chat.id);
}

// ---- Utilities ----
async function cmdClear(bot, m, ctx) {
  if (!(await guardGroup(bot, m))) return;
  if (!(await guardAdmin(bot, m))) return;
  const lang = await getLang(bot, m.chat.id);
  const parts = m.text ? m.text.trim().split(/\s+/) : [];
  if (parts.length < 2 || !parts[1]) {
    await bot.replyTo(m, tr(lang, "clear_usage"), { parse_mode: "Markdown" });
    return;
  }
  if (!/^\d+$/.test(parts[1])) {
    await bot.replyTo(m, tr(lang, "not_a_number"));
    return;
  }
  const count = parseInt(parts[1], 10);
  if (count < 1 || count > 100) {
    await bot.replyTo(m, tr(lang, "clear_range"));
    return;
  }
  let deleted = 0;
  let attempts = 0;
  let consecutiveMisses = 0;
  // FIX: message IDs in supergroups are not contiguous — keep walking back
  // until enough messages are deleted or a long gap is reached
  while (deleted < count + 1 && attempts < count + 100 && consecutiveMisses < 10) {
    const targetId = m.message_id - attempts;
    attempts++;
    if (targetId < 1) break;
    try {
      await bot.deleteMessage(m.chat.id, targetId);
      deleted++;
      consecutiveMisses = 0;
    } catch (e) {
      consecutiveMisses++;
    }
  }
  await statsIncrement(bot, m.chat.id, "deleted_messages", deleted);
  const msg = await bot.sendMessage(m.chat.id, tr(lang, "clear_done", { count: deleted }));
  // remove the service message after a delay (waitUntil, non-blocking)
  if (ctx) {
    ctx.waitUntil(
      new Promise((resolve) => setTimeout(resolve, 3000))
        .then(() => bot.deleteMessage(m.chat.id, msg.message_id))
        .catch(() => {})
    );
  }
}

async function cmdPin(bot, m) {
  if (!(await guardGroup(bot, m))) return;
  if (!(await guardAdmin(bot, m))) return;
  const lang = await getLang(bot, m.chat.id);
  if (!m.reply_to_message) {
    await bot.replyTo(m, tr(lang, "pin_usage"));
    return;
  }
  try {
    await bot.tg("pinChatMessage", { chat_id: m.chat.id, message_id: m.reply_to_message.message_id });
    await bot.replyTo(m, tr(lang, "pinned"));
  } catch (e) {
    await bot.replyTo(m, tr(lang, "action_error", { error: e.message || String(e) }));
  }
}

async function cmdUnpin(bot, m) {
  if (!(await guardGroup(bot, m))) return;
  if (!(await guardAdmin(bot, m))) return;
  const lang = await getLang(bot, m.chat.id);
  try {
    await bot.tg("unpinChatMessage", { chat_id: m.chat.id });
    await bot.replyTo(m, tr(lang, "unpinned"));
  } catch (e) {
    await bot.replyTo(m, tr(lang, "action_error", { error: e.message || String(e) }));
  }
}

// ---- Settings ----
async function cmdSettings(bot, m) {
  if (!(await guardGroup(bot, m))) return;
  if (!(await guardAdmin(bot, m))) return;
  const lang = await getLang(bot, m.chat.id);
  const s = await getSettings(bot, m.chat.id);
  const text =
    tr(lang, "settings_title") +
    tr(lang, "set_max_warns", { value: s.max_warns }) + "\n" +
    tr(lang, "set_antispam", { value: s.antispam_enabled ? "✅" : "❌" }) + "\n" +
    tr(lang, "set_antilink", { value: s.antilink_enabled ? "✅" : "❌" }) + "\n" +
    tr(lang, "set_welcome", { value: s.welcome_enabled ? "✅" : "❌" }) + "\n" +
    tr(lang, "set_goodbye", { value: s.goodbye_enabled ? "✅" : "❌" }) + "\n" +
    tr(lang, "set_language", { value: langName(lang) });
  await bot.sendMessage(m.chat.id, text, { parse_mode: "Markdown", reply_markup: await settingsKeyboard(bot, m.chat.id) });
}

async function cmdSetmaxwarns(bot, m) {
  if (!(await guardGroup(bot, m))) return;
  if (!(await guardAdmin(bot, m))) return;
  const lang = await getLang(bot, m.chat.id);
  const parts = m.text ? m.text.trim().split(/\s+/) : [];
  if (parts.length < 2) {
    await bot.replyTo(m, tr(lang, "setmaxwarns_usage"), { parse_mode: "Markdown" });
    return;
  }
  if (!/^\d+$/.test(parts[1])) {
    await bot.replyTo(m, tr(lang, "not_a_number"));
    return;
  }
  const value = parseInt(parts[1], 10);
  if (value < 1 || value > 10) {
    await bot.replyTo(m, tr(lang, "setmaxwarns_range"));
    return;
  }
  await setSetting(bot, m.chat.id, "max_warns", value);
  await bot.replyTo(m, tr(lang, "setmaxwarns_done", { value: value }));
}

async function cmdSetwelcome(bot, m) {
  if (!(await guardGroup(bot, m))) return;
  if (!(await guardAdmin(bot, m))) return;
  const lang = await getLang(bot, m.chat.id);
  const parts = m.text ? m.text.trim().split(/\s+/) : [];
  if (parts.length < 2) {
    await bot.replyTo(m, tr(lang, "setwelcome_usage"), { parse_mode: "Markdown" });
    return;
  }
  const text = parts.slice(1).join(" ");
  await setSetting(bot, m.chat.id, "welcome_message", text);
  await setSetting(bot, m.chat.id, "welcome_enabled", true);
  await bot.replyTo(m, tr(lang, "setwelcome_done"));
}

async function cmdSetgoodbye(bot, m) {
  if (!(await guardGroup(bot, m))) return;
  if (!(await guardAdmin(bot, m))) return;
  const lang = await getLang(bot, m.chat.id);
  const parts = m.text ? m.text.trim().split(/\s+/) : [];
  if (parts.length < 2) {
    await bot.replyTo(m, tr(lang, "setgoodbye_usage"), { parse_mode: "Markdown" });
    return;
  }
  const text = parts.slice(1).join(" ");
  await setSetting(bot, m.chat.id, "goodbye_message", text);
  await setSetting(bot, m.chat.id, "goodbye_enabled", true);
  await bot.replyTo(m, tr(lang, "setgoodbye_done"));
}

// ================================
// New/left chat members
// ================================
async function onNewChatMembers(bot, m) {
  const chatId = m.chat.id;
  // FIX: warn when the bot itself is added without admin rights
  try {
    const me = await getMe(bot);
    if ((m.new_chat_members || []).some((u) => u.is_bot && u.id === me.id)) {
      const member = await bot.getChatMember(chatId, me.id);
      if (member.status !== "administrator") {
        await bot.sendMessage(chatId, tr(await getLang(bot, chatId), "need_admin_rights"));
      }
    }
  } catch (e) {
    console.error("Bot self-check error:", e);
  }

  const s = await getSettings(bot, chatId);
  if (!s.welcome_enabled) return;
  const lang = await getLang(bot, chatId);
  const template = s.welcome_message || tr(lang, "default_welcome");
  for (const user of m.new_chat_members || []) {
    if (user.is_bot) continue;
    let text = template.split("{user}").join(userDisplay(user));
    text = text.split("{chat}").join(m.chat.title || tr(lang, "chat_word"));
    await bot.sendMessage(chatId, text);
  }
}

async function onLeftChatMember(bot, m) {
  const user = m.left_chat_member;
  if (!user || user.is_bot) return;
  const chatId = m.chat.id;
  const s = await getSettings(bot, chatId);
  if (!s.goodbye_enabled) return;
  const lang = await getLang(bot, chatId);
  const template = s.goodbye_message || tr(lang, "default_goodbye");
  let text = template.split("{user}").join(userDisplay(user));
  text = text.split("{chat}").join(m.chat.title || tr(lang, "chat_word"));
  await bot.sendMessage(chatId, text);
}

// ================================
// Catch-all message handler
// ================================
async function onMessage(bot, m) {
  // Private messages
  if (isPrivate(m)) {
    await bot.sendMessage(m.chat.id, tr(await getLang(bot, m.chat.id), "private_hello"));
    return;
  }
  if (!isGroup(m)) return;

  const chatId = m.chat.id;
  const userId = m.from ? m.from.id : null;
  if (!userId) return;
  const lang = await getLang(bot, chatId);
  // FIX: captions are checked too, not only plain text
  const text = (m.text || m.caption || "").trim();

  // Liveness check
  if (m.text && (text.toLowerCase() === "бот" || text.toLowerCase() === "bot")) {
    await bot.sendMessage(chatId, tr(lang, "im_working"));
    return;
  }

  // Skip chat admins (including anonymous ones)
  if (await canModerate(bot, chatId, userId)) return;

  const s = await getSettings(bot, chatId);

  // Anti-spam (any message type counts towards the flood limit)
  if (s.antispam_enabled) {
    const isSpam = await antispamCheck(bot, chatId, userId, s.antispam_messages, s.antispam_seconds);
    if (isSpam) {
      try {
        await bot.deleteMessage(chatId, m.message_id);
        await bot.restrictChatMember(chatId, userId, Math.floor(Date.now() / 1000) + 300, mutePermissions());
        await bot.sendMessage(chatId, tr(lang, "spam_muted", { user: userDisplay(m.from) }));
        await antispamReset(bot, chatId, userId);
        await statsIncrement(bot, chatId, "spam_blocked");
        await statsIncrement(bot, chatId, "mutes");
      } catch (e) {
        console.error("Anti-spam error:", e);
      }
      return;
    }
  }

  // Anti-links (regex on the text/caption + Telegram link entities)
  if (s.antilink_enabled && (hasLinks(text) || messageHasLinkEntities(m))) {
    try {
      await bot.deleteMessage(chatId, m.message_id);
      await bot.sendMessage(chatId, tr(lang, "links_removed", { user: userDisplay(m.from) }));
      await statsIncrement(bot, chatId, "links_blocked");
      await statsIncrement(bot, chatId, "deleted_messages");
    } catch (e) {
      console.error("Anti-link error:", e);
    }
    return;
  }

  // Trigger words
  if (!text) return;
  const foundWords = await findTriggers(bot, chatId, text);
  if (!foundWords.length) return;

  try {
    await bot.deleteMessage(chatId, m.message_id);
    const censored = foundWords.map(censorWord).join(", ");
    const display = userDisplay(m.from);
    await bot.sendMessage(chatId, tr(lang, "msg_deleted", { user: display, censored: censored }));
    await statsIncrement(bot, chatId, "deleted_messages");
    console.log("[trigger] chat=" + chatId + " user=" + userId + " words=" + foundWords.join(","));
  } catch (e) {
    if (String(e.message || e).toLowerCase().includes("not enough rights")) {
      await bot.sendMessage(chatId, tr(lang, "no_delete_rights")).catch(() => {});
    } else {
      console.error("Error:", e);
    }
  }
}

// ================================
// Callback queries
// ================================
async function handleCallback(bot, call) {
  const chatId = call.message && call.message.chat ? call.message.chat.id : null;
  if (!chatId) return;
  const userId = call.from.id;
  const lang = await getLang(bot, chatId);

  const privateChat = call.message.chat.type === "private";
  const hasAccess = privateChat ? false : await canModerate(bot, chatId, userId);
  if (!hasAccess) {
    await bot.answerCallbackQuery(call.id, tr(lang, "no_access"), true);
    return;
  }

  try {
    const data = call.data;
    if (data === "help_add") {
      await bot.answerCallbackQuery(call.id);
      await bot.sendMessage(chatId, tr(lang, "addword_usage"), { parse_mode: "Markdown" });
    } else if (data === "help_del") {
      await bot.answerCallbackQuery(call.id);
      await bot.sendMessage(chatId, tr(lang, "delword_usage"), { parse_mode: "Markdown" });
    } else if (data === "list_words") {
      await bot.answerCallbackQuery(call.id);
      await confirmStart(bot, chatId, userId);
      await bot.sendMessage(chatId, tr(lang, "confirm_title", { count: (await getTriggerWords(bot, chatId)).length }), {
        parse_mode: "Markdown",
      });
    } else if (data === "show_stats") {
      await bot.answerCallbackQuery(call.id);
      if (call.message.chat.type === "group" || call.message.chat.type === "supergroup") {
        await sendStats(bot, chatId);
      } else {
        await bot.sendMessage(chatId, tr(lang, "stats_groups_only"));
      }
    } else if (data === "show_settings") {
      await bot.answerCallbackQuery(call.id);
      if (call.message.chat.type === "group" || call.message.chat.type === "supergroup") {
        await bot.sendMessage(chatId, tr(lang, "settings_title"), {
          parse_mode: "Markdown",
          reply_markup: await settingsKeyboard(bot, chatId),
        });
      } else {
        await bot.sendMessage(chatId, tr(lang, "settings_groups_only"));
      }
    } else if (data === "toggle_antispam" || data === "toggle_antilink" || data === "toggle_welcome" || data === "toggle_goodbye") {
      const map = {
        toggle_antispam: ["antispam_enabled", "antispam_name", "m"],
        toggle_antilink: ["antilink_enabled", "antilink_name", "m"],
        toggle_welcome: ["welcome_enabled", "welcome_name", "f"],
        toggle_goodbye: ["goodbye_enabled", "goodbye_name", "f"],
      };
      const [key, nameKey, gender] = map[data];
      const current = (await getSettings(bot, chatId))[key];
      await setSetting(bot, chatId, key, !current);
      const status = !current ? tr(lang, "toggle_on_" + gender) : tr(lang, "toggle_off_" + gender);
      await bot.answerCallbackQuery(call.id, tr(lang, nameKey) + " " + status);
      await bot.editMessageReplyMarkup(chatId, call.message.message_id, await settingsKeyboard(bot, chatId));
    } else if (data === "cycle_lang") {
      const newLang = lang === "ru" ? "en" : "ru";
      await setSetting(bot, chatId, "language", newLang);
      await bot.answerCallbackQuery(call.id, tr(newLang, "lang_set", { value: langName(newLang) }));
      await bot.editMessageReplyMarkup(chatId, call.message.message_id, await settingsKeyboard(bot, chatId));
    } else if (data === "set_lang:ru" || data === "set_lang:en") {
      const newLang = data.split(":")[1];
      await setSetting(bot, chatId, "language", newLang);
      await bot.answerCallbackQuery(call.id, tr(newLang, "lang_set", { value: langName(newLang) }));
      try {
        await bot.editMessageText(tr(newLang, "lang_text", { current: langName(newLang) }), chatId, call.message.message_id, {
          reply_markup: langKeyboard(),
        });
      } catch (e) {
        /* message too old or not modified */
      }
    } else if (data === "back_main") {
      await bot.answerCallbackQuery(call.id);
      await bot.editMessageText(tr(lang, "main_menu"), chatId, call.message.message_id, {
        reply_markup: mainKeyboard(lang),
      });
    } else if (data === "all_commands") {
      await bot.answerCallbackQuery(call.id);
      await cmdAllCommands(bot, call.message);
    }
  } catch (e) {
    console.error("Callback error:", e);
    await bot.answerCallbackQuery(call.id, tr(lang, "cb_error")).catch(() => {});
  }
}

// ================================
// Routing
// ================================
const COMMANDS = {
  myid: cmdMyId,
  start: cmdHelp,
  help: cmdHelp,
  commands: cmdAllCommands,
  lang: cmdLang,
  confirm: cmdConfirm,
  addword: cmdAddword,
  addwords: cmdAddwords,
  delword: cmdDelword,
  clearwords: cmdClearwords,
  listwords: cmdListwords,
  warn: cmdWarn,
  unwarn: cmdUnwarn,
  warns: cmdWarns,
  clearwarns: cmdClearwarns,
  mute: cmdMute,
  unmute: cmdUnmute,
  ban: cmdBan,
  unban: cmdUnban,
  kick: cmdKick,
  userinfo: cmdUserinfo,
  chatinfo: cmdChatinfo,
  stats: cmdStats,
  clear: cmdClear,
  pin: cmdPin,
  unpin: cmdUnpin,
  settings: cmdSettings,
  setmaxwarns: cmdSetmaxwarns,
  setwelcome: cmdSetwelcome,
  setgoodbye: cmdSetgoodbye,
};

async function routeMessage(bot, m, ctx) {
  if (m.new_chat_members) return onNewChatMembers(bot, m);
  if (m.left_chat_member) return onLeftChatMember(bot, m);
  if (m.text && m.text.startsWith("/")) {
    const match = /^\/([a-zA-Z_]+)(?:@\S+)?/.exec(m.text);
    if (match) {
      const handler = COMMANDS[match[1].toLowerCase()];
      if (handler) return handler(bot, m, ctx);
    }
    // unknown command — falls through to moderation, like the Python version
  }
  return onMessage(bot, m);
}

async function handleUpdate(update, env, ctx) {
  const bot = new Bot(env);
  if (update.callback_query) {
    return handleCallback(bot, update.callback_query);
  }
  if (update.message) {
    return routeMessage(bot, update.message, ctx);
  }
  return null;
}

// ================================
// fetch handler (webhook + setup)
// ================================
async function fetchHandler(request, env, ctx) {
  const url = new URL(request.url);

  try {
    if (request.method === "GET") {
      if (url.pathname === "/setup") {
        const key = url.searchParams.get("key") || request.headers.get("X-Setup-Key");
        if (!env.BOT_TOKEN) return new Response("BOT_TOKEN is not set. Run: wrangler secret put BOT_TOKEN", { status: 500 });
        if (!env.WEBHOOK_SECRET) return new Response("WEBHOOK_SECRET is not set. Run: wrangler secret put WEBHOOK_SECRET", { status: 500 });
        if (key !== env.WEBHOOK_SECRET) return new Response("Forbidden: append ?key=YOUR_WEBHOOK_SECRET", { status: 403 });
        const bot = new Bot(env);
        const hookUrl = url.origin + "/webhook";
        const result = await bot.tg("setWebhook", {
          url: hookUrl,
          secret_token: env.WEBHOOK_SECRET,
          allowed_updates: ["message", "callback_query"],
          drop_pending_updates: false,
        });
        return Response.json({ ok: true, webhook_url: hookUrl, telegram: result });
      }
      if (url.pathname === "/health") return new Response("ok");
      if (url.pathname === "/") {
        return new Response(
          "Telegram moderation bot is running.\n" +
            "POST /webhook — Telegram updates (secret-protected)\n" +
            "GET /setup?key=... — register the Telegram webhook\n" +
            "GET /health — liveness check\n",
          { headers: { "Content-Type": "text/plain; charset=utf-8" } }
        );
      }
      return new Response("Not found", { status: 404 });
    }

    if (request.method === "POST" && url.pathname === "/webhook") {
      if (!env.WEBHOOK_SECRET) return new Response("WEBHOOK_SECRET is not configured", { status: 500 });
      const secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token");
      if (secret !== env.WEBHOOK_SECRET) return new Response("Forbidden", { status: 403 });
      let update;
      try {
        update = await request.json();
      } catch (e) {
        return new Response("Bad Request", { status: 400 });
      }
      try {
        await handleUpdate(update, env, ctx);
      } catch (e) {
        // always answer 200 so Telegram does not retry-storm the worker
        console.error("Update handler error:", e);
      }
      return new Response("ok");
    }

    return new Response("Not found", { status: 404 });
  } catch (e) {
    console.error("fetch error:", e);
    return new Response("Internal error: " + (e.message || e), { status: 500 });
  }
}

export default { fetch: fetchHandler };
export { handleUpdate };
