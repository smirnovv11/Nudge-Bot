from __future__ import annotations

import tempfile
from asyncio import to_thread
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Protocol

from nudge_bot.config import Settings
from nudge_bot.reminders.enums import DraftStatus, DraftType, ReminderSourceType
from nudge_bot.reminders.services.intake import ReminderIntakeService
from nudge_bot.reminders.services.schemas import (
    VoiceReminderOutcome,
    VoiceReminderResult,
    VoiceTranscript,
    VoiceTranscriptionOutcome,
    VoiceTranscriptionResult,
)
from nudge_bot.reminders.services.time import is_expired, to_utc
from nudge_bot.storage.unit_of_work import UnitOfWork

BYTES_PER_MEGABYTE = 1024 * 1024


class VoiceTranscriber(Protocol):
    async def warm_up(self, settings: Settings) -> None:
        """Load reusable transcription resources before the first voice message."""

    async def transcribe(
        self,
        audio: bytes,
        *,
        source_file_unique_id: str,
        duration_seconds: int | None,
        settings: Settings,
    ) -> VoiceTranscriptionResult:
        """Turn an incoming Telegram audio payload into transcript text."""


class FasterWhisperTranscriber:
    def __init__(self) -> None:
        self._model: object | None = None
        self._model_name: str | None = None
        self._device: str | None = None
        self._compute_type: str | None = None

    async def warm_up(self, settings: Settings) -> None:
        await to_thread(self._load_model, settings)

    async def transcribe(
        self,
        audio: bytes,
        *,
        source_file_unique_id: str,
        duration_seconds: int | None,
        settings: Settings,
    ) -> VoiceTranscriptionResult:
        try:
            model = await to_thread(self._load_model, settings)
            text, language = await to_thread(
                _transcribe_with_model,
                model,
                audio,
                language=settings.voice_transcription_language,
            )
        except Exception as exc:
            return VoiceTranscriptionResult(
                outcome=VoiceTranscriptionOutcome.FAILED,
                error_message=str(exc),
            )

        normalized_text = text.strip()
        if not normalized_text:
            return VoiceTranscriptionResult(outcome=VoiceTranscriptionOutcome.EMPTY)

        return VoiceTranscriptionResult(
            outcome=VoiceTranscriptionOutcome.TRANSCRIBED,
            transcript=VoiceTranscript(
                text=normalized_text,
                language=language,
                duration_seconds=duration_seconds,
                model=settings.voice_transcription_model,
                source_file_unique_id=source_file_unique_id,
            ),
        )

    def _load_model(self, settings: Settings) -> object:
        if (
            self._model is not None
            and self._model_name == settings.voice_transcription_model
            and self._device == settings.voice_transcription_device
            and self._compute_type == settings.voice_transcription_compute_type
        ):
            return self._model

        from faster_whisper import WhisperModel

        self._model = WhisperModel(
            settings.voice_transcription_model,
            device=settings.voice_transcription_device,
            compute_type=settings.voice_transcription_compute_type,
        )
        self._model_name = settings.voice_transcription_model
        self._device = settings.voice_transcription_device
        self._compute_type = settings.voice_transcription_compute_type
        return self._model


class VoiceReminderService:
    def __init__(
        self,
        *,
        transcriber: VoiceTranscriber | None = None,
        intake_service: ReminderIntakeService | None = None,
    ) -> None:
        self._transcriber = transcriber or FasterWhisperTranscriber()
        self._intake_service = intake_service or ReminderIntakeService()

    def validate_voice_input(
        self,
        *,
        audio: bytes | None = None,
        file_size: int | None,
        duration_seconds: int | None,
        settings: Settings,
    ) -> VoiceReminderResult | None:
        max_voice_bytes = settings.voice_max_file_size_mb * BYTES_PER_MEGABYTE
        if file_size is not None and file_size > max_voice_bytes:
            return VoiceReminderResult(outcome=VoiceReminderOutcome.TOO_LARGE)
        if audio is not None and len(audio) > max_voice_bytes:
            return VoiceReminderResult(outcome=VoiceReminderOutcome.TOO_LARGE)
        if duration_seconds is not None and duration_seconds > settings.voice_max_duration_seconds:
            return VoiceReminderResult(outcome=VoiceReminderOutcome.TOO_LONG)

        return None

    async def reject_pending_edit_time(
        self,
        uow: UnitOfWork,
        *,
        telegram_user_id: int,
        username: str | None,
        locale: str | None,
        now: datetime,
        settings: Settings,
    ) -> VoiceReminderResult | None:
        user = await uow.users.get_or_create(
            telegram_user_id=telegram_user_id,
            username=username,
            locale=locale,
            timezone=settings.default_timezone,
            repeat_interval_minutes=settings.default_repeat_interval_minutes,
        )
        pending_edit_draft = await uow.drafts.get_pending_by_type_for_user(
            user_id=user.id,
            draft_type=DraftType.REMINDER_EDIT_TIME,
        )
        if pending_edit_draft is not None:
            now_utc = to_utc(now)
            if is_expired(pending_edit_draft, now_utc):
                pending_edit_draft.status = DraftStatus.EXPIRED
                pending_edit_draft.updated_at = now_utc
                await uow.session.flush()
            else:
                return VoiceReminderResult(outcome=VoiceReminderOutcome.PENDING_EDIT_TIME)

        return None

    async def transcribe_voice_audio(
        self,
        *,
        audio: bytes,
        source_file_unique_id: str,
        duration_seconds: int | None,
        settings: Settings,
    ) -> VoiceTranscriptionResult:
        return await self._transcriber.transcribe(
            audio,
            source_file_unique_id=source_file_unique_id,
            duration_seconds=duration_seconds,
            settings=settings,
        )

    async def process_voice_transcription(
        self,
        uow: UnitOfWork,
        *,
        telegram_user_id: int,
        username: str | None,
        locale: str | None,
        transcription: VoiceTranscriptionResult,
        mime_type: str | None,
        now: datetime,
        settings: Settings,
    ) -> VoiceReminderResult:
        pending_edit_result = await self.reject_pending_edit_time(
            uow,
            telegram_user_id=telegram_user_id,
            username=username,
            locale=locale,
            now=now,
            settings=settings,
        )
        if pending_edit_result is not None:
            return pending_edit_result

        if transcription.outcome == VoiceTranscriptionOutcome.EMPTY:
            return VoiceReminderResult(outcome=VoiceReminderOutcome.EMPTY_TRANSCRIPT)
        if transcription.outcome != VoiceTranscriptionOutcome.TRANSCRIBED:
            return VoiceReminderResult(
                outcome=VoiceReminderOutcome.TRANSCRIPTION_FAILED,
                error_message=transcription.error_message,
            )
        if transcription.transcript is None:
            return VoiceReminderResult(outcome=VoiceReminderOutcome.TRANSCRIPTION_FAILED)

        metadata = {
            "language": transcription.transcript.language,
            "duration_seconds": transcription.transcript.duration_seconds,
            "model": transcription.transcript.model,
            "source_file_unique_id": transcription.transcript.source_file_unique_id,
            "mime_type": mime_type,
        }

        text_result = await self._intake_service.handle_reminder_text(
            uow,
            telegram_user_id=telegram_user_id,
            username=username,
            locale=locale,
            text=transcription.transcript.text,
            source_type=ReminderSourceType.VOICE,
            source_metadata=metadata,
            now=now,
            settings=settings,
        )
        return VoiceReminderResult(
            outcome=VoiceReminderOutcome.PROCESSED,
            text_result=text_result,
        )

    async def warm_up(self, settings: Settings) -> None:
        await self._transcriber.warm_up(settings)


def _transcribe_with_model(
    model: object,
    audio: bytes,
    *,
    language: str,
) -> tuple[str, str | None]:
    with tempfile.NamedTemporaryFile(
        prefix="nudge_voice_",
        suffix=".ogg",
        delete=False,
    ) as temporary_audio:
        temporary_audio.write(audio)
        temporary_path = Path(temporary_audio.name)

    try:
        segments, info = model.transcribe(
            str(temporary_path),
            language=language,
            beam_size=1,
            best_of=1,
            without_timestamps=True,
            condition_on_previous_text=False,
            vad_filter=True,
        )
        text = " ".join(segment.text.strip() for segment in _consume_segments(segments))
        return text, getattr(info, "language", None)
    finally:
        temporary_path.unlink(missing_ok=True)


def _consume_segments(segments: Iterable[object]) -> list[object]:
    return list(segments)
