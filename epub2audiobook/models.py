"""Data models for the epub2audiobook pipeline."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class Chapter:
    """A single chapter extracted from an EPUB."""
    index: int
    title: str
    text: str


@dataclass
class BookMetadata:
    """Metadata extracted from the EPUB file."""
    title: str
    author: str
    language: str
    cover_image: Optional[bytes] = None


@dataclass
class TTSConfig:
    """Configuration for TTS synthesis."""
    voice: str
    speed: float = 1.0
    pitch: Optional[str] = None
    language: str = "it"


@dataclass
class ChapterAudio:
    """A synthesized chapter audio file with duration info."""
    chapter: Chapter
    audio_path: Path
    duration_ms: int
