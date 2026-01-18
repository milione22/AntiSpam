import asyncio
import random
from datetime import datetime, timedelta
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv
import os

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    ChatJoinRequest,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery
)
from aiogram.filters import Command
from aiogram.enums import ParseMode

load_dotenv()
print("TOKEN =", os.getenv("TELEGRAM_BOT_TOKEN"))


bot = Bot(token=os.getenv('TELEGRAM_BOT_TOKEN') , default=DefaultBotProperties(parse_mode=ParseMode.HTML) )
dp = Dispatcher()

# Храним активные капчи
# user_id -> dict
active_captcha = {}

EMOJI_BUTTONS = {
    "apple": "Yaблоко",
    "pear": "Грyшa",
    "banana": "БаHaH",
    "tomato": "П0мид0p",
    "car": "MaшиHа",
    "heart": "Cepдце"
}


def build_keyboard():
    kb = []
    for key, text in EMOJI_BUTTONS.items():
        kb.append(
            InlineKeyboardButton(
                text=text,
                callback_data=f"captcha:{key}"
            )
        )
    return InlineKeyboardMarkup(inline_keyboard=[kb[i:i+3] for i in range(0, 6, 3)])


@dp.chat_join_request()
async def on_join_request(req: ChatJoinRequest):
    user = req.from_user
    chat_id = req.chat.id

    correct_key = random.choice(list(EMOJI_BUTTONS.keys()))
    correct_text = EMOJI_BUTTONS[correct_key]

    try:
        msg = await bot.send_message(
            user.id,
            f"Для вступления в чат нажмите:\n\n<b>{correct_text}</b>",
            reply_markup=build_keyboard()
        )
    except Exception:
        # ЛС закрыты → сразу отклоняем
        await bot.decline_chat_join_request(chat_id, user.id)
        return

    active_captcha[user.id] = {
        "chat_id": chat_id,
        "correct": correct_key,
        "message_id": msg.message_id,
        "time": datetime.utcnow()
    }

    asyncio.create_task(captcha_timeout(user.id))


async def captcha_timeout(user_id: int):
    await asyncio.sleep(120)

    data = active_captcha.get(user_id)
    if not data:
        return

    await bot.decline_chat_join_request(
        data["chat_id"],
        user_id
    )

    try:
        await bot.send_message(
            user_id,
            "⏱ Время истекло. Заявка отклонена."
        )
    except Exception:
        pass

    active_captcha.pop(user_id, None)


@dp.callback_query(F.data.startswith("captcha:"))
async def on_captcha_answer(call: CallbackQuery):
    user_id = call.from_user.id
    data = active_captcha.get(user_id)

    if not data:
        await call.answer("Капча устарела", show_alert=True)
        return

    chosen = call.data.split(":")[1]

    if chosen == data["correct"]:
        await call.answer("✅ Верно")

        try:
            await bot.edit_message_text(
                "✅ Капча пройдена.\nЗаявка отправлена на проверку администраторам.",
                chat_id=user_id,
                message_id=data["message_id"]
            )
        except Exception:
            pass

        # НИЧЕГО не делаем → заявка остаётся на ручное одобрение

    else:
        await call.answer("❌ Неверно", show_alert=True)

        await bot.decline_chat_join_request(
            data["chat_id"],
            user_id
        )

        try:
            await bot.edit_message_text(
                "❌ Неверный ответ. Заявка отклонена.",
                chat_id=user_id,
                message_id=data["message_id"]
            )
        except Exception:
            pass

    active_captcha.pop(user_id, None)


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())



