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
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS ads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        text TEXT,
        category TEXT,
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
    CREATE TABLE IF NOT EXISTS purchases (
        user_id INTEGER,
        ad_id INTEGER
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        seller_id INTEGER,
        user_id INTEGER,
        ad_id INTEGER,
        text TEXT,
        rating INTEGER
    )
    """)

    conn.commit()
    conn.close()


# 🔹 клавиатуры
def main_kb():
    return ReplyKeyboardMarkup([
        ["Создать", "📄 Мои"],
        ["🔍 Поиск", "⭐ Отзывы"],
        ["💬 Чаты"]
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

    cur.execute("SELECT text, likes FROM ads WHERE user_id=?", (update.effective_user.id,))
    ads = cur.fetchall()
    conn.close()

    if not ads:
        await update.message.reply_text("Нет объявлений")
        return

    for text, likes in ads:
        await update.message.reply_text(f"{text}\n❤️ {likes}")


# ⭐ отзывы
async def my_reviews(update, context):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()

    cur.execute("SELECT text, rating FROM reviews WHERE seller_id=?", (update.effective_user.id,))
    data = cur.fetchall()
    conn.close()

    if not data:
        await update.message.reply_text("Нет отзывов")
        return

    for text, rating in data:
        await update.message.reply_text(f"⭐ {rating}\n{text}")


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
            conn.close()
            return

        cur.execute("INSERT INTO likes VALUES (?,?)", (user_id, ad_id))
        cur.execute("UPDATE ads SET likes = likes + 1 WHERE id=?", (ad_id,))
        conn.commit()

    # 🛒 покупка
    elif action == "buy":
        cur.execute("SELECT * FROM purchases WHERE user_id=? AND ad_id=?", (user_id, ad_id))
        if cur.fetchone():
            await query.answer("Уже нажал")
            conn.close()
            return

        cur.execute("INSERT INTO purchases VALUES (?,?)", (user_id, ad_id))
        conn.commit()

        cur.execute("SELECT user_id FROM ads WHERE id=?", (ad_id,))
        seller = cur.fetchone()[0]

        # запускаем чат
        context.user_data["chat_with"] = seller

        await query.message.reply_text("💬 Напиши сообщение продавцу")

    conn.close()


# 📸 фото
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("create"):
        return

    context.user_data["photo"] = update.message.photo[-1].file_id
    await update.message.reply_text("Теперь напиши описание и цену (Nike Air, 200$)")


# 💬 сообщения
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    if text == "⬅️ Назад":
        context.user_data.clear()
        await update.message.reply_text("Меню", reply_markup=main_kb())
        return

    # 📄 мои
    if text == "📄 Мои":
        await my_ads(update, context)
        return

    # ⭐ отзывы
    if text == "⭐ Отзывы":
        await my_reviews(update, context)
        return

    # 💬 чат
    if context.user_data.get("chat_with"):
        seller = context.user_data["chat_with"]

        await context.bot.send_message(
            seller,
            f"💬 Сообщение от покупателя:\n{text}"
        )

        await update.message.reply_text("Отправлено ✅")
        return

    # 🔎 поиск
    if text == "🔍 Поиск":
        context.user_data["search"] = True
        await update.message.reply_text("Что ищем?")
        return

    if context.user_data.get("search"):
        conn = sqlite3.connect("bot.db")
        cur = conn.cursor()

        cur.execute("SELECT id, text, photo FROM ads WHERE text LIKE ?", (f"%{text}%",))
        data = cur.fetchall()
        conn.close()

        if not data:
            await update.message.reply_text("Ничего не найдено")
            return

        for ad_id, t, photo in data:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("❤️", callback_data=f"like_{ad_id}")],
                [InlineKeyboardButton("🛒 Купить", callback_data=f"buy_{ad_id}")]
            ])

            if photo:
                await update.message.reply_photo(photo, caption=t, reply_markup=keyboard)
            else:
                await update.message.reply_text(t, reply_markup=keyboard)

        context.user_data["search"] = False
        return

    # 🆕 создать
    if text == "Создать":
        keyboard = [["👕 Одежда", "📱 Техника"], ["🚗 Авто"]]
        await update.message.reply_text("Выбери категорию", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
        return

    if text in ["👕 Одежда", "📱 Техника", "🚗 Авто"]:
        context.user_data["category"] = text
        context.user_data["create"] = True
        await update.message.reply_text("Отправь фото", reply_markup=back_kb())
        return

    # 📝 создание
    if context.user_data.get("create"):
        if "," not in text:
            await update.message.reply_text("Пример: Nike Air Max, 200$")
            return

        name, price = text.split(",", 1)
        result = f"{name.strip()} — {price.strip()}"

        conn = sqlite3.connect("bot.db")
        cur = conn.cursor()

        cur.execute(
            "INSERT INTO ads (user_id, text, category, photo) VALUES (?,?,?,?)",
            (user_id, result, context.user_data["category"], context.user_data.get("photo"))
        )

        ad_id = cur.lastrowid
        conn.commit()
        conn.close()

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 Написать", url=f"tg://user?id={user_id}")],
            [InlineKeyboardButton("❤️", callback_data=f"like_{ad_id}")],
            [InlineKeyboardButton("🛒 Купить", callback_data=f"buy_{ad_id}")]
        ])

        if context.user_data.get("photo"):
            await context.bot.send_photo(CHANNEL_ID, context.user_data["photo"], caption=result, reply_markup=keyboard)
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

print("Bot FULL started 🚀")

app.run_polling()
