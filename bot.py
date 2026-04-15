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

# 🔐 ТВОЙ TELEGRAM ID (узнай через @userinfobot)
ADMIN_ID = 6116012945


# ❌ базовый фильтр
BAD_WORDS = ["казино", "ставки", "секс", "18+", "http", "https", "t.me"]


# 🤖 AI фильтр (простая логика)
def ai_filter(text):
    text = text.lower()

    # подозрительные паттерны
    if text.count("$") > 2:
        return False

    if len(text) < 5:
        return False

    if any(word in text for word in BAD_WORDS):
        return False

    return True


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
        photo TEXT
    )
    """)

    conn.commit()
    conn.close()


# 🔹 клавиатуры
def main_kb():
    return ReplyKeyboardMarkup([
        ["Создать", "📄 Мои"],
        ["🔍 Поиск"]
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

    cur.execute("SELECT id, text FROM ads WHERE user_id=?", (update.effective_user.id,))
    ads = cur.fetchall()
    conn.close()

    if not ads:
        await update.message.reply_text("Нет объявлений")
        return

    for ad_id, text in ads:
        await update.message.reply_text(f"{ad_id}: {text}")


# 🔎 поиск
async def search_ads(update, context, text):
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()

    cur.execute("SELECT id, text FROM ads WHERE text LIKE ?", (f"%{text}%",))
    data = cur.fetchall()
    conn.close()

    if not data:
        await update.message.reply_text("Ничего не найдено")
        return

    for ad_id, t in data:
        await update.message.reply_text(f"{ad_id}: {t}")


# 👑 АДМИН ПАНЕЛЬ
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    await update.message.reply_text(
        "👑 Админ панель:\n"
        "/all_ads - все объявления\n"
        "/delete ID - удалить объявление"
    )


async def all_ads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()

    cur.execute("SELECT id, text FROM ads")
    ads = cur.fetchall()
    conn.close()

    for ad_id, text in ads:
        await update.message.reply_text(f"{ad_id}: {text}")


async def delete_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    try:
        ad_id = int(context.args[0])
    except:
        await update.message.reply_text("Используй: /delete ID")
        return

    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()

    cur.execute("DELETE FROM ads WHERE id=?", (ad_id,))
    conn.commit()
    conn.close()

    await update.message.reply_text("Удалено ✅")


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

    if text == "📄 Мои":
        await my_ads(update, context)
        return

    if text == "🔍 Поиск":
        context.user_data["search"] = True
        await update.message.reply_text("Что ищем?")
        return

    if context.user_data.get("search"):
        await search_ads(update, context, text)
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

    # 🧠 СОЗДАНИЕ + AI МОДЕРАЦИЯ
    if context.user_data.get("create"):

        if not ai_filter(text):
            await update.message.reply_text("❌ Объявление отклонено AI фильтром")
            
            # уведомление админу
            await context.bot.send_message(
                ADMIN_ID,
                f"🚫 Заблокировано:\n{text}"
            )

            context.user_data.clear()
            return

        if "," not in text:
            await update.message.reply_text("Пример: Nike Air, 200$")
            return

        name, price = text.split(",", 1)
        result = f"{name.strip()} — {price.strip()}"

        conn = sqlite3.connect("bot.db")
        cur = conn.cursor()

        cur.execute(
            "INSERT INTO ads (user_id, text, category, photo) VALUES (?,?,?,?)",
            (user_id, result, context.user_data["category"], context.user_data.get("photo"))
        )

        conn.commit()
        conn.close()

        # уведомление админу
        await context.bot.send_message(
            ADMIN_ID,
            f"🆕 Новое объявление:\n{result}"
        )

        if context.user_data.get("photo"):
            await context.bot.send_photo(CHANNEL_ID, context.user_data["photo"], caption=result)
        else:
            await context.bot.send_message(CHANNEL_ID, result)

        await update.message.reply_text("Опубликовано 🚀", reply_markup=main_kb())
        context.user_data.clear()


# 🚀 запуск
init_db()

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("admin", admin))
app.add_handler(CommandHandler("all_ads", all_ads))
app.add_handler(CommandHandler("delete", delete_ad))

app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

print("🔥 BOT FINAL VERSION RUNNING")

app.run_polling()
