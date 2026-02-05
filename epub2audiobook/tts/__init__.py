"""TTS engine registry and factory."""

from epub2audiobook.tts.base import TTSEngine

ENGINE_REGISTRY: dict[str, type[TTSEngine]] = {}


def register_engine(name: str):
    """Decorator to register a TTS engine class."""
    def decorator(cls):
        ENGINE_REGISTRY[name] = cls
        return cls
    return decorator


def get_engine(name: str) -> TTSEngine:
    """Instantiate a TTS engine by name."""
    if name not in ENGINE_REGISTRY:
        available = ", ".join(ENGINE_REGISTRY.keys()) or "(nessuno)"
        raise ValueError(f"Engine sconosciuto '{name}'. Disponibili: {available}")
    return ENGINE_REGISTRY[name]()


def list_engines() -> list[str]:
    """Return names of all registered engines."""
    return list(ENGINE_REGISTRY.keys())
