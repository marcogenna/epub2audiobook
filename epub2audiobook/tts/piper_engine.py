"""Piper TTS engine - fast, local neural TTS with auto-download of voice models."""

import logging
import urllib.request
import wave
from pathlib import Path
from typing import Optional

from epub2audiobook.models import TTSConfig
from epub2audiobook.tts.base import TTSEngine
from epub2audiobook.tts import register_engine

logger = logging.getLogger(__name__)

DEFAULT_MODELS_DIR = Path.home() / ".epub2audiobook" / "piper-models"

# HuggingFace base URL for Piper voice models
HF_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main"

# Voice catalog: voice_name → (hf_subpath, language, gender)
VOICE_CATALOG = {
    # Italian
    "it_IT-paola-medium": ("it/it_IT/paola/medium", "it", "Female"),
    "it_IT-riccardo-x_low": ("it/it_IT/riccardo/x_low", "it", "Male"),
    # English
    "en_US-lessac-medium": ("en/en_US/lessac/medium", "en", "Male"),
    "en_US-amy-medium": ("en/en_US/amy/medium", "en", "Female"),
    # Spanish
    "es_ES-davefx-medium": ("es/es_ES/davefx/medium", "es", "Male"),
    # French
    "fr_FR-siwis-medium": ("fr/fr_FR/siwis/medium", "fr", "Female"),
    # German
    "de_DE-thorsten-medium": ("de/de_DE/thorsten/medium", "de", "Male"),
}

DEFAULT_VOICES = {
    "it": "it_IT-paola-medium",
    "en": "en_US-lessac-medium",
    "es": "es_ES-davefx-medium",
    "fr": "fr_FR-siwis-medium",
    "de": "de_DE-thorsten-medium",
}


def _download_file(url: str, dest: Path) -> None:
    """Download a file with progress logging."""
    logger.info("Download: %s", url)
    dest.parent.mkdir(parents=True, exist_ok=True)

    tmp = dest.with_suffix(dest.suffix + ".tmp")
    try:
        urllib.request.urlretrieve(url, str(tmp))
        tmp.rename(dest)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def _ensure_model(voice_name: str, models_dir: Path) -> Path:
    """Ensure the voice model is downloaded, return path to .onnx file."""
    model_file = models_dir / f"{voice_name}.onnx"
    config_file = models_dir / f"{voice_name}.onnx.json"

    if model_file.exists() and config_file.exists():
        return model_file

    if voice_name not in VOICE_CATALOG:
        available = ", ".join(VOICE_CATALOG.keys())
        raise ValueError(
            f"Voce Piper sconosciuta: '{voice_name}'\n"
            f"Voci disponibili: {available}"
        )

    hf_subpath, _lang, _gender = VOICE_CATALOG[voice_name]

    logger.info("Scaricamento modello Piper '%s'...", voice_name)

    if not model_file.exists():
        onnx_url = f"{HF_BASE}/{hf_subpath}/{voice_name}.onnx"
        _download_file(onnx_url, model_file)

    if not config_file.exists():
        json_url = f"{HF_BASE}/{hf_subpath}/{voice_name}.onnx.json"
        _download_file(json_url, config_file)

    logger.info("Modello Piper '%s' pronto.", voice_name)
    return model_file


@register_engine("piper")
class PiperTTSEngine(TTSEngine):
    """TTS engine using Piper - fast local neural text to speech.

    Voice models are downloaded automatically on first use from HuggingFace.
    """

    def __init__(self):
        self._voice = None
        self.model_path: str | None = None

    def initialize(self) -> None:
        try:
            from piper import PiperVoice  # noqa: F401
        except ImportError:
            raise RuntimeError(
                "piper-tts non installato. Installa con:\n"
                "  pip install 'epub2audiobook[piper]'"
            )

    def _load_voice(self, config: TTSConfig) -> None:
        """Load the Piper voice model, downloading if needed."""
        from piper import PiperVoice

        if self.model_path:
            model_file = Path(self.model_path)
            if not model_file.exists():
                raise RuntimeError(f"Modello Piper non trovato: {model_file}")
        else:
            voice_name = config.voice or DEFAULT_VOICES.get(
                config.language, DEFAULT_VOICES["it"]
            )
            model_file = _ensure_model(voice_name, DEFAULT_MODELS_DIR)

        config_file = model_file.with_suffix(".onnx.json")

        logger.info("Caricamento modello Piper: %s", model_file.name)
        self._voice = PiperVoice.load(str(model_file), str(config_file))

    def synthesize(self, text: str, output_path: Path, config: TTSConfig) -> None:
        if self._voice is None:
            self._load_voice(config)

        with wave.open(str(output_path), "wb") as wav_file:
            self._voice.synthesize(text, wav_file)

    def list_voices(self, language: Optional[str] = None) -> list[dict]:
        voices = []
        for name, (_, lang, gender) in VOICE_CATALOG.items():
            if language and lang != language:
                continue
            voices.append({"name": name, "language": lang, "gender": gender})
        return voices

    @property
    def name(self) -> str:
        return "Piper TTS"

    @property
    def output_format(self) -> str:
        return "wav"
