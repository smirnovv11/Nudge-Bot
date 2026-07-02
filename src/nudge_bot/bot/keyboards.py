from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from nudge_bot.bot.callbacks import ReminderActionCallback, ReminderDraftCallback
from nudge_bot.reminders.enums import CallbackAction


def reminder_actions_keyboard(
    reminder_id: int,
    notification_id: int | None = None,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Read",
                    callback_data=ReminderActionCallback(
                        action=CallbackAction.READ,
                        reminder_id=reminder_id,
                        notification_id=notification_id,
                    ).pack(),
                ),
                InlineKeyboardButton(
                    text="🔁 Repeat",
                    callback_data=ReminderActionCallback(
                        action=CallbackAction.REPEAT,
                        reminder_id=reminder_id,
                        notification_id=notification_id,
                    ).pack(),
                ),
                InlineKeyboardButton(
                    text="🕒 Choose time",
                    callback_data=ReminderActionCallback(
                        action=CallbackAction.CHOOSE_TIME,
                        reminder_id=reminder_id,
                        notification_id=notification_id,
                    ).pack(),
                ),
            ]
        ]
    )


def draft_confirmation_keyboard(draft_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Create",
                    callback_data=ReminderDraftCallback(
                        action=CallbackAction.CONFIRM,
                        draft_id=draft_id,
                    ).pack(),
                ),
                InlineKeyboardButton(
                    text="✖️ Cancel",
                    callback_data=ReminderDraftCallback(
                        action=CallbackAction.CANCEL,
                        draft_id=draft_id,
                    ).pack(),
                ),
            ]
        ]
    )


def edit_time_cancel_keyboard(draft_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Cancel",
                    callback_data=ReminderDraftCallback(
                        action=CallbackAction.CANCEL,
                        draft_id=draft_id,
                    ).pack(),
                ),
            ]
        ]
    )
