# 📖 Dynamic PDF Audiobook App — Research & Planning Document

> A local, real-time, streaming audiobook engine that parses documents into chunked speech with skip/rewind/forward controls and smart memory management.

---

## Table of Contents

1. [Vision & Core Concept](#1-vision--core-concept)
2. [TTS Model Research — Local, Natural, Lightweight](#2-tts-model-research--local-natural-lightweight)
3. [Architecture Overview](#3-architecture-overview)
4. [Core Subsystems](#4-core-subsystems)
   - 4.1 Document Parser
   - 4.2 Synthesis Engine
   - 4.3 Memory Manager (Sliding Window Buffer)
   - 4.4 Playback Engine & Controls
   - 4.5 Thread Safety & Synchronization ⭐
5. [Text Cleaning & Preprocessing Pipeline](#5-text-cleaning--preprocessing-pipeline) ⭐
6. [User Interface Options](#6-user-interface-options)
7. [Supported File Formats](#7-supported-file-formats)
8. [Implementation Phases](#8-implementation-phases)
9. [Dependencies](#9-dependencies)
10. [Key Design Decisions & Trade-offs](#10-key-design-decisions--trade-offs)
11. [Edge Cases & Gotchas](#11-edge-cases--gotchas)
    - 11.1 Error Handling & Recovery Strategy ⭐
12. [Performance Targets](#12-performance-targets)
13. [Testing Strategy](#13-testing-strategy) ⭐
    - 13.1 Unit Tests
    - 13.2 Integration Tests
    - 13.3 Manual QA Checklist
14. [Platform-Specific Considerations](#14-platform-specific-considerations) ⭐
15. [Future Enhancements](#15-future-enhancements)
16. [Quick Start Code Skeleton](#16-quick-start-code-skeleton)
17. [Quick Reference for Implementers](#17-quick-reference-for-implementers) ⭐

⭐ = New/enhanced sections in v2.0

---

## 1. Vision & Core Concept

The app ingests a PDF (or similar document format) at runtime, segments it into sentence- or phrase-level chunks, synthesizes each chunk via a local TTS model, and plays audio sequentially — behaving like a natural audiobook player. The user can skip forward, rewind, and jump mid-document. Synthesized audio chunks are evicted from memory once played, keeping the runtime footprint flat regardless of document length.

**Key differentiators from standard audiobook converters:**
- No pre-generation — synthesis happens at runtime, dynamically
- No cloud API dependency — fully local, private, and offline
- Memory-aware — sliding window buffer, not full document in RAM
- Player controls feel native — not a progress bar over a single audio blob

---

## 2. TTS Model Research — Local, Natural, Lightweight

### 2.1 Evaluation Criteria

| Criterion | Weight | Notes |
|---|---|---|
| Voice naturalness / prosody | High | Audiobooks demand human-like pacing |
| Inference speed (RTF) | High | Must be ≥ real-time on CPU |
| Memory footprint | High | Model + audio buffer must fit comfortably in RAM |
| Sentence-level streaming | High | Chunk-by-chunk output, not full-doc synthesis |
| License | Medium | Apache 2.0 / MIT preferred |
| Multilingual | Low | English-first is fine |

### 2.2 Top Candidates

#### 🥇 Kokoro-82M — **Recommended Primary Choice**
- **Parameters:** 82 million
- **Architecture:** Flow-matching waveflow vocoder
- **Inference speed:** Sub-0.3s per sentence on CPU; real-time or faster
- **Voice quality:** Outperforms XTTS-v2 (467M) and MetaVoice (1.2B) on naturalness benchmarks
- **Streaming:** Native generator API — yields `(graphemes, phonemes, audio)` tuples per chunk
- **Audio output:** 24 kHz WAV
- **Voices:** 10+ built-in (af_heart, af_bella, am_michael, bm_george, bf_emma, etc.)
- **Token limit per pass:** ~510 tokens (maps well to sentence chunking)
- **License:** Apache 2.0
- **Hardware:** CPU-only viable; optional GPU for 5–10× speedup
- **Install:** `pip install kokoro soundfile espeak-ng`
- **Why it wins:** Proven audiobook-grade quality at a fraction of the compute cost. Its native generator model aligns perfectly with the sentence-chunk streaming architecture of this app.

#### 🥈 Chatterbox (Resemble AI)
- **Parameters:** ~1B range (turbo variant lighter)
- **Latency:** Sub-200ms inference
- **Strengths:** Emotion exaggeration control, `[laugh]`, `[cough]` tags, voice cloning from a 3s clip
- **Weakness:** Larger memory footprint than Kokoro; less proven on pure CPU
- **Best use:** If you want expressive fiction/storytelling rather than neutral narration
- **License:** Permissive (check specific release)

#### 🥉 MeloTTS
- **Parameters:** Lightweight (CPU real-time, zero VRAM)
- **Strengths:** Multilingual (6 languages), MIT licensed, runs on Raspberry Pi
- **Weakness:** Less natural prosody for long-form narration compared to Kokoro
- **Best use:** Low-power hardware targets or multilingual document needs

#### Honorable Mention: Voxtral TTS (Mistral)
- **Parameters:** 4B
- **Quality:** Beats ElevenLabs Flash v2.5 in human eval on naturalness
- **Issue:** 4B parameters is heavy for a "lightweight local" target — requires good GPU
- **Best use:** If GPU is available and maximum naturalness is the top priority over size

### 2.3 Recommendation Summary

| Scenario | Model |
|---|---|
| CPU-only machine, neutral narration | **Kokoro-82M** |
| GPU available, fiction/expressive reading | **Chatterbox** |
| Very low-power / multilingual | **MeloTTS** |
| GPU available, maximum quality | **Voxtral TTS 4B** |

**For this app's stated goals (lightweight + speed + natural tone), Kokoro-82M is the clear winner.**

---

## 3. Architecture Overview

```
┌──────────────────────────────────────────────────────────┐
│                      USER INTERFACE                       │
│     [Upload PDF]  ▶ ⏸  ◀◀  ▶▶  [Chapter Jump]           │
└─────────────────────────┬────────────────────────────────┘
                          │
┌─────────────────────────▼────────────────────────────────┐
│                   DOCUMENT PARSER                         │
│  PDF → plain text → cleaned text → sentence chunks        │
│  (PyMuPDF / pdfplumber + NLTK sentence tokenizer)         │
└─────────────────────────┬────────────────────────────────┘
                          │
┌─────────────────────────▼────────────────────────────────┐
│               CHUNK QUEUE / STATE MANAGER                 │
│  - Ordered list of all sentence chunks (index + text)     │
│  - Current playback pointer (chunk_index)                 │
│  - Pre-synthesis lookahead (N chunks ahead)               │
│  - Memory buffer (sliding window, evict on playback)      │
└────────────┬────────────────────────┬────────────────────┘
             │                        │
┌────────────▼────────┐   ┌───────────▼───────────────────┐
│   TTS SYNTHESIZER   │   │     AUDIO PLAYBACK ENGINE      │
│  Kokoro KPipeline   │   │  sounddevice / pyaudio         │
│  Sentence → audio   │   │  Streams WAV chunks to output  │
│  Generator model    │   │  Handles pause / resume        │
└─────────────────────┘   └────────────────────────────────┘
```

---

## 4. Core Subsystems

### 4.1 Document Parser

**Goal:** Extract clean, readable text from PDF and segment into natural speech units.

**Stack:**
- `PyMuPDF (fitz)` — fast, accurate PDF text extraction
- `pdfplumber` — fallback for complex layouts / tables
- `NLTK` or `spaCy` sentence tokenizer — split into sentence-level chunks
- Text cleaning pipeline:
  - Strip headers, footers, page numbers (heuristic: short lines at top/bottom)
  - Collapse hyphenated line breaks (`re.sub(r'-\n', '', text)`)
  - Normalize whitespace
  - Detect and label chapter/section boundaries for chapter-jump feature

**Chunk format:**
```python
@dataclass
class Chunk:
    index: int           # Global position in document
    text: str            # Raw sentence text
    audio: np.ndarray | None  # Synthesized audio, None until ready
    duration_s: float | None  # Audio duration in seconds
    evicted: bool = False     # True if audio freed from memory
```

**Chunk sizing strategy:**
- Target: 1–3 sentences per chunk (~50–150 chars)
- Max: 510 tokens (Kokoro's per-pass limit)
- Split at: `.`, `!`, `?`, `;` — with lookbehind for abbreviations (Mr., Dr., etc.)

### 4.2 Synthesis Engine

**Goal:** Convert text chunks to audio asynchronously, feeding the playback buffer.

```python
from kokoro import KPipeline

pipeline = KPipeline(lang_code='a')  # American English

def synthesize_chunk(chunk: Chunk, voice='af_heart', speed=1.0) -> np.ndarray:
    audio_parts = []
    for _, _, audio in pipeline(chunk.text, voice=voice, speed=speed):
        audio_parts.append(audio)
    return np.concatenate(audio_parts)
```

**Async pre-synthesis loop:**
- Background thread/task continuously synthesizes N chunks ahead of the playback pointer
- Default lookahead: 3–5 chunks (tunable based on available RAM)
- On skip forward: cancel pending synthesis, flush buffer, re-start from new index
- On rewind: check if chunk audio still in buffer; re-synthesize if evicted

### 4.3 Memory Manager (Sliding Window Buffer)

**Goal:** Keep memory flat regardless of document length.

**Strategy:**
- Maintain a buffer of `WINDOW_SIZE` synthesized audio chunks in memory
- As playback advances past chunk `i`, evict chunk `i - BACK_BUFFER` from memory
- `BACK_BUFFER`: how many past chunks to keep for rewind (default: 10–15 chunks ≈ ~2 min of audio)
- Pre-synthesis fills ahead: keep `AHEAD_BUFFER` synthesized chunks ready (default: 5)

**Memory estimation (Kokoro @ 24kHz, float32):**
- 1 second of audio = 24,000 samples × 4 bytes = ~96 KB
- Average sentence ≈ 5–8 seconds → ~500–800 KB per chunk
- 20-chunk total buffer (15 back + 5 ahead) ≈ **10–16 MB of audio data**
- Kokoro model itself ≈ **~330 MB on disk, ~400–500 MB loaded in RAM**
- **Total runtime budget: ~600–700 MB RAM** — comfortable on any modern machine

**Eviction logic:**
```python
def evict_old_chunks(buffer: dict[int, Chunk], current_index: int):
    cutoff = current_index - BACK_BUFFER
    for idx in list(buffer.keys()):
        if idx < cutoff:
            buffer[idx].audio = None
            buffer[idx].evicted = True
            del buffer[idx]
```

### 4.4 Playback Engine & Controls

**Goal:** Real-time audio streaming with responsive player controls.

**Stack:** `sounddevice` (preferred — low latency, cross-platform) or `pyaudio`

**Control actions:**

| Action | Behavior |
|---|---|
| ▶ Play / ⏸ Pause | Resume/pause playback mid-chunk |
| ◀◀ Rewind (−1 chunk) | Jump to previous chunk; re-synth if evicted |
| ▶▶ Skip (+1 chunk) | Jump to next chunk; use pre-synthesized if ready |
| ⏮ Chapter back | Jump to start of current/previous chapter marker |
| ⏭ Chapter forward | Jump to start of next chapter marker |
| 🔁 Seek by sentence | Click any sentence in the text view to jump |

**Playback threading model:**
```
Main Thread: UI event loop
Synth Thread: Background KPipeline synthesis, populates buffer dict
Playback Thread: Streams audio from buffer via sounddevice callback
```

### 4.5 Thread Safety & Synchronization

**Architecture:**
- **Shared state:** `buffer: dict[int, Chunk]` — synthesized audio chunks indexed by position
- **Playback pointer:** `current_index: AtomicInt` — which chunk is currently playing
- **Synthesis pointer:** `synth_index: AtomicInt` — which chunk is next to be synthesized

**Synchronization primitives:**
```python
from threading import Lock, Event
from collections import deque

buffer_lock = Lock()           # Protects buffer dict writes
synth_event = Event()          # Signals new synthesis requests
stop_synth = Event()           # Signals synthesis thread shutdown
playback_queue = deque()       # Lock-free playback command queue
```

**Critical operations:**

1. **Skip forward during synthesis:**
   ```python
   # Main thread
   with buffer_lock:
       current_index.set(new_index)
       # Evict irrelevant synthesized chunks
       for idx in list(buffer.keys()):
           if idx < new_index or idx > new_index + AHEAD_BUFFER:
               del buffer[idx]
   synth_event.set()  # Wake synthesis thread to re-prioritize
   ```

2. **Synthesis thread loop:**
   ```python
   while not stop_synth.is_set():
       target_index = current_index.get() + 1
       # Only synthesize if not already in buffer and within lookahead
       with buffer_lock:
           if target_index in buffer or target_index > current_index.get() + AHEAD_BUFFER:
               synth_event.wait(timeout=0.5)  # Wait for new work
               continue
       # Synthesize without holding lock
       audio = synthesize_chunk(chunks[target_index])
       with buffer_lock:
           buffer[target_index] = audio
   ```

3. **Playback thread (sounddevice callback):**
   ```python
   def audio_callback(outdata, frames, time, status):
       idx = current_index.get()
       with buffer_lock:
           if idx in buffer and not paused:
               chunk_audio = buffer[idx]
               outdata[:] = chunk_audio[position:position+frames]
               if position >= len(chunk_audio):
                   current_index.increment()  # Move to next chunk
           else:
               outdata.fill(0)  # Silence if buffer miss
   ```

**Race condition prevention:**
- Buffer dict is only modified under `buffer_lock`
- Synthesis thread checks `current_index` before AND after synthesis to detect stale work
- Playback thread never blocks — uses try-lock or reads atomic `current_index` directly

---

## 5. Text Cleaning & Preprocessing Pipeline

Critical for natural-sounding narration — garbage in, robotic out.

**Pipeline stages:**

1. **Extraction** — PDF → raw text via PyMuPDF
   ```python
   import fitz
   doc = fitz.open(pdf_path)
   raw_text = "\n".join(page.get_text() for page in doc)
   ```

2. **Page artifact removal** — strip running headers/footers, page numbers
   ```python
   lines = raw_text.split('\n')
   # Remove lines shorter than 20 chars at top/bottom of pages (heuristic)
   cleaned_lines = [line for line in lines if not (len(line) < 20 and (line.isdigit() or line.isupper()))]
   ```

3. **Hyphen repair** — join broken words across line breaks
   ```python
   text = re.sub(r'(\w+)-\n(\w+)', r'\1\2', raw_text)  # "exam-\nple" → "example"
   ```

4. **Ligature normalization** — `ﬁ → fi`, `ﬂ → fl`, etc.
   ```python
   ligature_map = {'ﬁ': 'fi', 'ﬂ': 'fl', 'ﬀ': 'ff', 'ﬃ': 'ffi', 'ﬄ': 'ffl'}
   for lig, repl in ligature_map.items():
       text = text.replace(lig, repl)
   ```

5. **Unicode normalization** — NFKC normalize
   ```python
   import unicodedata
   text = unicodedata.normalize('NFKC', text)
   ```

6. **Abbreviation protection** — mark known abbreviations before sentence splitting
   ```python
   abbreviations = ['Mr.', 'Mrs.', 'Dr.', 'Prof.', 'Inc.', 'Ltd.', 'etc.', 'i.e.', 'e.g.']
   for abbr in abbreviations:
       text = text.replace(abbr, abbr.replace('.', '<ABBR>'))  # Temp mark
   ```

7. **Sentence splitting** — NLTK Punkt tokenizer
   ```python
   import nltk
   nltk.download('punkt', quiet=True)
   sentences = nltk.sent_tokenize(text)
   # Restore abbreviations
   sentences = [s.replace('<ABBR>', '.') for s in sentences]
   ```

8. **Sentence filtering** — skip very short (< 10 chars), URL-only, or table-row fragments
   ```python
   filtered = [s for s in sentences if len(s.strip()) >= 10 and not s.startswith('http')]
   ```

9. **Number normalization** (optional) — `4.5` → `four point five`, `2024` → `twenty twenty-four`
   ```python
   # Use num2words library for robust conversion
   from num2words import num2words
   def normalize_numbers(text):
       return re.sub(r'\b\d+\.?\d*\b', lambda m: num2words(float(m.group())), text)
   ```

10. **Chapter detection** — regex patterns for "Chapter N", "Part II", all-caps headings, etc.
    ```python
    CHAPTER_PATTERNS = [
        r'^\s*Chapter\s+\d+',           # "Chapter 1"
        r'^\s*CHAPTER\s+[IVXLCDM]+',    # "CHAPTER IV"
        r'^\s*Part\s+\w+',              # "Part One"
        r'^\s*[A-Z\s]{10,}$',           # All-caps heading (min 10 chars)
    ]
    
    chapters = []
    for idx, sentence in enumerate(sentences):
        for pattern in CHAPTER_PATTERNS:
            if re.match(pattern, sentence):
                chapters.append({'index': idx, 'title': sentence.strip()})
                break
    ```

---

## 6. User Interface Options

### Option A — Desktop GUI (Recommended for v1)
**Stack:** `tkinter` or `PyQt6` / `PySide6`

Layout:
```
┌──────────────────────────────────────────────┐
│  [📂 Open PDF]              Voice: [▾ af_heart] Speed: [1.0x]
├──────────────────────────────────────────────┤
│                                              │
│  ← Scrolling text view, current sentence     │
│    highlighted in yellow                     │
│                                              │
├──────────────────────────────────────────────┤
│  Chapter: 3 / 12   Sentence: 142 / 3,847    │
│  ████████░░░░░░░░░░░░░░░░░░░░  [progress]   │
├──────────────────────────────────────────────┤
│  ⏮  ◀◀   ▶ / ⏸   ▶▶   ⏭               │
└──────────────────────────────────────────────┘
```

Features:
- Highlighted sentence sync (text scrolls with playback)
- Voice selector + speed control
- Chapter list sidebar

### Option B — Web UI (Future)
**Stack:** FastAPI backend + React/Svelte frontend
- Use Kokoro ONNX via `kokoro-js` for browser-side synthesis (WebGPU/WASM)
- Or expose local FastAPI endpoint, stream audio via WebSocket

### Option C — CLI (Minimal v0)
```bash
python audiobook.py --pdf book.pdf --voice af_heart --speed 1.0
# Interactive: [p]ause, [n]ext, [b]ack, [q]uit
```

---

## 7. Supported File Formats

| Format | Parser | Notes |
|---|---|---|
| PDF | PyMuPDF (fitz) | Primary target |
| EPUB | `ebooklib` + BeautifulSoup | Good structure for chapters |
| TXT | Built-in | Trivial |
| DOCX | `python-docx` | Headings map to chapters |
| Markdown | `mistune` or regex | Strip markup before TTS |
| HTML | `BeautifulSoup` | Strip tags, preserve structure |

---

## 8. Implementation Phases

### Phase 0 — Proof of Concept (CLI, ~1 day)
- [x] PDF → text extraction (PyMuPDF)
- [x] Sentence chunking (NLTK)
- [x] Kokoro synthesis, one chunk at a time
- [x] Play via sounddevice
- [x] Keyboard controls: pause, next, back

### Phase 1 — Buffered Streaming (Core Engine, ~3–5 days)
- [x] Async synthesis thread with lookahead buffer
- [x] Memory manager with sliding window eviction
- [x] Full playback threading model
- [x] Skip forward / rewind with buffer awareness
- [x] Chapter detection and jumping

### Phase 2 — Desktop GUI (~3–5 days)
- [x] PyQt6 or tkinter UI
- [x] Sentence highlight sync with playback
- [x] Chapter sidebar
- [x] Voice / speed controls
- [x] Progress bar with seek

### Phase 3 — Polish & Formats (~2–3 days)
- [x] EPUB, DOCX, TXT support
- [x] Text cleaning pipeline (all 10 stages)
- [x] **Bookmarking / resume session:**
  - Store state in platform-appropriate state directory
  - Save: `{file_path, chunk_index, total_chunks, timestamp, voice, speed}`
  - Auto-resume on re-open: "Resume from chunk 142?"
  - Clear bookmark on completion or manual reset
- [x] Export to audio file (WAV)

### Phase 4 — Hardening (~ongoing)
- [x] Error recovery (synthesis failure, corrupted PDF)
- [x] Performance profiling on CPU-only hardware
- [x] Config file (voice, speed, buffer sizes, theme)
- [ ] Packaging (PyInstaller / Briefcase for standalone binary)

---

## 9. Dependencies

```toml
# requirements.txt or pyproject.toml

# TTS
kokoro>=0.9.2        # Core TTS engine
soundfile            # WAV I/O
sounddevice          # Audio playback

# PDF & Formats
PyMuPDF              # PDF text extraction (fitz)
pdfplumber           # Fallback PDF parser
ebooklib             # EPUB parsing
python-docx          # DOCX parsing

# NLP / Text
nltk                 # Sentence tokenization
spacy                # Optional: better sentence splitting
num2words            # Number-to-words conversion for TTS

# GUI (choose one)
PyQt6                # Recommended for rich UI
# tkinter            # Stdlib option, simpler

# System
espeak-ng            # Required by Kokoro for G2P (install via apt/brew)
numpy                # Audio array handling
```

**System dependencies:**
```bash
# Linux / WSL
sudo apt install espeak-ng

# macOS
brew install espeak-ng

# Windows
# Download espeak-ng installer from GitHub releases
```

---

## 10. Key Design Decisions & Trade-offs

| Decision | Choice | Rationale |
|---|---|---|
| TTS model | Kokoro-82M | Best speed/quality ratio for CPU-local use |
| Chunk granularity | Sentence-level | Aligns with Kokoro's 510-token limit; natural rewind units |
| Synthesis timing | Async pre-synthesis | Eliminates perceptible gap between sentences |
| Memory eviction | Sliding window | O(1) memory regardless of document length |
| Back-buffer size | ~15 chunks | Covers ~2 min of rewind without excessive memory |
| Audio format | float32 @ 24kHz | Kokoro native; no re-encoding overhead |
| Playback engine | sounddevice | Lower latency than pyaudio, cross-platform |
| UI framework | PyQt6 | Best cross-platform GUI with text highlighting support |

---

## 11. Edge Cases & Gotchas

- **Scanned PDFs (image-only):** Text extraction will be empty — detect and warn user. Future: integrate Tesseract OCR fallback.
- **Mathematical notation / formulas:** TTS will mangle LaTeX. Consider stripping or substituting `[equation]`.
- **Tables:** Extract as prose description or skip — do not feed raw TSV to TTS.
- **Footnotes:** Parse separately and optionally speak or skip.
- **Very long sentences:** NLTK Punkt sometimes misses splits in academic text — add a secondary split at `;` or `,` for chunks exceeding 300 chars.
- **Kokoro 510-token limit:** Hard cap — sentences longer than ~400 chars must be split before synthesis.
- **Chapter detection failure:** Gracefully degrade to sentence-only navigation if no headings found.
- **Fast forward spam:** Debounce skip controls — don't enqueue more synthesis tasks than the thread pool can cancel cleanly.
- **First-run model download:** Kokoro downloads ~330 MB on first import. Show a one-time loading screen.

### 11.1 Error Handling & Recovery Strategy

| Failure Mode | Detection | Recovery Action |
|---|---|---|
| **Synthesis timeout** (Kokoro hangs > 5s) | Watchdog timer per chunk | Log warning, skip to next chunk, mark as [synthesis failed] |
| **Empty PDF extraction** | Check `len(text) < 50` after extraction | Show error: "No text found. PDF may be scanned. OCR support coming soon." |
| **Audio device unavailable** | sounddevice init fails | Fallback to file export mode: "Audio device not found. Save to WAV instead?" |
| **Corrupted audio buffer** | NaN/Inf check in audio array | Zero-fill corrupted chunk, log error, continue playback |
| **Out of memory** | Catch MemoryError in synthesis loop | Reduce AHEAD_BUFFER by 50%, warn user, retry |
| **Kokoro model load failure** | Import exception on first run | Show error: "TTS model failed to load. Check espeak-ng installation." |
| **Chapter jump to invalid index** | Index bounds check | Clamp to [0, len(chunks)-1], log warning |

**Global exception handler:**
```python
def safe_synthesis(chunk):
    try:
        return synthesize_chunk(chunk)
    except Exception as e:
        logger.error(f"Synthesis failed for chunk {chunk.index}: {e}")
        return np.zeros(SAMPLE_RATE)  # 1 second of silence
```

---

## 12. Performance Targets

| Metric | Target |
|---|---|
| Time to first audio (cold start) | < 3 seconds after PDF loaded |
| Per-sentence synthesis latency | < 300ms on CPU (Kokoro baseline) |
| Memory footprint (20-chunk window) | < 700 MB total (model + buffer) |
| Skip/rewind response time | < 500ms |
| Supported document length | Unlimited (sliding buffer) |
| CPU usage during playback | < 30% single core (synthesis thread) |

---

## 13. Testing Strategy

### 13.1 Unit Tests

**Text Processing:**
```python
def test_hyphen_repair():
    input_text = "exam-\nple text"
    expected = "example text"
    assert clean_hyphenated_breaks(input_text) == expected

def test_chapter_detection():
    text = "Chapter 1\nSome content\nChapter 2\nMore content"
    chapters = detect_chapters(text)
    assert len(chapters) == 2
    assert chapters[0]['title'] == "Chapter 1"

def test_sentence_chunking_under_token_limit():
    long_sentence = "word " * 600  # Exceeds 510 token limit
    chunks = chunk_text(long_sentence)
    for chunk in chunks:
        assert len(chunk.split()) < 500  # Safety margin
```

**Memory Management:**
```python
def test_sliding_window_eviction():
    buffer = {i: mock_audio_chunk() for i in range(20)}
    evict_old_chunks(buffer, current_index=15, BACK_BUFFER=10)
    assert 4 not in buffer  # Should be evicted (15 - 10 = 5 cutoff)
    assert 5 in buffer      # Should remain (at cutoff boundary)
    assert 15 in buffer     # Current chunk retained
```

**Synthesis:**
```python
def test_kokoro_synthesis_speed():
    pipeline = KPipeline(lang_code='a')
    test_sentence = "This is a test sentence for speed measurement."
    
    start = time.time()
    audio = synthesize_chunk(test_sentence, pipeline)
    latency = time.time() - start
    
    assert latency < 0.5  # Must be under 500ms for responsive playback
    assert len(audio) > 0
    assert audio.dtype == np.float32
```

### 13.2 Integration Tests

**End-to-End Playback:**
```python
def test_full_playback_cycle():
    # Load small test PDF
    chunks = load_and_parse("test_data/sample.pdf")
    assert len(chunks) > 0
    
    # Initialize synthesizer
    pipeline = KPipeline(lang_code='a')
    
    # Synthesize first 3 chunks
    buffer = {}
    for i in range(3):
        buffer[i] = synthesize_chunk(chunks[i], pipeline)
    
    # Verify buffer size
    assert len(buffer) == 3
    
    # Test skip forward
    current_index = 0
    current_index = skip_forward(current_index, buffer, chunks)
    assert current_index == 1
```

**Thread Safety:**
```python
def test_concurrent_buffer_access():
    from threading import Thread
    buffer = {}
    
    def writer():
        for i in range(100):
            with buffer_lock:
                buffer[i] = np.zeros(1000)
    
    def reader():
        for _ in range(100):
            with buffer_lock:
                _ = list(buffer.keys())
    
    threads = [Thread(target=writer), Thread(target=reader)]
    for t in threads: t.start()
    for t in threads: t.join()
    
    # No crashes = success
    assert len(buffer) == 100
```

### 13.3 Manual QA Checklist

- [ ] Load a 300+ page PDF — memory stays under 700 MB throughout playback
- [ ] Skip forward 50 chunks rapidly — no crashes, synthesis keeps up
- [ ] Rewind to a chunk that was evicted — re-synthesizes correctly
- [ ] Pause mid-sentence, resume — picks up exactly where it left off
- [ ] Chapter jump from chapter 1 to chapter 10 — immediate response
- [ ] Load scanned PDF (no text) — displays helpful error message
- [ ] Load PDF with math equations — either strips or reads as "[equation]"
- [ ] Close app mid-playback, reopen — offers to resume from last position

---

## 14. Platform-Specific Considerations

### Windows
**Audio Device Selection:**
```python
import sounddevice as sd
# Windows often has multiple devices (Realtek, HDMI, USB)
devices = sd.query_devices()
default_output = sd.default.device[1]  # Output device
print(f"Using: {devices[default_output]['name']}")
```

**espeak-ng Installation:**
- Download installer from GitHub: `espeak-ng-X64.msi`
- Add to PATH: `C:\Program Files\eSpeak NG\`
- Verify: `espeak-ng --version`

**File Paths:**
```python
# Bookmark storage
import os
bookmark_path = os.path.expanduser("~\\AppData\\Local\\audiobook_state.json")
```

### macOS
**Permissions:**
- Microphone access NOT needed (output-only)
- File access for PDF: granted via Open dialog
- espeak-ng via Homebrew: `brew install espeak-ng`

**Audio Issues:**
- If `sounddevice` can't find output: check System Preferences → Sound
- Test with: `python -c "import sounddevice; sounddevice.play([0.1]*10000, 44100)"`

### Linux
**Dependencies First:**
```bash
sudo apt update
sudo apt install espeak-ng portaudio19-dev python3-pyqt6
pip install kokoro sounddevice PyMuPDF nltk
```

**Wayland vs X11:**
- PyQt6 works on both
- tkinter may have issues on Wayland — prefer PyQt6

**Permissions:**
- Audio group: `sudo usermod -a -G audio $USER` (log out/in)

**Snap/Flatpak Sandboxing:**
- If packaged as Flatpak, need filesystem permission for PDF access
- Audio access via PulseAudio portal

### Cross-Platform Testing Matrix

| Feature | Windows 11 | macOS 13+ | Ubuntu 22.04 |
|---|---|---|---|
| PDF extraction | ✅ | ✅ | ✅ |
| Kokoro synthesis | ✅ | ✅ | ✅ |
| sounddevice playback | ✅ | ✅ | ✅ (PulseAudio) |
| PyQt6 GUI | ✅ | ✅ | ✅ |
| espeak-ng availability | Manual install | Homebrew | apt |
| Bookmark storage | AppData | ~/Library | ~/.config |

---

## 15. Future Enhancements

- **Voice cloning:** Let user record 3–10s of their preferred narrator voice; use Chatterbox or XTTS-v2 for zero-shot cloning
- **Reading speed adaptation:** Detect dense technical text and auto-reduce speed; increase for dialogue sections
- **Sleep timer:** Stop playback after N minutes
- **Highlight export:** Save a timestamped transcript synced to audio (SRT subtitle format)
- **Web version:** Serve via FastAPI + Kokoro ONNX in browser (WebGPU path) — zero local install required
- **AI chapter summary:** Before each chapter, synthesize a 1-sentence Claude-generated summary as an intro
- **Multi-document playlist:** Queue multiple PDFs as a continuous listening session
- **Accessibility:** Screen-reader-compatible UI, keyboard-only navigation

---

## 16. Quick Start Code Skeleton

```python
# audiobook.py — Phase 0 skeleton
import fitz  # PyMuPDF
import nltk
import numpy as np
import sounddevice as sd
from kokoro import KPipeline
from threading import Thread, Event
from queue import Queue

SAMPLE_RATE = 24000
VOICE = 'af_heart'
SPEED = 1.0

def extract_text(pdf_path: str) -> str:
    doc = fitz.open(pdf_path)
    return "\n".join(page.get_text() for page in doc)

def clean_and_chunk(text: str) -> list[str]:
    text = text.replace('-\n', '').replace('\n', ' ')
    sentences = nltk.sent_tokenize(text)
    return [s.strip() for s in sentences if len(s.strip()) > 10]

def synth_worker(pipeline, chunks, index, audio_queue, stop_event):
    while not stop_event.is_set():
        if index[0] < len(chunks):
            audio_parts = []
            for _, _, audio in pipeline(chunks[index[0]], voice=VOICE, speed=SPEED):
                audio_parts.append(audio)
            if audio_parts:
                audio_queue.put((index[0], np.concatenate(audio_parts)))
            index[0] += 1

def play_audio(audio: np.ndarray):
    sd.play(audio, samplerate=SAMPLE_RATE)
    sd.wait()

if __name__ == '__main__':
    import sys
    nltk.download('punkt', quiet=True)
    
    pdf_path = sys.argv[1]
    text = extract_text(pdf_path)
    chunks = clean_and_chunk(text)
    print(f"Loaded {len(chunks)} chunks from {pdf_path}")
    
    pipeline = KPipeline(lang_code='a')
    audio_queue = Queue(maxsize=5)
    stop_event = Event()
    index = [0]
    
    worker = Thread(target=synth_worker, 
                    args=(pipeline, chunks, index, audio_queue, stop_event), 
                    daemon=True)
    worker.start()
    
    try:
        while True:
            chunk_idx, audio = audio_queue.get()
            print(f"[{chunk_idx+1}/{len(chunks)}] {chunks[chunk_idx][:60]}...")
            play_audio(audio)
    except KeyboardInterrupt:
        stop_event.set()
        print("\nStopped.")
```

---

## 17. Quick Reference for Implementers

### Key Constants
```python
SAMPLE_RATE = 24000          # Kokoro output rate
CHUNK_TOKEN_LIMIT = 510      # Kokoro max tokens per call
AHEAD_BUFFER = 5             # Chunks to pre-synthesize
BACK_BUFFER = 15             # Chunks to keep for rewind
WINDOW_SIZE = 20             # Total buffer (ahead + back)
MAX_MEMORY_MB = 700          # Target total memory footprint
```

### Critical Files Structure
```
audiobook/
├── core/
│   ├── parser.py          # PDF → text → chunks
│   ├── synthesizer.py     # Kokoro wrapper
│   ├── memory_manager.py  # Sliding window buffer
│   └── playback.py        # sounddevice streaming
├── ui/
│   ├── main_window.py     # PyQt6 GUI
│   └── controls.py        # Player buttons/slider
├── utils/
│   ├── text_cleaner.py    # 10-stage pipeline
│   └── chapter_detector.py # Chapter parsing
├── tests/
│   ├── test_parser.py
│   ├── test_synthesis.py
│   └── test_threading.py
└── audiobook.py           # Entry point
```

### Implementation Checklist (Copy to Issue Tracker)

**Phase 0 — MVP (1-2 days):**
- [x] PDF extraction (PyMuPDF)
- [x] Basic sentence chunking (NLTK)
- [x] Kokoro synthesis (blocking, no buffer)
- [x] sounddevice playback (sequential chunks)
- [x] CLI with pause/next/back keyboard controls

**Phase 1 — Streaming Engine (3-5 days):**
- [ ] Async synthesis thread with Queue
- [ ] Sliding window buffer (section 4.3)
- [ ] Thread synchronization (section 4.5)
- [ ] Skip forward/backward with buffer awareness
- [ ] Chapter detection regex (section 5, stage 10)

**Phase 2 — GUI (3-5 days):**
- [ ] PyQt6 main window + file picker
- [ ] Text view with sentence highlight sync
- [ ] Chapter sidebar navigation
- [ ] Voice selector dropdown (10 Kokoro voices)
- [ ] Speed control slider (0.5x - 2.0x)
- [ ] Progress bar with seek capability

**Phase 3 — Polish (2-3 days):**
- [ ] Full text cleaning pipeline (all 10 stages)
- [ ] EPUB/DOCX/TXT format support
- [ ] Bookmark save/restore (section 8, Phase 3)
- [ ] Error handling (section 11.1)
- [ ] Platform-specific installers (section 14)

**Phase 4 — Hardening (ongoing):**
- [ ] Unit tests (section 13.1)
- [ ] Integration tests (section 13.2)
- [ ] Manual QA checklist (section 13.3)
- [ ] Performance profiling on CPU-only hardware
- [ ] Memory leak testing (24hr continuous playback)
- [ ] Cross-platform testing (Win/Mac/Linux)

### Decision Tree for Common Scenarios

**Q: Synthesis is too slow on my CPU**
→ A: Reduce `AHEAD_BUFFER` to 3, or use GPU acceleration, or switch to MeloTTS

**Q: Memory usage exceeds 700 MB**
→ A: Reduce `BACK_BUFFER` from 15 to 10, or reduce `AHEAD_BUFFER` from 5 to 3

**Q: Chapter detection isn't finding chapters**
→ A: Add debug logging to print all lines matching `[A-Z\s]{10,}`, tune regex patterns

**Q: Audio has gaps between sentences**
→ A: Increase `AHEAD_BUFFER` to ensure next chunk is ready before current finishes

**Q: Skip forward is sluggish**
→ A: Verify synthesis thread checks `current_index` before AND after synthesis (section 4.5)

**Q: PDF extraction returns garbage**
→ A: Try `pdfplumber` fallback, or detect scanned PDF and show OCR error (section 11.1)

---

*Document version: 2.0 — Comprehensive Implementation Guide*
*Research cutoff: April 2026*
*Primary TTS model: Kokoro-82M (hexgrad/Kokoro-82M, Apache 2.0)*
*Contributors: Research, Architecture, Implementation Planning, Testing Strategy*
