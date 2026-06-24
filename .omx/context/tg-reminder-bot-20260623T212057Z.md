# TG reminder bot context snapshot

Task statement: The user wants to explore a Telegram bot for sending quick notes and time-based notifications to themselves, replacing the current habit of scheduling messages in a Telegram chat.

Desired outcome: Clarify the product idea, the problem it solves, likely functionality, creative differentiators, non-goals, and decision boundaries before any implementation or code planning.

Stated solution: A Telegram bot where the user can send notes and create notifications by time, with possible other reminder modes.

Probable intent hypothesis: Reduce friction around remembering small and important tasks, avoid cluttering saved Telegram messages, and make reminders fast enough to capture at the moment of thought. The primary pain is that Telegram scheduled messages require too many steps: opening saved messages, writing text, holding the send button, choosing an exact send time, and later dealing with a cluttered chat. The user also forgets to recreate notifications when events are not done.

Known facts/evidence: The repository is currently minimal. `AGENTS.md` says complex features or significant refactors should use an ExecPlan from `.agent/PLANS.md`. No `.omx` context existed before this snapshot. No `docs/` directory exists.

Constraints: No implementation should be started during this deep-interview turn. Future complex implementation should use an ExecPlan. The user speaks Russian and is still shaping the idea.

Unknowns/open questions: Target reminder workflow, required input language, reminder channels, note organization model, snooze/escalation behavior, privacy expectations, recurring reminders, and what should be out of scope.

Captured product decisions so far: The first product focus is notifications and reminders, not a full notes inbox. Voice creation is especially important. A successful reminder creation flow should accept phrases like "погулять с собакой через 20 мин" or "забрать справку 26 февраля 2027 года", parse the reminder text and due date/time, create the notification, then confirm success and offer menu/edit actions.

Primary UX criterion: The user ultimately wants the fastest possible flow: open the bot, send one phrase, and have the reminder created. In the future this should include tapping the microphone and speaking, but the text-based MVP must also be speed-first: if the user writes plain text to the bot, the bot should parse the reminder text plus date/time and create the notification without forcing a menu flow. Any confirmation or disambiguation should be minimized because speed is the main value. The first implementation focus should be text-based reminder creation, with voice creation deferred until the text grammar and reminder lifecycle are solid.

Proposed parsing rule under discussion: If a voice/text message contains a recognizable date or time, the bot should treat it as a reminder by default. If the user wants to preserve text that contains a date without scheduling it, there must be an explicit phrase or command to mark it as a plain saved item.

Confidence behavior: When parsing is confident, the bot should create the reminder immediately and send a success confirmation. When parsing is uncertain, it should show a short confirmation with actions such as create, edit, or cancel instead of silently creating the wrong reminder.

Notification behavior: When a reminder fires, the bot should send the reminder with buttons: "Прочитано" to acknowledge that the user saw it, "Повторить" to snooze using the user's configured short-repeat interval, and "Выбрать время" to choose a specific next reminder time. The default short-repeat interval should be 5 minutes. If the user does not choose anything, the bot should repeat the notification after the configured interval in minutes or hours.

Reminder status behavior: "Прочитано" means the task/reminder is done or handled, so the bot should stop repeating it and mark it as read/completed. The record should likely remain in history instead of being deleted immediately.

Out-of-scope for MVP: Recurring reminders such as "every day at 9" or "every Friday" should not be part of the first version. Preserve the idea for later, but keep the MVP focused on one-off reminders and manual/default repeat behavior.

Business direction: The bot is private-first: initially a personal tool for the user, with possible public release later. Data is considered moderately sensitive but not critical because the expected content is mostly small everyday tasks. The product should still preserve basic privacy boundaries if opened to others. The first version should be free. If monetization appears later, it is more likely to be through advertising posts in the bot rather than subscriptions or paid limits.

Future consideration: Preserve the idea of an "idea inbox" or "text without time" module for later development. It should not dominate the MVP, but the future architecture should not make it hard to store messages that are useful but do not yet have a reminder date.

Decision-boundary unknowns: Whether the assistant may choose product positioning, reminder grammar, data model, UI flow, storage, deployment, and Telegram bot interaction patterns later without confirmation.

Likely codebase touchpoints: Unknown because no app code exists yet.

Relevant repo docs/rules/context inspected: `AGENTS.md`; `.agent/PLANS.md`.

Terminology or doc/code conflicts found: None.

Prompt-safe initial-context summary status: not_needed.
