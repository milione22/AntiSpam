import random
import os
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
    ChatJoinRequestHandler
)

TOKEN = os.getenv("BOT_TOKEN")

# 🔐 ID администраторов бота
ADMIN_IDS = {7996717371, 8561438704}

# 🧠 Хранилища
pending_captcha = {}      # user_id -> {chat_id, fruit}
admin_notifications = {}  # admin_id -> True/False

# 🍎 База фруктов (название -> эмоджи)
FRUITS = {
    "Ябл0ко": "🍎",
    "БAHAH": "🍌",
    "ГPуWа": "🍐",
    "Апе/\ьсин": "🍊",
    "BиHоград": "🍇",
    "Apбуз": "🍉",
}


# ================== АДМИН ПАНЕЛЬ ==================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id in ADMIN_IDS:
        state = admin_notifications.get(user_id, True)
        text = "🔧 Панель администратора"

        keyboard = [[
            InlineKeyboardButton(
                f"🔔 Уведомления: {'ВКЛ' if state else 'ВЫКЛ'}",
                callback_data="toggle_notify"
            )
        ]]

        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.message.reply_text("Привет.")


async def toggle_notify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    admin_id = query.from_user.id
    if admin_id not in ADMIN_IDS:
        return

    current = admin_notifications.get(admin_id, True)
    admin_notifications[admin_id] = not current

    state = admin_notifications[admin_id]

    keyboard = [[
        InlineKeyboardButton(
            f"🔔 Уведомления: {'ВКЛ' if state else 'ВЫКЛ'}",
            callback_data="toggle_notify"
        )
    ]]

    await query.edit_message_reply_markup(
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ================== ЗАЯВКА В ЧАТ ==================

async def handle_join_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    req = update.chat_join_request
    user = req.from_user
    chat_id = req.chat.id

    fruit, emoji = random.choice(list(FRUITS.items()))

    # Генерация кнопок
    buttons = list(FRUITS.values())
    random.shuffle(buttons)

    keyboard = [
        [InlineKeyboardButton(e, callback_data=f"captcha_{e}")]
        for e in buttons[:4]
    ]

    # Сохраняем капчу
    pending_captcha[user.id] = {
        "chat_id": chat_id,
        "fruit": fruit,
        "emoji": emoji
    }

    try:
        await context.bot.send_message(
            user.id,
            f"🛡 Проверка: нажми на эмоджи фрукта **{fruit}**",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except:
        # Если бот не может написать в ЛС — отклоняем
        await req.decline()


# ================== ПРОВЕРКА КАПЧИ ==================

async def captcha_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    if user_id not in pending_captcha:
        return

    data = pending_captcha[user_id]
    correct_emoji = data["emoji"]
    chat_id = data["chat_id"]

    chosen = query.data.replace("captcha_", "")

    if chosen == correct_emoji:
        # ✅ ПРОЙДЕНО
        await query.edit_message_text("✅ Капча пройдена. Ожидайте решения администраторов.")

        # Уведомления админам
        for admin in ADMIN_IDS:
            if admin_notifications.get(admin, True):
                try:
                    await context.bot.send_message(
                        admin,
                        f"🟢 Пользователь {query.from_user.full_name} прошел капчу."
                    )
                except:
                    pass

    else:
        # ❌ НЕ ПРОЙДЕНО
        await context.bot.send_message(user_id, "❌ Капча не пройдена. Заявка отклонена.")

        await context.bot.decline_chat_join_request(chat_id, user_id)

    del pending_captcha[user_id]


# ================== ЗАПУСК ==================

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(toggle_notify, pattern="toggle_notify"))
    app.add_handler(CallbackQueryHandler(captcha_answer, pattern="captcha_"))
    app.add_handler(ChatJoinRequestHandler(handle_join_request))

    print("Bot started...")
    app.run_polling()


if __name__ == "__main__":
    main()

