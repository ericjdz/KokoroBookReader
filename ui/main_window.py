"""Main window for the PDF Audiobook PyQt6 GUI."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import threading
import time

from PyQt6.QtCore import QSettings, Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QFileDialog, QMainWindow, QMessageBox, QSplitter, QStackedWidget, QStatusBar, QVBoxLayout, QWidget,
)

from audiobook import (
    _evict_old_audio_cache,
    clean_and_chunk,
    create_kokoro_pipeline,
    detect_chapter_markers,
    download_kokoro_voice,
    np as numpy_backend,
    play_audio_chunk,
    sd as sounddevice_backend,
    synthesize_chunk,
)
from ui.bookmark import Bookmark, load_bookmark, save_bookmark, clear_bookmark, has_bookmark_for_file
from ui.config import AppConfig, load_config, save_config
from ui.document_extractor import extract_document, extract_pdf_sentences_with_page_map
from ui.player_model import PlayerModel
from ui.theme import catppuccin_stylesheet
from ui.widgets import ChapterSidebar, PlaybackControls, RawPdfView, TextView, VoiceHubDialog, VoiceSpeedPanel

KOKORO_VOICES = [
    "af_heart", "af_bella", "af_nicole", "af_sarah", "af_sky",
    "am_adam", "am_michael", "bm_george", "bm_lewis", "bf_emma",
]


class VoiceDownloadThread(QThread):
    """Background worker that downloads one Kokoro voice."""

    finished_ok = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, voice_id: str) -> None:
        super().__init__()
        self._voice_id = voice_id.strip()

    def run(self) -> None:
        try:
            downloaded = download_kokoro_voice(self._voice_id)
            self.finished_ok.emit(downloaded)
        except Exception as exc:
            self.failed.emit(str(exc))


class EngineThread(QThread):
    """Background thread running the audiobook engine.

    Signals:
        sentences_loaded(sentences: list[str]): All sentences extracted
        sentence_changed(index: int): Current sentence changed
        chapter_changed(index: int): Current chapter changed
        state_changed(state: str): 'playing', 'paused', 'stopped'
        progress_updated(current: int, total: int): Progress update
        error_occurred(message: str): Error during processing
    """

    sentences_loaded = pyqtSignal(object)
    sentence_changed = pyqtSignal(int)
    chapter_changed = pyqtSignal(int)
    state_changed = pyqtSignal(str)
    progress_updated = pyqtSignal(int, int)
    error_occurred = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self._file_path: str | None = None
        self._chunks: list[str] = []
        self._current_index: int = 0
        self._voice: str = "af_heart"
        self._speed: float = 1.0
        self._volume: float = 1.0
        self._pipeline = None
        self._playback_thread: threading.Thread | None = None
        self._lookahead_thread: threading.Thread | None = None
        self._playback_lock = threading.Lock()
        self._cache_condition = threading.Condition(self._playback_lock)
        self._audio_cache: dict[int, object] = {}
        self._worker_error: Exception | None = None
        self._stop_playback = threading.Event()
        self._paused = True
        self._back_cache_size = 10
        self._lookahead_size = 2
        self._doc_format = ""
        self._chunk_to_page_map: dict[int, int] = {}

    def set_voice(self, voice: str) -> None:
        self._voice = voice

    def set_speed(self, speed: float) -> None:
        self._speed = speed

    def set_volume(self, volume: float) -> None:
        self._volume = max(0.0, min(1.0, volume))

    def set_cache_sizes(self, back_cache_size: int, lookahead_size: int) -> None:
        with self._cache_condition:
            self._back_cache_size = max(0, back_cache_size)
            self._lookahead_size = max(0, lookahead_size)
            self._evict_cache_locked()
            self._cache_condition.notify_all()

    def _evict_cache_locked(self) -> None:
        _evict_old_audio_cache(
            self._audio_cache,
            self._current_index,
            back_cache_size=self._back_cache_size,
            forward_cache_size=self._lookahead_size,
        )

    def _reset_cache_locked(self) -> None:
        self._audio_cache.clear()
        self._worker_error = None

    def stop(self) -> None:
        self._stop_playback.set()
        self._paused = True
        with self._cache_condition:
            self._cache_condition.notify_all()

        if sounddevice_backend is not None:
            try:
                sounddevice_backend.stop()
            except Exception:
                pass

        playback_thread = self._playback_thread
        if playback_thread and playback_thread.is_alive():
            playback_thread.join(timeout=1.0)

        lookahead_thread = self._lookahead_thread
        if lookahead_thread and lookahead_thread.is_alive():
            lookahead_thread.join(timeout=1.0)

        with self._cache_condition:
            self._reset_cache_locked()
            self._playback_thread = None
            self._lookahead_thread = None

    def load_file(self, file_path: str) -> None:
        """Load a document file for processing."""
        self.stop()
        self._stop_playback.clear()
        self._file_path = file_path
        self._current_index = 0
        self._chunks = []
        self._pipeline = None
        self._doc_format = ""
        self._chunk_to_page_map = {}
        self.start()

    def run(self) -> None:
        if not self._file_path:
            self.error_occurred.emit("No document loaded.")
            return

        try:
            result = extract_document(self._file_path)
            self._doc_format = result.format
            if not result.text.strip():
                self.error_occurred.emit(
                    f"No text found in {result.format.upper()} file. "
                    f"It may be scanned/image-only. OCR support coming soon."
                )
                return

            if result.format == "pdf":
                pdf_result = extract_pdf_sentences_with_page_map(self._file_path)
                self._chunks = pdf_result.sentences
                self._chunk_to_page_map = pdf_result.chunk_to_page
            else:
                self._chunks = clean_and_chunk(result.text)
                self._chunk_to_page_map = {}

            if not self._chunks:
                self.error_occurred.emit("No playable text found after extraction.")
                return

            with self._cache_condition:
                self._reset_cache_locked()
                self._evict_cache_locked()

            self._start_lookahead_worker()

            self.sentences_loaded.emit(self._chunks)
            self.state_changed.emit("stopped")
            self.progress_updated.emit(0, len(self._chunks))

        except ImportError as exc:
            self.error_occurred.emit(f"Missing dependency: {exc}")
        except Exception as exc:
            self.error_occurred.emit(str(exc))

    def play(self) -> None:
        if not self._chunks:
            self.error_occurred.emit("No document is loaded, or no playable text was found.")
            return

        self._paused = False
        self._stop_playback.clear()
        self._start_lookahead_worker()
        with self._cache_condition:
            self._cache_condition.notify_all()
        self.state_changed.emit("playing")

        playback_thread = self._playback_thread
        if playback_thread and playback_thread.is_alive():
            return

        self._playback_thread = threading.Thread(
            target=self._playback_loop,
            name="audiobook-gui-playback",
            daemon=True,
        )
        self._playback_thread.start()

    def pause(self) -> None:
        self._paused = True
        self.state_changed.emit("paused")

    def next_chunk(self) -> None:
        with self._cache_condition:
            if self._current_index < len(self._chunks) - 1:
                self._current_index += 1
                self._evict_cache_locked()
                self._cache_condition.notify_all()
                current_index = self._current_index
            else:
                return
        self.sentence_changed.emit(current_index)
        self.progress_updated.emit(current_index, len(self._chunks))

    def previous_chunk(self) -> None:
        with self._cache_condition:
            if self._current_index > 0:
                self._current_index -= 1
                self._evict_cache_locked()
                self._cache_condition.notify_all()
                current_index = self._current_index
            else:
                return
        self.sentence_changed.emit(current_index)
        self.progress_updated.emit(current_index, len(self._chunks))

    def jump_to(self, index: int) -> None:
        if 0 <= index < len(self._chunks):
            with self._cache_condition:
                self._current_index = index
                self._evict_cache_locked()
                self._cache_condition.notify_all()
            self.sentence_changed.emit(index)
            self.progress_updated.emit(index, len(self._chunks))

    def _start_lookahead_worker(self) -> None:
        lookahead_thread = self._lookahead_thread
        if lookahead_thread and lookahead_thread.is_alive():
            return

        self._lookahead_thread = threading.Thread(
            target=self._lookahead_loop,
            name="audiobook-gui-lookahead",
            daemon=True,
        )
        self._lookahead_thread.start()

    def _lookahead_loop(self) -> None:
        while not self._stop_playback.is_set():
            with self._cache_condition:
                if not self._chunks:
                    self._cache_condition.wait(timeout=0.1)
                    continue

                if self._worker_error is not None:
                    return

                self._evict_cache_locked()
                max_index = min(len(self._chunks), self._current_index + self._lookahead_size + 1)
                target_index: int | None = None
                for candidate in range(self._current_index, max_index):
                    if candidate not in self._audio_cache:
                        target_index = candidate
                        break

                if target_index is None:
                    self._cache_condition.wait(timeout=0.05)
                    continue

                text = self._chunks[target_index]
                voice = self._voice
                speed = self._speed

            try:
                if self._pipeline is None:
                    self._pipeline = create_kokoro_pipeline()
                audio = synthesize_chunk(text, self._pipeline, voice=voice, speed=speed)
            except Exception as exc:
                with self._cache_condition:
                    self._worker_error = exc
                    self._cache_condition.notify_all()
                self.error_occurred.emit(str(exc))
                return

            with self._cache_condition:
                if self._stop_playback.is_set():
                    return
                if 0 <= target_index < len(self._chunks):
                    self._audio_cache[target_index] = audio
                self._evict_cache_locked()
                self._cache_condition.notify_all()

    def _playback_loop(self) -> None:
        try:
            while not self._stop_playback.is_set():
                if self._paused:
                    time.sleep(0.05)
                    continue

                with self._cache_condition:
                    while (
                        not self._stop_playback.is_set()
                        and self._current_index < len(self._chunks)
                        and self._current_index not in self._audio_cache
                        and self._worker_error is None
                    ):
                        self._cache_condition.notify_all()
                        self._cache_condition.wait(timeout=0.1)

                    if self._worker_error is not None:
                        raise self._worker_error

                    if self._current_index >= len(self._chunks):
                        break

                    index = self._current_index
                    audio = self._audio_cache.get(index)
                    volume = self._volume

                if audio is None:
                    continue

                self.sentence_changed.emit(index)
                self.progress_updated.emit(index, len(self._chunks))

                if self._stop_playback.is_set():
                    break

                play_audio_chunk(self._apply_volume(audio, volume))

                with self._cache_condition:
                    if self._current_index == index:
                        self._current_index += 1
                    self._evict_cache_locked()
                    self._cache_condition.notify_all()
                    reached_end = self._current_index >= len(self._chunks)

                self.progress_updated.emit(self._current_index, len(self._chunks))

                if reached_end:
                    break
        except Exception as exc:
            self.error_occurred.emit(str(exc))
        finally:
            self._paused = True
            self.state_changed.emit("stopped")

    @staticmethod
    def _apply_volume(audio: object, volume: float) -> object:
        if volume >= 0.999:
            return audio

        try:
            return audio * volume
        except Exception:
            pass

        if numpy_backend is not None:
            try:
                return numpy_backend.asarray(audio, dtype=numpy_backend.float32) * volume
            except Exception:
                return audio

        return audio


class MainWindow(QMainWindow):
    """Main application window for the PDF Audiobook player."""

    def __init__(self, file_path: str | None = None) -> None:
        super().__init__()
        self._settings = QSettings("PDFAudiobook", "AudiobookPlayer")
        self._config = load_config()
        self._engine = EngineThread()
        self._model = PlayerModel()
        self._file_path = file_path

        self.sidebar: ChapterSidebar | None = None
        self.text_view: TextView | None = None
        self.pdf_view: RawPdfView | None = None
        self.content_stack: QStackedWidget | None = None
        self.controls: PlaybackControls | None = None
        self.voice_speed_panel: VoiceSpeedPanel | None = None
        self._raw_pdf_action = None
        self._auto_pdf_sync_action = None
        self._voice_hub_dialog: VoiceHubDialog | None = None
        self._voice_download_worker: VoiceDownloadThread | None = None

        self._setup_ui()
        self._apply_config_to_ui()
        self._connect_signals()
        self._apply_theme()
        self._restore_geometry()

        self._engine.set_voice(self._config.voice)
        self._engine.set_speed(self._config.speed)
        self._engine.set_volume(self._config.volume)
        self._engine.set_cache_sizes(self._config.back_cache_size, self._config.lookahead_size)

        if self._file_path:
            self._load_file(self._file_path)

    def _apply_config_to_ui(self) -> None:
        """Apply loaded configuration to UI widgets."""
        if self.voice_speed_panel:
            self.voice_speed_panel.set_voices(self._build_voice_list())
            self.voice_speed_panel.set_current_voice(self._config.voice)
            self.voice_speed_panel.set_speed(self._config.speed)
            self.voice_speed_panel.set_volume(self._config.volume)

        if self._raw_pdf_action:
            self._raw_pdf_action.blockSignals(True)
            self._raw_pdf_action.setChecked(self._config.view_mode == "pdf")
            self._raw_pdf_action.blockSignals(False)

        if self._auto_pdf_sync_action:
            self._auto_pdf_sync_action.blockSignals(True)
            self._auto_pdf_sync_action.setChecked(self._config.auto_pdf_sync)
            self._auto_pdf_sync_action.blockSignals(False)

        self._apply_view_mode(self._config.view_mode)

    def _setup_ui(self) -> None:
        self.setWindowTitle("PDF Audiobook")
        self.setMinimumSize(900, 650)

        self._create_menu_bar()

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.sidebar = ChapterSidebar()
        self.sidebar.set_model(self._model)
        splitter.addWidget(self.sidebar)

        text_container = QWidget()
        text_layout = QVBoxLayout(text_container)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(0)

        self.text_view = TextView()
        self.pdf_view = RawPdfView()
        self.pdf_view.load_failed.connect(self._on_error)

        self.content_stack = QStackedWidget()
        self.content_stack.addWidget(self.text_view)
        self.content_stack.addWidget(self.pdf_view)
        text_layout.addWidget(self.content_stack)

        self.controls = PlaybackControls()
        text_layout.addWidget(self.controls)

        splitter.addWidget(text_container)
        splitter.setSizes([200, 700])

        main_layout.addWidget(splitter)

        self.voice_speed_panel = VoiceSpeedPanel(voices=self._build_voice_list())
        self.sidebar.layout().addWidget(self.voice_speed_panel)

        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("Ready")

    def _create_menu_bar(self) -> None:
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("&File")
        open_action = file_menu.addAction("&Open Document...")
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self._open_file_dialog)
        file_menu.addSeparator()
        export_action = file_menu.addAction("&Export to WAV...")
        export_action.setShortcut("Ctrl+E")
        export_action.triggered.connect(self._export_to_wav)
        file_menu.addSeparator()
        exit_action = file_menu.addAction("E&xit")
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)

        bookmark_menu = menu_bar.addMenu("&Bookmark")
        save_action = bookmark_menu.addAction("&Save Bookmark")
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self._save_current_bookmark)
        clear_action = bookmark_menu.addAction("&Clear Bookmark")
        clear_action.triggered.connect(self._clear_current_bookmark)

        help_menu = menu_bar.addMenu("&Help")
        about_action = help_menu.addAction("&About")
        about_action.triggered.connect(self._show_about)

        view_menu = menu_bar.addMenu("&View")
        self._raw_pdf_action = view_menu.addAction("Raw &PDF View")
        self._raw_pdf_action.setCheckable(True)
        self._raw_pdf_action.triggered.connect(self._on_toggle_raw_pdf_view)

        self._auto_pdf_sync_action = view_menu.addAction("Auto Sync PDF With Playback")
        self._auto_pdf_sync_action.setCheckable(True)
        self._auto_pdf_sync_action.triggered.connect(self._on_toggle_auto_pdf_sync)

        voices_menu = menu_bar.addMenu("&Voices")
        voice_hub_action = voices_menu.addAction("Voice &Hub...")
        voice_hub_action.triggered.connect(self._open_voice_hub)

    def _connect_signals(self) -> None:
        self.controls.play_clicked.connect(self._engine.play)
        self.controls.pause_clicked.connect(self._engine.pause)
        self.controls.next_clicked.connect(self._engine.next_chunk)
        self.controls.previous_clicked.connect(self._engine.previous_chunk)
        self.controls.chapter_back_clicked.connect(self._on_chapter_back)
        self.controls.chapter_forward_clicked.connect(self._on_chapter_forward)
        self.controls.progress_clicked.connect(self._on_progress_click)

        self.text_view.sentence_clicked.connect(self._engine.jump_to)
        self.sidebar.chapter_clicked.connect(self._on_chapter_click)

        self._engine.sentences_loaded.connect(self._on_sentences_loaded)
        self._engine.sentence_changed.connect(self._on_sentence_changed)
        self._engine.state_changed.connect(self._on_state_changed)
        self._engine.progress_updated.connect(self._on_progress_updated)
        self._engine.error_occurred.connect(self._on_error)

        self.voice_speed_panel.voice_changed.connect(self._on_voice_changed)
        self.voice_speed_panel.speed_changed.connect(self._on_speed_changed)
        self.voice_speed_panel.volume_changed.connect(self._on_volume_changed)

        if self.pdf_view is not None:
            self.pdf_view.page_changed.connect(self._on_pdf_page_changed)

    def _apply_theme(self) -> None:
        self.setStyleSheet(catppuccin_stylesheet())

    def _restore_geometry(self) -> None:
        geo = self._settings.value("geometry")
        if geo is not None:
            self.restoreGeometry(geo)

    def _save_geometry(self) -> None:
        self._settings.setValue("geometry", self.saveGeometry())

    def closeEvent(self, event) -> None:
        self._save_geometry()
        save_config(self._config)

        if self._voice_download_worker is not None and self._voice_download_worker.isRunning():
            self._voice_download_worker.quit()
            self._voice_download_worker.wait(1000)

        self._engine.stop()
        if self._engine.isRunning():
            self._engine.terminate()
            self._engine.wait(1000)
        super().closeEvent(event)

    def _open_file_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Document", "",
            "Supported Documents (*.pdf *.epub *.docx *.txt);;"
            "PDF Files (*.pdf);;EPUB Files (*.epub);;"
            "DOCX Files (*.docx);;Text Files (*.txt);;All Files (*)"
        )
        if path:
            self._load_file(path)

    def _load_file(self, path: str) -> None:
        self._file_path = path
        self.setWindowTitle(f"PDF Audiobook \u2014 {Path(path).name}")
        self._status_bar.showMessage(f"Loading: {Path(path).name}...")

        if self._engine.isRunning():
            self._engine.stop()
            self._engine.terminate()
            self._engine.wait(1000)

        self._engine = EngineThread()
        self._engine.set_voice(self._config.voice)
        self._engine.set_speed(self._config.speed)
        self._engine.set_volume(self._config.volume)
        self._engine.set_cache_sizes(self._config.back_cache_size, self._config.lookahead_size)
        self._engine.load_file(path)
        self._connect_signals()
        self._apply_view_mode(self._config.view_mode)

        # Check for bookmark
        bookmark = load_bookmark()
        if bookmark and has_bookmark_for_file(path) and self._config.auto_resume:
            self._ask_resume(bookmark)

    def _on_sentences_loaded(self, sentences: list[str]) -> None:
        self.text_view.set_sentences(sentences)
        chapters = detect_chapter_markers(sentences)
        self._model.update_chapters(chapters, len(sentences))
        self.controls.set_status(0, len(sentences))
        fmt = self._engine._doc_format or "document"

        if fmt == "pdf" and self.pdf_view is not None:
            self.pdf_view.load_pdf(self._file_path or "")

        self._apply_view_mode(self._config.view_mode)

        self._status_bar.showMessage(
            f"Loaded {len(sentences)} sentences from {fmt.upper()}, {len(chapters.markers)} chapters."
        )

        # Auto-resume from bookmark
        bookmark = load_bookmark()
        if bookmark and has_bookmark_for_file(self._file_path or ""):
            if 0 <= bookmark.chunk_index < len(sentences):
                self._engine.jump_to(bookmark.chunk_index)

    def _on_sentence_changed(self, index: int) -> None:
        self.text_view.highlight_sentence(index)
        self._model.update_current_sentence(index)
        self.controls.set_status(index + 1, self._model.total_sentences)

        if self._config.auto_pdf_sync and self._config.view_mode == "pdf":
            self._sync_pdf_to_sentence(index)

    def _on_progress_updated(self, current: int, total: int) -> None:
        self.controls.set_progress(current, total)

    def _on_state_changed(self, state: str) -> None:
        self.controls.set_playing(state == "playing")
        self._status_bar.showMessage(f"Playback: {state}")

    def _on_error(self, message: str) -> None:
        QMessageBox.critical(self, "Error", message)
        self._status_bar.showMessage(f"Error: {message}")

    def _on_progress_click(self, position: float) -> None:
        total = self._model.total_sentences
        if total > 0:
            target = int(position * total)
            self._engine.jump_to(target)

    def _on_chapter_click(self, index: int) -> None:
        if not self._model._chapters or index >= len(self._model._chapters):
            return
        chapter_index = self._model._chapters[index].start_index
        self._engine.jump_to(chapter_index)

    def _on_chapter_back(self) -> None:
        if not self._model._chapters:
            return

        current = self._engine._current_index
        target = None
        for chapter in self._model._chapters:
            if chapter.start_index < current:
                target = chapter.start_index
            else:
                break
        if target is not None:
            self._engine.jump_to(target)

    def _on_chapter_forward(self) -> None:
        if not self._model._chapters:
            return

        current = self._engine._current_index
        for chapter in self._model._chapters:
            if chapter.start_index > current:
                self._engine.jump_to(chapter.start_index)
                return

    def _on_voice_changed(self, voice: str) -> None:
        self._config.voice = voice
        self._engine.set_voice(voice)
        self._status_bar.showMessage(f"Voice: {voice}")
        save_config(self._config)

    def _build_voice_list(self) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []

        for voice in KOKORO_VOICES + list(self._config.custom_voices):
            voice_id = voice.strip()
            if not voice_id or voice_id in seen:
                continue
            seen.add(voice_id)
            ordered.append(voice_id)

        return ordered

    def _refresh_voice_list(self, preferred_voice: str | None = None) -> None:
        voices = self._build_voice_list()
        if self.voice_speed_panel is not None:
            self.voice_speed_panel.set_voices(voices)

        target_voice = preferred_voice or self._config.voice
        if target_voice not in voices and voices:
            target_voice = voices[0]

        if target_voice:
            self._config.voice = target_voice
            self._engine.set_voice(target_voice)
            if self.voice_speed_panel is not None:
                self.voice_speed_panel.set_current_voice(target_voice)

    def _open_voice_hub(self) -> None:
        dialog = VoiceHubDialog(
            installed_voices=self._build_voice_list(),
            downloadable_voices=self._build_voice_list(),
            parent=self,
        )
        self._voice_hub_dialog = dialog
        dialog.download_requested.connect(self._start_voice_download)
        dialog.add_log("Select a known voice or add a custom voice id, then click Download Selected.")
        dialog.exec()
        self._voice_hub_dialog = None

    def _start_voice_download(self, voice_id: str) -> None:
        normalized = voice_id.strip()
        if not normalized:
            return

        if self._voice_download_worker is not None and self._voice_download_worker.isRunning():
            if self._voice_hub_dialog is not None:
                self._voice_hub_dialog.add_log("A download is already in progress.")
            return

        self._voice_download_worker = VoiceDownloadThread(normalized)
        self._voice_download_worker.finished_ok.connect(self._on_voice_download_success)
        self._voice_download_worker.failed.connect(self._on_voice_download_failed)
        self._voice_download_worker.finished.connect(self._on_voice_download_finished)

        if self._voice_hub_dialog is not None:
            self._voice_hub_dialog.set_busy(True)
            self._voice_hub_dialog.add_log(f"Downloading voice: {normalized}")

        self._status_bar.showMessage(f"Downloading voice: {normalized}...")
        self._voice_download_worker.start()

    def _on_voice_download_success(self, voice_id: str) -> None:
        if voice_id not in self._config.custom_voices and voice_id not in KOKORO_VOICES:
            self._config.custom_voices.append(voice_id)

        self._refresh_voice_list(preferred_voice=voice_id)
        save_config(self._config)

        if self._voice_hub_dialog is not None:
            self._voice_hub_dialog.add_log(f"Downloaded: {voice_id}")
            self._voice_hub_dialog.set_installed_voices(self._build_voice_list())
            self._voice_hub_dialog.set_downloadable_voices(self._build_voice_list())

        self._status_bar.showMessage(f"Voice downloaded: {voice_id}")

    def _on_voice_download_failed(self, message: str) -> None:
        if self._voice_hub_dialog is not None:
            self._voice_hub_dialog.add_log(f"Download failed: {message}")
        self._status_bar.showMessage("Voice download failed")
        QMessageBox.warning(self, "Voice Download Failed", message)

    def _on_voice_download_finished(self) -> None:
        if self._voice_hub_dialog is not None:
            self._voice_hub_dialog.set_busy(False)
        self._voice_download_worker = None

    def _on_toggle_raw_pdf_view(self, checked: bool) -> None:
        self._config.view_mode = "pdf" if checked else "text"
        self._apply_view_mode(self._config.view_mode)
        save_config(self._config)

    def _on_toggle_auto_pdf_sync(self, checked: bool) -> None:
        self._config.auto_pdf_sync = checked
        save_config(self._config)

    def _apply_view_mode(self, mode: str) -> None:
        if self.content_stack is None:
            return

        if mode == "pdf":
            is_pdf_loaded = self._engine._doc_format == "pdf" and self.pdf_view is not None and self.pdf_view.page_count > 0
            if is_pdf_loaded:
                self.content_stack.setCurrentWidget(self.pdf_view)
                self._status_bar.showMessage("View mode: Raw PDF")
                return

            self.content_stack.setCurrentWidget(self.text_view)
            if self._engine._doc_format and self._engine._doc_format != "pdf":
                self._status_bar.showMessage("Raw PDF view is only available for PDF documents. Showing text view.")
            else:
                self._status_bar.showMessage("PDF view is not ready yet. Showing text view.")
            return

        self.content_stack.setCurrentWidget(self.text_view)
        self._status_bar.showMessage("View mode: Text")

    def _sync_pdf_to_sentence(self, sentence_index: int) -> None:
        if self.pdf_view is None:
            return

        target_page = self._engine._chunk_to_page_map.get(sentence_index)
        if target_page is None:
            return

        self.pdf_view.set_page(target_page)

    def _on_pdf_page_changed(self, page_index: int) -> None:
        if self._config.view_mode == "pdf":
            self._status_bar.showMessage(f"Raw PDF page {page_index + 1}")

    def _ask_resume(self, bookmark: Bookmark) -> None:
        """Ask user if they want to resume from bookmark."""
        reply = QMessageBox.question(
            self,
            "Resume Playback?",
            f"Resume from chunk {bookmark.chunk_index + 1} "
            f"(last played on {bookmark.timestamp})?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply == QMessageBox.StandardButton.Yes:
            # Will be handled in _on_sentences_loaded
            pass

    def _save_current_bookmark(self) -> None:
        """Save current position as bookmark."""
        if not self._file_path:
            return
        bookmark = Bookmark(
            file_path=self._file_path,
            chunk_index=self._engine._current_index,
            total_chunks=self._model.total_sentences,
            timestamp=datetime.now(timezone.utc).isoformat(),
            voice=self._config.voice,
            speed=self._config.speed,
        )
        save_bookmark(bookmark)
        self._status_bar.showMessage("Bookmark saved.")

    def _clear_current_bookmark(self) -> None:
        """Clear saved bookmark."""
        clear_bookmark()
        self._status_bar.showMessage("Bookmark cleared.")

    def _export_to_wav(self) -> None:
        """Export current document to WAV files."""
        if not self._file_path:
            QMessageBox.warning(self, "Export", "No document loaded.")
            return

        output_dir = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if not output_dir:
            return

        try:
            from ui.export import export_full_audiobook
            from audiobook import create_kokoro_pipeline, synthesize_chunk

            pipeline = create_kokoro_pipeline()
            voice = self._config.voice
            speed = self._config.speed

            def synthesize_fn(text: str):
                return synthesize_chunk(text, pipeline, voice=voice, speed=speed)

            output_path = Path(output_dir) / f"{Path(self._file_path).stem}.wav"
            export_full_audiobook(
                self._engine._chunks,
                str(output_path),
                synthesize_fn,
            )
            QMessageBox.information(
                self, "Export Complete", f"Audio exported to:\n{output_path}"
            )
        except ImportError as exc:
            QMessageBox.critical(self, "Export Error", str(exc))
        except Exception as exc:
            QMessageBox.critical(self, "Export Error", f"Export failed: {exc}")

    def _on_speed_changed(self, speed: float) -> None:
        self._config.speed = speed
        self._engine.set_speed(speed)
        self._status_bar.showMessage(f"Speed: {speed:.1f}x")
        save_config(self._config)

    def _on_volume_changed(self, volume: float) -> None:
        self._config.volume = volume
        self._engine.set_volume(volume)
        self._status_bar.showMessage(f"Volume: {int(volume * 100)}%")
        save_config(self._config)

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "About PDF Audiobook",
            "PDF Audiobook Player\n\n"
            "A local, real-time audiobook player for PDF, EPUB, DOCX, and TXT documents.\n"
            "Powered by Kokoro TTS and PyQt6.\n\n"
            "Version 0.3.0",
        )
