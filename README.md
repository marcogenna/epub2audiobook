# epub2audiobook

Convert EPUB books to M4B audiobooks with AI-powered text-to-speech.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

https://github.com/user-attachments/assets/demo-placeholder

## Features

- **Multi-engine TTS** - Choose between Edge TTS (online, high quality) or Kokoro (offline)
- **M4B output** - Single audiobook file with chapter markers
- **Cover art** - Extracts from EPUB or fetches from Open Library
- **Web UI** - Drag-and-drop interface with real-time progress
- **CLI** - Batch conversion from terminal
- **Resume support** - Continue interrupted conversions
- **Italian optimized** - Smart text cleanup for natural TTS pronunciation

## Quick Start

```bash
# Install
pip install git+https://github.com/marcogenna/epub2audiobook.git

# Web UI
epub2audiobook-web
# Open http://127.0.0.1:8000

# CLI
epub2audiobook book.epub output.m4b
```

## Installation

### From GitHub

```bash
pip install git+https://github.com/marcogenna/epub2audiobook.git
```

### From source (for development)

```bash
git clone https://github.com/marcogenna/epub2audiobook.git
cd epub2audiobook
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Usage

### Web Interface

```bash
epub2audiobook-web --host 0.0.0.0 --port 8000
```

1. Drag and drop an EPUB file
2. Select TTS engine and voice
3. Click "Avvia conversione"
4. Download your audiobook

### Command Line

```bash
# Basic conversion
epub2audiobook book.epub

# With options
epub2audiobook book.epub output.m4b \
  --engine kokoro \
  --voice if_sara \
  --speed 1.2 \
  --language it

# List available voices
epub2audiobook --list-voices --engine edge --language it

# Resume interrupted conversion
epub2audiobook book.epub output.m4b --work-dir ./work
```

### CLI Options

| Option | Description | Default |
|--------|-------------|---------|
| `-e, --engine` | TTS engine (`edge`, `kokoro`) | `edge` |
| `-v, --voice` | Voice name | Engine default |
| `-s, --speed` | Speech rate (0.5-2.0) | `1.0` |
| `-l, --language` | Language code | `it` |
| `-b, --bitrate` | Audio bitrate | `64k` |
| `-w, --work-dir` | Working directory (enables resume) | temp |
| `--list-voices` | List available voices | - |

## TTS Engines

### Edge TTS (Online)
- High quality Microsoft voices
- Requires internet connection
- Many languages and voices available

```bash
epub2audiobook --list-voices --engine edge --language it
```

### Kokoro (Offline)
- High quality offline synthesis
- ~350MB model download on first use
- Italian voices: `if_sara` (F), `im_nicola` (M)

```bash
epub2audiobook book.epub --engine kokoro --voice if_sara
```

## Project Structure

```
epub2audiobook/
├── audio/           # FFmpeg integration, M4B builder
├── tts/             # TTS engine implementations
│   ├── base.py      # Abstract base class
│   ├── edge_engine.py
│   └── kokoro_engine.py
├── web/             # FastAPI web interface
├── cli.py           # Command-line interface
├── converter.py     # Main conversion pipeline
├── epub_parser.py   # EPUB parsing and text extraction
├── metadata.py      # Open Library API integration
└── models.py        # Data classes
```

## Contributing

Contributions are welcome! Here are some areas where help is needed:

### Good First Issues
- [ ] Add more languages to web UI dropdown
- [ ] Improve chapter title extraction
- [ ] Add unit tests for edge cases

### Feature Ideas
- [ ] Support for more TTS engines (Coqui, Bark, etc.)
- [ ] Batch conversion of multiple EPUBs
- [ ] Docker image for easy deployment
- [ ] Progress persistence across server restarts
- [ ] Audio preview before full conversion

### Development Setup

```bash
git clone https://github.com/marcogenna/epub2audiobook.git
cd epub2audiobook
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Run tests
pytest

# Run with auto-reload
uvicorn epub2audiobook.web.app:app --reload
```

### Code Style
- Python 3.11+ with type hints
- Black for formatting
- Ruff for linting

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

- [edge-tts](https://github.com/rany2/edge-tts) - Microsoft Edge TTS
- [Kokoro](https://github.com/hexgrad/kokoro) - Offline TTS
- [ebooklib](https://github.com/aerkalov/ebooklib) - EPUB parsing
- [static-ffmpeg](https://github.com/zackees/static-ffmpeg) - Bundled FFmpeg
