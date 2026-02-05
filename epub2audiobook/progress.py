"""Progress reporting for the conversion pipeline."""

from tqdm import tqdm


class ProgressReporter:
    """Wraps tqdm for chapter-level progress reporting."""

    def __init__(self, total_chapters: int):
        self._bar = tqdm(
            total=total_chapters,
            desc="Conversione",
            unit="cap",
            bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} capitoli [{elapsed}<{remaining}]",
        )

    def update(self, current: int, total: int, chapter_title: str) -> None:
        """Update progress after a chapter is synthesized."""
        self._bar.set_postfix_str(chapter_title, refresh=False)
        self._bar.update(1)

    def close(self) -> None:
        self._bar.close()
