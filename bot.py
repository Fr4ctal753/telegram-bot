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
        ["🔍 Поиск", "⭐ Избранное"],
        ["⭐ Мои отзывы"]
    ], resize_keyboard=True)


def back_kb():
    return ReplyKeyboardMarkup([["⬅️ Назад"]], resize_keyboard=True)


# 🚀 старт
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Меню", reply_markup=main_kb())


# 📊 отзывы пользователя
async def my_reviews(update, context):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()

    cur.execute("""
    SELECT text, rating FROM reviews WHERE seller_id = ?
    """, (update.effective_user.id,))

    data = cur.fetchall()
    conn.close()

    if not data:
        await update.message.reply_text("У тебя нет отзывов")
        return

    total = 0

    for text, rating in data:
        total += rating
        await update.message.reply_text(f"⭐ {rating}\n{text}")

    avg = total / len(data)
    await update.message.reply_text(f"Средний рейтинг: {round(avg,2)} ⭐")


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

    elif action == "buy":
        cur.execute("SELECT * FROM purchases WHERE user_id=? AND ad_id=?", (user_id, ad_id))
        if cur.fetchone():
            await query.answer("Уже купил 😄")
            conn.close()
            return

        cur.execute("INSERT INTO purchases VALUES (?,?)", (user_id, ad_id))
        conn.commit()

        # сохраняем состояние для отзыва
        context.user_data["review_ad"] = ad_id

        cur.execute("SELECT user_id FROM ads WHERE id=?", (ad_id,))
        seller = cur.fetchone()[0]

        context.user_data["review_seller"] = seller

        await query.message.reply_text(
            "Оставь отзыв (пример: Отличный товар, 5)"
        )

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

    if text == "⭐ Мои отзывы":
        await my_reviews(update, context)
        return

    # ⭐ отзыв
    if context.user_data.get("review_ad"):
        if "," not in text:
            await update.message.reply_text("Пример: Хороший товар, 5")
            return

        review_text, rating = text.split(",", 1)
        rating = int(rating.strip())

        ad_id = context.user_data["review_ad"]
        seller_id = context.user_data["review_seller"]

        conn = sqlite3.connect("bot.db")
        cur = conn.cursor()

        # проверка повторного отзыва
        cur.execute("""
        SELECT * FROM reviews WHERE user_id=? AND ad_id=?
        """, (user_id, ad_id))

        if cur.fetchone():
            await update.message.reply_text("Ты уже оставил отзыв")
            conn.close()
            context.user_data.clear()
            return

        cur.execute("""
        INSERT INTO reviews (seller_id, user_id, ad_id, text, rating)
        VALUES (?, ?, ?, ?, ?)
        """, (seller_id, user_id, ad_id, review_text.strip(), rating))

        conn.commit()
        conn.close()

        await update.message.reply_text("Спасибо за отзыв ⭐")

        context.user_data.clear()
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
