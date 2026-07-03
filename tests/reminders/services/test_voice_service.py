from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from nudge_bot.config import Settings
from nudge_bot.reminders.draft_payloads import edit_time_payload
from nudge_bot.reminders.enums import DraftStatusEnum, DraftTypeEnum, ReminderSourceTypeEnum
from nudge_bot.reminders.services import VoiceReminderService
from nudge_bot.reminders.services.intake import SOURCE_METADATA_PAYLOAD_KEY, SOURCE_TYPE_PAYLOAD_KEY
from nudge_bot.reminders.services.schemas import (
    TextReminderOutcomeEnum,
    VoiceReminderOutcomeEnum,
    VoiceTranscript,
    VoiceTranscriptionOutcomeEnum,
    VoiceTranscriptionResult,
)
from nudge_bot.reminders.services.voice import BYTES_PER_MEGABYTE, _transcribe_with_model
from nudge_bot.storage.models import Draft

from .fakes import FakeDraftRepository, FakeReminderRepository, FakeUnitOfWork

NOW = datetime(2026, 6, 24, 12, 0, tzinfo=ZoneInfo("Europe/Minsk"))
SETTINGS = Settings()


@dataclass
class FakeVoiceTranscriber:
    result: VoiceTranscriptionResult
    calls: int = 0

    async def warm_up(self, settings: Settings) -> None:
        return None

    async def transcribe(
        self,
        audio: bytes,
        *,
        source_file_unique_id: str,
        duration_seconds: int | None,
        settings: Settings,
    ) -> VoiceTranscriptionResult:
        self.calls += 1
        return self.result


@pytest.mark.asyncio
async def test_voice_reminder_creates_voice_reminder_from_transcript() -> None:
    reminders = FakeReminderRepository()

    result = await VoiceReminderService().process_voice_transcription(
        FakeUnitOfWork(reminders),
        telegram_user_id=100,
        username=None,
        locale="ru",
        transcription=_transcribed("walk the dog in 20 minutes"),
        mime_type="audio/ogg",
        now=NOW,
        settings=SETTINGS,
    )

    assert result.outcome == VoiceReminderOutcomeEnum.PROCESSED
    assert result.text_result is not None
    assert result.text_result.outcome == TextReminderOutcomeEnum.CREATED
    assert result.text_result.reminder is reminders.added[0]
    assert result.text_result.reminder.source_type == ReminderSourceTypeEnum.VOICE
    assert result.text_result.reminder.extra["source_file_unique_id"] == "voice-file"
    assert result.text_result.reminder.extra["mime_type"] == "audio/ogg"


@pytest.mark.asyncio
async def test_voice_reminder_creates_voice_confirmation_draft_for_uncertain_transcript() -> None:
    drafts = FakeDraftRepository()

    result = await VoiceReminderService().process_voice_transcription(
        FakeUnitOfWork(FakeReminderRepository(), drafts=drafts),
        telegram_user_id=100,
        username=None,
        locale="ru",
        transcription=_transcribed("pick up order tomorrow"),
        mime_type="audio/ogg",
        now=NOW,
        settings=SETTINGS,
    )

    assert result.outcome == VoiceReminderOutcomeEnum.PROCESSED
    assert result.text_result is not None
    assert result.text_result.outcome == TextReminderOutcomeEnum.DRAFT
    assert result.text_result.draft is drafts.added[0]
    assert result.text_result.draft.payload[SOURCE_TYPE_PAYLOAD_KEY] == ReminderSourceTypeEnum.VOICE
    assert (
        result.text_result.draft.payload[SOURCE_METADATA_PAYLOAD_KEY]["source_file_unique_id"]
        == "voice-file"
    )


@pytest.mark.asyncio
async def test_empty_voice_transcript_creates_nothing() -> None:
    reminders = FakeReminderRepository()
    drafts = FakeDraftRepository()

    result = await VoiceReminderService().process_voice_transcription(
        FakeUnitOfWork(reminders, drafts=drafts),
        telegram_user_id=100,
        username=None,
        locale="ru",
        transcription=VoiceTranscriptionResult(outcome=VoiceTranscriptionOutcomeEnum.EMPTY),
        mime_type="audio/ogg",
        now=NOW,
        settings=SETTINGS,
    )

    assert result.outcome == VoiceReminderOutcomeEnum.EMPTY_TRANSCRIPT
    assert reminders.added == []
    assert drafts.added == []


@pytest.mark.asyncio
async def test_failed_voice_transcript_creates_nothing() -> None:
    reminders = FakeReminderRepository()
    drafts = FakeDraftRepository()

    result = await VoiceReminderService().process_voice_transcription(
        FakeUnitOfWork(reminders, drafts=drafts),
        telegram_user_id=100,
        username=None,
        locale="ru",
        transcription=VoiceTranscriptionResult(
            outcome=VoiceTranscriptionOutcomeEnum.FAILED,
            error_message="model unavailable",
        ),
        mime_type="audio/ogg",
        now=NOW,
        settings=SETTINGS,
    )

    assert result.outcome == VoiceReminderOutcomeEnum.TRANSCRIPTION_FAILED
    assert result.error_message == "model unavailable"
    assert reminders.added == []
    assert drafts.added == []


def test_oversized_voice_metadata_is_rejected_before_transcription() -> None:
    result = VoiceReminderService().validate_voice_input(
        file_size=SETTINGS.voice_max_file_size_mb * BYTES_PER_MEGABYTE + 1,
        duration_seconds=4,
        settings=SETTINGS,
    )

    assert result is not None
    assert result.outcome == VoiceReminderOutcomeEnum.TOO_LARGE


def test_oversized_voice_bytes_are_rejected_when_metadata_is_missing() -> None:
    result = VoiceReminderService().validate_voice_input(
        audio=b"x" * (SETTINGS.voice_max_file_size_mb * BYTES_PER_MEGABYTE + 1),
        file_size=None,
        duration_seconds=4,
        settings=SETTINGS,
    )

    assert result is not None
    assert result.outcome == VoiceReminderOutcomeEnum.TOO_LARGE


def test_long_voice_is_rejected_before_transcription() -> None:
    result = VoiceReminderService().validate_voice_input(
        file_size=1024,
        duration_seconds=SETTINGS.voice_max_duration_seconds + 1,
        settings=SETTINGS,
    )

    assert result is not None
    assert result.outcome == VoiceReminderOutcomeEnum.TOO_LONG


@pytest.mark.asyncio
async def test_voice_does_not_satisfy_pending_edit_time_draft() -> None:
    pending_edit_draft = Draft(
        id=1,
        user_id=10,
        type=DraftTypeEnum.REMINDER_EDIT_TIME,
        status=DraftStatusEnum.PENDING,
        input_text="",
        payload=edit_time_payload(
            reminder_id=1,
            notification_id=7,
            callback_key="callback",
            timezone="Europe/Minsk",
        ),
        expires_at=NOW.astimezone(UTC) + timedelta(hours=12),
    )
    transcriber = FakeVoiceTranscriber(_transcribed("walk the dog in 20 minutes"))

    result = await VoiceReminderService(transcriber=transcriber).reject_pending_edit_time(
        FakeUnitOfWork(
            FakeReminderRepository(),
            drafts=FakeDraftRepository(pending_edit_draft),
        ),
        telegram_user_id=100,
        username=None,
        locale="ru",
        now=NOW,
        settings=SETTINGS,
    )

    assert result is not None
    assert result.outcome == VoiceReminderOutcomeEnum.PENDING_EDIT_TIME
    assert transcriber.calls == 0


@pytest.mark.asyncio
async def test_voice_audio_transcription_delegates_to_transcriber() -> None:
    transcriber = FakeVoiceTranscriber(_transcribed("walk the dog in 20 minutes"))

    result = await VoiceReminderService(transcriber=transcriber).transcribe_voice_audio(
        audio=b"voice",
        source_file_unique_id="voice-file",
        duration_seconds=4,
        settings=SETTINGS,
    )

    assert result.outcome == VoiceTranscriptionOutcomeEnum.TRANSCRIBED
    assert transcriber.calls == 1


def test_faster_whisper_transcribe_uses_fast_voice_options() -> None:
    model = FakeWhisperModel()

    text, language = _transcribe_with_model(model, b"voice", language="ru")

    assert text == "walk the dog"
    assert language == "ru"
    assert model.kwargs == {
        "language": "ru",
        "beam_size": 1,
        "best_of": 1,
        "without_timestamps": True,
        "condition_on_previous_text": False,
        "vad_filter": True,
    }


def _transcribed(text: str) -> VoiceTranscriptionResult:
    return VoiceTranscriptionResult(
        outcome=VoiceTranscriptionOutcomeEnum.TRANSCRIBED,
        transcript=VoiceTranscript(
            text=text,
            language="ru",
            duration_seconds=4,
            model="small",
            source_file_unique_id="voice-file",
        ),
    )


@dataclass
class FakeWhisperSegment:
    text: str


@dataclass
class FakeWhisperInfo:
    language: str


class FakeWhisperModel:
    def __init__(self) -> None:
        self.kwargs: dict[str, object] = {}

    def transcribe(
        self,
        path: str,
        **kwargs: object,
    ) -> tuple[list[FakeWhisperSegment], FakeWhisperInfo]:
        assert path.endswith(".ogg")
        assert Path(path).name.startswith("nudge_voice_")
        self.kwargs = kwargs
        return [FakeWhisperSegment("walk"), FakeWhisperSegment("the dog")], FakeWhisperInfo("ru")
