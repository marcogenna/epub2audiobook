"""Tests for the converter orchestrator."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from epub2audiobook.converter import Converter
from epub2audiobook.models import TTSConfig, Chapter, BookMetadata


class TestConverter:
    def test_converter_skips_existing_audio_files(self, tmp_path):
        """Test resume: existing audio files should be reused."""
        engine = MagicMock()
        engine.output_format = "mp3"
        config = TTSConfig(voice="test", language="it")
        converter = Converter(engine, config)

        # Create a fake existing audio file
        audio_file = tmp_path / "chapter_0000.mp3"
        audio_file.write_bytes(b"fake mp3 data")

        # Mock the parser and other dependencies
        mock_metadata = BookMetadata(title="Test", author="Test", language="it")
        mock_chapters = [Chapter(index=0, title="Cap 1", text="Testo")]

        with (
            patch("epub2audiobook.converter.EpubParser") as MockParser,
            patch("epub2audiobook.converter.probe_duration_ms", return_value=5000),
            patch("epub2audiobook.converter.build_m4b"),
        ):
            MockParser.return_value.parse.return_value = (mock_metadata, mock_chapters)

            converter.convert(
                epub_path="test.epub",
                output_path=str(tmp_path / "out.m4b"),
                work_dir=str(tmp_path),
            )

            # Engine.synthesize should NOT have been called (file exists)
            engine.synthesize.assert_not_called()

    def test_converter_calls_synthesize_for_missing_files(self, tmp_path):
        """Test that synthesize is called when no cached audio exists."""
        engine = MagicMock()
        engine.output_format = "mp3"
        config = TTSConfig(voice="test", language="it")
        converter = Converter(engine, config)

        mock_metadata = BookMetadata(title="Test", author="Test", language="it")
        mock_chapters = [Chapter(index=0, title="Cap 1", text="Testo del capitolo")]

        with (
            patch("epub2audiobook.converter.EpubParser") as MockParser,
            patch("epub2audiobook.converter.probe_duration_ms", return_value=5000),
            patch("epub2audiobook.converter.build_m4b"),
        ):
            MockParser.return_value.parse.return_value = (mock_metadata, mock_chapters)

            converter.convert(
                epub_path="test.epub",
                output_path=str(tmp_path / "out.m4b"),
                work_dir=str(tmp_path),
            )

            engine.synthesize.assert_called_once()
