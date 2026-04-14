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

TOKEN = "8779699748:AAFOLAf6y5t-McKiZRU3v22h5PQZbCcJ0Ls"


# 🔹 Главное меню
def get_main_keyboard():
    return ReplyKeyboardMarkup([
        ["Создать", "📄 Мои"],
        ["🔍 Поиск", "⭐ Избранное"],
        ["📊 Статистика"]
    ], resize_keyboard=True)


# 🚀 Старт
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Меню", reply_markup=get_main_keyboard())


# 📄 Показ объявлений
async def show_ads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        with open("ads.txt", "r", encoding="utf-8") as f:
            lines = f.readlines()

        if not lines:
            await update.message.reply_text("Нет объявлений")
            return

        for i, line in enumerate(lines):
            keyboard = [[
                InlineKeyboardButton("✏️", callback_data=f"edit_{i}"),
                InlineKeyboardButton("❌", callback_data=f"del_{i}"),
                InlineKeyboardButton("⭐", callback_data=f"fav_{i}")
            ]]

            await update.message.reply_text(
                line,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

    except:
        await update.message.reply_text("Ошибка")


# 🔘 INLINE КНОПКИ
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    action, index = query.data.split("_")
    index = int(index)

    with open("ads.txt", "r", encoding="utf-8") as f:
        lines = f.readlines()

    # ❌ удалить
    if action == "del":
        if 0 <= index < len(lines):
            deleted = lines.pop(index)

            with open("ads.txt", "w", encoding="utf-8") as f:
                f.writelines(lines)

            await query.edit_message_text(f"Удалено: {deleted}")

    # ⭐ избранное
    elif action == "fav":
        if 0 <= index < len(lines):
            with open("fav.txt", "a", encoding="utf-8") as f:
                f.write(lines[index])

            await query.answer("Добавлено ⭐")

    # ✏️ редактирование
    elif action == "edit":
        context.user_data["edit_mode"] = True
        context.user_data["edit_index"] = index
        await query.message.reply_text("Напиши новый текст")


# 💬 ТЕКСТ
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    # ✏️ режим редактирования
    if context.user_data.get("edit_mode"):
        index = context.user_data.get("edit_index")

        with open("ads.txt", "r", encoding="utf-8") as f:
            lines = f.readlines()

        if 0 <= index < len(lines):
            lines[index] = text + "\n"

            with open("ads.txt", "w", encoding="utf-8") as f:
                f.writelines(lines)

            await update.message.reply_text("Обновлено")

        context.user_data["edit_mode"] = False
        return

    # 🔹 создание
    if text == "Создать":
        context.user_data["create"] = True
        await update.message.reply_text("Напиши объявление")
        return

    if context.user_data.get("create"):
        with open("ads.txt", "a", encoding="utf-8") as f:
            f.write(text + "\n")

        await update.message.reply_text("Добавлено")
        context.user_data["create"] = False
        return

    # 📄 мои объявления
    if text == "📄 Мои":
        await show_ads(update, context)
        return

    # 🔍 поиск
    if text == "🔍 Поиск":
        context.user_data["search"] = True
        await update.message.reply_text("Напиши слово для поиска")
        return

    if context.user_data.get("search"):
        keyword = text.lower()

        with open("ads.txt", "r", encoding="utf-8") as f:
            lines = f.readlines()

        results = [l for l in lines if keyword in l.lower()]

        if results:
            await update.message.reply_text("Найдено:\n" + "".join(results))
        else:
            await update.message.reply_text("Ничего не найдено")

        context.user_data["search"] = False
        return

    # ⭐ избранное
    if text == "⭐ Избранное":
        try:
            with open("fav.txt", "r", encoding="utf-8") as f:
                await update.message.reply_text("⭐ Избранное:\n" + f.read())
        except:
            await update.message.reply_text("Пусто")
        return

    # 📊 статистика
    if text == "📊 Статистика":
        try:
            with open("ads.txt", "r", encoding="utf-8") as f:
                ads = len(f.readlines())
        except:
            ads = 0

        try:
            with open("fav.txt", "r", encoding="utf-8") as f:
                fav = len(f.readlines())
        except:
            fav = 0

        await update.message.reply_text(
            f"📊 Всего объявлений: {ads}\n⭐ В избранном: {fav}"
        )
        return


# 🚀 запуск
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT, handle_message))
app.add_handler(CallbackQueryHandler(buttons))

app.run_polling()