"""EPUB file parser - extracts chapters and metadata."""

import logging
import re

import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup

from epub2audiobook.models import Chapter, BookMetadata

logger = logging.getLogger(__name__)


class EpubParser:
    """Parse an EPUB file into structured chapters and metadata."""

    def __init__(self, epub_path: str):
        self.epub_path = epub_path
        self._book: epub.EpubBook | None = None

    def parse(self) -> tuple[BookMetadata, list[Chapter]]:
        """Parse the EPUB and return metadata + ordered chapters."""
        self._book = epub.read_epub(self.epub_path)
        metadata = self._extract_metadata()
        chapters = self._extract_chapters()
        return metadata, chapters

    def _extract_metadata(self) -> BookMetadata:
        """Extract book metadata from EPUB Dublin Core fields."""
        title = self._book.get_metadata("DC", "title")
        author = self._book.get_metadata("DC", "creator")
        language = self._book.get_metadata("DC", "language")

        cover = self._extract_cover()

        return BookMetadata(
            title=title[0][0] if title else "Sconosciuto",
            author=author[0][0] if author else "Sconosciuto",
            language=language[0][0] if language else "it",
            cover_image=cover,
        )

    def _extract_cover(self) -> bytes | None:
        """Extract cover image from EPUB, trying multiple strategies."""
        # Strategy 1: ITEM_COVER type
        for item in self._book.get_items_of_type(ebooklib.ITEM_COVER):
            content = item.get_content()
            if content and len(content) > 1000:
                logger.debug("Copertina trovata via ITEM_COVER")
                return content

        # Strategy 2: metadata cover reference (most EPUBs use this)
        cover_meta = self._book.get_metadata("OPF", "cover")
        if cover_meta:
            cover_id = None
            for meta_val, meta_attrs in cover_meta:
                cover_id = meta_attrs.get("content") or meta_val
                break
            if cover_id:
                item = self._book.get_item_with_id(cover_id)
                if item:
                    content = item.get_content()
                    if content and len(content) > 1000:
                        logger.debug("Copertina trovata via OPF metadata: %s", cover_id)
                        return content

        # Strategy 3: look for image items with 'cover' in the name
        for item in self._book.get_items_of_type(ebooklib.ITEM_IMAGE):
            name = (item.get_name() or "").lower()
            item_id = (item.id or "").lower()
            if "cover" in name or "cover" in item_id:
                content = item.get_content()
                if content and len(content) > 1000:
                    logger.debug("Copertina trovata via nome file: %s", item.get_name())
                    return content

        logger.debug("Nessuna copertina trovata nell'EPUB")
        return None

    def _extract_chapters(self) -> list[Chapter]:
        """Extract chapters in spine (reading) order."""
        chapters = []
        index = 0

        for item_id, _ in self._book.spine:
            item = self._book.get_item_with_id(item_id)
            if item is None:
                continue

            html_content = item.get_body_content()
            if html_content is None:
                continue

            text = self._html_to_text(html_content)
            if not text.strip():
                logger.debug("Saltato elemento vuoto: %s", item_id)
                continue

            title = self._extract_title(html_content) or f"Capitolo {index + 1}"
            chapters.append(Chapter(index=index, title=title, text=text))
            index += 1

        if not chapters:
            raise ValueError(f"Nessun capitolo trovato in {self.epub_path}")

        logger.info("Estratti %d capitoli da '%s'", len(chapters), self.epub_path)
        return chapters

    def _html_to_text(self, html_content: bytes) -> str:
        """Convert HTML content to clean plain text suitable for TTS."""
        soup = BeautifulSoup(html_content, "lxml")

        # Remove non-text elements
        for tag in soup(["script", "style", "nav", "aside", "figure"]):
            tag.decompose()

        # Extract text from leaf block elements only (avoid parent divs that
        # contain child blocks, which would duplicate the text).
        leaf_tags = ["p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "blockquote"]
        leaves = soup.find_all(leaf_tags)

        if leaves:
            parts = []
            for tag in leaves:
                # Skip tags that themselves contain block-level children
                if tag.find(leaf_tags):
                    continue
                text = tag.get_text(strip=True)
                if text:
                    parts.append(text)
            text = "\n".join(parts)
        else:
            text = soup.get_text(separator="\n", strip=True)

        # --- TTS-friendly text cleanup ---
        text = self._clean_for_tts(text)
        return text.strip()

    @staticmethod
    def _clean_for_tts(text: str) -> str:
        """Clean extracted text for optimal TTS pronunciation."""

        # Normalize Unicode punctuation to ASCII equivalents
        replacements = {
            "\u2018": "'",   # left single quote  → '
            "\u2019": "'",   # right single quote  → '
            "\u201C": '"',   # left double quote   → "
            "\u201D": '"',   # right double quote  → "
            "\u2013": " ",   # en-dash  → space (TTS may read dash)
            "\u2014": " ",   # em-dash  → space
            "\u2026": "...", # ellipsis → three dots
            "\u00A0": " ",   # non-breaking space  → space
        }
        for old, new in replacements.items():
            text = text.replace(old, new)

        # Protect ellipsis by converting to placeholder
        text = text.replace("...", "\x00ELLIPSIS\x00")

        # Remove standalone/isolated periods that TTS reads as "punto"
        # Period preceded by whitespace/start or followed by whitespace/end (not part of word)
        text = re.sub(r"(?:^|(?<=\s))\.(?=\s|$)", "", text)

        # Remove lines that are just punctuation
        text = re.sub(r"^\s*[.\-–—,;:]+\s*$", "", text, flags=re.MULTILINE)

        # Ensure space after sentence-ending punctuation (.!?) if followed by letter
        text = re.sub(r"([.!?])([A-ZÀ-Úa-zà-ú])", r"\1 \2", text)

        # Handle Italian dialogue ending pattern: "–." or "– ." at end of quote
        # The dash closes the dialogue, the period ends the sentence - keep only period effect (pause)
        text = re.sub(r"[-–—]\s*\.\s*", ". ", text)
        text = re.sub(r"[-–—]\s*,\s*", ", ", text)

        # Remove remaining decorative patterns like ". –"
        text = re.sub(r"\s*\.\s*[-–—]\s*", ". ", text)

        # Remove period at start of line (after optional whitespace)
        text = re.sub(r"^\s*\.+\s*", "", text, flags=re.MULTILINE)

        # Restore ellipsis
        text = text.replace("\x00ELLIPSIS\x00", "...")

        # Clean up excessive whitespace
        text = re.sub(r" {2,}", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)

        return text

    def _extract_title(self, html_content: bytes) -> str | None:
        """Try to extract a chapter title from headings."""
        soup = BeautifulSoup(html_content, "lxml")
        for tag_name in ["h1", "h2", "h3", "title"]:
            tag = soup.find(tag_name)
            if tag:
                title = tag.get_text(strip=True)
                if title:
                    return title
        return None
