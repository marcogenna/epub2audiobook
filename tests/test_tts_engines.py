"""Tests for TTS engine registry and base interface."""

from epub2audiobook.tts import ENGINE_REGISTRY, register_engine, get_engine, list_engines
from epub2audiobook.tts.base import TTSEngine


class TestEngineRegistry:
    def test_edge_engine_registered(self):
        # Import to trigger registration
        import epub2audiobook.tts.edge_engine  # noqa: F401
        assert "edge" in ENGINE_REGISTRY

    def test_kokoro_engine_registered(self):
        import epub2audiobook.tts.kokoro_engine  # noqa: F401
        assert "kokoro" in ENGINE_REGISTRY

    def test_piper_engine_registered(self):
        import epub2audiobook.tts.piper_engine  # noqa: F401
        assert "piper" in ENGINE_REGISTRY

    def test_get_engine_returns_instance(self):
        import epub2audiobook.tts.edge_engine  # noqa: F401
        engine = get_engine("edge")
        assert isinstance(engine, TTSEngine)
        assert engine.name == "Edge TTS"
        assert engine.output_format == "mp3"

    def test_get_engine_unknown_raises(self):
        import pytest
        with pytest.raises(ValueError, match="Engine sconosciuto"):
            get_engine("non_esiste")

    def test_list_engines(self):
        import epub2audiobook.tts.edge_engine  # noqa: F401
        engines = list_engines()
        assert "edge" in engines


class TestEdgeEngineTextSplitting:
    def test_short_text_no_split(self):
        from epub2audiobook.tts.edge_engine import EdgeTTSEngine
        chunks = EdgeTTSEngine._split_text("Ciao mondo.")
        assert len(chunks) == 1

    def test_long_text_splits_at_sentences(self):
        from epub2audiobook.tts.edge_engine import EdgeTTSEngine
        # Create text longer than MAX_CHUNK_CHARS
        sentence = "Questa è una frase di test. "
        text = sentence * 200  # ~5600 chars
        chunks = EdgeTTSEngine._split_text(text)
        assert len(chunks) > 1
        # All chunks should be within limit (roughly)
        for chunk in chunks:
            assert len(chunk) <= 4000  # Some tolerance

    def test_speed_to_rate(self):
        from epub2audiobook.tts.edge_engine import EdgeTTSEngine
        assert EdgeTTSEngine._speed_to_rate(1.0) == "+0%"
        assert EdgeTTSEngine._speed_to_rate(1.2) == "+20%"
        assert EdgeTTSEngine._speed_to_rate(0.8) == "-20%"
