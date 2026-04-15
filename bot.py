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

    cur.execute("""
    CREATE TABLE IF NOT EXISTS subscribers (
        user_id INTEGER
    )
    """)

    conn.commit()
    conn.close()


# 🔹 клавиатуры
def main_kb():
    return ReplyKeyboardMarkup([
        ["Создать", "📄 Мои"],
        ["🔍 Поиск", "⭐ Избранное"],
        ["⭐ Отзывы", "🔔 Подписка"]
    ], resize_keyboard=True)


def back_kb():
    return ReplyKeyboardMarkup([["⬅️ Назад"]], resize_keyboard=True)


# 🚀 старт
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Меню", reply_markup=main_kb())


# 🔔 подписка
async def subscribe(update, context):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()

    user_id = update.effective_user.id

    cur.execute("SELECT * FROM subscribers WHERE user_id=?", (user_id,))
    if cur.fetchone():
        await update.message.reply_text("Ты уже подписан 🔔")
    else:
        cur.execute("INSERT INTO subscribers VALUES (?)", (user_id,))
        conn.commit()
        await update.message.reply_text("Подписка включена 🔔")

    conn.close()


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

    total = 0
    for text, rating in data:
        total += rating
        await update.message.reply_text(f"{text} ⭐{rating}")

    await update.message.reply_text(f"Средний рейтинг: {round(total/len(data),2)} ⭐")


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

        # автоуведомление продавцу
        cur.execute("SELECT user_id FROM ads WHERE id=?", (ad_id,))
        seller = cur.fetchone()[0]

        await context.bot.send_message(
            seller,
            "📩 У тебя новый покупатель! Напиши ему первым"
        )

        context.user_data["review_ad"] = ad_id
        context.user_data["review_seller"] = seller

        await query.message.reply_text("Напиши отзыв: текст, оценка (например: круто, 5)")

    conn.close()


# 📸 фото
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("create"):
        return

    context.user_data["photo"] = update.message.photo[-1].file_id
    await update.message.reply_text("Теперь напиши: название, цена (через запятую)")


# 💬 сообщения
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id

    if text == "⬅️ Назад":
        context.user_data.clear()
        await update.message.reply_text("Меню", reply_markup=main_kb())
        return

    if text == "🔔 Подписка":
        await subscribe(update, context)
        return

    if text == "📄 Мои":
        await my_ads(update, context)
        return

    if text == "⭐ Отзывы":
        await my_reviews(update, context)
        return

    # ⭐ отзыв
    if context.user_data.get("review_ad"):
        if "," not in text:
            await update.message.reply_text("Пример: отлично, 5")
            return

        t, r = text.split(",", 1)

        conn = sqlite3.connect("bot.db")
        cur = conn.cursor()

        cur.execute("INSERT INTO reviews VALUES (NULL,?,?,?,?,?)",
                    (context.user_data["review_seller"], user_id,
                     context.user_data["review_ad"], t.strip(), int(r.strip())))

        conn.commit()
        conn.close()

        await update.message.reply_text("Отзыв сохранен ⭐")
        context.user_data.clear()
        return

    # 🆕 создание
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

        # 🔔 уведомления
        cur.execute("SELECT user_id FROM subscribers")
        subs = cur.fetchall()

        for (uid,) in subs:
            if uid != user_id:
                try:
                    await context.bot.send_message(uid, f"🔥 Новое объявление:\n{result}")
                except:
                    pass

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

print("БОТ ЗАПУСТИЛСЯ 🚀")

app.run_polling()
