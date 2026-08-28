// Local test suite for worker.js — no Cloudflare account needed.
// Emulates D1 with a local SQLite (node:sqlite / better-sqlite3) and mocks
// the Telegram Bot API by intercepting global fetch.
//
// Run:  node test.mjs

import { readFileSync } from "node:fs";
import { createTestDb } from "./d1-shim.mjs";
import { handleUpdate } from "./worker.js";

const ADMIN = 1; // creator
const ADMIN2 = 2; // administrator
const USER = 3; // regular member
const BOT_ID = 999; // must match the getMe() mock

const schema = readFileSync(new URL("./schema.sql", import.meta.url), "utf8");

// ---------------- Telegram API mock ----------------
const calls = [];
let failDeleteIds = new Set();
let msgId = 1000;

globalThis.fetch = async (input, init) => {
  const url = String(input);
  const m = /\/bot([^/]+)\/([A-Za-z]+)$/.exec(url);
  if (!m) throw new Error("unexpected fetch: " + url);
  const method = m[2];
  let params = null;
  if (init && typeof init.body === "string") {
    try {
      params = JSON.parse(init.body);
    } catch (e) {}
  }
  calls.push({ method, params });

  if (method === "deleteMessage" && params && failDeleteIds.has(params.message_id)) {
    return new Response(JSON.stringify({ ok: false, error_code: 400, description: "Bad Request: message to delete not found" }), {
      headers: { "content-type": "application/json" },
    });
  }
  return new Response(JSON.stringify({ ok: true, result: mockResult(method, params) }), {
    headers: { "content-type": "application/json" },
  });
};

function mockResult(method, params) {
  switch (method) {
    case "getMe":
      return { id: BOT_ID, is_bot: true, username: "modbot", first_name: "ModBot" };
    case "getChatMember": {
      const uid = params.user_id;
      let status = "member";
      if (uid === ADMIN) status = "creator";
      else if (uid === ADMIN2) status = "administrator";
      return { status: status, user: { id: uid, first_name: "User" + uid, is_bot: false } };
    }
    case "getChatMemberCount":
      return 42;
    case "sendMessage":
      return { message_id: ++msgId, chat: { id: params.chat_id } };
    default:
      return {};
  }
}

// ---------------- helpers ----------------
const env = {
  DB: await createTestDb(schema),
  BOT_TOKEN: "TEST:TOKEN",
  WEBHOOK_SECRET: "s3cret",
  DEFAULT_LANG: "ru",
  SEED_TRIGGER_WORDS: "спам, казино",
};
const ctx = { waitUntil() {} };

function msg(chatId, fromId, text, extra = {}) {
  const m = {
    message_id: ++msgId,
    from: Object.assign({ id: fromId, first_name: "User" + fromId, is_bot: false }, extra.from),
    chat: Object.assign({ id: chatId, type: "supergroup", title: "Chat" + chatId }, extra.chat),
    date: Math.floor(Date.now() / 1000),
  };
  for (const [k, v] of Object.entries(extra)) {
    if (k !== "from" && k !== "chat") m[k] = v;
  }
  if (text !== null && text !== undefined) m.text = text;
  return m;
}

async function send(chatId, fromId, text, extra) {
  return handleUpdate({ update_id: msgId, message: msg(chatId, fromId, text, extra) }, env, ctx);
}
async function sendCallback(call) {
  return handleUpdate({ update_id: msgId, callback_query: call }, env, ctx);
}

let passed = 0;
let failed = 0;
function check(name, cond, extra) {
  if (cond) {
    passed++;
    console.log("  ✅ " + name);
  } else {
    failed++;
    console.log("  ❌ " + name + (extra !== undefined ? " — " + JSON.stringify(extra) : ""));
  }
}
function resetCalls() {
  calls.length = 0;
}
function sent(method) {
  return calls.filter((c) => c.method === method);
}
function sentTexts(method) {
  return sent(method).map((c) => (c.params ? c.params.text : "")).filter(Boolean);
}

// ================= TESTS =================
console.log("T1. /start в приватном чате");
resetCalls();
await send(777, USER, "/start", { chat: { id: 777, type: "private" } });
check("приветствие отправлено", sentTexts("sendMessage").some((t) => t.includes("Бот модерации")));
check("клавиатура не приложена (приват)", sent("sendMessage").every((c) => !c.params.reply_markup));

console.log("T2. /myid");
resetCalls();
await send(778, USER, "/myid", { chat: { id: 778, type: "private" } });
check("ID пользователя и чата", sentTexts("sendMessage").some((t) => t.includes("`" + USER + "`") && t.includes("`778`")));

console.log("T3. /addword (админ, чат -100)");
resetCalls();
await send(-100, ADMIN, "/addword дурак");
check("слово добавлено", sentTexts("sendMessage").some((t) => t.includes("дурак")));
check("слово в БД только для чата -100", env.DB.raw("SELECT word FROM triggers WHERE chat_id = -100 AND word = 'дурак'").length === 1);

console.log("T4. Изоляция чатов + сидинг из SEED_TRIGGER_WORDS");
resetCalls();
await send(-200, USER, "большое казино открылось"); // сид-слово "казино"
check("сид-слово сработало в новом чате", sent("deleteMessage").length === 1);
check("причина показана с цензурой", sentTexts("sendMessage").some((t) => t.includes("к****о")));
resetCalls();
await send(-200, USER, "ты дурак"); // слово из ДРУГОГО чата
check("слово из чужого чата не сработало", sent("deleteMessage").length === 0);
resetCalls();
await send(-100, USER, "ты дурак");
check("слово сработало в своём чате", sent("deleteMessage").length === 1);

console.log("T5. Границы слов");
await send(-300, ADMIN, "/addword тест");
resetCalls();
await send(-300, USER, "я протестовал против");
check("внутри слова не матчится", sent("deleteMessage").length === 0);
await send(-300, USER, "это тест");
check("отдельное слово матчится", sent("deleteMessage").length === 1);

console.log("T6. Анти-ссылки: широкие TLD, подписи, entities");
await env.DB.exec("INSERT INTO settings (chat_id, data) VALUES (-400, '{\"antilink_enabled\":true}')");
resetCalls();
await send(-400, USER, "заходи на example.de"); // .de не было в старом списке
check("голый домен .de удалён", sent("deleteMessage").length === 1);
resetCalls();
await send(-400, USER, null, { caption: "смотри https://spammer.example", photo: [{}] });
check("ссылка в подписи к фото удалена", sent("deleteMessage").length === 1);
resetCalls();
await send(-400, USER, "клик", { entities: [{ offset: 0, length: 4, type: "url" }] });
check("ссылка через entity (text_link/url) удалена", sent("deleteMessage").length === 1);
resetCalls();
await send(-400, USER, "просто текст без ссылок");
check("обычный текст не тронут", sent("deleteMessage").length === 0);
const linksStat = env.DB.raw("SELECT count FROM stats WHERE chat_id = -400 AND stat_type = 'links_blocked'");
check("статистика ссылок = 3", linksStat.length === 1 && linksStat[0].count === 3, linksStat);

console.log("T7. Анти-спам 5 сообщений / 10 сек (через D1)");
resetCalls();
for (let i = 1; i <= 5; i++) await send(-500, USER, "сообщение " + i);
check("первые 5 не удалены", sent("deleteMessage").length === 0);
await send(-500, USER, "сообщение 6");
check("6-е удалено", sent("deleteMessage").length === 1);
const restrict = sent("restrictChatMember");
check("автомут на 5 минут", restrict.length === 1 && restrict[0].params.until_date > Math.floor(Date.now() / 1000));
check("сообщение о спаме", sentTexts("sendMessage").some((t) => t.includes("спам")));

console.log("T8. /warn ×3 → автобан");
resetCalls();
for (let i = 1; i <= 3; i++) await send(-600, ADMIN, "/warn 77777 причина" + i);
check("3 предупреждения записаны", env.DB.raw("SELECT COUNT(*) AS c FROM warns WHERE chat_id = -600 AND user_id = 77777")[0].c === 3);
check("бан после 3-го", sent("banChatMember").length === 1 && sent("banChatMember")[0].params.user_id === 77777);
check("сообщение о бане по лимиту", sentTexts("sendMessage").some((t) => t.includes("достигнут лимит")));
const w = env.DB.raw("SELECT count FROM stats WHERE chat_id = -600 AND stat_type = 'warns_given'");
check("статистика warns_given = 3", w.length === 1 && w[0].count === 3);

console.log("T9. /mute по реплаю с причиной (без длительности)");
resetCalls();
await send(-700, ADMIN2, "/mute за флуд", {
  reply_to_message: { message_id: 55, from: { id: 888, first_name: "Bob", is_bot: false } },
});
const r = sent("restrictChatMember");
check("мут навсегда (без until_date)", r.length === 1 && r[0].params.until_date === undefined, r.map((x) => x.params));
check("причина указана", sentTexts("sendMessage").some((t) => t.includes("за флуд") && t.includes("навсегда")));

console.log("T10. /mute с некорректной длительностью");
resetCalls();
await send(-700, ADMIN2, "/mute 0m", {
  reply_to_message: { message_id: 56, from: { id: 888, first_name: "Bob", is_bot: false } },
});
await send(-700, ADMIN2, "/mute 99w", {
  reply_to_message: { message_id: 57, from: { id: 888, first_name: "Bob", is_bot: false } },
});
check("ошибка формата времени", sentTexts("sendMessage").filter((t) => t.includes("Неверный формат")).length === 2);
check("мут не применён", sent("restrictChatMember").length === 0);

console.log("T11. /clear с пропусками в ID сообщений");
resetCalls();
failDeleteIds = new Set([1998, 1996]);
const clearMsg = msg(-800, ADMIN, "/clear 3");
clearMsg.message_id = 2000;
await handleUpdate({ update_id: 1, message: clearMsg }, env, ctx);
const deletedIds = sent("deleteMessage").map((c) => c.params.message_id);
check("перешёл через дыры в ID", JSON.stringify(deletedIds) === JSON.stringify([2000, 1999, 1998, 1997, 1996, 1995]), deletedIds);
check("итог: 4 сообщения (3 + команда)", sentTexts("sendMessage").some((t) => t.includes("4")));
failDeleteIds = new Set();

console.log("T12. /listwords → /confirm ×3 → файл");
resetCalls();
await send(-900, ADMIN, "/listwords");
check("запрошено тройное подтверждение", sentTexts("sendMessage").some((t) => t.includes("Подтвердите 3 раза")));
resetCalls();
await send(-900, ADMIN, "/confirm");
await send(-900, ADMIN, "/confirm");
await send(-900, ADMIN, "/confirm");
check("файл отправлен на 3-м подтверждении", sent("sendDocument").length === 1);
check("квитанции очищены", env.DB.raw("SELECT COUNT(*) AS c FROM confirmations")[0].c === 0);

console.log("T13. Переключение языка и /stats");
resetCalls();
await sendCallback({
  id: "cb1",
  from: { id: ADMIN, first_name: "Admin", is_bot: false },
  message: { message_id: 5, chat: { id: -1000, type: "supergroup", title: "Chat" } },
  data: "set_lang:en",
});
check("язык переключён на en", sentTexts("editMessageText").some((t) => t.includes("English")));
resetCalls();
await send(-1000, ADMIN, "/stats");
check("статистика на английском", sentTexts("sendMessage").some((t) => t.includes("Moderation statistics")));

console.log("T14. Предупреждение при добавлении бота без прав админа");
resetCalls();
await send(-1100, ADMIN, null, { new_chat_members: [{ id: BOT_ID, is_bot: true, first_name: "ModBot" }] });
check("бот просит права администратора", sentTexts("sendMessage").some((t) => t.includes("администратором")));

console.log("T15. /setwelcome + приветствие новому участнику");
resetCalls();
await send(-1200, ADMIN, "/setwelcome Привет, {user}! Добро пожаловать в {chat}");
check("приветствие сохранено и включено", sentTexts("sendMessage").some((t) => t.includes("Приветствие обновлено")));
resetCalls();
await send(-1200, ADMIN, null, { new_chat_members: [{ id: 55, is_bot: false, first_name: "Виктор" }] });
check("переменные подставлены", sentTexts("sendMessage").some((t) => t.includes("Привет, Виктор!") && t.includes("Chat-1200")));

console.log("T16. /kick по реплаю (бан + разбан)");
resetCalls();
await send(-1300, ADMIN, "/kick", {
  reply_to_message: { message_id: 70, from: { id: 444, first_name: "Kick", is_bot: false } },
});
check("бан+разбан = кик", sent("banChatMember").length === 1 && sent("unbanChatMember").length === 1);
check("статистика киков", env.DB.raw("SELECT count FROM stats WHERE chat_id = -1300 AND stat_type = 'kicks'")[0].count === 1);

console.log("T17. Неизвестная команда проходит модерацию, админ не модерируется");
resetCalls();
await send(-200, USER, "/unknowncommand казино");
check("триггер в неизвестной команде удалён", sent("deleteMessage").length === 1);
resetCalls();
await send(-200, ADMIN, "казино");
check("сообщение админа не тронуто", sent("deleteMessage").length === 0);

console.log("T18. /unban и /userinfo");
resetCalls();
await send(-600, ADMIN, "/unban 77777");
check("разбан", sent("unbanChatMember").length === 1 && sent("unbanChatMember")[0].params.only_if_banned === true);
resetCalls();
await send(-600, ADMIN, "/userinfo 77777");
check("инфо о пользователе с варнами", sentTexts("sendMessage").some((t) => t.includes("77777") && t.includes("Предупреждений")));

console.log("");
console.log("==============================");
console.log("Пройдено: " + passed + ", упало: " + failed);
if (failed > 0) process.exit(1);
