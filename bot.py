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

TOKEN = os.getenv("BOT_TOKEN")

# 🔥 список каналов
CHANNEL_IDS = [
    -1003685752199, -1002837639684 ]
    # добавь сюда другие каналы
]

ADMIN_ID = 6116012945

BAD_WORDS = ["казино", "ставки", "секс", "18+", "http", "https", "t.me"]


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
        likes INTEGER DEFAULT 0,
        views INTEGER DEFAULT 0
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

    conn.commit()
    conn.close()


# 🤖 фильтр
def ai_filter(text):
    text = text.lower()

    if len(text) < 5:
        return False

    if any(word in text for word in BAD_WORDS):
        return False

    if text.count("$") > 3:
        return False

    return True


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
    await update.message.reply_text("🚀 Маркетплейс бот", reply_markup=main_kb())


# 📄 мои объявления
async def my_ads(update, context):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()

    cur.execute("SELECT text, likes, views FROM ads WHERE user_id=?", (update.effective_user.id,))
    ads = cur.fetchall()
    conn.close()

    if not ads:
        await update.message.reply_text("Нет объявлений")
        return

    for text, likes, views in ads:
        await update.message.reply_text(f"{text}\n❤️ {likes} 👁 {views}")


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
async def top_ads(update, context):
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
            return

        cur.execute("INSERT INTO likes VALUES (?,?)", (user_id, ad_id))
        cur.execute("UPDATE ads SET likes=likes+1 WHERE id=?", (ad_id,))
        conn.commit()

    elif action == "fav":
        cur.execute("INSERT INTO favorites VALUES (?,?)", (user_id, ad_id))
        conn.commit()
        await query.answer("Добавлено ⭐")

    elif action == "contact":
        cur.execute("SELECT user_id FROM ads WHERE id=?", (ad_id,))
        seller = cur.fetchone()[0]

        await context.bot.send_message(
            seller,
            f"💬 Тебе написал покупатель: @{query.from_user.username}"
        )

    conn.close()


# 📸 фото
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("create"):
        return

    context.user_data["photo"] = update.message.photo[-1].file_id
    await update.message.reply_text("Теперь напиши: описание, цена")


# 🚀 отправка во все каналы
async def send_to_channels(context, photo, text, keyboard):
    for channel in CHANNEL_IDS:
        try:
            if photo:
                await context.bot.send_photo(channel, photo, caption=text, reply_markup=keyboard)
            else:
                await context.bot.send_message(channel, text, reply_markup=keyboard)
        except Exception as e:
            print(f"Ошибка отправки в канал {channel}: {e}")


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
        await top_ads(update, context)
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
                [InlineKeyboardButton("⭐", callback_data=f"fav_{ad_id}")],
                [InlineKeyboardButton("💬 Написать", callback_data=f"contact_{ad_id}")]
            ])

            await update.message.reply_text(t, reply_markup=keyboard)

        context.user_data["search"] = False
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

    # 🧠 создание
    if context.user_data.get("create"):

        if not ai_filter(text):
            await update.message.reply_text("❌ Отклонено")
            return

        if "," not in text:
            await update.message.reply_text("Пример: iPhone 13, 500$")
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
            [InlineKeyboardButton("❤️", callback_data=f"like_{ad_id}")],
            [InlineKeyboardButton("⭐", callback_data=f"fav_{ad_id}")],
            [InlineKeyboardButton("💬 Написать", callback_data=f"contact_{ad_id}")]
        ])

        # 🔥 отправка во все каналы
        await send_to_channels(context, context.user_data.get("photo"), result, keyboard)

        await update.message.reply_text("Опубликовано во все каналы 🚀", reply_markup=main_kb())
        context.user_data.clear()


# 🚀 запуск
init_db()

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
app.add_handler(CallbackQueryHandler(buttons))

print("🚀 MULTI CHANNEL BOT RUNNING")

app.run_polling()
