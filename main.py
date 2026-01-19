import asyncio
import random
from datetime import datetime

import os
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import (
    ChatJoinRequest,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    Message
)

# ================== НАСТРОЙКИ ==================

ADMIN_IDS = {
    8374810497,  # <-- ЗАМЕНИ
    8302596774
}

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не задан")

# ================== INIT ==================

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

# ================== ХРАНИЛИЩА ==================

active_captcha = {}      # user_id -> captcha data
passed_captcha = {}      # user_id -> data
failed_captcha = {}      # user_id -> data

# ================== КАПЧА ==================

EMOJI_BUTTONS = {
    "apple":  {"emoji": "🍎", "text": "Yaблоко"},
    "pear":   {"emoji": "🍐", "text": "Грyшa"},
    "banana": {"emoji": "🍌", "text": "БаHaH"},
    "tomato": {"emoji": "🍅", "text": "П0мид0p"},
    "car":    {"emoji": "🚗", "text": "MaшиHа"},
    "heart":  {"emoji": "❤️", "text": "Cepдце"},
}


def build_keyboard():
    items = list(EMOJI_BUTTONS.items())
    random.shuffle(items)

    kb = []
    for key, data in items:
        kb.append(
            InlineKeyboardButton(
                text=data["emoji"],
                callback_data=f"captcha:{key}"
            )
        )

    return InlineKeyboardMarkup(
        inline_keyboard=[kb[i:i+3] for i in range(0, len(kb), 3)]
    )

# ================== JOIN REQUEST ==================

@dp.chat_join_request()
async def on_join_request(req: ChatJoinRequest):
    user = req.from_user
    chat_id = req.chat.id

    correct_key = random.choice(list(EMOJI_BUTTONS.keys()))
    correct_text = EMOJI_BUTTONS[correct_key]["text"]

    try:
        msg = await bot.send_message(
            user.id,
            f"Для вступления в чат нажмите:\n\n<b>{correct_text}</b>",
            reply_markup=build_keyboard()
        )
    except Exception:
        await bot.decline_chat_join_request(chat_id, user.id)
        return

    active_captcha[user.id] = {
        "chat_id": chat_id,
        "correct": correct_key,
        "message_id": msg.message_id,
        "date": datetime.utcnow(),
        "user": user
    }

    asyncio.create_task(captcha_timeout(user.id))


async def captcha_timeout(user_id: int):
    await asyncio.sleep(120)

    data = active_captcha.get(user_id)
    if not data:
        return

    await bot.decline_chat_join_request(data["chat_id"], user_id)
    failed_captcha[user_id] = data
    active_captcha.pop(user_id, None)

# ================== CAPTCHA ANSWER ==================

@dp.callback_query(F.data.startswith("captcha:"))
async def on_captcha(call: CallbackQuery):
    user_id = call.from_user.id
    data = active_captcha.get(user_id)

    if not data:
        await call.answer("Капча устарела", show_alert=True)
        return

    chosen = call.data.split(":")[1]

    if chosen == data["correct"]:
        passed_captcha[user_id] = data
        await call.answer("✅ Верно")
        await bot.edit_message_text(
            "✅ Капча пройдена.\nОжидайте решения администратора.",
            chat_id=user_id,
            message_id=data["message_id"]
        )
    else:
        failed_captcha[user_id] = data
        await bot.decline_chat_join_request(data["chat_id"], user_id)
        await call.answer("❌ Неверно", show_alert=True)

    active_captcha.pop(user_id, None)

# ================== ADMIN PANEL ==================

def admin_only(func):
    async def wrapper(message: Message, *args, **kwargs):
        if message.from_user.id not in ADMIN_IDS:
            return
        return await func(message, *args, **kwargs)
    return wrapper


@dp.message(F.text == "/admin")
@admin_only
async def admin_panel(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🤖 Боты", callback_data="admin:failed")],
        [InlineKeyboardButton(text="🟢 Активные заявки", callback_data="admin:passed")]
    ])
    await message.answer("⚙️ Панель администратора", reply_markup=kb)


@dp.callback_query(F.data == "admin:failed")
async def admin_failed(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return

    text = "<b>❌ Не прошли проверку:</b>\n\n"
    for u in failed_captcha.values():
        user = u["user"]
        text += f"{user.full_name} | @{user.username or '—'} | {user.id}\n"

    await call.message.edit_text(text or "Пусто")


@dp.callback_query(F.data == "admin:passed")
async def admin_passed(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return

    kb = []
    for uid, data in passed_captcha.items():
        user = data["user"]
        kb.append([
            InlineKeyboardButton(
                text=f"{user.full_name} (@{user.username or user.id})",
                callback_data=f"admin:req:{uid}"
            )
        ])

    await call.message.edit_text(
        "🟢 Активные заявки:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )


@dp.callback_query(F.data.startswith("admin:req:"))
async def admin_request(call: CallbackQuery):
    uid = int(call.data.split(":")[2])
    data = passed_captcha.get(uid)
    if not data:
        return

    user = data["user"]
    text = (
        f"<b>Заявка</b>\n\n"
        f"👤 {user.full_name}\n"
        f"🆔 {user.id}\n"
        f"🔗 @{user.username or '—'}\n"
        f"📅 {data['date']}"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Принять", callback_data=f"admin:accept:{uid}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"admin:decline:{uid}")
        ]
    ])

    await call.message.edit_text(text, reply_markup=kb)


@dp.callback_query(F.data.startswith("admin:accept:"))
async def admin_accept(call: CallbackQuery):
    uid = int(call.data.split(":")[2])
    data = passed_captcha.pop(uid, None)
    if data:
        await bot.approve_chat_join_request(data["chat_id"], uid)
    await call.message.edit_text("✅ Заявка принята")


@dp.callback_query(F.data.startswith("admin:decline:"))
async def admin_decline(call: CallbackQuery):
    uid = int(call.data.split(":")[2])
    data = passed_captcha.pop(uid, None)
    if data:
        await bot.decline_chat_join_request(data["chat_id"], uid)
    await call.message.edit_text("❌ Заявка отклонена")

# ================== START ==================

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
