import os
import random
import re
from datetime import datetime, timedelta
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
    MessageHandler,
    filters
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
ISOLATION_MODE = False  # Глобальный режим изоляции
known_chats = set()  # сюда добавляем ID чатов, где бот админ

# ================= UI =================

def admin_keyboard(admin_id):
    notify = admin_notifications.get(admin_id, True)
    iso = "ВКЛ" if ISOLATION_MODE else "ВЫКЛ"
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
    global ISOLATION_MODE
    query = update.callback_query
    await query.answer()

    ISOLATION_MODE = not ISOLATION_MODE

    perms = ChatPermissions(
        can_send_messages=not ISOLATION_MODE,
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

    if ISOLATION_MODE:
        # при изоляции заявки можно отклонять автоматически или оставлять для проверки админам
        await req.decline()
        return

    fruit = random.choice(list(FRUITS.keys()))

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

# ================= BAN =================

async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ У вас нет прав для этой команды.")
        return

    target_user = None
    if update.message.reply_to_message:
        target_user = update.message.reply_to_message.from_user
    elif context.args:
        arg = context.args[0]
        if arg.startswith("@"):
            username = arg[1:]
            try:
                chat = await context.bot.get_chat(update.effective_chat.id)
                async for member in chat.get_members():
                    if member.user.username == username:
                        target_user = member.user
                        break
            except:
                pass
        else:
            try:
                user_id = int(arg)
                member = await context.bot.get_chat_member(update.effective_chat.id, user_id)
                target_user = member.user
            except:
                pass

    if not target_user:
        await update.message.reply_text("❌ Не удалось найти пользователя.")
        return

    try:
        await context.bot.ban_chat_member(update.effective_chat.id, target_user.id)
        await update.message.reply_text(f"✅ Пользователь {target_user.full_name} заблокирован.")
    except Exception as e:
        await update.message.reply_text(f"❌ Не удалось заблокировать пользователя: {e}")

# ================= MUTE =================

async def mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ У вас нет прав для этой команды.")
        return

    if not context.args:
        await update.message.reply_text("❌ Укажите срок мутa и пользователя.")
        return

    time_arg = context.args[0]
    match = re.fullmatch(r"(\d+)([dh])", time_arg)
    if not match:
        await update.message.reply_text("❌ Неверный формат времени. Пример: 5d или 2h")
        return

    amount, unit = match.groups()
    amount = int(amount)
    delta = timedelta(days=amount) if unit == "d" else timedelta(hours=amount)
    until_date = datetime.utcnow() + delta

    target_user = None
    if update.message.reply_to_message:
        target_user = update.message.reply_to_message.from_user
    elif len(context.args) > 1:
        arg = context.args[1]
        if arg.startswith("@"):
            username = arg[1:]
            try:
                chat = await context.bot.get_chat(update.effective_chat.id)
                async for member in chat.get_members():
                    if member.user.username == username:
                        target_user = member.user
                        break
            except:
                pass
        else:
            try:
                user_id = int(arg)
                member = await context.bot.get_chat_member(update.effective_chat.id, user_id)
                target_user = member.user
            except:
                pass

    if not target_user:
        await update.message.reply_text("❌ Не удалось найти пользователя.")
        return

    perms = ChatPermissions(
        can_send_messages=False,
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

    try:
        await context.bot.restrict_chat_member(
            update.effective_chat.id,
            target_user.id,
            permissions=perms,
            until_date=until_date
        )
        await update.message.reply_text(f"✅ Пользователь {target_user.full_name} замучен до {until_date} UTC.")
    except Exception as e:
        await update.message.reply_text(f"❌ Не удалось замутить пользователя: {e}")

# ================= RUN =================
async def mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ У вас нет прав для этой команды.")
        return

    if not context.args and not update.message.reply_to_message:
        await update.message.reply_text("❌ Укажите срок мутa и пользователя или ответьте на сообщение.")
        return

    # Определяем срок
    if update.message.reply_to_message:
        target_user = update.message.reply_to_message.from_user
        time_arg = context.args[0] if context.args else None
    else:
        time_arg = context.args[0]
        arg = context.args[1] if len(context.args) > 1 else None
        target_user = None

        # По username или ID
        if arg:
            if arg.startswith("@"):
                username = arg[1:]
                try:
                    member = await context.bot.get_chat_member(update.effective_chat.id, username)
                    target_user = member.user
                except:
                    pass
            else:
                try:
                    user_id = int(arg)
                    member = await context.bot.get_chat_member(update.effective_chat.id, user_id)
                    target_user = member.user
                except:
                    pass

    if not target_user or not time_arg:
        await update.message.reply_text("❌ Не удалось найти пользователя или указать срок.")
        return

    match = re.fullmatch(r"(\d+)([dh])", time_arg)
    if not match:
        await update.message.reply_text("❌ Неверный формат времени. Пример: 5d или 2h")
        return

    amount, unit = match.groups()
    amount = int(amount)
    delta = timedelta(days=amount) if unit == "d" else timedelta(hours=amount)
    until_date = datetime.utcnow() + delta

    perms = ChatPermissions(
        can_send_messages=False,
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

    try:
        await context.bot.restrict_chat_member(
            update.effective_chat.id,
            target_user.id,
            permissions=perms,
            until_date=until_date
        )
        await update.message.reply_text(f"✅ Пользователь {target_user.full_name} замучен до {until_date} UTC.")
    except Exception as e:
        await update.message.reply_text(f"❌ Не удалось замутить пользователя: {e}")

# ================= UNMUTE =================
async def unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ У вас нет прав для этой команды.")
        return

    target_user = None
    if update.message.reply_to_message:
        target_user = update.message.reply_to_message.from_user
    elif context.args:
        arg = context.args[0]
        try:
            user_id = int(arg)
            member = await context.bot.get_chat_member(update.effective_chat.id, user_id)
            target_user = member.user
        except:
            try:
                username = arg.lstrip("@")
                member = await context.bot.get_chat_member(update.effective_chat.id, username)
                target_user = member.user
            except:
                pass

    if not target_user:
        await update.message.reply_text("❌ Не удалось найти пользователя.")
        return

    perms = ChatPermissions(
        can_send_messages=True,
        can_send_audios=True,
        can_send_documents=True,
        can_send_photos=True,
        can_send_videos=True,
        can_send_video_notes=True,
        can_send_voice_notes=True,
        can_send_polls=True,
        can_send_other_messages=True,
        can_add_web_page_previews=True
    )

    try:
        await context.bot.restrict_chat_member(
            update.effective_chat.id,
            target_user.id,
            permissions=perms
        )
        await update.message.reply_text(f"✅ Пользователь {target_user.full_name} размучен.")
    except Exception as e:
        await update.message.reply_text(f"❌ Не удалось размутить пользователя: {e}")

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("mute", mute))
    app.add_handler(CommandHandler("unmute", unmute))
    app.add_handler(CallbackQueryHandler(toggle_notify, pattern="^toggle_notify$"))
    app.add_handler(CallbackQueryHandler(toggle_isolation, pattern="^toggle_isolation$"))
    app.add_handler(CallbackQueryHandler(captcha_answer, pattern="^captcha:"))
    app.add_handler(ChatJoinRequestHandler(handle_join_request))
    app.add_handler(CommandHandler("ban", ban))
    app.add_handler(CommandHandler("mute", mute))

    print("Bot started")
    app.run_polling()

if __name__ == "__main__":
    main()
