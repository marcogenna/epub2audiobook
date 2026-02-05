"""FastAPI web interface for epub2audiobook."""

import asyncio
import json
import logging
import threading
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from epub2audiobook.web.jobs import JobManager

logger = logging.getLogger(__name__)


# --- Pydantic models ---

class ConvertRequest(BaseModel):
    engine: str = "edge"
    voice: str = ""
    speed: float = 1.0
    pitch: Optional[str] = None
    language: str = "it"
    bitrate: str = "64k"


# --- Engine registration ---

def _import_engines():
    """Import all engine modules to trigger registration."""
    import epub2audiobook.tts.edge_engine  # noqa: F401
    import epub2audiobook.tts.kokoro_engine  # noqa: F401
    try:
        import epub2audiobook.tts.piper_engine  # noqa: F401
    except ImportError:
        pass  # piper-tts is optional


# --- App factory ---

def create_app(data_dir: str = "./data") -> FastAPI:
    app = FastAPI(title="epub2audiobook", version="0.1.0")
    data_path = Path(data_dir).resolve()
    data_path.mkdir(parents=True, exist_ok=True)

    jobs = JobManager()
    _import_engines()

    # --- Routes ---

    @app.get("/", response_class=HTMLResponse)
    async def index():
        html_path = Path(__file__).parent / "static" / "index.html"
        return HTMLResponse(html_path.read_text(encoding="utf-8"))

    @app.get("/api/engines")
    async def list_engines_route():
        from epub2audiobook.tts import list_engines
        return {"engines": list_engines()}

    @app.get("/api/voices")
    async def list_voices_route(engine: str, language: str = "it"):
        from epub2audiobook.tts import get_engine
        try:
            eng = get_engine(engine)
            eng.initialize()
            voices = eng.list_voices(language)
            return {"voices": voices}
        except (ValueError, RuntimeError) as e:
            raise HTTPException(400, detail=str(e))

    @app.post("/api/upload")
    async def upload_epub(file: UploadFile):
        if not file.filename or not file.filename.lower().endswith(".epub"):
            raise HTTPException(400, detail="Il file deve essere un EPUB")

        job_id = uuid.uuid4().hex[:12]
        job_dir = data_path / job_id
        job_dir.mkdir(parents=True)

        epub_path = job_dir / file.filename
        content = await file.read()
        epub_path.write_bytes(content)

        # Parse metadata (fast, sync is fine)
        from epub2audiobook.epub_parser import EpubParser
        try:
            parser = EpubParser(str(epub_path))
            metadata, chapters = parser.parse()
        except Exception as e:
            raise HTTPException(400, detail=f"Errore nel parsing EPUB: {e}")

        # Try to fetch cover from internet if not in EPUB
        cover = metadata.cover_image
        if not cover:
            try:
                from epub2audiobook.metadata import fetch_cover_image
                cover = fetch_cover_image(metadata.title, metadata.author)
                if cover:
                    logger.info("Copertina trovata online per '%s'", metadata.title)
            except Exception as e:
                logger.debug("Ricerca copertina online fallita: %s", e)

        jobs.create(
            job_id,
            epub_path=str(epub_path),
            title=metadata.title,
            author=metadata.author,
            language=metadata.language,
            total_chapters=len(chapters),
            cover_image=cover,
        )

        return {
            "job_id": job_id,
            "title": metadata.title,
            "author": metadata.author,
            "language": metadata.language,
            "chapters": len(chapters),
            "has_cover": cover is not None,
        }

    @app.post("/api/convert/{job_id}", status_code=202)
    async def start_convert(job_id: str, req: ConvertRequest):
        job = jobs.get(job_id)
        if not job:
            raise HTTPException(404, detail="Job non trovato")
        if job["status"] != "uploaded":
            raise HTTPException(409, detail=f"Job già in stato: {job['status']}")

        jobs.update_status(job_id, "converting")

        def run_conversion():
            try:
                from epub2audiobook.tts import get_engine
                from epub2audiobook.converter import Converter
                from epub2audiobook.models import TTSConfig
                from epub2audiobook.audio.audio_utils import check_ffmpeg

                check_ffmpeg()

                engine = get_engine(req.engine)
                engine.initialize()

                config = TTSConfig(
                    voice=req.voice or "",
                    speed=req.speed,
                    pitch=req.pitch,
                    language=req.language,
                )

                epub_path = job["epub_path"]
                output_path = str(Path(epub_path).with_suffix(".m4b"))
                work_dir = str(Path(epub_path).parent / "work")

                converter = Converter(engine, config, bitrate=req.bitrate)

                def on_progress(current, total, title):
                    jobs.update_progress(job_id, current, total, title)

                converter.convert(
                    epub_path=epub_path,
                    output_path=output_path,
                    on_progress=on_progress,
                    work_dir=work_dir,
                )

                jobs.set_output(job_id, output_path)
                jobs.update_status(job_id, "done")

            except Exception as e:
                logger.exception("Conversione fallita per job %s", job_id)
                jobs.set_error(job_id, str(e))
                jobs.update_status(job_id, "error")

        thread = threading.Thread(target=run_conversion, daemon=True)
        thread.start()

        return {"job_id": job_id, "status": "converting"}

    @app.get("/api/progress/{job_id}")
    async def progress_stream(job_id: str):
        job = jobs.get(job_id)
        if not job:
            raise HTTPException(404, detail="Job non trovato")

        async def event_generator():
            last_chapter = -1
            while True:
                job = jobs.get(job_id)
                if not job:
                    break

                current = job.get("current_chapter", 0)
                status = job["status"]

                if current != last_chapter or status in ("done", "error"):
                    last_chapter = current
                    yield {
                        "event": "progress",
                        "data": json.dumps({
                            "status": status,
                            "current_chapter": current,
                            "total_chapters": job.get("total_chapters", 0),
                            "chapter_title": job.get("chapter_title", ""),
                        }),
                    }

                if status == "done":
                    yield {
                        "event": "done",
                        "data": json.dumps({"status": "done"}),
                    }
                    break

                if status == "error":
                    yield {
                        "event": "error",
                        "data": json.dumps({
                            "status": "error",
                            "error": job.get("error", "Errore sconosciuto"),
                        }),
                    }
                    break

                await asyncio.sleep(0.5)

        return EventSourceResponse(event_generator())

    @app.get("/api/jobs/{job_id}")
    async def get_job_status(job_id: str):
        job = jobs.get(job_id)
        if not job:
            raise HTTPException(404, detail="Job non trovato")
        # Don't serialize binary cover data in JSON
        safe_job = {k: v for k, v in job.items() if k != "cover_image"}
        safe_job["has_cover"] = job.get("cover_image") is not None
        return safe_job

    @app.get("/api/cover/{job_id}")
    async def get_cover(job_id: str):
        job = jobs.get(job_id)
        if not job or not job.get("cover_image"):
            raise HTTPException(404, detail="Copertina non disponibile")

        data = job["cover_image"]
        # Detect content type from magic bytes
        if data[:3] == b"\xff\xd8\xff":
            media_type = "image/jpeg"
        elif data[:8] == b"\x89PNG\r\n\x1a\n":
            media_type = "image/png"
        else:
            media_type = "image/jpeg"

        return Response(content=data, media_type=media_type)

    @app.get("/api/download/{job_id}")
    async def download(job_id: str):
        job = jobs.get(job_id)
        if not job or job["status"] != "done":
            raise HTTPException(404, detail="File non pronto")

        output = Path(job["output_path"])
        if not output.exists():
            raise HTTPException(404, detail="File non trovato")

        filename = f"{job.get('title', 'audiobook')}.m4b"
        return FileResponse(
            str(output),
            filename=filename,
            media_type="audio/mp4",
        )

    return app


# --- CLI entry point ---

def main():
    """Run the epub2audiobook web server."""
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description="epub2audiobook web interface")
    parser.add_argument("--host", default="127.0.0.1", help="Host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port (default: 8000)")
    parser.add_argument("--data-dir", default="./data", help="Directory per upload e output")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    app = create_app(data_dir=args.data_dir)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
