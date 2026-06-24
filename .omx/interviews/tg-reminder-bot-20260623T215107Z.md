# TG reminder bot interview summary

Profile: standard
Context type: greenfield product clarification
Final ambiguity: 17%
Threshold: 20%
Context snapshot: `.omx/context/tg-reminder-bot-20260623T212057Z.md`

## Summary

The user currently uses Telegram scheduled messages to remind themselves about tasks and events. This is slow and uncomfortable because it requires opening saved messages, writing the text, holding the send button, selecting a send time, and then dealing with a cluttered chat. The intended product is a Telegram bot that makes personal reminder creation much faster and more reliable.

The first product version should focus on one-off reminders and notifications, not a general note inbox. Text-based creation should come first, but it should still be optimized for speed: the user should be able to send ordinary text to the bot and have the bot parse reminder text plus date/time without forcing a menu-first flow. Voice creation remains a major desired future capability, but it is deferred until text parsing and the reminder lifecycle are stable.

## Interview Findings

Primary pain: creating scheduled messages in Telegram takes too many steps, and missed or unfinished events are easy to forget because the user may not recreate the notification.

MVP focus: fast one-message text creation of personal reminders, reminder notifications with action buttons, configurable default repeat interval, and history-preserving completion.

Deferred ideas: voice creation, idea inbox / notes without time, recurring reminders, statistics, restoring completed reminders, and creating new reminders from history.

Business direction: The bot should start as a personal private-first tool. It may become public later, but the first version should avoid unnecessary public-product overhead. The first version should be free. Possible future monetization is advertising posts in the bot, not subscriptions or paid limits.

Important UX principle: the bot should optimize for speed. If the bot confidently parses a reminder, it should create it and send a confirmation. If parsing is uncertain, it should ask for a short confirmation instead of silently creating the wrong reminder.

## Condensed Transcript

The user clarified that reminders and notifications are the main problem. A full idea inbox is secondary.

For a phrase like "забрать справку 26 февраля 2027 года", the bot should create a reminder with text "забрать справку" and due date February 26, 2027, then confirm creation and offer menu/edit options.

If a user wants to save text containing a date without scheduling it, the preferred direction is an explicit marker such as "заметка:" or "сохрани:" rather than making the bot ask every time.

When parsing is uncertain, the bot should show a compact confirmation with create/edit/cancel options.

When a reminder fires, it should include buttons: "Прочитано", "Повторить", and "Выбрать время". "Прочитано" means the task is handled, active repeats stop, and the item is marked read/completed while likely remaining in history.

If the user does not press any button on a fired reminder, the bot should repeat it after the user's configured interval. The default is 5 minutes.

Recurring reminders are out of scope for the first version, but should be remembered as a future module.
