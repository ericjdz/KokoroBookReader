# Phase 2 GUI Design — PyQt6 Desktop Player

**Date:** 2026-04-05
**Status:** Approved
**Phase:** Phase 2 — Desktop GUI

## Architecture

### Technology Stack
- **GUI Framework:** PyQt6
- **Theme:** Catppuccin Mocha (dark, warm tones)
- **Layout:** Chapter sidebar (left, ~200px) + text view (center) + playback controls (bottom)
- **Threading:** QThread for core engine, signal/slot for UI updates

### File Structure
```
audiobook/
├── core/                  # Phase 1 engine (existing audiobook.py split)
│   └── (refactored from audiobook.py)
├── ui/
│   ├── __init__.py
│   ├── main_window.py     # QMainWindow, wires all components
│   ├── widgets.py         # PlaybackControls, ChapterSidebar, TextView, VoiceSpeedPanel
│   ├── theme.py           # Catppuccin Mocha QSS stylesheet
│   └── player_model.py    # QAbstractTableModel for chapter/sentence data
├── audiobook.py           # Entry point (CLI + GUI launcher)
└── test_audiobook.py      # Existing tests + new UI tests
```

## Components

### 1. MainWindow (`ui/main_window.py`)
- QMainWindow subclass
- Layout: QHBoxLayout (sidebar + text area) + QVBoxLayout (text + controls at bottom)
- Menu bar: File (Open PDF, Exit), Help (About)
- Window title: "PDF Audiobook — {filename}"
- Minimum size: 800x600
- Restores geometry from QSettings on startup

### 2. ChapterSidebar (`ui/widgets.py`)
- QTreeView backed by player_model
- Shows chapters with expandable sentence lists
- Click any sentence → emits `jump_to_sentence(index)` signal
- Current chapter highlighted in blue (Catppuccin #89b4fa)
- Width: ~200px, resizable via splitter

### 3. TextView (`ui/widgets.py`)
- QTextBrowser (read-only, supports rich text)
- Renders full text as HTML paragraphs
- Current sentence highlighted with yellow background (Catppuccin #f9e2af)
- Auto-scrolls to keep highlighted sentence visible
- Click any sentence → emits `jump_to_sentence(index)` signal
- Font: system default, 12px, line-height 1.7

### 4. PlaybackControls (`ui/widgets.py`)
- Custom QWidget with icon buttons: ⏮ ◀◀ ▶/⏸ ▶▶ ⏭
- QProgressBar for document progress (clickable to seek)
- Time display: "Sentence 142 / 3,847"
- Buttons emit signals: `play()`, `pause()`, `next()`, `previous()`, `chapter_forward()`, `chapter_back()`

### 5. VoiceSpeedPanel (`ui/widgets.py`)
- QComboBox for voice selection (populated from Kokoro available voices)
- QSlider for speed (0.5x–2.0x, step 0.1)
- Speed label: "1.0x"
- Emits `voice_changed(voice)` and `speed_changed(speed)` signals

### 6. PlayerModel (`ui/player_model.py`)
- QAbstractTableModel bridging core state to UI
- Columns: Chapter name, sentence count, status
- Updates via signals from core engine
- Thread-safe: all updates queued to main thread via QMetaObject.invokeMethod

## Data Flow

```
Core Engine (QThread)
    │
    ├── sentence_changed(index) ──→ TextView highlights sentence
    ├── chapter_changed(index) ───→ ChapterSidebar updates selection
    ├── state_changed(state) ─────→ PlaybackControls updates play/pause icon
    ├── progress_updated(pct) ────→ ProgressBar updates
    └── error_occurred(msg) ──────→ Error dialog / toast
    │
    ▲
    ├── jump_to_sentence(index) ──→ Core seeks to sentence
    ├── play() / pause() ─────────→ Core toggles playback
    ├── next() / previous() ──────→ Core advances/rewinds
    ├── chapter_forward() ────────→ Core jumps to next chapter
    ├── chapter_back() ───────────→ Core jumps to previous chapter
    ├── voice_changed(voice) ─────→ Core updates voice
    └── speed_changed(speed) ─────→ Core updates speed
```

## Theme (Catppuccin Mocha)

```
Base:       #1e1e2e  (background)
Surface0:   #181825  (sidebar, panels)
Surface1:   #313244  (borders, dividers)
Text:       #cdd6f4  (primary text)
Subtext0:   #a6adc8  (secondary text)
Overlay0:   #6c7086  (inactive text)
Blue:       #89b4fa  (accent, highlights, progress)
Yellow:     #f9e2af  (current sentence highlight)
Green:      #a6e3a1  (success states)
Red:        #f38ba8  (error states)
```

## Error Handling

| Error | Response |
|-------|----------|
| Kokoro model load failure | Dialog: "TTS model failed to load. Check espeak-ng installation." |
| PDF load failure | Dialog: "No text found. PDF may be scanned. OCR support coming soon." |
| Audio device unavailable | Dialog: "Audio device not found. Save to WAV instead?" |
| Synthesis error (mid-playback) | Non-blocking toast: "Synthesis failed for chunk N, skipping." |
| No PDF loaded | Placeholder text: "Open a PDF file to begin." |

## Testing Strategy

- Unit tests for theme.py (stylesheet generation)
- Unit tests for player_model.py (data binding)
- Integration tests for signal/slot connections
- Manual QA: load PDF, verify highlight sync, chapter navigation, voice/speed changes

## Dependencies

Add to requirements:
```
PyQt6>=6.6.0
```

## Implementation Notes

- Core engine (`audiobook.py`) remains unchanged — GUI wraps it via QThread
- No changes to CLI behavior — `python audiobook.py book.pdf` still works
- GUI launched via: `python audiobook.py --gui book.pdf` or `python audiobook_gui.py book.pdf`
- QSettings used for: window geometry, last opened PDF, voice preference, speed preference
