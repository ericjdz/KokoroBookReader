from __future__ import annotations

import contextlib
import io
import threading
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import ANY, MagicMock, call, patch

import fitz

import audiobook


class FakeAudio(list):
    def astype(self, dtype, copy: bool = False):  # pragma: no cover - trivial helper
        return self


class FakeNumpy:
    float32 = "float32"

    def asarray(self, part, dtype=None):
        return FakeAudio(list(part))

    def zeros(self, length, dtype=None):
        return FakeAudio([0] * length)

    def concatenate(self, arrays):
        merged = FakeAudio()
        for array in arrays:
            merged.extend(list(array))
        return merged


class PdfExtractionTests(unittest.TestCase):
    def test_clean_and_chunk_normalizes_text_before_sentence_tokenization(self) -> None:
        fake_nltk = MagicMock()
        fake_nltk.sent_tokenize.return_value = [" First sentence. ", "", "Second sentence?  "]

        with patch.object(audiobook, "nltk", fake_nltk):
            chunks = audiobook.clean_and_chunk("First sen-\ntence.\n\nSecond sentence?")

        fake_nltk.sent_tokenize.assert_called_once_with("First sentence. Second sentence?")
        self.assertEqual(chunks, ["First sentence.", "Second sentence?"])

    def test_clean_and_chunk_returns_empty_list_for_blank_text(self) -> None:
        with patch.object(audiobook, "nltk", MagicMock()):
            self.assertEqual(audiobook.clean_and_chunk("   \n\t  "), [])

    def test_clean_and_chunk_falls_back_to_cleaned_text_when_tokenizer_returns_no_sentences(
        self,
    ) -> None:
        fake_nltk = MagicMock()
        fake_nltk.sent_tokenize.return_value = []

        with patch.object(audiobook, "nltk", fake_nltk):
            chunks = audiobook.clean_and_chunk("Hello world.")

        self.assertEqual(chunks, ["Hello world."])

    def test_clean_and_chunk_raises_when_nltk_is_unavailable(self) -> None:
        with patch.object(audiobook, "nltk", None):
            chunks = audiobook.clean_and_chunk("Hello world. Another sentence.")

        self.assertEqual(chunks, ["Hello world.", "Another sentence."])

    def test_clean_and_chunk_falls_back_when_tokenizer_data_is_missing(self) -> None:
        fake_nltk = MagicMock()
        fake_nltk.sent_tokenize.side_effect = LookupError("missing tokenizer data")

        with patch.object(audiobook, "nltk", fake_nltk):
            chunks = audiobook.clean_and_chunk("Hello world. Another sentence.")

        self.assertEqual(chunks, ["Hello world.", "Another sentence."])

    def test_clean_and_chunk_uses_real_tokenizer_when_punkt_data_is_available(self) -> None:
        if audiobook.nltk is None:
            self.skipTest("NLTK is not installed")

        try:
            chunks = audiobook.clean_and_chunk("One sentence. Two sentences.")
        except RuntimeError as exc:
            if "NLTK sentence tokenizer data is unavailable" in str(exc):
                self.skipTest("NLTK tokenizer data is not installed")
            raise

        self.assertEqual(chunks, ["One sentence.", "Two sentences."])

    def test_detect_chapter_markers_matches_phase1_heading_patterns(self) -> None:
        result = audiobook.detect_chapter_markers(
            [
                "Preface",
                "Chapter 1",
                "Body text",
                "CHAPTER IV",
                "Part One",
                "THE FALL OF THE HOUSE",
                "More prose",
            ]
        )

        self.assertEqual(result.marker_indexes, (1, 3, 4, 5))
        self.assertEqual(
            result.markers,
            (
                audiobook.ChapterMarker(chunk_index=1, heading="Chapter 1", marker_type="chapter_number"),
                audiobook.ChapterMarker(chunk_index=3, heading="CHAPTER IV", marker_type="chapter_roman"),
                audiobook.ChapterMarker(chunk_index=4, heading="Part One", marker_type="part_heading"),
                audiobook.ChapterMarker(
                    chunk_index=5,
                    heading="THE FALL OF THE HOUSE",
                    marker_type="all_caps_heading",
                ),
            ),
        )

    def test_detect_chapter_markers_supports_chunk_objects_with_text(self) -> None:
        chunks = [
            SimpleNamespace(text="Opening"),
            SimpleNamespace(text="Chapter 2"),
            SimpleNamespace(text="Part Two"),
        ]

        result = audiobook.detect_chapter_markers(chunks)

        self.assertEqual(result.marker_indexes, (1, 2))

    def test_detect_chapter_markers_ignores_non_heading_chunks(self) -> None:
        result = audiobook.detect_chapter_markers(
            [
                "chapter one",
                "Chapterhouse 1",
                "Part",
                "THE END",
                "This is regular prose.",
            ]
        )

        self.assertEqual(result.marker_indexes, ())
        self.assertEqual(result.markers, ())

    def test_detect_chapter_markers_raises_for_malformed_chunk(self) -> None:
        with self.assertRaisesRegex(TypeError, "Chunk must be a string or expose a text attribute"):
            audiobook.detect_chapter_markers([object()])

    def test_build_parser_accepts_pdf_path(self) -> None:
        parser = audiobook.build_parser()
        args = parser.parse_args(["sample.pdf"])

        self.assertEqual(args.pdf_path, "sample.pdf")
        self.assertEqual(
            parser.description,
            "Extract PDF text, chunk it, synthesize audio, and play it back.",
        )

    def test_create_kokoro_pipeline_raises_when_package_is_missing(self) -> None:
        with patch.object(audiobook, "KPipeline", None):
            with self.assertRaisesRegex(RuntimeError, "Kokoro is not installed"):
                audiobook.create_kokoro_pipeline()

    def test_synthesize_chunk_combines_kokoro_audio_segments(self) -> None:
        fake_pipeline = MagicMock()
        fake_pipeline.return_value = iter(
            [
                ("text", "phonemes", [1, 2]),
                ("text", "phonemes", [3, 4]),
            ]
        )

        with patch.object(audiobook, "np", FakeNumpy()):
            audio = audiobook.synthesize_chunk("Hello world.", pipeline=fake_pipeline)

        fake_pipeline.assert_called_once_with("Hello world.", voice="af_heart", speed=1.0)
        self.assertEqual(list(audio), [1, 2, 3, 4])

    def test_synthesize_chunk_creates_pipeline_when_missing(self) -> None:
        created_pipeline = MagicMock()
        created_pipeline.return_value = iter([("text", "phonemes", [1, 2])])

        with (
            patch.object(audiobook, "create_kokoro_pipeline", return_value=created_pipeline) as create_pipeline,
            patch.object(audiobook, "np", FakeNumpy()),
        ):
            audio = audiobook.synthesize_chunk("Hello world.", pipeline=None)

        create_pipeline.assert_called_once_with()
        created_pipeline.assert_called_once_with("Hello world.", voice="af_heart", speed=1.0)
        self.assertEqual(list(audio), [1, 2])

    def test_synthesize_chunk_accepts_result_like_payload_object(self) -> None:
        fake_result = SimpleNamespace(output=SimpleNamespace(audio=[1, 2]))
        fake_pipeline = MagicMock(return_value=iter([fake_result]))

        with patch.object(audiobook, "np", FakeNumpy()):
            audio = audiobook.synthesize_chunk("Hello world.", pipeline=fake_pipeline)

        self.assertEqual(list(audio), [1, 2])

    def test_synthesize_chunk_raises_for_malformed_kokoro_payload(self) -> None:
        fake_pipeline = MagicMock()
        fake_pipeline.return_value = iter([("text", "phonemes")])

        with self.assertRaisesRegex(ValueError, "Kokoro pipeline yielded malformed payload"):
            audiobook.synthesize_chunk("Hello world.", pipeline=fake_pipeline)

    def test_synthesize_chunk_raises_when_numpy_is_missing(self) -> None:
        fake_pipeline = MagicMock()
        fake_pipeline.return_value = iter([("text", "phonemes", [1, 2])])

        with patch.object(audiobook, "np", None):
            with self.assertRaisesRegex(RuntimeError, "NumPy is required for Kokoro synthesis"):
                audiobook.synthesize_chunk("Hello world.", pipeline=fake_pipeline)

    def test_synthesize_chunk_returns_silence_for_blank_text(self) -> None:
        fake_pipeline = MagicMock()

        with patch.object(audiobook, "np", FakeNumpy()):
            audio = audiobook.synthesize_chunk("   \n\t  ", pipeline=fake_pipeline)

        fake_pipeline.assert_not_called()
        self.assertEqual(list(audio), [])

    def test_synthesize_chunks_processes_each_chunk_sequentially(self) -> None:
        calls: list[str] = []

        def fake_pipeline(text, voice=None, speed=None):
            calls.append(text)
            return iter([("text", "phonemes", [len(text)])])

        with patch.object(audiobook, "np", FakeNumpy()):
            audio_chunks = audiobook.synthesize_chunks(
                ["First sentence.", "Second sentence."], pipeline=fake_pipeline
            )

        self.assertEqual(calls, ["First sentence.", "Second sentence."])
        self.assertEqual([list(chunk) for chunk in audio_chunks], [[15], [16]])

    def test_synthesize_chunks_reuses_created_pipeline_for_all_chunks(self) -> None:
        created_pipeline = MagicMock()
        synthesize_calls: list[tuple[str, object, str, float]] = []

        def fake_synthesize_chunk(chunk, pipeline, *, voice=None, speed=None):
            synthesize_calls.append((chunk, pipeline, voice, speed))
            return chunk

        with (
            patch.object(audiobook, "create_kokoro_pipeline", return_value=created_pipeline) as create_pipeline,
            patch.object(audiobook, "synthesize_chunk", side_effect=fake_synthesize_chunk),
        ):
            audio_chunks = audiobook.synthesize_chunks(["First sentence.", "Second sentence."])

        create_pipeline.assert_called_once_with()
        self.assertEqual(
            synthesize_calls,
            [
                ("First sentence.", created_pipeline, audiobook.DEFAULT_KOKORO_VOICE, audiobook.DEFAULT_KOKORO_SPEED),
                ("Second sentence.", created_pipeline, audiobook.DEFAULT_KOKORO_VOICE, audiobook.DEFAULT_KOKORO_SPEED),
            ],
        )
        self.assertEqual(audio_chunks, ["First sentence.", "Second sentence."])

    def test_synthesize_chunks_does_not_create_pipeline_for_empty_chunks(self) -> None:
        with patch.object(audiobook, "create_kokoro_pipeline") as create_pipeline:
            audio_chunks = audiobook.synthesize_chunks([])

        create_pipeline.assert_not_called()
        self.assertEqual(audio_chunks, [])

    def test_play_audio_chunk_uses_sounddevice_blocking_playback(self) -> None:
        fake_sd = MagicMock()

        with patch.object(audiobook, "sd", fake_sd):
            audiobook.play_audio_chunk([1, 2, 3], samplerate=22050)

        fake_sd.play.assert_called_once_with([1, 2, 3], samplerate=22050)
        fake_sd.wait.assert_called_once_with()

    def test_play_audio_chunks_raises_on_none_chunk_before_later_chunks(self) -> None:
        calls: list[tuple[str, object]] = []

        def fake_play_audio_chunk(audio, *, samplerate=24000):
            calls.append((audio, samplerate))

        with patch.object(audiobook, "play_audio_chunk", side_effect=fake_play_audio_chunk):
            with self.assertRaisesRegex(ValueError, "Audio chunk at index 1 is None"):
                audiobook.play_audio_chunks([[1], None, [2, 3]], samplerate=16000)

        self.assertEqual(calls, [([1], 16000)])

    def test_play_audio_chunks_with_controls_resumes_on_enter_when_paused(self) -> None:
        played: list[tuple[object, int]] = []
        commands = iter(["p", ""])
        stdout = io.StringIO()

        def fake_play_audio_chunk(audio, *, samplerate=24000):
            played.append((audio, samplerate))

        with patch.object(audiobook, "play_audio_chunk", side_effect=fake_play_audio_chunk):
            audiobook.play_audio_chunks_with_controls(
                [[1], [2]],
                samplerate=16000,
                input_func=lambda _prompt: next(commands),
                output=stdout,
            )

        self.assertEqual(played, [([1], 16000), ([2], 16000)])
        self.assertIn("available between chunks only", stdout.getvalue())
        self.assertIn("Paused.", stdout.getvalue())
        self.assertIn("Resumed.", stdout.getvalue())

    def test_play_audio_chunks_with_controls_supports_next_chunk(self) -> None:
        played: list[object] = []
        commands = iter(["n"])

        def fake_play_audio_chunk(audio, *, samplerate=24000):
            played.append(audio)

        with patch.object(audiobook, "play_audio_chunk", side_effect=fake_play_audio_chunk):
            audiobook.play_audio_chunks_with_controls(
                [[1], [2], [3]],
                input_func=lambda _prompt: next(commands),
                output=io.StringIO(),
            )

        self.assertEqual(played, [[1], [3]])

    def test_play_audio_chunks_with_controls_reports_unknown_commands(self) -> None:
        commands = iter(["x", "q"])
        stdout = io.StringIO()

        with patch.object(audiobook, "play_audio_chunk") as play_audio_chunk:
            audiobook.play_audio_chunks_with_controls(
                [[1], [2]],
                input_func=lambda _prompt: next(commands),
                output=stdout,
            )

        play_audio_chunk.assert_called_once_with([1], samplerate=24000)
        self.assertIn("Unknown command at a chunk boundary", stdout.getvalue())

    def test_play_audio_chunks_with_controls_supports_previous_chunk(self) -> None:
        played: list[object] = []
        commands = iter(["b", ""])

        def fake_play_audio_chunk(audio, *, samplerate=24000):
            played.append(audio)

        with patch.object(audiobook, "play_audio_chunk", side_effect=fake_play_audio_chunk):
            audiobook.play_audio_chunks_with_controls(
                [[1], [2]],
                input_func=lambda _prompt: next(commands),
                output=io.StringIO(),
            )

        self.assertEqual(played, [[1], [1], [2]])

    def test_play_audio_chunks_with_controls_supports_quit(self) -> None:
        played: list[object] = []
        commands = iter(["q"])
        stdout = io.StringIO()

        def fake_play_audio_chunk(audio, *, samplerate=24000):
            played.append(audio)

        with patch.object(audiobook, "play_audio_chunk", side_effect=fake_play_audio_chunk):
            audiobook.play_audio_chunks_with_controls(
                [[1], [2]],
                input_func=lambda _prompt: next(commands),
                output=stdout,
            )

        self.assertEqual(played, [[1]])
        self.assertIn("Quitting playback.", stdout.getvalue())

    def test_synthesize_and_play_chunks_with_controls_synthesizes_lookahead_chunks_in_background(
        self,
    ) -> None:
        synthesized: list[str] = []
        played: list[str] = []
        commands = iter(["q"])
        pipeline = object()
        second_chunk_ready = threading.Event()

        def fake_synthesize_chunk(chunk, pipeline_arg, *, voice=None, speed=None):
            synthesized.append(chunk)
            self.assertIs(pipeline_arg, pipeline)
            if chunk == "Second sentence.":
                second_chunk_ready.set()
            return f"audio::{chunk}"

        def fake_play_audio_chunk(audio, *, samplerate=24000):
            if audio == "audio::First sentence.":
                self.assertTrue(
                    second_chunk_ready.wait(timeout=1.0),
                    "Expected lookahead chunk to synthesize while first chunk is playing.",
                )
            played.append(audio)

        with (
            patch.object(audiobook, "create_kokoro_pipeline", return_value=pipeline) as create_pipeline,
            patch.object(audiobook, "synthesize_chunk", side_effect=fake_synthesize_chunk),
            patch.object(audiobook, "play_audio_chunk", side_effect=fake_play_audio_chunk),
        ):
            audiobook.synthesize_and_play_chunks_with_controls(
                ["First sentence.", "Second sentence.", "Third sentence."],
                lookahead_size=1,
                input_func=lambda _prompt: next(commands),
                output=io.StringIO(),
            )

        create_pipeline.assert_called_once_with()
        self.assertEqual(played, ["audio::First sentence."])
        self.assertEqual(synthesized.count("First sentence."), 1)
        self.assertEqual(synthesized.count("Second sentence."), 1)

    def test_synthesize_and_play_chunks_with_controls_supports_previous_with_cache(self) -> None:
        synthesized: list[str] = []
        played: list[str] = []
        commands = iter(["b", "q"])
        pipeline = object()

        def fake_synthesize_chunk(chunk, _pipeline, *, voice=None, speed=None):
            synthesized.append(chunk)
            return f"audio::{chunk}"

        def fake_play_audio_chunk(audio, *, samplerate=24000):
            played.append(audio)

        with (
            patch.object(audiobook, "create_kokoro_pipeline", return_value=pipeline),
            patch.object(audiobook, "synthesize_chunk", side_effect=fake_synthesize_chunk),
            patch.object(audiobook, "play_audio_chunk", side_effect=fake_play_audio_chunk),
        ):
            audiobook.synthesize_and_play_chunks_with_controls(
                ["First sentence.", "Second sentence."],
                lookahead_size=1,
                input_func=lambda _prompt: next(commands),
                output=io.StringIO(),
            )

        self.assertEqual(synthesized.count("First sentence."), 1)
        self.assertEqual(synthesized.count("Second sentence."), 1)
        self.assertEqual(played, ["audio::First sentence.", "audio::First sentence."])

    def test_synthesize_and_play_chunks_with_controls_resynthesizes_evicted_rewind_chunk(self) -> None:
        synthesized: list[str] = []
        played: list[str] = []
        commands = iter(["", "p", "b", "b", "", "q"])
        pipeline = object()

        def fake_synthesize_chunk(chunk, _pipeline, *, voice=None, speed=None):
            synthesized.append(chunk)
            return f"audio::{chunk}"

        def fake_play_audio_chunk(audio, *, samplerate=24000):
            played.append(audio)

        with (
            patch.object(audiobook, "create_kokoro_pipeline", return_value=pipeline),
            patch.object(audiobook, "synthesize_chunk", side_effect=fake_synthesize_chunk),
            patch.object(audiobook, "play_audio_chunk", side_effect=fake_play_audio_chunk),
        ):
            audiobook.synthesize_and_play_chunks_with_controls(
                ["First sentence.", "Second sentence.", "Third sentence."],
                back_cache_size=0,
                lookahead_size=1,
                input_func=lambda _prompt: next(commands),
                output=io.StringIO(),
            )

        self.assertEqual(synthesized.count("First sentence."), 2)
        self.assertGreaterEqual(synthesized.count("Second sentence."), 1)
        self.assertEqual(
            played,
            ["audio::First sentence.", "audio::Second sentence.", "audio::First sentence."],
        )

    def test_synthesize_and_play_chunks_with_controls_stops_worker_thread_on_quit(self) -> None:
        commands = iter(["q"])
        pipeline = object()
        worker_name = "audiobook-lookahead-worker"

        def active_worker_count() -> int:
            return sum(
                1
                for thread in threading.enumerate()
                if thread.name == worker_name and thread.is_alive()
            )

        before_count = active_worker_count()

        with (
            patch.object(audiobook, "create_kokoro_pipeline", return_value=pipeline),
            patch.object(
                audiobook,
                "synthesize_chunk",
                side_effect=lambda chunk, *_args, **_kwargs: f"audio::{chunk}",
            ),
            patch.object(audiobook, "play_audio_chunk", side_effect=lambda *_args, **_kwargs: None),
        ):
            audiobook.synthesize_and_play_chunks_with_controls(
                ["First sentence.", "Second sentence."],
                lookahead_size=1,
                input_func=lambda _prompt: next(commands),
                output=io.StringIO(),
            )

        self.assertEqual(active_worker_count(), before_count)

    def test_synthesize_and_play_chunks_with_controls_stops_worker_thread_after_playback_end(
        self,
    ) -> None:
        pipeline = object()
        worker_name = "audiobook-lookahead-worker"

        def active_worker_count() -> int:
            return sum(
                1
                for thread in threading.enumerate()
                if thread.name == worker_name and thread.is_alive()
            )

        before_count = active_worker_count()

        with (
            patch.object(audiobook, "create_kokoro_pipeline", return_value=pipeline),
            patch.object(
                audiobook,
                "synthesize_chunk",
                side_effect=lambda chunk, *_args, **_kwargs: f"audio::{chunk}",
            ),
            patch.object(audiobook, "play_audio_chunk", side_effect=lambda *_args, **_kwargs: None),
        ):
            audiobook.synthesize_and_play_chunks_with_controls(
                ["First sentence."],
                lookahead_size=1,
                output=io.StringIO(),
            )

        self.assertEqual(active_worker_count(), before_count)

    def test_synthesize_and_play_chunks_with_controls_surfaces_worker_errors(self) -> None:
        commands = iter([""])
        pipeline = object()
        worker_name = "audiobook-lookahead-worker"

        def active_worker_count() -> int:
            return sum(
                1
                for thread in threading.enumerate()
                if thread.name == worker_name and thread.is_alive()
            )

        def fake_synthesize_chunk(chunk, _pipeline, *, voice=None, speed=None):
            if chunk == "Second sentence.":
                raise RuntimeError("lookahead synthesis failed")
            return f"audio::{chunk}"

        before_count = active_worker_count()

        with (
            patch.object(audiobook, "create_kokoro_pipeline", return_value=pipeline),
            patch.object(audiobook, "synthesize_chunk", side_effect=fake_synthesize_chunk),
            patch.object(audiobook, "play_audio_chunk", side_effect=lambda *_args, **_kwargs: None),
        ):
            with self.assertRaisesRegex(RuntimeError, "lookahead synthesis failed"):
                audiobook.synthesize_and_play_chunks_with_controls(
                    ["First sentence.", "Second sentence."],
                    lookahead_size=1,
                    input_func=lambda _prompt: next(commands),
                    output=io.StringIO(),
                )

        self.assertEqual(active_worker_count(), before_count)

    def test_evict_old_audio_cache_keeps_only_recent_back_window(self) -> None:
        audio_cache = {0: "a0", 1: "a1", 2: "a2", 3: "a3", 4: "a4"}

        audiobook._evict_old_audio_cache(audio_cache, current_index=4, back_cache_size=2)

        self.assertEqual(audio_cache, {2: "a2", 3: "a3", 4: "a4"})

    def test_evict_old_audio_cache_prunes_forward_entries_after_rewind(self) -> None:
        audio_cache = {0: "a0", 1: "a1", 2: "a2", 3: "a3"}

        audiobook._evict_old_audio_cache(audio_cache, current_index=1, back_cache_size=2)

        self.assertEqual(audio_cache, {0: "a0", 1: "a1"})

    def test_evict_old_audio_cache_honors_forward_window_when_configured(self) -> None:
        audio_cache = {0: "a0", 1: "a1", 2: "a2", 3: "a3", 4: "a4"}

        audiobook._evict_old_audio_cache(
            audio_cache,
            current_index=2,
            back_cache_size=1,
            forward_cache_size=1,
        )

        self.assertEqual(audio_cache, {1: "a1", 2: "a2", 3: "a3"})

    def test_play_audio_chunk_raises_when_sounddevice_is_missing(self) -> None:
        with patch.object(audiobook, "sd", None):
            with self.assertRaisesRegex(RuntimeError, "sounddevice is required for audio playback"):
                audiobook.play_audio_chunk([1, 2, 3])

    def test_play_audio_chunk_wraps_sounddevice_errors(self) -> None:
        fake_sd = MagicMock()
        fake_sd.play.side_effect = OSError("device unavailable")

        with patch.object(audiobook, "sd", fake_sd):
            with self.assertRaisesRegex(RuntimeError, "Unable to play audio chunk: device unavailable"):
                audiobook.play_audio_chunk([1, 2, 3])

    def test_play_audio_chunk_wraps_sounddevice_wait_errors(self) -> None:
        fake_sd = MagicMock()
        fake_sd.wait.side_effect = OSError("stream interrupted")

        with patch.object(audiobook, "sd", fake_sd):
            with self.assertRaisesRegex(RuntimeError, "Unable to play audio chunk: stream interrupted") as cm:
                audiobook.play_audio_chunk([1, 2, 3])

        self.assertIsInstance(cm.exception.__cause__, OSError)
        self.assertEqual(str(cm.exception.__cause__), "stream interrupted")

    def test_extract_pdf_text_reads_all_pages(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            pdf_path = Path(temp_dir) / "sample.pdf"
            document = fitz.open()
            first_page = document.new_page()
            first_page.insert_text((72, 72), "First page text")
            second_page = document.new_page()
            second_page.insert_text((72, 72), "Second page text")
            document.save(pdf_path)
            document.close()

            result = audiobook.extract_pdf_text(str(pdf_path))

        self.assertEqual(result.page_count, 2)
        self.assertIn("First page text", result.text)
        self.assertIn("Second page text", result.text)
        self.assertIn("\n", result.text)

    def test_extract_pdf_text_rejects_missing_path(self) -> None:
        with self.assertRaises(ValueError):
            audiobook.extract_pdf_text("")

    def test_extract_pdf_text_rejects_unreadable_pdf(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            pdf_path = Path(temp_dir) / "broken.pdf"
            pdf_path.write_text("not a real pdf", encoding="utf-8")

            with self.assertRaises(ValueError):
                audiobook.extract_pdf_text(str(pdf_path))

    def test_main_prints_summary_and_runs_playback_pipeline(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            pdf_path = Path(temp_dir) / "sample.pdf"
            document = fitz.open()
            page = document.new_page()
            page.insert_text((72, 72), "Hello audiobook")
            document.save(pdf_path)
            document.close()

            stdout = io.StringIO()
            stderr = io.StringIO()
            with (
                patch.object(audiobook, "clean_and_chunk", return_value=["First sentence.", "Second sentence."]) as clean_and_chunk,
                patch.object(audiobook, "synthesize_chunks", side_effect=AssertionError("must not pre-synthesize")),
                patch.object(
                    audiobook,
                    "synthesize_and_play_chunks_with_controls",
                ) as synthesize_and_play_chunks_with_controls,
                contextlib.redirect_stdout(stdout),
                contextlib.redirect_stderr(stderr),
            ):
                call_order = MagicMock()
                call_order.attach_mock(clean_and_chunk, "clean")
                call_order.attach_mock(synthesize_and_play_chunks_with_controls, "playback")
                exit_code = audiobook.main([str(pdf_path)])

        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr.getvalue(), "")
        self.assertIn("Extracted", stdout.getvalue())
        self.assertIn("characters from 1 pages", stdout.getvalue())
        self.assertEqual(clean_and_chunk.call_count, 1)
        self.assertIn("Hello audiobook", clean_and_chunk.call_args.args[0])
        self.assertEqual(
            call_order.mock_calls,
            [
                call.clean(ANY),
                call.playback(["First sentence.", "Second sentence."]),
            ],
        )

    def test_main_returns_one_when_playback_pipeline_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            pdf_path = Path(temp_dir) / "sample.pdf"
            document = fitz.open()
            page = document.new_page()
            page.insert_text((72, 72), "Hello audiobook")
            document.save(pdf_path)
            document.close()

            stdout = io.StringIO()
            stderr = io.StringIO()
            with (
                patch.object(audiobook, "clean_and_chunk", return_value=["First sentence."]),
                patch.object(
                    audiobook,
                    "synthesize_and_play_chunks_with_controls",
                    side_effect=ValueError("Audio chunk at index 1 is None"),
                ),
                contextlib.redirect_stdout(stdout),
                contextlib.redirect_stderr(stderr),
            ):
                exit_code = audiobook.main([str(pdf_path)])

        self.assertEqual(exit_code, 1)
        self.assertIn("Extracted", stdout.getvalue())
        self.assertIn("Error: Audio chunk at index 1 is None", stderr.getvalue())

    def test_main_returns_one_with_guidance_when_no_playable_text(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()

        with (
            patch.object(audiobook, "extract_pdf_text", return_value=audiobook.PdfExtractionResult(text="  \n\t ", page_count=2)),
            patch.object(audiobook, "clean_and_chunk", return_value=[]),
            patch.object(
                audiobook,
                "synthesize_and_play_chunks_with_controls",
                side_effect=AssertionError("should not synthesize or play"),
            ),
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
        ):
            exit_code = audiobook.main(["sample.pdf"])

        self.assertEqual(exit_code, 1)
        self.assertIn("No playable text was found after extraction/chunking", stderr.getvalue())
        self.assertIn("run OCR", stderr.getvalue())

    def test_main_returns_one_for_unreadable_pdf(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            pdf_path = Path(temp_dir) / "broken.pdf"
            pdf_path.write_text("not a real pdf", encoding="utf-8")

            stdout = io.StringIO()
            stderr = io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                exit_code = audiobook.main([str(pdf_path)])

        self.assertEqual(exit_code, 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("Error: Unable to read PDF", stderr.getvalue())

    def test_main_returns_one_for_missing_pdf_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            pdf_path = Path(temp_dir) / "missing.pdf"

            stdout = io.StringIO()
            stderr = io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                exit_code = audiobook.main([str(pdf_path)])

        self.assertEqual(exit_code, 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("Error: PDF not found", stderr.getvalue())

    def test_main_exits_with_usage_when_path_missing(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as cm:
                audiobook.main([])

        self.assertEqual(cm.exception.code, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("a PDF path is required", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
