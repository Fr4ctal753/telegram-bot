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
        photo TEXT,
        likes INTEGER DEFAULT 0
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
        "SELECT id, text, likes FROM ads WHERE user_id = ?",
        (update.effective_user.id,)
    )

    ads = cursor.fetchall()
    conn.close()

    if not ads:
        await update.message.reply_text("Нет объявлений")
        return

    for ad_id, text, likes in ads:
        keyboard = [[
            InlineKeyboardButton(f"❤️ {likes}", callback_data=f"like_{ad_id}"),
            InlineKeyboardButton("❌", callback_data=f"del_{ad_id}")
        ]]

        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


# 🔘 кнопки
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    action, index = query.data.split("_")
    index = int(index)

    conn = sqlite3.connect("bot.db")
    cursor = conn.cursor()

    if action == "del":
        cursor.execute("DELETE FROM ads WHERE id = ?", (index,))
        conn.commit()
        await query.edit_message_text("Удалено")

    elif action == "like":
        cursor.execute("UPDATE ads SET likes = likes + 1 WHERE id = ?", (index,))
        conn.commit()

        cursor.execute("SELECT likes FROM ads WHERE id = ?", (index,))
        likes = cursor.fetchone()[0]

        keyboard = InlineKeyboardMarkup([[ 
            InlineKeyboardButton(f"❤️ {likes}", callback_data=f"like_{index}")
        ]])

        await query.edit_message_reply_markup(reply_markup=keyboard)

    conn.close()


# 📸 фото
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("create"):
        return

    photo_file = update.message.photo[-1].file_id
    context.user_data["photo"] = photo_file

    await update.message.reply_text("Теперь напиши название и цену (пример: Nike 200$)")


# 💬 сообщения (главная логика)
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "⬅️ Назад":
        context.user_data.clear()
        await update.message.reply_text("Меню", reply_markup=get_main_keyboard())
        return

    # 🆕 создать
    if text == "Создать":
        context.user_data["create"] = True
        await update.message.reply_text("Отправь фото товара 📸", reply_markup=get_back_keyboard())
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

        cursor.execute("SELECT text, photo FROM ads WHERE text LIKE ?", (f"%{text}%",))
        results = cursor.fetchall()
        conn.close()

        if not results:
            await update.message.reply_text("Ничего не найдено")
            return

        for t, photo in results:
            if photo:
                await update.message.reply_photo(photo, caption=t)
            else:
                await update.message.reply_text(t)

        context.user_data["search"] = False
        return

    # 📝 создание (ПОСЛЕ ФОТО)
    if context.user_data.get("create"):
        parts = text.split()

        if len(parts) < 2:
            await update.message.reply_text("Пример: Nike 200$")
            return

        result = f"{parts[0]} — {parts[1]}"
        user_id = update.effective_user.id
        photo = context.user_data.get("photo")

        conn = sqlite3.connect("bot.db")
        cursor = conn.cursor()

        cursor.execute(
            "INSERT INTO ads (user_id, text, photo) VALUES (?, ?, ?)",
            (user_id, result, photo)
        )

        ad_id = cursor.lastrowid

        conn.commit()
        conn.close()

        keyboard = InlineKeyboardMarkup([[ 
            InlineKeyboardButton("💬 Написать", url=f"tg://user?id={user_id}"),
            InlineKeyboardButton("❤️ 0", callback_data=f"like_{ad_id}")
        ]])

        # 🚀 в канал
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

print("Bot started v2 🚀")

app.run_polling()
