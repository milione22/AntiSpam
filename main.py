import os
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
    ChatJoinRequestHandler,
)

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("BOT_TOKEN не задан")

ADMIN_IDS = {7996717371, 8561438704}

FRUITS = {
    "Ябл0ко": "🍎",
    "БAHAH": "🍌",
    "ГPуWа": "🍐",
    "Апе/льсин": "🍊",
    "BиHоград": "🍇",
    "Apбуз": "🍉",
}

pending_captcha = {}
admin_notifications = {}

# ================== UI ==================

def admin_keyboard(admin_id):
    state = admin_notifications.get(admin_id, True)
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(
            f"🔔 Уведомления: {'ВКЛ' if state else 'ВЫКЛ'}",
            callback_data="toggle_notify"
        )
    ]])

# ================== АДМИН ПАНЕЛЬ ==================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id in ADMIN_IDS:
        await update.message.reply_text(
            "🔧 Панель администратора",
            reply_markup=admin_keyboard(user_id)
        )
    else:
        await update.message.reply_text("Привет.")

async def toggle_notify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    admin_id = query.from_user.id
    if admin_id not in ADMIN_IDS:
        return

    admin_notifications[admin_id] = not admin_notifications.get(admin_id, True)

    await query.edit_message_text(
        "🔧 Панель администратора",
        reply_markup=admin_keyboard(admin_id)
    )

# ================== JOIN REQUEST ==================

async def handle_join_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    req = update.chat_join_request
    user = req.from_user

    fruit = random.choice(list(FRUITS.keys()))

    keyboard = [
        [InlineKeyboardButton(emoji, callback_data=f"captcha:{name}")]
        for name, emoji in FRUITS.items()
    ]

    pending_captcha[user.id] = {
        "chat_id": req.chat.id,
        "fruit": fruit
    }

    try:
        await context.bot.send_message(
            user.id,
            f"🛡 Проверка: нажми на эмоджи фрукта {fruit}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except:
        await req.decline()

# ================== CAPTCHA ==================

async def captcha_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    user_id = user.id

    if user_id not in pending_captcha:
        return

    data = pending_captcha[user_id]
    correct = data["fruit"]
    chat_id = data["chat_id"]

    chosen = query.data.split(":")[1]

    if chosen == correct:
        await query.edit_message_text("✅ Капча пройдена. Ожидайте решения администраторов.")

        username = f"@{user.username}" if user.username else "без username"

        text = (
            f"🟢 ПРОЙДЕНА КАПЧА\n"
            f"Имя: {user.full_name}\n"
            f"Username: {username}\n"
            f"ID: {user.id}"
        )

        for admin in ADMIN_IDS:
            if admin_notifications.get(admin, True):
                try:
                    await context.bot.send_message(admin, text)
                except:
                    pass
    else:
        await query.edit_message_text("❌ Капча неверная. Заявка отклонена.")

        try:
            await context.bot.decline_chat_join_request(chat_id, user_id)
        except:
            pass

    del pending_captcha[user_id]

# ================== RUN ==================

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(toggle_notify, pattern=r"^toggle_notify$"))
    app.add_handler(CallbackQueryHandler(captcha_answer, pattern=r"^captcha:"))
    app.add_handler(ChatJoinRequestHandler(handle_join_request))

    print("Bot started")
    app.run_polling()

if __name__ == "__main__":
    main()
