"""Tests for M4B builder metadata generation."""

from epub2audiobook.audio.m4b_builder import _build_ffmetadata, _escape
from epub2audiobook.models import BookMetadata, Chapter, ChapterAudio
from pathlib import Path


class TestFFMetadata:
    def test_build_ffmetadata_basic(self):
        metadata = BookMetadata(
            title="Il Libro",
            author="Mario Rossi",
            language="it",
        )
        chapters = [
            ChapterAudio(
                chapter=Chapter(index=0, title="Capitolo 1", text="..."),
                audio_path=Path("/tmp/ch0.mp3"),
                duration_ms=60000,
            ),
            ChapterAudio(
                chapter=Chapter(index=1, title="Capitolo 2", text="..."),
                audio_path=Path("/tmp/ch1.mp3"),
                duration_ms=90000,
            ),
        ]

        result = _build_ffmetadata(chapters, metadata)

        assert ";FFMETADATA1" in result
        assert "title=Il Libro" in result
        assert "artist=Mario Rossi" in result
        assert "[CHAPTER]" in result
        assert "START=0" in result
        assert "END=60000" in result
        assert "START=60000" in result
        assert "END=150000" in result
        assert "title=Capitolo 1" in result
        assert "title=Capitolo 2" in result

    def test_build_ffmetadata_cumulative_times(self):
        metadata = BookMetadata(title="Test", author="Test", language="it")
        chapters = [
            ChapterAudio(
                chapter=Chapter(index=i, title=f"Ch {i}", text="..."),
                audio_path=Path(f"/tmp/ch{i}.mp3"),
                duration_ms=30000,
            )
            for i in range(3)
        ]

        result = _build_ffmetadata(chapters, metadata)

        # Chapter 0: 0-30000, Chapter 1: 30000-60000, Chapter 2: 60000-90000
        assert "START=0" in result
        assert "END=30000" in result
        assert "START=30000" in result
        assert "END=60000" in result
        assert "START=60000" in result
        assert "END=90000" in result

    def test_escape_special_chars(self):
        # _escape replaces = with \= (single backslash + char)
        assert _escape("title=value") == r"title\=value"
        assert _escape("test;semi") == r"test\;semi"
        assert _escape("hash#tag") == r"hash\#tag"
