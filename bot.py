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

# ⚠️ ВАЖНО: правильный ID канала
CHANNEL_ID = -1003685752199

# 🔑 токен из Railway
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
        category TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS favorites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
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
        ["🔍 Поиск", "⭐ Избранное"],
        ["📊 Статистика"]
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
        "SELECT id, text FROM ads WHERE user_id = ?",
        (update.effective_user.id,)
    )

    ads = cursor.fetchall()
    conn.close()

    if not ads:
        await update.message.reply_text("Нет объявлений")
        return

    for ad_id, text in ads:
        keyboard = [[
            InlineKeyboardButton("✏️", callback_data=f"edit_{ad_id}"),
            InlineKeyboardButton("❌", callback_data=f"del_{ad_id}"),
            InlineKeyboardButton("⭐", callback_data=f"fav_{ad_id}")
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

    elif action == "fav":
        cursor.execute(
            "INSERT INTO favorites (user_id, ad_id) VALUES (?, ?)",
            (query.from_user.id, index)
        )
        conn.commit()
        await query.answer("Добавлено ⭐")

    elif action == "edit":
        context.user_data["edit_mode"] = True
        context.user_data["edit_index"] = index
        await query.message.reply_text(
            "Напиши новый текст",
            reply_markup=get_back_keyboard()
        )

    conn.close()


# 💬 сообщения
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "⬅️ Назад":
        context.user_data.clear()
        await update.message.reply_text("Меню", reply_markup=get_main_keyboard())
        return

    # ✏️ редактирование
    if context.user_data.get("edit_mode"):
        index = context.user_data.get("edit_index")

        conn = sqlite3.connect("bot.db")
        cursor = conn.cursor()

        cursor.execute(
            "UPDATE ads SET text = ? WHERE id = ?",
            (text, index)
        )

        conn.commit()
        conn.close()

        await update.message.reply_text("Обновлено", reply_markup=get_main_keyboard())
        context.user_data["edit_mode"] = False
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
            "Напиши товар и цену",
            reply_markup=get_back_keyboard()
        )
        return

    # 📝 создание объявления
    if context.user_data.get("create"):
        parts = text.split()

        if len(parts) >= 2:
            result = f"{parts[0]} — {parts[1]}"
            user_id = update.effective_user.id

            conn = sqlite3.connect("bot.db")
            cursor = conn.cursor()

            cursor.execute(
                "INSERT INTO ads (user_id, text, category) VALUES (?, ?, ?)",
                (user_id, result, context.user_data.get("category"))
            )

            conn.commit()
            conn.close()

            # кнопка написать продавцу
            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    "💬 Написать продавцу",
                    url=f"tg://user?id={user_id}"
                )
            ]])

            # 🚀 отправка в канал
            await context.bot.send_message(
                chat_id=CHANNEL_ID,
                text=result,
                reply_markup=keyboard
            )

            await update.message.reply_text(
                "Объявление опубликовано 🚀",
                reply_markup=get_main_keyboard()
            )

        else:
            await update.message.reply_text(
                "Пример: Nike 200$",
                reply_markup=get_back_keyboard()
            )

        context.user_data["create"] = False
        return

    # 📄 мои объявления
    if text == "📄 Мои":
        await show_ads(update, context)
        return


# 🚀 запуск
init_db()

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT, handle_message))
app.add_handler(CallbackQueryHandler(buttons))

print("Bot started... NEW VERSION")

app.run_polling()