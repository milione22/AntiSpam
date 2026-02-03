import os
import random
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ChatPermissions,
)
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
isolation_mode = False

# ================= UI =================

def admin_keyboard(admin_id):
    notify = admin_notifications.get(admin_id, True)
    iso = "ВКЛ" if isolation_mode else "ВЫКЛ"

    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🔔 Уведомления: {'ВКЛ' if notify else 'ВЫКЛ'}", callback_data="toggle_notify")],
        [InlineKeyboardButton(f"🚨 Изоляция: {iso}", callback_data="toggle_isolation")]
    ])

# ================= АДМИН ПАНЕЛЬ =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id in ADMIN_IDS:
        await update.message.reply_text("🔧 Панель администратора", reply_markup=admin_keyboard(update.effective_user.id))
    else:
        await update.message.reply_text("Привет.")

async def toggle_notify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    admin_id = query.from_user.id

    admin_notifications[admin_id] = not admin_notifications.get(admin_id, True)
    await query.edit_message_text("🔧 Панель администратора", reply_markup=admin_keyboard(admin_id))

# ================= ИЗОЛЯЦИЯ =================

async def toggle_isolation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global isolation_mode
    query = update.callback_query
    await query.answer()

    isolation_mode = not isolation_mode

    perms = ChatPermissions(
        can_send_messages=not isolation_mode,
        can_send_audios=False,
        can_send_documents=False,
        can_send_photos=False,
        can_send_videos=False,
        can_send_video_notes=False,
        can_send_voice_notes=False,
        can_send_polls=False,
        can_send_other_messages=False,
        can_add_web_page_previews=False
    )

    for chat_id in known_chats:
        try:
            await context.bot.set_chat_permissions(chat_id, perms)
        except Exception as e:
            print("Permissions error:", e)

    await query.edit_message_text(
        "🔧 Панель администратора",
        reply_markup=admin_keyboard(query.from_user.id)
    )

# ================= JOIN REQUEST =================

async def handle_join_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    req = update.chat_join_request
    user = req.from_user

    if isolation_mode:
        await req.decline()
        return

    fruit = random.choice(list(FRUITS.keys()))

    # 2 колонки
    items = list(FRUITS.items())
    keyboard = []
    for i in range(0, len(items), 2):
        row = []
        for name, emoji in items[i:i+2]:
            row.append(InlineKeyboardButton(emoji, callback_data=f"captcha:{name}"))
        keyboard.append(row)

    pending_captcha[user.id] = {"chat_id": req.chat.id, "fruit": fruit}

    try:
        await context.bot.send_message(user.id, f"🛡 Проверка: нажми на эмоджи фрукта {fruit}", reply_markup=InlineKeyboardMarkup(keyboard))
    except:
        await req.decline()

# ================= CAPTCHA =================

async def captcha_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    user_id = user.id

    if user_id not in pending_captcha:
        return

    data = pending_captcha[user_id]
    chosen = query.data.split(":")[1]

    if chosen == data["fruit"]:
        await query.edit_message_text("✅ Капча пройдена. Ожидайте решения администраторов.")

        username = f"@{user.username}" if user.username else "без username"
        text = f"🟢 ПРОЙДЕНА КАПЧА\nИмя: {user.full_name}\nUsername: {username}\nID: {user.id}"

        for admin in ADMIN_IDS:
            if admin_notifications.get(admin, True):
                try:
                    await context.bot.send_message(admin, text)
                except:
                    pass
    else:
        await query.edit_message_text("❌ Капча неверная. Заявка отклонена.")
        try:
            await context.bot.decline_chat_join_request(data["chat_id"], user_id)
        except:
            pass

    del pending_captcha[user_id]

# ================= RUN =================

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(toggle_notify, pattern="^toggle_notify$"))
    app.add_handler(CallbackQueryHandler(toggle_isolation, pattern="^toggle_isolation$"))
    app.add_handler(CallbackQueryHandler(captcha_answer, pattern="^captcha:"))
    app.add_handler(ChatJoinRequestHandler(handle_join_request))

    print("Bot started")
    app.run_polling()

if __name__ == "__main__":
    main()

