# PDF Audiobook Player — User Guide

> A local, real-time audiobook player for PDF, EPUB, DOCX, and TXT documents.
> Powered by Kokoro TTS and PyQt6. Everything runs on your machine — no cloud, no subscriptions.

---

## Quick Start (5 minutes)

### 1. Install Dependencies

```bash
# Install Python packages
pip install -r requirements.txt

# Download NLTK tokenizer data
python -m nltk.downloader punkt punkt_tab

# Install espeak-ng (required by Kokoro TTS)
# Windows: Download installer from https://github.com/espeak-ng/espeak-ng/releases
# macOS:   brew install espeak-ng
# Linux:   sudo apt install espeak-ng
```

### 2. Launch the App

```bash
# GUI mode (recommended)
python audiobook_gui.py

# Or pass a file directly
python audiobook_gui.py path\to\book.pdf

# CLI mode (terminal-only)
python audiobook.py path\to\book.pdf
python audiobook.py --gui path\to\book.pdf
```

### 3. Open a Document

- Click **File → Open Document...** or press `Ctrl+O`
- Select a `.pdf`, `.epub`, `.docx`, or `.txt` file
- The app extracts text, detects chapters, and displays them in the sidebar

---

## Using the GUI

### Layout Overview

```
┌──────────────────────────────────────────────────────┐
│  File    Bookmark    Help                            │  ← Menu bar
├────────────┬─────────────────────────────────────────┤
│ 📚 Chapters│                                         │
│ Chapter 1  │  Lorem ipsum dolor sit amet,            │
│ Chapter 2  │  consectetur adipiscing elit.           │  ← Text view
│ Chapter 3  │  Sed do eiusmod tempor incididunt.      │     (highlighted
│            │                                         │      sentence in
│            │                                         │      yellow)
│            │                                         │
├────────────┼─────────────────────────────────────────┤
│ Voice: [▾] │  ⏮  ◀◀  ▶  ▶▶  ⏭                      │  ← Playback controls
│ Speed: ──●─│  ████████░░░░░░░░░░░░░░░  Sentence 3/47│     + progress bar
└────────────┴─────────────────────────────────────────┘
```

### Playback Controls

| Button | Action | Description |
|--------|--------|-------------|
| ⏮ | Chapter back | Jump to previous chapter |
| ◀◀ | Previous | Go to previous sentence |
| ▶ / ⏸ | Play / Pause | Start or pause playback |
| ▶▶ | Next | Skip to next sentence |
| ⏭ | Chapter forward | Jump to next chapter |

**Progress bar:** Click anywhere to jump to that position in the document.

### Chapter Sidebar

- Lists all detected chapters (Chapter 1, Part II, etc.)
- Click any chapter to jump directly to it
- Current chapter is highlighted in blue
- Shows progress within each chapter (e.g., "3 / 12 sentences")

### Voice & Speed Controls

- **Voice selector:** Choose from available Kokoro voices (af_heart, af_bella, etc.)
- **Voice Hub:** Open **Voices -> Voice Hub...** to add/download additional voice ids
- **Speed slider:** Adjust from 0.5x (slow) to 2.0x (fast)
- Settings are saved automatically and persist between sessions

#### Voice Prefix Meanings

- `af_*`: A-family female voice
- `am_*`: A-family male voice
- `bf_*`: B-family female voice
- `bm_*`: B-family male voice

### Text View

- Shows the full document text
- Current sentence is highlighted in **yellow**
- Text auto-scrolls to follow playback
- Click any sentence to jump to it

### Raw PDF View

- Use **View -> Raw PDF View** to switch from sentence text to the original PDF pages
- Use **Prev Page** / **Next Page** in the PDF pane for manual navigation
- Use **+ / -** and the zoom slider to control PDF size (25% to 400%)
- Use **Fit Width** to fill the pane width, or **Fit Page** to keep the full page visible
- Hold **Ctrl** and scroll the mouse wheel to zoom in/out quickly
- Normal mouse wheel scrolling moves up/down through the page
- Use **View -> Auto Sync PDF With Playback** to enable/disable automatic page jumps during playback
- Raw PDF view is available for `.pdf` files; other formats stay in text mode

---

## Bookmarking

### Save Your Position

- **File → Bookmark → Save Bookmark** (`Ctrl+S`)
- Saves your current sentence position, voice, and speed
- Stored in your system's app data directory

### Auto-Resume

When you reopen a document with a saved bookmark, the app asks:
> "Resume from chunk 142 (last played on 2026-04-05T12:00:00)?"

Click **Yes** to jump to your last position, or **No** to start fresh.

### Clear Bookmark

- **File → Bookmark → Clear Bookmark**
- Removes the saved position for the current document

---

## Export to Audio

### Export Full Document to WAV

- **File → Export to WAV...** (`Ctrl+E`)
- Select an output directory
- The app synthesizes the entire document and saves it as a single `.wav` file
- Useful for listening offline or transferring to other devices

**Note:** Export requires the `soundfile` package (`pip install soundfile`).

---

## Supported File Formats

| Format | Extension | Parser | Notes |
|--------|-----------|--------|-------|
| PDF | `.pdf` | PyMuPDF | Primary format, best results |
| EPUB | `.epub` | ebooklib + BeautifulSoup | Good chapter structure |
| DOCX | `.docx` | python-docx | Headings map to chapters |
| Text | `.txt` | Built-in | Simple, no formatting |

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+O` | Open document |
| `Ctrl+E` | Export to WAV |
| `Ctrl+S` | Save bookmark |
| `Ctrl+Q` | Quit |

---

## Troubleshooting

### "No text found" error
Your document may be **scanned/image-only** (not searchable text).
**Solution:** Run OCR first using a tool like [OCRmyPDF](https://github.com/ocrmypdf/OCRmyPDF).

### "TTS model failed to load" error
Kokoro requires `espeak-ng` for text-to-phoneme conversion.
**Solution:** Install espeak-ng (see Quick Start section).

### "Audio device not found" error
No audio output device is available.
**Solution:** Check your system audio settings, or use **Export to WAV** instead.

### First run is slow
Kokoro downloads ~330 MB of model data on first use.
**Solution:** This is a one-time download. Subsequent runs are fast.

### "Missing dependency" error
A required Python package isn't installed.
**Solution:** Run `pip install -r requirements.txt`.

### Slow synthesis on large documents
Long documents may take time to process.
**Solution:** The app uses async synthesis with lookahead buffering — playback starts while synthesis continues in the background.

---

## Configuration

User settings are stored in:
- **Windows:** `%LOCALAPPDATA%\pdf-audiobook\config.json`
- **macOS:** `~/Library/Application Support/pdf-audiobook/config.json`
- **Linux:** `~/.config/pdf-audiobook/config.json`

You can edit this file directly or use the in-app controls.

### Config Options

```json
{
  "voice": "af_heart",
  "speed": 1.0,
  "volume": 1.0,
  "view_mode": "text",
  "auto_pdf_sync": true,
  "back_cache_size": 10,
  "lookahead_size": 1,
  "last_opened_pdf": "",
  "window_geometry": "",
  "theme": "catppuccin_mocha",
  "auto_resume": true
}
```

---

## Performance Targets

| Metric | Target |
|--------|--------|
| Time to first audio | < 3 seconds |
| Per-sentence synthesis | < 300ms on CPU |
| Memory footprint | < 700 MB total |
| Skip/rewind response | < 500ms |
| CPU usage during playback | < 30% single core |

---

## Project Structure

```
audiobook/
├── audiobook.py              # Core engine + CLI entry point
├── audiobook_gui.py          # GUI entry point
├── test_audiobook.py         # Core engine tests (47 tests)
├── test_gui.py               # GUI tests (12 tests)
├── ui/
│   ├── __init__.py           # GUI package
│   ├── theme.py              # Catppuccin Moha stylesheet
│   ├── player_model.py       # Chapter navigation model
│   ├── widgets.py            # UI components (controls, sidebar, text view)
│   ├── main_window.py        # Main application window
│   ├── bookmark.py           # Bookmark save/restore
│   ├── config.py             # Configuration management
│   ├── document_extractor.py # Multi-format document parsing
│   └── export.py             # WAV export functionality
├── requirements.txt          # Python dependencies
├── README.md                 # Project overview
├── CHANGELOG.md              # Version history
├── REVISION_SUMMARY.md       # Detailed change summaries
└── pdf_audiobook_plan.md     # Full implementation plan
```

---

## Development

### Running Tests

```bash
# All tests
pytest test_audiobook.py test_gui.py -v

# Core engine only
pytest test_audiobook.py -v

# GUI only
pytest test_gui.py -v
```

### Current Test Status
- **59 tests passing** (1 skipped)
- 47 core engine tests
- 12 GUI tests

### Adding New Features

1. Write failing tests first (TDD)
2. Implement minimal code to pass
3. Run full test suite to verify no regressions
4. Commit frequently

---

## Future Enhancements

- Voice cloning (record your preferred narrator voice)
- Reading speed adaptation (auto-adjust for dense text)
- Sleep timer
- Highlight export (SRT subtitle format)
- Web version (FastAPI + browser-based synthesis)
- AI chapter summaries
- Multi-document playlist
- Accessibility improvements

---

## License & Credits

- **Kokoro TTS:** Local text-to-speech engine
- **PyQt6:** Cross-platform GUI framework
- **PyMuPDF:** PDF text extraction
- **NLTK:** Sentence tokenization
- **Catppuccin:** Dark theme color palette

Built with love for offline-first, privacy-respecting software.
