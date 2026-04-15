import sqlite3
import os
import asyncio

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
        likes INTEGER DEFAULT 0,
        sent INTEGER DEFAULT 0
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
        user_id INTEGER,
        channel_id INTEGER
    )
    """)

    conn.commit()
    conn.close()


# 🔹 клавиатура
def main_kb():
    return ReplyKeyboardMarkup([
        ["➕ Подключить канал", "📡 Мои каналы"],
        ["Создать", "📄 Мои"],
        ["🔍 Поиск", "⭐ Избранное"],
        ["🏆 Топ"]
    ], resize_keyboard=True)


def back_kb():
    return ReplyKeyboardMarkup([["⬅️ Назад"]], resize_keyboard=True)


# 🚀 старт
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    # если /start в канале → сохраняем канал
    if update.effective_chat.type == "channel":
        channel_id = update.effective_chat.id
        user_id = update.effective_user.id if update.effective_user else None

        if user_id:
            conn = sqlite3.connect("bot.db")
            cur = conn.cursor()
            cur.execute("INSERT INTO channels VALUES (?,?)", (user_id, channel_id))
            conn.commit()
            conn.close()

        return

    await update.message.reply_text("🚀 Маркет бот", reply_markup=main_kb())


# 📡 мои каналы
async def my_channels(update, context):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()

    cur.execute("SELECT channel_id FROM channels WHERE user_id=?", (update.effective_user.id,))
    data = cur.fetchall()
    conn.close()

    if not data:
        await update.message.reply_text("Нет каналов")
        return

    for (cid,) in data:
        await update.message.reply_text(f"Канал ID: {cid}")


# 📄 мои объявления
async def my_ads(update, context):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()

    cur.execute("SELECT text, likes FROM ads WHERE user_id=?", (update.effective_user.id,))
    data = cur.fetchall()
    conn.close()

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
    user_id = query.from_user.id

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

    if text == "➕ Подключить канал":
        await update.message.reply_text(
            "Добавь бота в канал → сделай админом → напиши /start в канале"
        )
        return

    if text == "📡 Мои каналы":
        await my_channels(update, context)
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

    if context.user_data.get("search"):
        conn = sqlite3.connect("bot.db")
        cur = conn.cursor()

        cur.execute("SELECT id, text FROM ads WHERE text LIKE ?", (f"%{text}%",))
        data = cur.fetchall()
        conn.close()

        for ad_id, t in data:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("❤️", callback_data=f"like_{ad_id}")],
                [InlineKeyboardButton("⭐", callback_data=f"fav_{ad_id}")]
            ])
            await update.message.reply_text(t, reply_markup=keyboard)

        context.user_data["search"] = False
        return

    if text == "Создать":
        context.user_data["create"] = True
        await update.message.reply_text("Отправь фото", reply_markup=back_kb())
        return

    if context.user_data.get("create"):

        if "," not in text:
            await update.message.reply_text("Пример: iPhone, 500$")
            return

        name, price = text.split(",", 1)
        result = f"{name.strip()} — {price.strip()}"

        conn = sqlite3.connect("bot.db")
        cur = conn.cursor()

        cur.execute("INSERT INTO ads (user_id, text, photo) VALUES (?,?,?)",
                    (user_id, result, context.user_data.get("photo")))

        conn.commit()
        conn.close()

        await update.message.reply_text("Объявление создано 🚀")

        context.user_data.clear()


# 🔥 авто реклама
async def auto_ads(app):
    while True:
        await asyncio.sleep(60)

        conn = sqlite3.connect("bot.db")
        cur = conn.cursor()

        cur.execute("SELECT id, text, photo, user_id FROM ads WHERE sent=0 LIMIT 1")
        ad = cur.fetchone()

        if not ad:
            conn.close()
            continue

        ad_id, text, photo, owner = ad

        cur.execute("SELECT channel_id FROM channels WHERE user_id=?", (owner,))
        channels = cur.fetchall()

        for (cid,) in channels:
            try:
                if photo:
                    await app.bot.send_photo(cid, photo, caption=f"🔥 {text}")
                else:
                    await app.bot.send_message(cid, f"🔥 {text}")
            except:
                pass

        cur.execute("UPDATE ads SET sent=1 WHERE id=?", (ad_id,))
        conn.commit()
        conn.close()


# 🚀 главный запуск
async def main():
    init_db()

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(buttons))

    print("🔥 BOT STARTED")

    # запускаем авто рекламу
    asyncio.create_task(auto_ads(app))

    await app.run_polling()


if __name__ == "__main__":
    asyncio.run(main())
