from __future__ import annotations

import argparse
import sys
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence, TextIO

import fitz

try:
    import nltk
except ImportError:  # pragma: no cover - handled at call time
    nltk = None

try:
    import numpy as np
except ImportError:  # pragma: no cover - handled at call time
    np = None

try:
    from kokoro import KPipeline
except ImportError:  # pragma: no cover - handled at call time
    KPipeline = None

try:
    import sounddevice as sd
except ImportError:  # pragma: no cover - handled at call time
    sd = None


@dataclass(frozen=True)
class PdfExtractionResult:
    text: str
    page_count: int


@dataclass(frozen=True)
class ChapterMarker:
    chunk_index: int
    heading: str
    marker_type: str


@dataclass(frozen=True)
class ChapterDetectionResult:
    marker_indexes: tuple[int, ...]
    markers: tuple[ChapterMarker, ...]


CHAPTER_PATTERNS: list[tuple[str, str]] = [
    (r"^\s*Chapter\s+\d+", "chapter_number"),
    (r"^\s*CHAPTER\s+[IVXLCDM]+$", "chapter_roman"),
    (r"^\s*Part\s+\w+", "part_heading"),
    (r"^\s*[A-Z\s]{10,}$", "all_caps_heading"),
]


def detect_chapter_markers(chunks: Iterable[str | Any]) -> ChapterDetectionResult:
    """Detect chapter/section markers in a list of text chunks.

    Returns a ChapterDetectionResult with marker_indexes and markers tuples.
    """
    markers: list[ChapterMarker] = []

    for idx, chunk in enumerate(chunks):
        text = _extract_chunk_text(chunk).strip()
        if not text:
            continue

        for pattern, marker_type in CHAPTER_PATTERNS:
            if re.match(pattern, text):
                markers.append(ChapterMarker(chunk_index=idx, heading=text, marker_type=marker_type))
                break

    marker_indexes = tuple(m.chunk_index for m in markers)
    return ChapterDetectionResult(marker_indexes=marker_indexes, markers=tuple(markers))


DEFAULT_KOKORO_LANG_CODE = "a"
DEFAULT_KOKORO_VOICE = "af_heart"
DEFAULT_KOKORO_SPEED = 1.0
DEFAULT_BACK_CACHE_SIZE = 10
DEFAULT_LOOKAHEAD_SIZE = 1
NLTK_TOKENIZER_PACKAGES = ("punkt", "punkt_tab")
_nltk_tokenizer_init_lock = threading.Lock()
_nltk_tokenizer_init_attempted = False


def _require_numpy() -> Any:
    if np is None:
        raise RuntimeError("NumPy is required for Kokoro synthesis")
    return np


def create_kokoro_pipeline(lang_code: str = DEFAULT_KOKORO_LANG_CODE) -> Any:
    if KPipeline is None:
        raise RuntimeError("Kokoro is not installed; install the 'kokoro' package to synthesize audio")

    return KPipeline(lang_code=lang_code)


def download_kokoro_voice(
    voice: str,
    *,
    lang_code: str = DEFAULT_KOKORO_LANG_CODE,
) -> str:
    """Download and validate a Kokoro voice by id.

    Returns the normalized voice id on success.
    """
    voice_id = voice.strip()
    if not voice_id:
        raise ValueError("Voice id is required")

    pipeline = create_kokoro_pipeline(lang_code=lang_code)
    loader = getattr(pipeline, "load_voice", None)
    if loader is None:
        raise RuntimeError("This Kokoro version does not support explicit voice downloads")

    try:
        loader(voice_id)
    except Exception as exc:
        raise RuntimeError(f"Unable to download voice '{voice_id}': {exc}") from exc

    return voice_id


def _extract_chunk_text(chunk: str | Any) -> str:
    if isinstance(chunk, str):
        return chunk

    text = getattr(chunk, "text", None)
    if text is None:
        raise TypeError("Chunk must be a string or expose a text attribute")

    return str(text)


def _concatenate_audio_parts(audio_parts: Sequence[Any]) -> Any:
    numpy = _require_numpy()
    if not audio_parts:
        return numpy.zeros(0, dtype=numpy.float32)

    arrays = [numpy.asarray(part, dtype=numpy.float32) for part in audio_parts if part is not None]
    if not arrays:
        return numpy.zeros(0, dtype=numpy.float32)

    if len(arrays) == 1:
        return arrays[0]

    return numpy.concatenate(arrays).astype(numpy.float32, copy=False)


def _extract_kokoro_audio_segment(payload: Any) -> Any:
    """Return the audio segment from a Kokoro pipeline payload."""
    output_obj = getattr(payload, "output", None)
    if output_obj is not None:
        output_audio = getattr(output_obj, "audio", None)
        if output_audio is not None:
            return output_audio

    direct_audio = getattr(payload, "audio", None)
    if direct_audio is not None:
        return direct_audio

    if isinstance(payload, dict):
        if payload.get("audio") is not None:
            return payload["audio"]
        output_value = payload.get("output")
        if isinstance(output_value, dict) and output_value.get("audio") is not None:
            return output_value["audio"]

    if isinstance(payload, Sequence) and not isinstance(payload, (str, bytes, bytearray)) and len(payload) >= 3:
        return payload[2]

    raise ValueError(
        "Kokoro pipeline yielded malformed payload: expected tuple(text, phonemes, audio) or Result-like object"
    )


def synthesize_chunk(
    chunk: str | Any,
    pipeline: Any | None = None,
    *,
    voice: str = DEFAULT_KOKORO_VOICE,
    speed: float = DEFAULT_KOKORO_SPEED,
) -> Any:
    text = _extract_chunk_text(chunk).strip()
    if not text:
        return _concatenate_audio_parts([])

    if pipeline is None:
        pipeline = create_kokoro_pipeline()

    audio_parts: list[Any] = []
    for payload in pipeline(text, voice=voice, speed=speed):
        if payload is None:
            continue
        audio_parts.append(_extract_kokoro_audio_segment(payload))

    return _concatenate_audio_parts(audio_parts)


def synthesize_chunks(
    chunks: Iterable[str | Any],
    pipeline: Any | None = None,
    *,
    voice: str = DEFAULT_KOKORO_VOICE,
    speed: float = DEFAULT_KOKORO_SPEED,
) -> list[Any]:
    shared_pipeline = pipeline
    audio_chunks: list[Any] = []

    for chunk in chunks:
        if shared_pipeline is None:
            shared_pipeline = create_kokoro_pipeline()
        audio_chunks.append(synthesize_chunk(chunk, shared_pipeline, voice=voice, speed=speed))

    return audio_chunks


def _require_sounddevice() -> Any:
    if sd is None:
        raise RuntimeError("sounddevice is required for audio playback")
    return sd


def _evict_old_audio_cache(
    audio_cache: dict[int, Any],
    current_index: int,
    *,
    back_cache_size: int = DEFAULT_BACK_CACHE_SIZE,
    forward_cache_size: int = 0,
) -> None:
    back_cache_size = max(0, back_cache_size)
    forward_cache_size = max(0, forward_cache_size)

    min_index = current_index - back_cache_size
    max_index = current_index + forward_cache_size
    for chunk_index in list(audio_cache.keys()):
        if chunk_index < min_index or chunk_index > max_index:
            del audio_cache[chunk_index]


def play_audio_chunk(audio: Any, *, samplerate: int = 24000) -> None:
    """Play one synthesized audio chunk and block until it finishes."""
    sounddevice = _require_sounddevice()
    try:
        sounddevice.play(audio, samplerate=samplerate)
        sounddevice.wait()
    except Exception as exc:  # pragma: no cover - depends on runtime audio backend
        raise RuntimeError(f"Unable to play audio chunk: {exc}") from exc


def play_audio_chunks(chunks: Iterable[Any], *, samplerate: int = 24000) -> None:
    """Play each synthesized chunk sequentially in a blocking loop."""
    for index, chunk in enumerate(chunks):
        if chunk is None:
            raise ValueError(f"Audio chunk at index {index} is None")
        play_audio_chunk(chunk, samplerate=samplerate)


def play_audio_chunks_with_controls(
    chunks: Iterable[Any],
    *,
    samplerate: int = 24000,
    input_func: Callable[[str], str] = input,
    output: TextIO | None = None,
) -> None:
    """Play synthesized chunks with CLI controls between chunk boundaries."""
    stream = output if output is not None else sys.stdout
    audio_chunks = list(chunks)
    total_chunks = len(audio_chunks)
    if total_chunks == 0:
        return

    print(
        "Playback controls (available between chunks only because playback is blocking): "
        "[Enter]=resume when paused/continue, p=pause/resume, n=next, b=previous, q=quit",
        file=stream,
    )
    index = 0
    paused = False

    while index < total_chunks:
        if not paused:
            chunk = audio_chunks[index]
            if chunk is None:
                raise ValueError(f"Audio chunk at index {index} is None")
            print(f"Playing chunk {index + 1}/{total_chunks}", file=stream)
            play_audio_chunk(chunk, samplerate=samplerate)
            index += 1
            if index >= total_chunks:
                break

        while True:
            command = input_func("Chunk boundary command [Enter/p/n/b/q]: ").strip().lower()
            if command == "":
                if paused:
                    paused = False
                    print("Resumed.", file=stream)
                break

            if command == "p":
                paused = not paused
                print("Paused." if paused else "Resumed.", file=stream)
                break
            elif command == "n":
                if index >= total_chunks - 1:
                    print("Already at last chunk.", file=stream)
                else:
                    index += 1
                    print(f"Moved to chunk {index + 1}/{total_chunks}.", file=stream)
                break
            elif command == "b":
                if index == 0:
                    print("Already at first chunk.", file=stream)
                else:
                    index -= 1
                    print(f"Moved to chunk {index + 1}/{total_chunks}.", file=stream)
                break
            elif command == "q":
                print("Quitting playback.", file=stream)
                return
            else:
                print(
                    "Unknown command at a chunk boundary. Use Enter, p, n, b, or q.",
                    file=stream,
                )


def _find_chapter_jump_target(
    chapters: ChapterDetectionResult, current_index: int, forward: bool
) -> int | None:
    """Find the nearest chapter marker to jump to.

    Returns the target chunk index, or None if no valid jump exists.
    """
    if not chapters.marker_indexes:
        return None

    targets = chapters.marker_indexes
    if forward:
        for t in targets:
            if t > current_index:
                return t
        return None
    else:
        for t in reversed(targets):
            if t < current_index:
                return t
        return None


def synthesize_and_play_chunks_with_controls(
    chunks: Iterable[str | Any],
    *,
    pipeline: Any | None = None,
    voice: str = DEFAULT_KOKORO_VOICE,
    speed: float = DEFAULT_KOKORO_SPEED,
    samplerate: int = 24000,
    back_cache_size: int = DEFAULT_BACK_CACHE_SIZE,
    lookahead_size: int = DEFAULT_LOOKAHEAD_SIZE,
    chapters: ChapterDetectionResult | None = None,
    input_func: Callable[[str], str] = input,
    output: TextIO | None = None,
) -> None:
    """Synthesize and play chunks with boundary controls and lookahead buffering."""
    stream = output if output is not None else sys.stdout
    text_chunks = list(chunks)
    total_chunks = len(text_chunks)
    if total_chunks == 0:
        return

    has_chapters = chapters is not None and bool(chapters.marker_indexes)
    controls_hint = "[Enter]=resume when paused/continue, p=pause/resume, n=next, b=previous"
    if has_chapters:
        controls_hint += ", f=forward chapter, r=rewind chapter"
    controls_hint += ", q=quit"

    print(
        f"Playback controls (available between chunks only because playback is blocking): {controls_hint}",
        file=stream,
    )
    index = 0
    paused = False
    shared_pipeline = pipeline
    audio_cache: dict[int, Any] = {}
    lookahead_size = max(0, lookahead_size)
    cache_condition = threading.Condition()
    stop_event = threading.Event()
    worker_error: Exception | None = None

    def _evict_cache_locked() -> None:
        _evict_old_audio_cache(
            audio_cache,
            index,
            back_cache_size=back_cache_size,
            forward_cache_size=lookahead_size,
        )

    def _raise_worker_error_if_any() -> None:
        with cache_condition:
            error = worker_error
        if error is not None:
            raise error

    def _wait_for_audio_chunk(chunk_index: int) -> Any:
        with cache_condition:
            while chunk_index not in audio_cache:
                if worker_error is not None:
                    raise worker_error
                cache_condition.wait(timeout=0.1)
            return audio_cache[chunk_index]

    def _lookahead_worker() -> None:
        nonlocal shared_pipeline, worker_error

        while not stop_event.is_set():
            with cache_condition:
                _evict_cache_locked()
                chunk_index: int | None = None
                max_index = min(total_chunks, index + lookahead_size + 1)
                for candidate_index in range(index, max_index):
                    if candidate_index not in audio_cache:
                        chunk_index = candidate_index
                        break
                if chunk_index is None:
                    cache_condition.wait(timeout=0.1)
                    continue
                chunk_text = text_chunks[chunk_index]

            try:
                if shared_pipeline is None:
                    shared_pipeline = create_kokoro_pipeline()
                chunk_audio = synthesize_chunk(
                    chunk_text,
                    shared_pipeline,
                    voice=voice,
                    speed=speed,
                )
            except Exception as exc:
                with cache_condition:
                    worker_error = exc
                    stop_event.set()
                    cache_condition.notify_all()
                return

            with cache_condition:
                audio_cache[chunk_index] = chunk_audio
                _evict_cache_locked()
                cache_condition.notify_all()

    worker_thread = threading.Thread(
        target=_lookahead_worker,
        name="audiobook-lookahead-worker",
    )
    worker_thread.start()

    try:
        while index < total_chunks:
            with cache_condition:
                _evict_cache_locked()
                cache_condition.notify_all()
            _raise_worker_error_if_any()

            if not paused:
                audio_chunk = _wait_for_audio_chunk(index)
                if audio_chunk is None:
                    raise ValueError(f"Audio chunk at index {index} is None")
                print(f"Playing chunk {index + 1}/{total_chunks}", file=stream)
                play_audio_chunk(audio_chunk, samplerate=samplerate)
                with cache_condition:
                    index += 1
                    _evict_cache_locked()
                    cache_condition.notify_all()
                if index >= total_chunks:
                    break

            command = input_func("Chunk boundary command [Enter/p/n/b/q]: ").strip().lower()
            if command == "":
                if paused:
                    paused = False
                    print("Resumed.", file=stream)
                continue

            if command == "p":
                paused = not paused
                print("Paused." if paused else "Resumed.", file=stream)
            elif command == "n":
                with cache_condition:
                    if index >= total_chunks - 1:
                        already_last = True
                    else:
                        already_last = False
                        index += 1
                        _evict_cache_locked()
                        cache_condition.notify_all()
                if already_last:
                    print("Already at last chunk.", file=stream)
                else:
                    print(f"Moved to chunk {index + 1}/{total_chunks}.", file=stream)
            elif command == "b":
                with cache_condition:
                    if index == 0:
                        already_first = True
                    else:
                        already_first = False
                        index -= 1
                        _evict_cache_locked()
                        cache_condition.notify_all()
                if already_first:
                    print("Already at first chunk.", file=stream)
                else:
                    print(f"Moved to chunk {index + 1}/{total_chunks}.", file=stream)
            elif command == "f" and has_chapters:
                with cache_condition:
                    target = _find_chapter_jump_target(chapters, index, forward=True)
                    if target is not None:
                        index = target
                        _evict_cache_locked()
                        cache_condition.notify_all()
                if target is not None:
                    chapter_label = next(
                        (m.heading for m in chapters.markers if m.chunk_index == target),
                        f"chunk {target + 1}",
                    )
                    print(f"Jumped forward to: {chapter_label} (chunk {target + 1}).", file=stream)
                else:
                    print("Already at or past the last chapter.", file=stream)
            elif command == "r" and has_chapters:
                with cache_condition:
                    target = _find_chapter_jump_target(chapters, index, forward=False)
                    if target is not None:
                        index = target
                        _evict_cache_locked()
                        cache_condition.notify_all()
                if target is not None:
                    chapter_label = next(
                        (m.heading for m in chapters.markers if m.chunk_index == target),
                        f"chunk {target + 1}",
                    )
                    print(f"Rewound to: {chapter_label} (chunk {target + 1}).", file=stream)
                else:
                    print("Already at or before the first chapter.", file=stream)
            elif command == "q":
                print("Quitting playback.", file=stream)
                break
            else:
                print(
                    "Unknown command at a chunk boundary. Use Enter, p, n, b, or q.",
                    file=stream,
                )
    finally:
        stop_event.set()
        with cache_condition:
            cache_condition.notify_all()
        worker_thread.join()

    _raise_worker_error_if_any()


LIGATURE_MAP = {"\ufb01": "fi", "\ufb02": "fl", "\ufb00": "ff", "\ufb03": "ffi", "\ufb04": "ffl"}

ABBREVIATIONS = ["Mr.", "Mrs.", "Dr.", "Prof.", "Inc.", "Ltd.", "etc.", "i.e.", "e.g."]


def _remove_page_artifacts(text: str) -> str:
    lines = text.split("\n")
    cleaned = []
    for line in lines:
        stripped = line.strip()
        if len(stripped) < 20 and (stripped.isdigit() or (stripped.isupper() and len(stripped) > 0)):
            continue
        cleaned.append(line)
    return "\n".join(cleaned)


def _repair_hyphenated_breaks(text: str) -> str:
    return re.sub(r"(?<=\w)-\s*\n\s*(?=\w)", "", text)


def _normalize_ligatures(text: str) -> str:
    for lig, repl in LIGATURE_MAP.items():
        text = text.replace(lig, repl)
    return text


def _normalize_unicode(text: str) -> str:
    import unicodedata
    return unicodedata.normalize("NFKC", text)


def _protect_abbreviations(text: str) -> str:
    for abbr in ABBREVIATIONS:
        text = text.replace(abbr, abbr.replace(".", "<ABBR>"))
    return text


def _restore_abbreviations(text: str) -> str:
    return text.replace("<ABBR>", ".")


def _filter_sentences(sentences: list[str]) -> list[str]:
    return [
        s for s in sentences
        if len(s.strip()) >= 10 and not s.strip().startswith("http")
    ]


def _clean_extracted_text(text: str) -> str:
    text = _remove_page_artifacts(text)
    text = _repair_hyphenated_breaks(text)
    text = _normalize_ligatures(text)
    text = _normalize_unicode(text)
    text = _protect_abbreviations(text)
    text = re.sub(r"\s+", " ", text)
    text = _restore_abbreviations(text)
    return text.strip()


def _ensure_nltk_tokenizer_data() -> None:
    global _nltk_tokenizer_init_attempted
    if nltk is None:
        return

    with _nltk_tokenizer_init_lock:
        if _nltk_tokenizer_init_attempted:
            return
        _nltk_tokenizer_init_attempted = True

    for package_name in NLTK_TOKENIZER_PACKAGES:
        try:
            nltk.download(package_name, quiet=True)
        except Exception:
            continue


def _regex_sentence_tokenize(text: str) -> list[str]:
    sentence_boundary_pattern = r"(?<=[.!?])\s+(?=[\"'\(\[]?[A-Z0-9])"
    sentences = [part.strip() for part in re.split(sentence_boundary_pattern, text) if part.strip()]
    return sentences or [text.strip()]


def _sent_tokenize(text: str) -> list[str]:
    if nltk is None:
        return _regex_sentence_tokenize(text)

    try:
        return nltk.sent_tokenize(text)
    except LookupError:
        _ensure_nltk_tokenizer_data()

    try:
        return nltk.sent_tokenize(text)
    except LookupError:
        return _regex_sentence_tokenize(text)


def clean_and_chunk(text: str) -> list[str]:
    cleaned_text = _clean_extracted_text(text)
    if not cleaned_text:
        return []

    sentences = _sent_tokenize(cleaned_text)
    chunks = [re.sub(r"\s+", " ", sentence).strip() for sentence in sentences if sentence and sentence.strip()]
    return chunks or [cleaned_text]


def extract_pdf_text(pdf_path: str) -> PdfExtractionResult:
    if not pdf_path:
        raise ValueError("PDF path is required")

    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    try:
        document = fitz.open(str(path))
    except (fitz.FileDataError, OSError, RuntimeError, ValueError) as exc:
        raise ValueError(f"Unable to read PDF: {pdf_path}") from exc

    try:
        pages = [page.get_text("text") for page in document]
        return PdfExtractionResult(text="\n".join(pages), page_count=document.page_count)
    finally:
        document.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract PDF text, chunk it, synthesize audio, and play it back."
    )
    parser.add_argument(
        "pdf_path",
        nargs="?",
        help="Path to the PDF file to extract, chunk, synthesize, and play",
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Launch the PyQt6 GUI instead of the CLI",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.gui:
        try:
            from PyQt6.QtWidgets import QApplication
            from ui.main_window import MainWindow
        except ImportError:
            print("Error: PyQt6 is required for the GUI.", file=sys.stderr)
            print("Install with: pip install PyQt6", file=sys.stderr)
            return 1

        app = QApplication(sys.argv)
        app.setApplicationName("PDF Audiobook")
        app.setOrganizationName("PDFAudiobook")
        window = MainWindow(pdf_path=args.pdf_path)
        window.show()
        return app.exec()

    if not args.pdf_path:
        parser.error("a PDF path is required")

    try:
        result = extract_pdf_text(args.pdf_path)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    char_count = len(result.text)
    if char_count == 0:
        print(f"Extracted no text from {result.page_count} pages.")
    else:
        print(f"Extracted {char_count} characters from {result.page_count} pages.")

    try:
        chunks = clean_and_chunk(result.text)
        if not chunks:
            print(
                "Error: No playable text was found after extraction/chunking. "
                "This PDF may be scanned or image-only; run OCR (for example, OCRmyPDF) "
                "or provide a text-searchable PDF.",
                file=sys.stderr,
            )
            return 1
        synthesize_and_play_chunks_with_controls(chunks)
    except (RuntimeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
