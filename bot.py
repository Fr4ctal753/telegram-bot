import sqlite3
import os

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    CallbackQueryHandler,
    ChatMemberHandler,
    filters,
    ContextTypes
)

TOKEN = os.getenv("BOT_TOKEN")


# 🧠 БД
def init_db():
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS ads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        text TEXT,
        photo TEXT,
        likes INTEGER DEFAULT 0
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS likes (
        user_id INTEGER,
        ad_id INTEGER
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS favorites (
        user_id INTEGER,
        ad_id INTEGER
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS channels (
        chat_id INTEGER UNIQUE
    )
    """)

    conn.commit()
    conn.close()


# 📡 авто добавление канала
async def track_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.my_chat_member.chat

    if chat.type == "channel":
        chat_id = chat.id

        conn = sqlite3.connect("bot.db")
        cur = conn.cursor()

        cur.execute("INSERT OR IGNORE INTO channels (chat_id) VALUES (?)", (chat_id,))
        conn.commit()
        conn.close()

        print(f"✅ Канал добавлен: {chat_id}")


# 🔹 клавиатуры
def main_kb():
    return ReplyKeyboardMarkup([
        ["Создать", "📄 Мои"],
        ["🔍 Поиск", "⭐ Избранное"],
        ["🏆 Топ"]
    ], resize_keyboard=True)


def back_kb():
    return ReplyKeyboardMarkup([["⬅️ Назад"]], resize_keyboard=True)


# 🚀 старт
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚀 Маркет бот", reply_markup=main_kb())


# 📄 мои объявления
async def my_ads(update, context):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()

    cur.execute("SELECT text, likes FROM ads WHERE user_id=?", (update.effective_user.id,))
    data = cur.fetchall()
    conn.close()

    if not data:
        await update.message.reply_text("Нет объявлений")
        return

    for text, likes in data:
        await update.message.reply_text(f"{text}\n❤️ {likes}")


# ⭐ избранное
async def favs(update, context):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()

    cur.execute("""
    SELECT ads.text FROM ads
    JOIN favorites ON ads.id = favorites.ad_id
    WHERE favorites.user_id=?
    """, (update.effective_user.id,))

    data = cur.fetchall()
    conn.close()

    if not data:
        await update.message.reply_text("Пусто")
        return

    for (text,) in data:
        await update.message.reply_text(text)


# 🏆 топ
async def top(update, context):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()

    cur.execute("SELECT text, likes FROM ads ORDER BY likes DESC LIMIT 5")
    data = cur.fetchall()
    conn.close()

    for text, likes in data:
        await update.message.reply_text(f"{text}\n❤️ {likes}")


# 🔘 кнопки
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    action, ad_id = query.data.split("_")
    ad_id = int(ad_id)
    user = query.from_user
    user_id = user.id

    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()

    if action == "like":
        cur.execute("SELECT * FROM likes WHERE user_id=? AND ad_id=?", (user_id, ad_id))
        if cur.fetchone():
            await query.answer("Уже лайкал")
            conn.close()
            return

        cur.execute("INSERT INTO likes VALUES (?,?)", (user_id, ad_id))
        cur.execute("UPDATE ads SET likes = likes + 1 WHERE id=?", (ad_id,))
        conn.commit()

    elif action == "fav":
        cur.execute("INSERT INTO favorites VALUES (?,?)", (user_id, ad_id))
        conn.commit()
        await query.answer("Добавлено ⭐")

    elif action == "msg":
        cur.execute("SELECT user_id FROM ads WHERE id=?", (ad_id,))
        seller = cur.fetchone()[0]

        # 👇 получаем username
        if user.username:
            user_info = f"@{user.username}"
        else:
            user_info = user.first_name

        try:
            await context.bot.send_message(
                seller,
                f"📩 Кто-то хочет написать тебе!\n👤 {user_info}"
            )
        except:
            pass

        await query.answer("Продавец уведомлен 📩")

    conn.close()


# 📸 фото
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("create"):
        return

    context.user_data["photo"] = update.message.photo[-1].file_id
    await update.message.reply_text("Теперь напиши: описание, цена (через запятую)")


# 💬 сообщения
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    if text == "⬅️ Назад":
        context.user_data.clear()
        await update.message.reply_text("Меню", reply_markup=main_kb())
        return

    if text == "📄 Мои":
        await my_ads(update, context)
        return

    if text == "⭐ Избранное":
        await favs(update, context)
        return

    if text == "🏆 Топ":
        await top(update, context)
        return

    if text == "🔍 Поиск":
        context.user_data["search"] = True
        await update.message.reply_text("Что ищем?")
        return

    # 🔎 поиск
    if context.user_data.get("search"):
        conn = sqlite3.connect("bot.db")
        cur = conn.cursor()

        cur.execute("SELECT id, text FROM ads WHERE text LIKE ?", (f"%{text}%",))
        data = cur.fetchall()
        conn.close()

        if not data:
            await update.message.reply_text("Ничего не найдено")
            return

        for ad_id, t in data:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("💬 Написать", callback_data=f"msg_{ad_id}")],
                [InlineKeyboardButton("❤️", callback_data=f"like_{ad_id}")],
                [InlineKeyboardButton("⭐", callback_data=f"fav_{ad_id}")]
            ])
            await update.message.reply_text(t, reply_markup=keyboard)

        context.user_data["search"] = False
        return

    # 🆕 создать
    if text == "Создать":
        context.user_data["create"] = True
        await update.message.reply_text("Отправь фото", reply_markup=back_kb())
        return

    # 📝 создание
    if context.user_data.get("create"):

        if "," not in text:
            await update.message.reply_text("Пример: iPhone 13, 500$")
            return

        name, price = text.split(",", 1)
        result = f"{name.strip()} — {price.strip()}"

        conn = sqlite3.connect("bot.db")
        cur = conn.cursor()

        cur.execute("INSERT INTO ads (user_id, text, photo) VALUES (?,?,?)",
                    (user_id, result, context.user_data.get("photo")))

        ad_id = cur.lastrowid

        cur.execute("SELECT chat_id FROM channels")
        channels = cur.fetchall()

        conn.commit()
        conn.close()

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 Написать", callback_data=f"msg_{ad_id}")],
            [InlineKeyboardButton("❤️", callback_data=f"like_{ad_id}")],
            [InlineKeyboardButton("⭐", callback_data=f"fav_{ad_id}")]
        ])

        for (chat_id,) in channels:
            try:
                member = await context.bot.get_chat_member(chat_id, user_id)

                if member.status in ["administrator", "creator"]:
                    if context.user_data.get("photo"):
                        await context.bot.send_photo(chat_id, context.user_data["photo"], caption=result, reply_markup=keyboard)
                    else:
                        await context.bot.send_message(chat_id, result, reply_markup=keyboard)
            except:
                pass

        await update.message.reply_text("Объявление опубликовано 🚀", reply_markup=main_kb())
        context.user_data.clear()


# 🚀 запуск
if __name__ == "__main__":
    init_db()

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(ChatMemberHandler(track_channel, ChatMemberHandler.MY_CHAT_MEMBER))

    print("🔥 BOT STARTED")

    app.run_polling()
