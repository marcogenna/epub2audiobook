"""Command-line interface for epub2audiobook."""

import argparse
import logging
import sys
from pathlib import Path

from epub2audiobook import __version__
from epub2audiobook.audio.audio_utils import check_ffmpeg
from epub2audiobook.models import TTSConfig


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="epub2audiobook",
        description="Converti libri EPUB in audiobook M4B",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    parser.add_argument(
        "input_file",
        nargs="?",
        help="File EPUB da convertire",
    )
    parser.add_argument(
        "output_file",
        nargs="?",
        help="File M4B di output (default: stesso nome dell'input con .m4b)",
    )

    parser.add_argument(
        "-e", "--engine",
        default="edge",
        choices=["edge", "kokoro", "piper"],
        help="Motore TTS da usare (default: edge)",
    )
    parser.add_argument(
        "-v", "--voice",
        default=None,
        help="Nome della voce (dipende dall'engine)",
    )
    parser.add_argument(
        "-s", "--speed",
        type=float,
        default=1.0,
        help="Velocità di lettura (default: 1.0)",
    )
    parser.add_argument(
        "--pitch",
        default=None,
        help="Regolazione pitch (dipende dall'engine, es. '+0Hz')",
    )
    parser.add_argument(
        "-l", "--language",
        default="it",
        help="Codice lingua (default: it)",
    )
    parser.add_argument(
        "--list-voices",
        action="store_true",
        help="Elenca le voci disponibili per l'engine selezionato ed esci",
    )
    parser.add_argument(
        "-b", "--bitrate",
        default="64k",
        help="Bitrate AAC per l'output M4B (default: 64k)",
    )
    parser.add_argument(
        "-w", "--work-dir",
        default=None,
        help="Directory per file intermedi (abilita il resume)",
    )
    parser.add_argument(
        "--piper-model",
        default=None,
        help="Percorso al modello Piper .onnx (richiesto per engine piper)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Abilita log dettagliati",
    )

    args = parser.parse_args(argv)

    # Configure logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    # Import engines (triggers registration)
    _import_engines()

    from epub2audiobook.tts import get_engine, list_engines

    # Handle --list-voices
    if args.list_voices:
        engine = get_engine(args.engine)
        engine.initialize()
        voices = engine.list_voices(args.language)
        if not voices:
            print(f"Nessuna voce trovata per lingua '{args.language}' con engine '{args.engine}'")
            sys.exit(0)
        print(f"\nVoci disponibili ({engine.name}, lingua: {args.language}):\n")
        for v in voices:
            gender = v.get("gender", "")
            print(f"  {v['name']:<35} {v['language']:<10} {gender}")
        sys.exit(0)

    # Validate input file
    if not args.input_file:
        parser.error("Specificare il file EPUB da convertire")

    input_path = Path(args.input_file)
    if not input_path.exists():
        parser.error(f"File non trovato: {input_path}")
    if not input_path.suffix.lower() == ".epub":
        parser.error(f"Il file deve essere un EPUB: {input_path}")

    # Determine output path
    if args.output_file:
        output_path = Path(args.output_file)
    else:
        output_path = input_path.with_suffix(".m4b")

    # Check ffmpeg
    check_ffmpeg()

    # Setup engine
    engine = get_engine(args.engine)

    # Pass piper model path if needed
    if args.engine == "piper" and args.piper_model:
        engine.model_path = args.piper_model

    engine.initialize()

    # Build TTS config
    config = TTSConfig(
        voice=args.voice or "",
        speed=args.speed,
        pitch=args.pitch,
        language=args.language,
    )

    # Run conversion
    from epub2audiobook.converter import Converter
    from epub2audiobook.progress import ProgressReporter

    converter = Converter(engine, config, bitrate=args.bitrate)

    # We create the progress reporter after parsing to know chapter count
    # Use a wrapper that lazily creates it
    progress = {"reporter": None}

    def on_progress(current: int, total: int, title: str) -> None:
        if progress["reporter"] is None:
            progress["reporter"] = ProgressReporter(total)
        progress["reporter"].update(current, total, title)

    try:
        converter.convert(
            epub_path=str(input_path),
            output_path=str(output_path),
            on_progress=on_progress,
            work_dir=args.work_dir,
        )
    except KeyboardInterrupt:
        print("\n\nConversione interrotta.")
        if args.work_dir:
            print(f"Puoi riprendere con: epub2audiobook {input_path} {output_path} -w {args.work_dir}")
        sys.exit(1)
    except Exception as e:
        logging.error("Errore: %s", e)
        if args.verbose:
            logging.exception("Dettagli:")
        sys.exit(1)
    finally:
        if progress["reporter"]:
            progress["reporter"].close()

    print(f"\nAudiobook creato: {output_path}")


def _import_engines() -> None:
    """Import all engine modules to trigger registration."""
    import epub2audiobook.tts.edge_engine  # noqa: F401
    import epub2audiobook.tts.kokoro_engine  # noqa: F401
    try:
        import epub2audiobook.tts.piper_engine  # noqa: F401
    except ImportError:
        pass  # piper-tts is optional


if __name__ == "__main__":
    main()
