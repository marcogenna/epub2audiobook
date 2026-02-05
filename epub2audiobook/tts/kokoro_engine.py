"""Kokoro TTS engine - open source, offline neural TTS."""

import logging
from pathlib import Path
from typing import Optional

from epub2audiobook.models import TTSConfig
from epub2audiobook.tts.base import TTSEngine
from epub2audiobook.tts import register_engine

logger = logging.getLogger(__name__)

# Kokoro language code prefixes
LANGUAGE_CODES = {
    "it": "i",
    "en": "a",  # American English
    "es": "e",
    "fr": "f",
    "de": "d",
    "ja": "j",
    "zh": "z",
}

# Default voices per language (Kokoro naming convention)
DEFAULT_VOICES = {
    "it": "if_sara",
    "en": "af_heart",
    "es": "ef_dora",
    "fr": "ff_siwis",
}

# Known voices for listing
KNOWN_VOICES = {
    "it": [
        {"name": "if_sara", "language": "it", "gender": "Female"},
        {"name": "im_nicola", "language": "it", "gender": "Male"},
    ],
    "en": [
        {"name": "af_heart", "language": "en", "gender": "Female"},
        {"name": "am_adam", "language": "en", "gender": "Male"},
    ],
}


@register_engine("kokoro")
class KokoroTTSEngine(TTSEngine):
    """TTS engine using Kokoro - lightweight open source neural TTS."""

    def __init__(self):
        self._pipeline = None

    def initialize(self) -> None:
        import kokoro  # noqa: F401
        import soundfile  # noqa: F401
        logger.info(
            "Kokoro TTS pronto. Al primo utilizzo il modello (~350 MB) "
            "verrà scaricato automaticamente da HuggingFace."
        )

    def synthesize(self, text: str, output_path: Path, config: TTSConfig) -> None:
        import numpy as np
        import soundfile as sf
        from kokoro import KPipeline

        lang_code = LANGUAGE_CODES.get(config.language, "i")

        if self._pipeline is None:
            logger.info("Caricamento modello Kokoro (lingua: %s)...", lang_code)
            self._pipeline = KPipeline(lang_code=lang_code)

        voice = config.voice or DEFAULT_VOICES.get(config.language, DEFAULT_VOICES["it"])
        speed = config.speed

        # Generate audio from text
        audio_segments = []
        for _graphemes, _phonemes, audio in self._pipeline(text, voice=voice, speed=speed):
            if audio is not None:
                audio_segments.append(audio)

        if not audio_segments:
            raise RuntimeError(f"Kokoro non ha prodotto audio per il testo (lunghezza: {len(text)})")

        # Concatenate all segments
        full_audio = np.concatenate(audio_segments)

        # Write WAV at 24kHz (Kokoro's native sample rate)
        sf.write(str(output_path), full_audio, 24000)

    def list_voices(self, language: Optional[str] = None) -> list[dict]:
        if language and language in KNOWN_VOICES:
            return KNOWN_VOICES[language]
        if language:
            return []
        # Return all known voices
        all_voices = []
        for voices in KNOWN_VOICES.values():
            all_voices.extend(voices)
        return all_voices

    @property
    def name(self) -> str:
        return "Kokoro TTS"

    @property
    def output_format(self) -> str:
        return "wav"
