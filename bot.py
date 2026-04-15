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
    filters,
    ContextTypes
)

CHANNEL_ID = -1003685752199
TOKEN = os.getenv("BOT_TOKEN")


# 🧠 БД
def init_db():
    conn = sqlite3.connect("bot.db")
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        text TEXT,
        category TEXT,
        photo TEXT,
        likes INTEGER DEFAULT 0,
        views INTEGER DEFAULT 0
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS likes (
        user_id INTEGER,
        ad_id INTEGER
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS favorites (
        user_id INTEGER,
        ad_id INTEGER
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS purchases (
        user_id INTEGER,
        ad_id INTEGER
    )
    """)

    conn.commit()
    conn.close()


# 🔹 клавиатуры
def main_kb():
    return ReplyKeyboardMarkup([
        ["Создать", "📄 Мои"],
        ["🔍 Поиск", "⭐ Избранное"]
    ], resize_keyboard=True)


def back_kb():
    return ReplyKeyboardMarkup([["⬅️ Назад"]], resize_keyboard=True)


# 🚀 старт
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Меню", reply_markup=main_kb())


# 📄 мои объявления
async def my_ads(update, context):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()

    cur.execute("SELECT id, text, likes, views FROM ads WHERE user_id = ?", (update.effective_user.id,))
    ads = cur.fetchall()
    conn.close()

    if not ads:
        await update.message.reply_text("Нет объявлений")
        return

    for ad_id, text, likes, views in ads:
        await update.message.reply_text(f"{text}\n❤️ {likes} 👁 {views}")


# ⭐ избранное
async def favorites(update, context):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()

    cur.execute("""
    SELECT ads.text FROM ads
    JOIN favorites ON ads.id = favorites.ad_id
    WHERE favorites.user_id = ?
    """, (update.effective_user.id,))

    data = cur.fetchall()
    conn.close()

    if not data:
        await update.message.reply_text("Пусто")
        return

    for (text,) in data:
        await update.message.reply_text(text)


# 🔘 кнопки
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    action, ad_id = query.data.split("_")
    ad_id = int(ad_id)
    user_id = query.from_user.id

    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()

    # ❤️ лайк
    if action == "like":
        cur.execute("SELECT * FROM likes WHERE user_id=? AND ad_id=?", (user_id, ad_id))
        if cur.fetchone():
            await query.answer("Уже лайкал")
            return

        cur.execute("INSERT INTO likes VALUES (?,?)", (user_id, ad_id))
        cur.execute("UPDATE ads SET likes = likes + 1 WHERE id=?", (ad_id,))
        conn.commit()

    # ⭐ избранное
    elif action == "fav":
        cur.execute("INSERT INTO favorites VALUES (?,?)", (user_id, ad_id))
        conn.commit()
        await query.answer("Добавлено ⭐")

    # 🛒 покупка
    elif action == "buy":
        cur.execute("SELECT * FROM purchases WHERE user_id=? AND ad_id=?", (user_id, ad_id))
        if cur.fetchone():
            await query.answer("Ты уже нажал 😄")
            return

        cur.execute("INSERT INTO purchases VALUES (?,?)", (user_id, ad_id))
        conn.commit()

        # уведомление продавцу
        cur.execute("SELECT user_id FROM ads WHERE id=?", (ad_id,))
        seller = cur.fetchone()[0]

        await context.bot.send_message(
            seller,
            "🔥 Твоим товаром заинтересовались!"
        )

        await query.answer("Свяжись с продавцом")

    conn.close()


# 📸 фото
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("create"):
        return

    context.user_data["photo"] = update.message.photo[-1].file_id
    await update.message.reply_text("Теперь напиши название и цену")


# 💬 сообщения
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "⬅️ Назад":
        context.user_data.clear()
        await update.message.reply_text("Меню", reply_markup=main_kb())
        return

    if text == "Создать":
        keyboard = [["👕 Одежда", "📱 Техника"], ["🚗 Авто"]]
        await update.message.reply_text("Выбери категорию", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
        return

    if text in ["👕 Одежда", "📱 Техника", "🚗 Авто"]:
        context.user_data["category"] = text
        context.user_data["create"] = True
        await update.message.reply_text("Отправь фото", reply_markup=back_kb())
        return

    if text == "📄 Мои":
        await my_ads(update, context)
        return

    if text == "⭐ Избранное":
        await favorites(update, context)
        return

    if text == "🔍 Поиск":
        context.user_data["search"] = True
        await update.message.reply_text("Что ищем?")
        return

    # 🔎 поиск
    if context.user_data.get("search"):
        conn = sqlite3.connect("bot.db")
        cur = conn.cursor()

        cur.execute("SELECT id, text, photo FROM ads WHERE text LIKE ?", (f"%{text}%",))
        data = cur.fetchall()
        conn.close()

        for ad_id, t, photo in data:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("❤️", callback_data=f"like_{ad_id}")],
                [InlineKeyboardButton("⭐", callback_data=f"fav_{ad_id}")],
                [InlineKeyboardButton("🛒 Купить", callback_data=f"buy_{ad_id}")]
            ])

            if photo:
                await update.message.reply_photo(photo, caption=t, reply_markup=keyboard)
            else:
                await update.message.reply_text(t, reply_markup=keyboard)

        context.user_data["search"] = False
        return

    # 📝 создание
    if context.user_data.get("create"):
        parts = text.split()
        if len(parts) < 2:
            await update.message.reply_text("Пример: Nike 200$")
            return

        result = f"{parts[0]} — {parts[1]}"
        user_id = update.effective_user.id
        photo = context.user_data.get("photo")

        conn = sqlite3.connect("bot.db")
        cur = conn.cursor()

        cur.execute(
            "INSERT INTO ads (user_id, text, category, photo) VALUES (?,?,?,?)",
            (user_id, result, context.user_data["category"], photo)
        )

        ad_id = cur.lastrowid
        conn.commit()
        conn.close()

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 Написать", url=f"tg://user?id={user_id}")],
            [InlineKeyboardButton("❤️", callback_data=f"like_{ad_id}")],
            [InlineKeyboardButton("⭐", callback_data=f"fav_{ad_id}")],
            [InlineKeyboardButton("🛒 Купить", callback_data=f"buy_{ad_id}")]
        ])

        if photo:
            await context.bot.send_photo(CHANNEL_ID, photo, caption=result, reply_markup=keyboard)
        else:
            await context.bot.send_message(CHANNEL_ID, result, reply_markup=keyboard)

        await update.message.reply_text("Опубликовано 🚀", reply_markup=main_kb())
        context.user_data.clear()


# 🚀 запуск
init_db()

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
app.add_handler(CallbackQueryHandler(buttons))

print("Bot V3 started 🚀")

app.run_polling()
