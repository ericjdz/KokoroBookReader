# PDF Audiobook App — Phase 0 CLI

This repository now includes a working Phase 0 CLI implementation (`audiobook.py`) plus the original planning documents.

## 📁 Repository Contents

### 1. **pdf_audiobook_plan.md** (PRIMARY DOCUMENT)
**966 lines** | **v2.0** | **Production-ready implementation guide**

The comprehensive planning document covering:
- TTS model research and selection (Kokoro-82M recommended)
- Complete system architecture with threading model
- All 10 text cleaning pipeline stages (with code)
- Error handling and recovery strategies
- Testing strategy (unit, integration, manual QA)
- Platform-specific considerations (Windows/Mac/Linux)
- Quick reference for implementers

**Start here:** Read sections 1-4 for overview, then jump to Section 17 for implementation checklist.

### 2. **REVISION_SUMMARY.md**
**Summary of v1.0 → v2.0 improvements**

Quick overview of what was added in the comprehensive revision:
- 6 new sections
- 3 major expansions
- Production-ready status

### 3. **CHANGELOG.md**
**Version history and change tracking**

Detailed changelog following semantic versioning:
- v2.0.0: Comprehensive revision (current)
- v1.0.0: Original research document

---

## 🚀 Quick Start

### Setup requirement
Install the NLTK tokenizer data locally before running the app or tests:

```bash
python -m nltk.downloader punkt punkt_tab
```

### If you want to understand the project:
1. Read **pdf_audiobook_plan.md** sections 1-3 (Vision, TTS Research, Architecture)
2. Review Section 10 (Key Design Decisions)

### Run Phase 0 CLI
```bash
python audiobook.py path\to\book.pdf
```

The CLI extracts text, chunks by sentence, synthesizes one chunk at a time, and plays audio with controls at chunk boundaries.

### Run Phase 2 GUI

```bash
# Install PyQt6 first
pip install PyQt6

# Launch GUI with optional PDF
python audiobook_gui.py [path\to\book.pdf]

# Or use the CLI flag
python audiobook.py --gui [path\to\book.pdf]
```

The GUI features:
- Chapter sidebar with navigation
- Synchronized text highlighting
- Playback controls with progress bar
- Voice selector and speed slider
- Catppuccin Mocha dark theme

### If you want to review what changed:
1. Read **REVISION_SUMMARY.md** first
2. Check **CHANGELOG.md** for detailed changes
3. Look for ⭐ markers in the main document (new v2.0 content)

---

## 📊 Document Statistics

| Metric | Value |
|--------|-------|
| Total lines | 966 |
| Sections | 17 |
| Code examples | ~35 |
| Dependencies | 11 libraries |
| Implementation phases | 4 (0-3) |
| Estimated MVP time | 1-2 days |
| Estimated full app time | 9-15 days |

---

## 🎯 Project Status

**Phase:** All phases implemented ✅ (0-4)  
**Current app:** CLI + PyQt6 Desktop GUI with multi-format support, bookmarks, config, and WAV export  
**Readiness:** Production-ready MVP with tests (59 passing)

### Known limitations
- Playback controls are available only at chunk boundaries (blocking playback model).
- Previous chunk replay is chunk-based (returns to previous boundary).
- In-memory audio cache keeps a bounded back window (default: 10 chunks) and re-synthesizes older chunks if needed.
- Eviction helper supports an ahead window, but Phase 0 runtime currently uses a forward window of 0.
- Image-only/scanned PDFs require OCR before playback.

---

## 🔑 Key Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| TTS Model | Kokoro-82M | Best CPU speed/quality ratio (82M params, <300ms latency) |
| Memory Strategy | Sliding window buffer | O(1) memory regardless of doc length |
| Audio Engine | sounddevice | Low latency, cross-platform |
| GUI Framework | PyQt6 | Best text highlighting support |
| Chunk Granularity | Sentence-level | Aligns with Kokoro 510-token limit |

---

## 📚 Sections at a Glance

| Section | Focus Area | Status |
|---------|------------|--------|
| 1-2 | Vision & TTS Research | ✅ Complete |
| 3-4 | Architecture & Core Systems | ✅ Complete (v2.0 threading) |
| 5 | Text Cleaning Pipeline | ✅ Complete (v2.0 all stages) |
| 6-7 | UI & File Formats | ✅ Complete |
| 8 | Implementation Phases | ✅ Complete (v2.0 bookmarking) |
| 9-10 | Dependencies & Design | ✅ Complete |
| 11 | Edge Cases & Errors | ✅ Complete (v2.0 recovery) |
| 12 | Performance Targets | ✅ Complete |
| 13 | Testing Strategy | ✅ Complete (v2.0 NEW) |
| 14 | Platform Support | ✅ Complete (v2.0 NEW) |
| 15 | Future Enhancements | ✅ Complete |
| 16 | Starter Code | ✅ Complete |
| 17 | Quick Reference | ✅ Complete (v2.0 NEW) |

---

## 🛠️ For Maintainers

### To update the plan:
1. Edit **pdf_audiobook_plan.md**
2. Update **CHANGELOG.md** with changes
3. Bump version number in footer
4. Update **REVISION_SUMMARY.md** if major changes

### To propose changes:
1. Open issue with section number and proposed change
2. Tag with `documentation` label
3. Reference specific line numbers

---

## 📖 Reading Order Recommendations

**For Project Managers:**
→ Sections 1, 8, 12 (Vision, Phases, Performance Targets)

**For Architects:**
→ Sections 2-4, 10 (TTS Research, Architecture, Design Decisions)

**For Developers:**
→ Sections 17, 16, 4, 5 (Quick Ref, Starter Code, Core Systems, Pipeline)

**For QA Engineers:**
→ Sections 11, 13 (Edge Cases, Testing Strategy)

**For DevOps:**
→ Sections 9, 14 (Dependencies, Platform Considerations)

---

## 💡 Contributing

This repository now contains both implementation and planning artifacts:
1. `audiobook.py` and `test_audiobook.py` for Phase 0 CLI behavior
2. `pdf_audiobook_plan.md` and related docs for architecture and future phases

---

## 📄 License

Planning documents: CC BY 4.0  
Recommended implementation license: Apache 2.0 or MIT  
(Kokoro-82M is Apache 2.0)

---

**Repository Version:** 2.0  
**Last Updated:** 2026-04-04  
**Status:** ✅ Phase 0 Implemented  
**Primary Author:** Research, Planning, and Implementation Team  

---

*Start building: Jump to [Section 17 - Quick Reference →](pdf_audiobook_plan.md#17-quick-reference-for-implementers)*
