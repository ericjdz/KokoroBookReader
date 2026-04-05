"""Export audiobook chunks to audio files."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Iterable


def export_chunks_to_wav(
    chunks: Iterable[str],
    output_dir: str,
    synthesize_fn: Callable[[str], Any],
    *,
    samplerate: int = 24000,
    progress_callback: Callable[[int, int], None] | None = None,
) -> list[Path]:
    """Export text chunks to individual WAV files.

    Args:
        chunks: Text chunks to synthesize.
        output_dir: Directory to save WAV files.
        synthesize_fn: Function that takes text and returns numpy audio array.
        samplerate: Audio sample rate.
        progress_callback: Optional callback(current, total) for progress.

    Returns:
        List of paths to created WAV files.
    """
    try:
        import soundfile as sf
    except ImportError:
        raise ImportError(
            "WAV export requires soundfile. "
            "Install with: pip install soundfile"
        )

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    chunk_list = list(chunks)
    total = len(chunk_list)
    wav_files: list[Path] = []

    for i, text in enumerate(chunk_list):
        if not text.strip():
            continue

        audio = synthesize_fn(text)
        if audio is not None:
            wav_file = output_path / f"chunk_{i:04d}.wav"
            sf.write(str(wav_file), audio, samplerate)
            wav_files.append(wav_file)

        if progress_callback:
            progress_callback(i + 1, total)

    return wav_files


def export_full_audiobook(
    chunks: Iterable[str],
    output_path: str,
    synthesize_fn: Callable[[str], Any],
    *,
    samplerate: int = 24000,
    progress_callback: Callable[[int, int], None] | None = None,
) -> Path:
    """Export all chunks to a single concatenated WAV file.

    Args:
        chunks: Text chunks to synthesize.
        output_path: Path for the output WAV file.
        synthesize_fn: Function that takes text and returns numpy audio array.
        samplerate: Audio sample rate.
        progress_callback: Optional callback(current, total) for progress.

    Returns:
        Path to the created WAV file.
    """
    try:
        import numpy as np
        import soundfile as sf
    except ImportError:
        raise ImportError(
            "WAV export requires numpy and soundfile. "
            "Install with: pip install numpy soundfile"
        )

    chunk_list = list(chunks)
    total = len(chunk_list)
    audio_parts = []

    for i, text in enumerate(chunk_list):
        if not text.strip():
            continue

        audio = synthesize_fn(text)
        if audio is not None:
            audio_parts.append(audio)

        if progress_callback:
            progress_callback(i + 1, total)

    if not audio_parts:
        raise ValueError("No audio was generated from the provided chunks.")

    combined = np.concatenate(audio_parts)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out), combined, samplerate)
    return out
