# CHANGELOG - PDF Audiobook Plan

All notable changes to the PDF Audiobook planning document.

## [2.0.0] - 2026-04-04

### Added

#### New Sections
- **Section 4.5:** Thread Safety & Synchronization
  - Complete threading architecture with locks and events
  - Code examples for skip-forward, synthesis loop, playback callback
  - Race condition prevention strategies

- **Section 11.1:** Error Handling & Recovery Strategy
  - 7 failure modes with detection and recovery
  - Global exception handler pattern
  - Graceful degradation strategies

- **Section 13:** Testing Strategy
  - 13.1: Unit tests for text processing, memory, synthesis
  - 13.2: Integration tests for playback and threading
  - 13.3: Manual QA checklist (8 scenarios)

- **Section 14:** Platform-Specific Considerations
  - Windows: Audio devices, espeak-ng, file paths
  - macOS: Permissions, Homebrew, troubleshooting
  - Linux: Dependencies, Wayland/X11, sandboxing
  - Cross-platform testing matrix

- **Section 17:** Quick Reference for Implementers
  - Key constants reference
  - Recommended file structure
  - Phase-by-phase checklist
  - Decision tree for common issues

- **Table of Contents** at document start with section links

### Enhanced

#### Section 5: Text Cleaning & Preprocessing Pipeline
- **Before:** Bullet points only
- **After:** Full Python code for all 10 stages
- Added: Regex patterns for hyphen repair, ligatures, abbreviations
- Added: 4 chapter detection regex patterns
- Added: Number normalization with `num2words`

#### Section 8: Implementation Phases
- **Phase 3 Enhanced:** Bookmarking now fully specified
  - Storage location: `~/.audiobook_state.json`
  - Data format: `{pdf_path, chunk_index, timestamp}`
  - UX flow: auto-resume prompt

#### Section 9: Dependencies
- Added `num2words` library for number-to-words conversion

### Changed
- Document version: 1.0 → 2.0
- Line count: 501 → 966 (+93%)
- Code examples: ~15 → ~35 (+133%)
- Total sections: 14 → 17 (+3)

### Fixed
- All cross-references validated (sections 4.3, 4.5, 11.1, 13.1-13.3)
- No TODO/FIXME markers remaining
- All code examples syntactically correct

---

## [1.0.0] - 2026-04-04 (Original)

### Initial Release
- TTS model research and comparison
- Architecture overview
- Core subsystems design
- Memory management strategy
- UI options
- Implementation phases
- Dependencies list
- Edge cases and gotchas
- Performance targets
- Future enhancements
- Quick start code skeleton

### Strengths
- Excellent TTS research with clear winner (Kokoro-82M)
- Well-designed sliding window buffer
- Realistic performance targets
- Good edge case coverage

### Gaps (addressed in v2.0)
- Threading synchronization unspecified
- Text cleaning pipeline incomplete
- No error handling strategy
- No testing guidance
- Platform differences not documented
- Bookmarking feature underspecified

---

## Version Numbering

- **Major version (X.0.0):** Complete revisions with new sections
- **Minor version (0.X.0):** Enhanced existing sections
- **Patch version (0.0.X):** Typo fixes, clarifications

---

*Maintained by: PDF Audiobook Project Team*
*Last updated: 2026-04-04*
