"""M4B audiobook builder - assembles chapter audio into a single M4B with chapter markers and cover art."""

import logging
import subprocess
from pathlib import Path

from epub2audiobook.audio.audio_utils import get_ffmpeg
from epub2audiobook.models import BookMetadata, ChapterAudio

logger = logging.getLogger(__name__)


def build_m4b(
    chapter_audios: list[ChapterAudio],
    metadata: BookMetadata,
    output_path: Path,
    temp_dir: Path,
    bitrate: str = "64k",
) -> None:
    """Assemble chapter audio files into a single M4B with chapter markers and cover art.

    Three-step process:
    1. Concatenate all chapter audio → single AAC stream
    2. Embed ffmetadata chapter markers → intermediate M4B
    3. If cover art available → embed it in the final M4B
    """
    # Step 1: Write concat file list
    concat_path = temp_dir / "concat.txt"
    with open(concat_path, "w") as f:
        for ch in chapter_audios:
            safe_path = str(ch.audio_path).replace("'", "'\\''")
            f.write(f"file '{safe_path}'\n")

    # Step 2: Write ffmetadata with chapter markers
    meta_path = temp_dir / "ffmetadata.txt"
    meta_content = _build_ffmetadata(chapter_audios, metadata)
    with open(meta_path, "w") as f:
        f.write(meta_content)

    ffmpeg = get_ffmpeg()

    # Step 3: Concatenate + encode to AAC
    intermediate = temp_dir / "combined.m4a"
    logger.info("Codifica audio in AAC (%s)...", bitrate)
    subprocess.run(
        [
            ffmpeg, "-y",
            "-f", "concat", "-safe", "0", "-i", str(concat_path),
            "-c:a", "aac", "-b:a", bitrate,
            str(intermediate),
        ],
        check=True,
        capture_output=True,
    )

    # Step 4: Mux chapter metadata
    # If we have a cover image, we'll do it in 2 sub-steps:
    #   4a: mux metadata → intermediate with chapters
    #   4b: add cover art → final output
    # Otherwise, mux metadata directly to final output.

    cover_path = _save_cover(metadata, temp_dir)

    if cover_path:
        # 4a: Mux chapters into intermediate M4B
        with_chapters = temp_dir / "with_chapters.m4b"
        logger.info("Aggiunta capitoli...")
        subprocess.run(
            [
                ffmpeg, "-y",
                "-i", str(intermediate),
                "-f", "ffmetadata", "-i", str(meta_path),
                "-map", "0:a",
                "-map_metadata", "1",
                "-c", "copy",
                str(with_chapters),
            ],
            check=True,
            capture_output=True,
        )

        # 4b: Embed cover art
        logger.info("Aggiunta copertina...")
        subprocess.run(
            [
                ffmpeg, "-y",
                "-i", str(with_chapters),
                "-i", str(cover_path),
                "-map", "0:a",           # Only audio from first input
                "-map", "1:v",           # Only video (cover) from second input
                "-c:a", "copy",          # Copy audio codec
                "-c:v", "copy",          # Copy video codec
                "-disposition:v:0", "attached_pic",
                "-metadata:s:v", "title=Cover",
                "-metadata:s:v", "comment=Cover (front)",
                str(output_path),
            ],
            check=True,
            capture_output=True,
        )
        with_chapters.unlink(missing_ok=True)
    else:
        # No cover: mux metadata directly to final output
        logger.info("Creazione M4B con capitoli...")
        subprocess.run(
            [
                ffmpeg, "-y",
                "-i", str(intermediate),
                "-f", "ffmetadata", "-i", str(meta_path),
                "-map", "0:a",
                "-map_metadata", "1",
                "-c", "copy",
                str(output_path),
            ],
            check=True,
            capture_output=True,
        )

    # Cleanup
    intermediate.unlink(missing_ok=True)
    logger.info("M4B creato: %s", output_path)


def _save_cover(metadata: BookMetadata, temp_dir: Path) -> Path | None:
    """Save cover image to temp dir if available, return path or None."""
    if not metadata.cover_image:
        return None

    # Detect format from magic bytes
    data = metadata.cover_image
    if data[:3] == b"\xff\xd8\xff":
        ext = ".jpg"
    elif data[:8] == b"\x89PNG\r\n\x1a\n":
        ext = ".png"
    else:
        ext = ".jpg"  # assume JPEG

    cover_path = temp_dir / f"cover{ext}"
    cover_path.write_bytes(data)
    logger.debug("Copertina salvata: %s (%d bytes)", cover_path, len(data))
    return cover_path


def _build_ffmetadata(
    chapter_audios: list[ChapterAudio], metadata: BookMetadata
) -> str:
    """Generate an ffmetadata string with chapter markers."""
    lines = [";FFMETADATA1"]
    lines.append(f"title={_escape(metadata.title)}")
    lines.append(f"artist={_escape(metadata.author)}")
    lines.append("")

    current_time_ms = 0
    for ch_audio in chapter_audios:
        lines.append("[CHAPTER]")
        lines.append("TIMEBASE=1/1000")
        lines.append(f"START={current_time_ms}")
        current_time_ms += ch_audio.duration_ms
        lines.append(f"END={current_time_ms}")
        lines.append(f"title={_escape(ch_audio.chapter.title)}")
        lines.append("")

    return "\n".join(lines)


def _escape(value: str) -> str:
    """Escape special characters for ffmetadata format."""
    # Must escape backslash first to avoid double-escaping
    value = value.replace("\\", "\\\\")
    for char in ("=", ";", "#", "\n"):
        value = value.replace(char, f"\\{char}")
    return value
