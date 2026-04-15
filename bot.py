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
    CREATE TABLE IF NOT EXISTS purchases (
        user_id INTEGER,
        ad_id INTEGER
    )
    """)

    conn.commit()
    conn.close()


# 🔹 клавиатуры
def get_main_keyboard():
    return ReplyKeyboardMarkup([
        ["Создать", "📄 Мои"],
        ["🔍 Поиск"]
    ], resize_keyboard=True)


def get_back_keyboard():
    return ReplyKeyboardMarkup([["⬅️ Назад"]], resize_keyboard=True)


# 🚀 старт
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Меню", reply_markup=get_main_keyboard())


# 📄 мои объявления
async def show_ads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect("bot.db")
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id, text, likes, views FROM ads WHERE user_id = ?",
        (update.effective_user.id,)
    )

    ads = cursor.fetchall()
    conn.close()

    if not ads:
        await update.message.reply_text("Нет объявлений")
        return

    for ad_id, text, likes, views in ads:
        await update.message.reply_text(
            f"{text}\n❤️ {likes} | 👁 {views}"
        )


# 🔘 кнопки
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    action, index = query.data.split("_")
    index = int(index)

    conn = sqlite3.connect("bot.db")
    cursor = conn.cursor()

    # ❤️ лайк (1 раз)
    if action == "like":
        user_id = query.from_user.id

        cursor.execute(
            "SELECT * FROM likes WHERE user_id = ? AND ad_id = ?",
            (user_id, index)
        )

        if cursor.fetchone():
            await query.answer("Ты уже лайкнул 😎", show_alert=True)
            conn.close()
            return

        cursor.execute(
            "INSERT INTO likes (user_id, ad_id) VALUES (?, ?)",
            (user_id, index)
        )

        cursor.execute(
            "UPDATE ads SET likes = likes + 1 WHERE id = ?",
            (index,)
        )

        conn.commit()

        cursor.execute("SELECT likes FROM ads WHERE id = ?", (index,))
        likes = cursor.fetchone()[0]

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("💬 Написать", url=f"tg://user?id={query.message.chat_id}"),
                InlineKeyboardButton("🛒 Купить", callback_data=f"buy_{index}")
            ],
            [
                InlineKeyboardButton(f"❤️ {likes}", callback_data=f"like_{index}")
            ]
        ])

        await query.edit_message_reply_markup(reply_markup=keyboard)

    # 🛒 покупка (антиспам)
    elif action == "buy":
        user_id = query.from_user.id

        cursor.execute(
            "SELECT * FROM purchases WHERE user_id = ? AND ad_id = ?",
            (user_id, index)
        )

        if cursor.fetchone():
            await query.answer("Ты уже нажимал купить 😄", show_alert=True)
            conn.close()
            return

        cursor.execute(
            "INSERT INTO purchases (user_id, ad_id) VALUES (?, ?)",
            (user_id, index)
        )

        conn.commit()

        await query.message.reply_text("🛒 Напиши продавцу для покупки")

    conn.close()


# 📸 фото
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("create"):
        return

    context.user_data["photo"] = update.message.photo[-1].file_id

    await update.message.reply_text(
        "Теперь напиши название и цену (пример: Nike 200$)"
    )


# 💬 сообщения
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "⬅️ Назад":
        context.user_data.clear()
        await update.message.reply_text("Меню", reply_markup=get_main_keyboard())
        return

    # 🆕 создать
    if text == "Создать":
        keyboard = [
            ["👕 Одежда", "📱 Техника"],
            ["🚗 Авто"],
            ["⬅️ Назад"]
        ]
        await update.message.reply_text(
            "Выбери категорию",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return

    # 📂 категория
    if text in ["👕 Одежда", "📱 Техника", "🚗 Авто"]:
        context.user_data["category"] = text
        context.user_data["create"] = True

        await update.message.reply_text(
            "Отправь фото товара 📸",
            reply_markup=get_back_keyboard()
        )
        return

    # 📄 мои
    if text == "📄 Мои":
        await show_ads(update, context)
        return

    # 🔎 поиск
    if text == "🔍 Поиск":
        context.user_data["search"] = True
        await update.message.reply_text("Напиши что искать")
        return

    # 🔎 логика поиска
    if context.user_data.get("search"):
        conn = sqlite3.connect("bot.db")
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id, text, photo, likes FROM ads WHERE text LIKE ?",
            (f"%{text}%",)
        )

        results = cursor.fetchall()
        conn.close()

        if not results:
            await update.message.reply_text("Ничего не найдено")
            return

        for ad_id, t, photo, likes in results:

            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("💬 Написать", url=f"tg://user?id={update.effective_user.id}"),
                    InlineKeyboardButton("🛒 Купить", callback_data=f"buy_{ad_id}")
                ],
                [
                    InlineKeyboardButton(f"❤️ {likes}", callback_data=f"like_{ad_id}")
                ]
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
        category = context.user_data.get("category")

        conn = sqlite3.connect("bot.db")
        cursor = conn.cursor()

        cursor.execute(
            "INSERT INTO ads (user_id, text, category, photo) VALUES (?, ?, ?, ?)",
            (user_id, result, category, photo)
        )

        ad_id = cursor.lastrowid

        conn.commit()
        conn.close()

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("💬 Написать", url=f"tg://user?id={user_id}"),
                InlineKeyboardButton("🛒 Купить", callback_data=f"buy_{ad_id}")
            ],
            [
                InlineKeyboardButton("❤️ 0", callback_data=f"like_{ad_id}")
            ]
        ])

        # 🚀 канал
        if photo:
            await context.bot.send_photo(CHANNEL_ID, photo, caption=result, reply_markup=keyboard)
        else:
            await context.bot.send_message(CHANNEL_ID, result, reply_markup=keyboard)

        await update.message.reply_text("Опубликовано 🚀", reply_markup=get_main_keyboard())

        context.user_data.clear()


# 🚀 запуск
init_db()

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
app.add_handler(CallbackQueryHandler(buttons))

print("Bot FULL READY 🚀")

app.run_polling()
