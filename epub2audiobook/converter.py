"""Converter - orchestrates the full EPUB → TTS → M4B pipeline."""

import logging
import shutil
import tempfile
from pathlib import Path
from typing import Callable, Optional

from epub2audiobook.epub_parser import EpubParser
from epub2audiobook.metadata import fetch_cover_image, enrich_metadata
from epub2audiobook.tts.base import TTSEngine
from epub2audiobook.audio.audio_utils import probe_duration_ms
from epub2audiobook.audio.m4b_builder import build_m4b
from epub2audiobook.models import TTSConfig, ChapterAudio

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[int, int, str], None]


class Converter:
    """Orchestrates the full conversion pipeline."""

    def __init__(self, engine: TTSEngine, config: TTSConfig, bitrate: str = "64k"):
        self.engine = engine
        self.config = config
        self.bitrate = bitrate

    def convert(
        self,
        epub_path: str,
        output_path: str,
        on_progress: Optional[ProgressCallback] = None,
        work_dir: Optional[str] = None,
    ) -> None:
        """Full pipeline: EPUB → chapters → TTS → M4B.

        Args:
            epub_path: Path to the input EPUB file.
            output_path: Path for the output M4B file.
            on_progress: Callback(current, total, chapter_title) for progress.
            work_dir: Directory for intermediate files (enables resume). If None, uses a temp dir.
        """
        # 1. Parse EPUB
        logger.info("Parsing EPUB: %s", epub_path)
        parser = EpubParser(epub_path)
        metadata, chapters = parser.parse()
        logger.info(
            "Libro: '%s' di %s — %d capitoli",
            metadata.title, metadata.author, len(chapters),
        )

        # 1b. Enrich metadata from internet if EPUB data is incomplete
        metadata = self._enrich_metadata(metadata)

        # 2. Determine working directory
        cleanup_work_dir = work_dir is None
        work_path = Path(work_dir) if work_dir else Path(tempfile.mkdtemp(prefix="e2a_"))
        work_path.mkdir(parents=True, exist_ok=True)
        logger.info("Directory di lavoro: %s", work_path)

        try:
            # 3. Synthesize each chapter
            chapter_audios = []
            for chapter in chapters:
                ext = self.engine.output_format
                audio_path = work_path / f"chapter_{chapter.index:04d}.{ext}"

                # Resume: skip if audio file already exists with content
                if audio_path.exists() and audio_path.stat().st_size > 0:
                    logger.info("Riutilizzo audio esistente: %s", audio_path.name)
                else:
                    logger.info(
                        "Sintesi capitolo %d/%d: %s",
                        chapter.index + 1, len(chapters), chapter.title,
                    )
                    self.engine.synthesize(chapter.text, audio_path, self.config)

                duration = probe_duration_ms(audio_path)
                chapter_audios.append(ChapterAudio(
                    chapter=chapter,
                    audio_path=audio_path,
                    duration_ms=duration,
                ))

                if on_progress:
                    on_progress(chapter.index + 1, len(chapters), chapter.title)

            # 4. Assemble M4B
            logger.info("Assemblaggio M4B...")
            out = Path(output_path)
            build_m4b(chapter_audios, metadata, out, work_path, self.bitrate)
            logger.info("Audiobook creato: %s", out)

        finally:
            if cleanup_work_dir:
                shutil.rmtree(work_path, ignore_errors=True)

    @staticmethod
    def _enrich_metadata(metadata):
        """Try to fill in missing metadata (especially cover) from Open Library."""
        from epub2audiobook.models import BookMetadata

        if metadata.cover_image:
            logger.debug("Copertina già presente dall'EPUB, salto ricerca online")
            return metadata

        logger.info("Nessuna copertina nell'EPUB, ricerca online...")

        try:
            enriched = enrich_metadata(metadata.title, metadata.author)
        except Exception as e:
            logger.debug("Ricerca metadati online fallita: %s", e)
            return metadata

        cover = enriched.get("cover_image")
        if cover:
            logger.info("Copertina trovata online da Open Library")
            metadata = BookMetadata(
                title=metadata.title,
                author=metadata.author,
                language=metadata.language,
                cover_image=cover,
            )
        else:
            # Last resort: try a direct cover-only search
            try:
                cover = fetch_cover_image(metadata.title, metadata.author)
                if cover:
                    logger.info("Copertina trovata con ricerca diretta Open Library")
                    metadata = BookMetadata(
                        title=metadata.title,
                        author=metadata.author,
                        language=metadata.language,
                        cover_image=cover,
                    )
            except Exception as e:
                logger.debug("Ricerca copertina diretta fallita: %s", e)

        return metadata
