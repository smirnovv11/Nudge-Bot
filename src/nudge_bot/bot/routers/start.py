from __future__ import annotations

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from nudge_bot.bot.keyboards import bottom_menu_keyboard

router = Router(name="start")


@router.message(CommandStart())
async def handle_start(message: Message) -> None:
    await message.answer(
        "Send me a reminder in plain text or voice.",
        reply_markup=bottom_menu_keyboard(),
    )
