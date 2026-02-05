"""In-memory job tracking for web conversions."""

import threading
from typing import Optional


class JobManager:
    """Thread-safe in-memory job store.

    Status state machine: uploaded → converting → done | error
    """

    def __init__(self):
        self._jobs: dict[str, dict] = {}
        self._lock = threading.Lock()

    def create(
        self,
        job_id: str,
        *,
        epub_path: str,
        title: str,
        author: str,
        language: str,
        total_chapters: int,
        cover_image: bytes | None = None,
    ) -> dict:
        with self._lock:
            job = {
                "job_id": job_id,
                "status": "uploaded",
                "epub_path": epub_path,
                "output_path": None,
                "title": title,
                "author": author,
                "language": language,
                "total_chapters": total_chapters,
                "current_chapter": 0,
                "chapter_title": "",
                "error": None,
                "cover_image": cover_image,
            }
            self._jobs[job_id] = job
            return dict(job)

    def get(self, job_id: str) -> Optional[dict]:
        with self._lock:
            job = self._jobs.get(job_id)
            return dict(job) if job else None

    def update_status(self, job_id: str, status: str) -> None:
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id]["status"] = status

    def update_progress(self, job_id: str, current: int, total: int, title: str) -> None:
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id]["current_chapter"] = current
                self._jobs[job_id]["total_chapters"] = total
                self._jobs[job_id]["chapter_title"] = title

    def set_output(self, job_id: str, path: str) -> None:
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id]["output_path"] = path

    def set_error(self, job_id: str, error: str) -> None:
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id]["error"] = error
