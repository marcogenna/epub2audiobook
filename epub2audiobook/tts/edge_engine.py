"""Edge TTS engine - free online neural TTS via Microsoft Edge."""

import asyncio
import logging
import re
import tempfile
from concurrent.futures import Future
from pathlib import Path
from threading import Thread
from typing import Optional

from epub2audiobook.models import TTSConfig
from epub2audiobook.tts.base import TTSEngine
from epub2audiobook.tts import register_engine

logger = logging.getLogger(__name__)

# Default voices per language
DEFAULT_VOICES = {
    "it": "it-IT-IsabellaNeural",
    "en": "en-US-AriaNeural",
    "es": "es-ES-ElviraNeural",
    "fr": "fr-FR-DeniseNeural",
    "de": "de-DE-KatjaNeural",
}

# Max characters per TTS request to avoid Edge TTS limits
MAX_CHUNK_CHARS = 3000


def _run_async(coro):
    """Run an async coroutine safely, even if an event loop is already running.

    When called from a sync context (e.g. CLI), uses asyncio.run().
    When called from within an existing event loop (e.g. FastAPI/uvicorn),
    runs the coroutine in a fresh event loop on a separate thread.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # No event loop running — safe to use asyncio.run()
        return asyncio.run(coro)

    # An event loop is already running — spin up a new one in a thread
    result = None
    exception = None

    def _target():
        nonlocal result, exception
        try:
            result = asyncio.run(coro)
        except Exception as e:
            exception = e

    t = Thread(target=_target)
    t.start()
    t.join()

    if exception:
        raise exception
    return result


@register_engine("edge")
class EdgeTTSEngine(TTSEngine):
    """TTS engine using Microsoft Edge's free online neural voices."""

    def initialize(self) -> None:
        import edge_tts  # noqa: F401

    def synthesize(self, text: str, output_path: Path, config: TTSConfig) -> None:
        _run_async(self._synthesize_async(text, output_path, config))

    async def _synthesize_async(
        self, text: str, output_path: Path, config: TTSConfig
    ) -> None:
        import edge_tts

        voice = config.voice or DEFAULT_VOICES.get(config.language, DEFAULT_VOICES["it"])
        rate = self._speed_to_rate(config.speed)
        pitch = config.pitch or "+0Hz"

        chunks = self._split_text(text)

        if len(chunks) == 1:
            communicate = edge_tts.Communicate(chunks[0], voice, rate=rate, pitch=pitch)
            await communicate.save(str(output_path))
        else:
            # Multiple chunks: synthesize each, then concatenate
            chunk_files = []
            try:
                for i, chunk in enumerate(chunks):
                    chunk_path = output_path.parent / f"{output_path.stem}_chunk{i:04d}.mp3"
                    communicate = edge_tts.Communicate(chunk, voice, rate=rate, pitch=pitch)
                    await communicate.save(str(chunk_path))
                    chunk_files.append(chunk_path)

                self._concat_mp3_files(chunk_files, output_path)
            finally:
                for f in chunk_files:
                    f.unlink(missing_ok=True)

    def list_voices(self, language: Optional[str] = None) -> list[dict]:
        return _run_async(self._list_voices_async(language))

    async def _list_voices_async(self, language: Optional[str] = None) -> list[dict]:
        import edge_tts

        voices = await edge_tts.list_voices()
        result = []
        for v in voices:
            locale = v.get("Locale", "")
            if language and not locale.lower().startswith(language.lower()):
                continue
            result.append({
                "name": v["ShortName"],
                "language": locale,
                "gender": v.get("Gender", ""),
            })
        return result

    @property
    def name(self) -> str:
        return "Edge TTS"

    @property
    def output_format(self) -> str:
        return "mp3"

    @staticmethod
    def _speed_to_rate(speed: float) -> str:
        """Convert speed multiplier (e.g. 1.2) to Edge TTS rate string (e.g. '+20%')."""
        percent = round((speed - 1.0) * 100)
        if percent >= 0:
            return f"+{percent}%"
        return f"{percent}%"

    @staticmethod
    def _split_text(text: str) -> list[str]:
        """Split text into chunks at sentence boundaries, respecting MAX_CHUNK_CHARS."""
        if len(text) <= MAX_CHUNK_CHARS:
            return [text]

        # Split on sentence-ending punctuation followed by whitespace
        sentences = re.split(r"(?<=[.!?…])\s+", text)

        chunks = []
        current_chunk = ""

        for sentence in sentences:
            if len(current_chunk) + len(sentence) + 1 > MAX_CHUNK_CHARS and current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = sentence
            else:
                current_chunk = f"{current_chunk} {sentence}" if current_chunk else sentence

        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        return chunks if chunks else [text]

    @staticmethod
    def _concat_mp3_files(files: list[Path], output_path: Path) -> None:
        """Concatenate multiple MP3 files using ffmpeg."""
        import subprocess
        from epub2audiobook.audio.audio_utils import get_ffmpeg

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            for mp3 in files:
                safe_path = str(mp3).replace("'", "'\\''")
                f.write(f"file '{safe_path}'\n")
            concat_list = f.name

        try:
            subprocess.run(
                [
                    get_ffmpeg(), "-y",
                    "-f", "concat", "-safe", "0",
                    "-i", concat_list,
                    "-c", "copy",
                    str(output_path),
                ],
                check=True,
                capture_output=True,
            )
        finally:
            Path(concat_list).unlink(missing_ok=True)
