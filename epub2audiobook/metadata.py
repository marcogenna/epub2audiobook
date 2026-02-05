"""Internet metadata lookup - fetch cover art and book info from Open Library."""

import json
import logging
import urllib.request
import urllib.parse
from typing import Optional

logger = logging.getLogger(__name__)

OL_SEARCH_URL = "https://openlibrary.org/search.json"
OL_COVER_URL = "https://covers.openlibrary.org/b/id/{cover_id}-L.jpg"

# Timeout for HTTP requests (seconds)
REQUEST_TIMEOUT = 10


def fetch_cover_image(title: str, author: str = "") -> Optional[bytes]:
    """Try to fetch a cover image from Open Library.

    Args:
        title: Book title to search for.
        author: Book author (optional, improves accuracy).

    Returns:
        Cover image as JPEG bytes, or None if not found.
    """
    cover_id = _search_cover_id(title, author)
    if not cover_id:
        return None

    url = OL_COVER_URL.format(cover_id=cover_id)
    try:
        logger.info("Download copertina da Open Library: %s", url)
        req = urllib.request.Request(url, headers={"User-Agent": "epub2audiobook/0.1"})
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            data = resp.read()
            # Open Library returns a 1x1 pixel if no cover exists
            if len(data) < 1000:
                logger.debug("Copertina troppo piccola, probabilmente placeholder")
                return None
            return data
    except Exception as e:
        logger.debug("Errore download copertina: %s", e)
        return None


def enrich_metadata(
    title: str, author: str = ""
) -> dict:
    """Search Open Library for additional metadata about a book.

    Returns a dict with any found fields:
        - title, author, cover_image (bytes), description,
          publisher, publish_year, isbn, language
    """
    result = {}

    params = _build_search_params(title, author)
    if not params:
        return result

    try:
        query = urllib.parse.urlencode(params)
        url = f"{OL_SEARCH_URL}?{query}"
        logger.info("Ricerca metadati su Open Library: %s", url)

        req = urllib.request.Request(url, headers={"User-Agent": "epub2audiobook/0.1"})
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        logger.debug("Errore ricerca Open Library: %s", e)
        return result

    docs = data.get("docs", [])
    if not docs:
        logger.debug("Nessun risultato su Open Library per '%s'", title)
        return result

    book = docs[0]  # Best match

    result["title"] = book.get("title", "")
    result["publish_year"] = book.get("first_publish_year")
    result["publisher"] = (book.get("publisher") or [None])[0]
    result["isbn"] = (book.get("isbn") or [None])[0]

    authors = book.get("author_name", [])
    if authors:
        result["author"] = authors[0]

    # Cover
    cover_id = book.get("cover_i")
    if cover_id:
        result["cover_id"] = cover_id
        cover_data = _download_cover(cover_id)
        if cover_data:
            result["cover_image"] = cover_data

    return result


def _build_search_params(title: str, author: str = "") -> dict:
    """Build Open Library search query parameters."""
    if not title or title in ("Sconosciuto", "Unknown"):
        return {}

    params = {"title": title, "limit": "1", "fields": "title,author_name,cover_i,isbn,publisher,first_publish_year"}
    if author and author not in ("Sconosciuto", "Unknown"):
        params["author"] = author

    return params


def _search_cover_id(title: str, author: str = "") -> Optional[int]:
    """Search Open Library for a book's cover ID."""
    params = _build_search_params(title, author)
    if not params:
        return None

    params["fields"] = "cover_i"

    try:
        query = urllib.parse.urlencode(params)
        url = f"{OL_SEARCH_URL}?{query}"

        req = urllib.request.Request(url, headers={"User-Agent": "epub2audiobook/0.1"})
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        logger.debug("Errore ricerca copertina: %s", e)
        return None

    docs = data.get("docs", [])
    if docs and docs[0].get("cover_i"):
        return docs[0]["cover_i"]
    return None


def _download_cover(cover_id: int) -> Optional[bytes]:
    """Download cover image by Open Library cover ID."""
    url = OL_COVER_URL.format(cover_id=cover_id)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "epub2audiobook/0.1"})
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            data = resp.read()
            if len(data) < 1000:
                return None
            return data
    except Exception:
        return None
