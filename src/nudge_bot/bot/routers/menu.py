from __future__ import annotations

from datetime import UTC, datetime, timedelta

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from nudge_bot.bot.callbacks import MenuActionEnum, MenuCallback
from nudge_bot.bot.keyboards import (
    MENU_ACTIVE_BUTTON_TEXT,
    MENU_ARCHIVE_BUTTON_TEXT,
    MENU_HISTORY_BUTTON_TEXT,
    MENU_REPLY_ACTIONS,
    REPEAT_INTERVAL_PRESETS,
    TIMEZONE_PRESETS,
    back_to_menu_keyboard,
    bottom_menu_keyboard,
    main_menu_keyboard,
    reminder_list_keyboard,
    repeat_interval_menu_keyboard,
    settings_menu_keyboard,
    timezone_menu_keyboard,
)
from nudge_bot.config import Settings
from nudge_bot.storage.models import Reminder, User
from nudge_bot.storage.unit_of_work import unit_of_work

router = Router(name="menu")
MENU_PAGE_SIZE = 5
ARCHIVE_LOOKBACK_DAYS = 90


@router.message(Command("menu"))
async def handle_menu_command(
    message: Message,
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    if message.from_user is None:
        return

    async with unit_of_work(session_factory) as uow:
        await ensure_menu_user(message.from_user, settings, uow)

    await message.answer(format_reply_menu_intro(), reply_markup=bottom_menu_keyboard())


@router.message(F.text.in_(set(MENU_REPLY_ACTIONS)))
async def handle_reply_menu_button(
    message: Message,
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    if message.from_user is None:
        return

    async with unit_of_work(session_factory) as uow:
        user = await ensure_menu_user(message.from_user, settings, uow)
        text, reply_markup = await build_menu_screen(
            action=MENU_REPLY_ACTIONS[message.text],
            value=None,
            user=user,
            settings=settings,
            uow=uow,
            now=datetime.now(UTC),
        )

    await message.answer(text, reply_markup=reply_markup)


@router.callback_query(MenuCallback.filter(F.action == MenuActionEnum.VIEW_REMINDER.value))
async def handle_reminder_button_callback(callback: CallbackQuery) -> None:
    await callback.answer("Reminder actions are coming later")


@router.callback_query(MenuCallback.filter())
async def handle_menu_callback(
    callback: CallbackQuery,
    callback_data: MenuCallback,
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with unit_of_work(session_factory) as uow:
        user = await ensure_menu_user(callback.from_user, settings, uow)

        text, reply_markup = await build_menu_screen(
            action=callback_data.action,
            value=callback_data.value,
            user=user,
            settings=settings,
            uow=uow,
            now=datetime.now(UTC),
        )

    await edit_or_answer_menu(callback, text=text, reply_markup=reply_markup)


async def build_menu_screen(
    *,
    action: MenuActionEnum,
    value: str | None,
    user: User,
    settings: Settings,
    uow: object,
    now: datetime,
) -> tuple[str, object]:
    if action == MenuActionEnum.SETTINGS:
        return format_settings_menu(user), settings_menu_keyboard()

    if action == MenuActionEnum.TIMEZONE:
        return (
            "🌍 Choose timezone",
            timezone_menu_keyboard(user.settings.timezone),
        )

    if action == MenuActionEnum.SET_TIMEZONE:
        timezone = value if value in TIMEZONE_PRESETS else settings.default_timezone
        user.settings = await uow.users.update_settings(user_id=user.id, timezone=timezone)
        return format_settings_menu(user), settings_menu_keyboard()

    if action == MenuActionEnum.REPEAT_INTERVAL:
        return (
            "🔁 Choose repeat interval",
            repeat_interval_menu_keyboard(user.settings.repeat_interval_minutes),
        )

    if action == MenuActionEnum.SET_REPEAT_INTERVAL:
        interval = _parse_repeat_interval(value, settings.default_repeat_interval_minutes)
        user.settings = await uow.users.update_settings(
            user_id=user.id,
            repeat_interval_minutes=interval,
        )
        return format_settings_menu(user), settings_menu_keyboard()

    if action == MenuActionEnum.ACTIVE:
        page = _parse_page(value)
        reminders = await uow.reminders.list_active_for_user(
            user_id=user.id,
            limit=MENU_PAGE_SIZE + 1,
            offset=page * MENU_PAGE_SIZE,
        )
        visible_reminders, has_next_page = _page_items(reminders)
        return (
            format_reminder_list_screen(
                title=MENU_ACTIVE_BUTTON_TEXT,
                empty_text="No active reminders.",
                reminders=visible_reminders,
                page=page,
            ),
            reminder_list_keyboard(
                reminders=visible_reminders,
                screen=MenuActionEnum.ACTIVE,
                page=page,
                has_next_page=has_next_page,
            ),
        )

    if action == MenuActionEnum.HISTORY:
        page = _parse_page(value)
        reminders = await uow.reminders.list_recent_for_user(
            user_id=user.id,
            limit=MENU_PAGE_SIZE + 1,
            offset=page * MENU_PAGE_SIZE,
        )
        visible_reminders, has_next_page = _page_items(reminders)
        return (
            format_reminder_list_screen(
                title=MENU_HISTORY_BUTTON_TEXT,
                empty_text="No reminders yet.",
                reminders=visible_reminders,
                page=page,
            ),
            reminder_list_keyboard(
                reminders=visible_reminders,
                screen=MenuActionEnum.HISTORY,
                page=page,
                has_next_page=has_next_page,
            ),
        )

    if action == MenuActionEnum.ARCHIVE:
        page = _parse_page(value)
        reminders = await uow.reminders.list_completed_since(
            user_id=user.id,
            since=now - timedelta(days=ARCHIVE_LOOKBACK_DAYS),
            limit=MENU_PAGE_SIZE + 1,
            offset=page * MENU_PAGE_SIZE,
        )
        visible_reminders, has_next_page = _page_items(reminders)
        return (
            format_reminder_list_screen(
                title=MENU_ARCHIVE_BUTTON_TEXT,
                empty_text="No completed reminders in the last 3 months.",
                reminders=visible_reminders,
                page=page,
            ),
            reminder_list_keyboard(
                reminders=visible_reminders,
                screen=MenuActionEnum.ARCHIVE,
                page=page,
                has_next_page=has_next_page,
            ),
        )

    if action == MenuActionEnum.NEW_REMINDER:
        return (
            "✍️ Send the reminder as text or voice.\n\nExample: walk the dog in 20 minutes",
            back_to_menu_keyboard(),
        )

    if action == MenuActionEnum.HELP:
        return (
            "ℹ️ Nudge help\n\n"
            "Send text or voice with a time to create a reminder.\n"
            "Use Read to complete, Repeat to snooze, or Choose time to reschedule.",
            back_to_menu_keyboard(),
        )

    return format_main_menu(), main_menu_keyboard()


async def ensure_menu_user(from_user: object, settings: Settings, uow: object) -> User:
    return await uow.users.get_or_create(
        telegram_user_id=from_user.id,
        username=from_user.username,
        locale=from_user.language_code,
        timezone=settings.default_timezone,
        repeat_interval_minutes=settings.default_repeat_interval_minutes,
    )


async def edit_or_answer_menu(
    callback: CallbackQuery,
    *,
    text: str,
    reply_markup: object,
) -> None:
    await callback.answer()
    if isinstance(callback.message, Message):
        try:
            await callback.message.edit_text(text, reply_markup=reply_markup)
        except TelegramBadRequest as exc:
            if _is_message_not_modified_error(exc):
                return
            raise


def format_main_menu() -> str:
    return "📋 Nudge menu\n\nSend a reminder anytime as text or voice."


def format_reply_menu_intro() -> str:
    return "Menu is pinned below. Choose an action or send a reminder anytime."


def _is_message_not_modified_error(exc: TelegramBadRequest) -> bool:
    return "message is not modified" in exc.message.lower()


def format_settings_menu(user: User) -> str:
    return (
        "⚙️ Settings\n\n"
        f"🌍 Timezone: {user.settings.timezone}\n"
        f"🔁 Repeat interval: {user.settings.repeat_interval_minutes} min"
    )


def format_reminder_list_screen(
    *,
    title: str,
    empty_text: str,
    reminders: list[Reminder],
    page: int,
) -> str:
    if not reminders:
        return f"{title}\n\n{empty_text}"

    return f"{title}\n\nPage {page + 1}. Choose a reminder."


def _parse_repeat_interval(value: str | None, default: int) -> int:
    try:
        interval = int(value or "")
    except ValueError:
        return default
    if interval not in REPEAT_INTERVAL_PRESETS:
        return default
    return interval


def _parse_page(value: str | None) -> int:
    try:
        page = int(value or "0")
    except ValueError:
        return 0
    return max(page, 0)


def _page_items(reminders: list[Reminder]) -> tuple[list[Reminder], bool]:
    return reminders[:MENU_PAGE_SIZE], len(reminders) > MENU_PAGE_SIZE
