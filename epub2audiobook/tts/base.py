"""Abstract base class for TTS engines."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from epub2audiobook.models import TTSConfig


class TTSEngine(ABC):
    """Abstract base class that all TTS engines must implement."""

    @abstractmethod
    def initialize(self) -> None:
        """Initialize the engine (load models, check availability).

        Raises:
            RuntimeError: If the engine cannot be used (missing deps, etc.).
        """
        ...

    @abstractmethod
    def synthesize(self, text: str, output_path: Path, config: TTSConfig) -> None:
        """Synthesize text to an audio file.

        Args:
            text: Plain text to synthesize.
            output_path: Where to write the audio file.
            config: Voice, speed, pitch settings.

        Raises:
            RuntimeError: If synthesis fails.
        """
        ...

    @abstractmethod
    def list_voices(self, language: Optional[str] = None) -> list[dict]:
        """Return available voices, optionally filtered by language.

        Each dict contains at least 'name' and 'language' keys.
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable engine name."""
        ...

    @property
    @abstractmethod
    def output_format(self) -> str:
        """Audio format produced natively: 'wav' or 'mp3'."""
        ...
