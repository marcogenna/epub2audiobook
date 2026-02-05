"""Tests for EPUB parser."""

import tempfile
from pathlib import Path

import pytest
from ebooklib import epub

from epub2audiobook.epub_parser import EpubParser


def _create_test_epub(path: str, chapters: list[tuple[str, str]]) -> None:
    """Create a minimal EPUB file for testing.

    Args:
        path: Where to write the EPUB.
        chapters: List of (title, html_body) tuples.
    """
    book = epub.EpubBook()
    book.set_identifier("test-book-001")
    book.set_title("Libro di Test")
    book.set_language("it")
    book.add_author("Autore Test")

    spine_items = ["nav"]
    toc = []

    for i, (title, body) in enumerate(chapters):
        ch = epub.EpubHtml(
            title=title,
            file_name=f"chap_{i:02d}.xhtml",
            lang="it",
        )
        ch.content = f"<html><body><h1>{title}</h1>{body}</body></html>".encode()
        book.add_item(ch)
        spine_items.append(ch)
        toc.append(ch)

    book.toc = toc
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = spine_items

    epub.write_epub(path, book)


class TestEpubParser:
    def test_parse_basic_epub(self, tmp_path):
        epub_path = str(tmp_path / "test.epub")
        _create_test_epub(epub_path, [
            ("Capitolo 1", "<p>Questo è il primo capitolo.</p>"),
            ("Capitolo 2", "<p>Questo è il secondo capitolo.</p>"),
        ])

        parser = EpubParser(epub_path)
        metadata, chapters = parser.parse()

        assert metadata.title == "Libro di Test"
        assert metadata.author == "Autore Test"
        assert metadata.language == "it"
        assert len(chapters) == 2
        assert chapters[0].title == "Capitolo 1"
        assert "primo capitolo" in chapters[0].text
        assert chapters[1].index == 1

    def test_parse_extracts_titles_from_headings(self, tmp_path):
        epub_path = str(tmp_path / "test.epub")
        _create_test_epub(epub_path, [
            ("Il Risveglio", "<p>Era una mattina fredda.</p>"),
        ])

        parser = EpubParser(epub_path)
        _, chapters = parser.parse()

        assert chapters[0].title == "Il Risveglio"

    def test_parse_multiple_chapters_preserves_order(self, tmp_path):
        """Chapters should be returned in spine order with correct indices."""
        epub_path = str(tmp_path / "test.epub")
        _create_test_epub(epub_path, [
            ("Primo", "<p>Contenuto primo.</p>"),
            ("Secondo", "<p>Contenuto secondo.</p>"),
            ("Terzo", "<p>Contenuto terzo.</p>"),
        ])

        parser = EpubParser(epub_path)
        _, chapters = parser.parse()

        assert len(chapters) == 3
        assert chapters[0].index == 0
        assert chapters[1].index == 1
        assert chapters[2].index == 2
        assert "primo" in chapters[0].text
        assert "terzo" in chapters[2].text

    def test_parse_cleans_html(self, tmp_path):
        epub_path = str(tmp_path / "test.epub")
        html = (
            "<p>Paragrafo uno.</p>"
            "<script>alert('xss')</script>"
            "<style>.foo{color:red}</style>"
            "<p>Paragrafo due.</p>"
        )
        _create_test_epub(epub_path, [("Test", html)])

        parser = EpubParser(epub_path)
        _, chapters = parser.parse()

        assert "alert" not in chapters[0].text
        assert "color" not in chapters[0].text
        assert "Paragrafo uno" in chapters[0].text
        assert "Paragrafo due" in chapters[0].text

    def test_parse_raises_on_nonexistent_file(self, tmp_path):
        """Attempting to parse a nonexistent file should raise."""
        parser = EpubParser(str(tmp_path / "nonexistent.epub"))
        with pytest.raises(Exception):
            parser.parse()
