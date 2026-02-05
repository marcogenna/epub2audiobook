"""Audio utility functions - duration probing, format helpers, and ffmpeg paths."""

import json
import subprocess
from pathlib import Path

import static_ffmpeg


def get_ffmpeg_paths() -> tuple[str, str]:
    """Return (ffmpeg_path, ffprobe_path) using the bundled static-ffmpeg binaries.

    Downloads binaries on first use if not already present.
    """
    ffmpeg_path, ffprobe_path = static_ffmpeg.run.get_or_fetch_platform_executables_else_raise()
    return ffmpeg_path, ffprobe_path


def get_ffmpeg() -> str:
    """Return the path to the ffmpeg executable."""
    ffmpeg, _ = get_ffmpeg_paths()
    return ffmpeg


def get_ffprobe() -> str:
    """Return the path to the ffprobe executable."""
    _, ffprobe = get_ffmpeg_paths()
    return ffprobe


def check_ffmpeg() -> None:
    """Verify that ffmpeg and ffprobe are available (downloads if needed)."""
    try:
        get_ffmpeg_paths()
    except Exception as e:
        raise RuntimeError(
            f"Impossibile ottenere ffmpeg: {e}\n"
            f"Prova a reinstallare: pip install --force-reinstall static-ffmpeg"
        ) from e


def probe_duration_ms(audio_path: Path) -> int:
    """Get audio file duration in milliseconds using ffprobe."""
    ffprobe = get_ffprobe()
    result = subprocess.run(
        [
            ffprobe, "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            str(audio_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout)
    duration_seconds = float(data["format"]["duration"])
    return int(duration_seconds * 1000)
