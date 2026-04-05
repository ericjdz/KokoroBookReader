"""Reusable PyQt6 widget components for the audiobook player."""
from __future__ import annotations

from typing import Sequence

from PyQt6.QtCore import QEvent, Qt, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap, QTextCursor
from PyQt6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QProgressBar, QPushButton, QSlider,
    QDialog, QLineEdit, QListWidget, QPlainTextEdit, QScrollArea, QTextBrowser, QTreeView,
    QVBoxLayout, QWidget,
)

from ui.theme import MOCHA


class PlaybackControls(QWidget):
    """Playback control bar with transport buttons and progress bar.

    Signals:
        play_clicked: User pressed play
        pause_clicked: User pressed pause
        next_clicked: User pressed next chunk
        previous_clicked: User pressed previous chunk
        chapter_forward_clicked: User pressed chapter forward
        chapter_back_clicked: User pressed chapter back
        progress_clicked(position): User clicked progress bar (0.0-1.0)
    """

    play_clicked = pyqtSignal()
    pause_clicked = pyqtSignal()
    next_clicked = pyqtSignal()
    previous_clicked = pyqtSignal()
    chapter_forward_clicked = pyqtSignal()
    chapter_back_clicked = pyqtSignal()
    progress_clicked = pyqtSignal(float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._is_playing = False
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)

        self._progress = QProgressBar()
        self._progress.setTextVisible(False)
        self._progress.setFixedHeight(4)
        self._progress.mousePressEvent = self._on_progress_click
        layout.addWidget(self._progress)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(4)

        self._chapter_back_btn = QPushButton("\u23ee")
        self._chapter_back_btn.setFixedSize(36, 36)
        self._chapter_back_btn.clicked.connect(self.chapter_back_clicked.emit)

        self._prev_btn = QPushButton("\u25c0\u25c0")
        self._prev_btn.setFixedSize(36, 36)
        self._prev_btn.clicked.connect(self.previous_clicked.emit)

        self._play_btn = QPushButton("\u25b6")
        self._play_btn.setFixedSize(44, 44)
        self._play_btn.setStyleSheet(
            f"background-color: {MOCHA['blue']}; color: {MOCHA['crust']}; "
            f"border-radius: 22px; font-size: 18px;"
        )
        self._play_btn.clicked.connect(self._on_play_pause_clicked)

        self._next_btn = QPushButton("\u25b6\u25b6")
        self._next_btn.setFixedSize(36, 36)
        self._next_btn.clicked.connect(self.next_clicked.emit)

        self._chapter_fwd_btn = QPushButton("\u23ed")
        self._chapter_fwd_btn.setFixedSize(36, 36)
        self._chapter_fwd_btn.clicked.connect(self.chapter_forward_clicked.emit)

        btn_layout.addStretch()
        btn_layout.addWidget(self._chapter_back_btn)
        btn_layout.addWidget(self._prev_btn)
        btn_layout.addWidget(self._play_btn)
        btn_layout.addWidget(self._next_btn)
        btn_layout.addWidget(self._chapter_fwd_btn)
        btn_layout.addStretch()

        layout.addLayout(btn_layout)

        self._status_label = QLabel("Sentence 0 / 0")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._status_label)

    def _on_progress_click(self, event) -> None:
        width = self._progress.width()
        if width > 0:
            position = event.pos().x() / width
            self.progress_clicked.emit(max(0.0, min(1.0, position)))

    def set_progress(self, value: int, maximum: int = 100) -> None:
        self._progress.setMaximum(maximum)
        self._progress.setValue(value)

    def set_status(self, current: int, total: int) -> None:
        self._status_label.setText(f"Sentence {current} / {total}")

    def set_playing(self, playing: bool) -> None:
        self._is_playing = playing
        self._play_btn.setText("\u23f8" if playing else "\u25b6")

    def _on_play_pause_clicked(self) -> None:
        if self._is_playing:
            self.pause_clicked.emit()
        else:
            self.play_clicked.emit()


class ChapterSidebar(QWidget):
    """Chapter navigation sidebar with expandable chapter list.

    Signals:
        chapter_clicked(index): User clicked a chapter
    """

    chapter_clicked = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()
        self.setFixedWidth(200)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QLabel("\U0001f4da Chapters")
        header.setStyleSheet(
            f"color: {MOCHA['blue']}; font-weight: bold; font-size: 12px; "
            f"padding: 10px 12px; border-bottom: 1px solid {MOCHA['surface0']};"
        )
        layout.addWidget(header)

        self._tree = QTreeView()
        self._tree.setHeaderHidden(True)
        self._tree.clicked.connect(self._on_item_clicked)
        layout.addWidget(self._tree)

    def set_model(self, model) -> None:
        self._tree.setModel(model)

    def _on_item_clicked(self, index) -> None:
        self.chapter_clicked.emit(index.row())

    def set_current_chapter(self, index: int) -> None:
        from PyQt6.QtCore import QModelIndex
        model_index = self._tree.model().index(index, 0, QModelIndex())
        self._tree.setCurrentIndex(model_index)
        self._tree.scrollTo(model_index)


class TextView(QTextBrowser):
    """Text view with synchronized sentence highlighting.

    Signals:
        sentence_clicked(index): User clicked a sentence to jump to it
    """

    sentence_clicked = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._sentences: list[str] = []
        self._highlighted_index: int = -1
        self.setReadOnly(True)
        self.setOpenExternalLinks(False)
        self.setStyleSheet(
            f"QTextBrowser {{ background-color: {MOCHA['base']}; "
            f"color: {MOCHA['text']}; border: none; font-size: 12px; padding: 12px; }}"
        )

    def set_sentences(self, sentences: Sequence[str]) -> None:
        """Set all sentences and render them as HTML."""
        self._sentences = list(sentences)
        self._render_text()

    def highlight_sentence(self, index: int) -> None:
        """Highlight the sentence at the given index."""
        if index < 0 or index >= len(self._sentences):
            return

        self._highlighted_index = index
        self._render_text()
        self._scroll_to_highlight()

    def _render_text(self) -> None:
        """Render all sentences as HTML with highlighting."""
        parts = []
        for i, sentence in enumerate(self._sentences):
            escaped = sentence.replace("<", "&lt;").replace(">", "&gt;")
            if i == self._highlighted_index:
                parts.append(
                    f'<p style="background-color: {MOCHA["yellow"]}; '
                    f'color: {MOCHA["crust"]}; padding: 4px 8px; '
                    f'border-radius: 4px; border-left: 3px solid {MOCHA["yellow"]}; '
                    f'margin: 0 0 6px;">{escaped}</p>'
                )
            else:
                parts.append(
                    f'<p style="color: {MOCHA["overlay0"]}; '
                    f'margin: 0 0 6px; line-height: 1.7;">{escaped}</p>'
                )
        self.setHtml("".join(parts))

    def _scroll_to_highlight(self) -> None:
        """Scroll to make the highlighted sentence visible."""
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        for _ in range(self._highlighted_index):
            cursor.movePosition(QTextCursor.MoveOperation.NextBlock)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    def mousePressEvent(self, event) -> None:
        cursor = self.cursorForPosition(event.pos())
        block_num = cursor.blockNumber()
        if 0 <= block_num < len(self._sentences):
            self.sentence_clicked.emit(block_num)
        super().mousePressEvent(event)


class VoiceSpeedPanel(QWidget):
    """Voice selection and speed control panel.

    Signals:
        voice_changed(voice: str): User selected a new voice
        speed_changed(speed: float): User changed playback speed
        volume_changed(volume: float): User changed playback volume
    """

    voice_changed = pyqtSignal(str)
    speed_changed = pyqtSignal(float)
    volume_changed = pyqtSignal(float)

    def __init__(
        self,
        voices: Sequence[str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._setup_ui()
        if voices:
            self.set_voices(list(voices))

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        voice_layout = QHBoxLayout()
        voice_layout.addWidget(QLabel("Voice:"))
        self._voice_combo = QComboBox()
        voice_layout.addWidget(self._voice_combo)
        self._voice_combo.currentTextChanged.connect(self.voice_changed.emit)
        layout.addLayout(voice_layout)

        speed_layout = QHBoxLayout()
        speed_layout.addWidget(QLabel("Speed:"))
        self._speed_slider = QSlider(Qt.Orientation.Horizontal)
        self._speed_slider.setMinimum(5)
        self._speed_slider.setMaximum(20)
        self._speed_slider.setValue(10)
        self._speed_slider.valueChanged.connect(self._on_speed_changed)
        speed_layout.addWidget(self._speed_slider)

        self._speed_label = QLabel("1.0x")
        self._speed_label.setFixedWidth(36)
        self._speed_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        speed_layout.addWidget(self._speed_label)

        layout.addLayout(speed_layout)

        volume_layout = QHBoxLayout()
        volume_layout.addWidget(QLabel("Volume:"))
        self._volume_slider = QSlider(Qt.Orientation.Horizontal)
        self._volume_slider.setMinimum(0)
        self._volume_slider.setMaximum(100)
        self._volume_slider.setValue(100)
        self._volume_slider.valueChanged.connect(self._on_volume_changed)
        volume_layout.addWidget(self._volume_slider)

        self._volume_label = QLabel("100%")
        self._volume_label.setFixedWidth(40)
        self._volume_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        volume_layout.addWidget(self._volume_label)

        layout.addLayout(volume_layout)

    def _on_speed_changed(self, value: int) -> None:
        speed = value / 10.0
        self._speed_label.setText(f"{speed:.1f}x")
        self.speed_changed.emit(speed)

    def _on_volume_changed(self, value: int) -> None:
        volume = value / 100.0
        self._volume_label.setText(f"{value}%")
        self.volume_changed.emit(volume)

    def set_voices(self, voices: list[str]) -> None:
        self._voice_combo.clear()
        self._voice_combo.addItems(voices)

    def set_current_voice(self, voice: str) -> None:
        index = self._voice_combo.findText(voice)
        if index >= 0:
            self._voice_combo.setCurrentIndex(index)

    def set_speed(self, speed: float) -> None:
        self._speed_slider.setValue(int(speed * 10))

    def set_volume(self, volume: float) -> None:
        clamped = max(0.0, min(1.0, volume))
        self._volume_slider.setValue(int(clamped * 100))


class RawPdfView(QWidget):
    """Simple raw PDF viewer backed by PyMuPDF page rendering."""

    page_changed = pyqtSignal(int)
    load_failed = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._document = None
        self._path: str | None = None
        self._current_page = 0
        self._zoom = 1.35
        self._fit_mode = "manual"
        self._updating_zoom_ui = False
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(10, 6, 10, 0)

        self._prev_btn = QPushButton("Prev Page")
        self._prev_btn.clicked.connect(self.previous_page)
        toolbar.addWidget(self._prev_btn)

        self._next_btn = QPushButton("Next Page")
        self._next_btn.clicked.connect(self.next_page)
        toolbar.addWidget(self._next_btn)

        self._zoom_out_btn = QPushButton("-")
        self._zoom_out_btn.setFixedWidth(28)
        self._zoom_out_btn.clicked.connect(self.zoom_out)
        toolbar.addWidget(self._zoom_out_btn)

        self._zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self._zoom_slider.setMinimum(25)
        self._zoom_slider.setMaximum(400)
        self._zoom_slider.setValue(int(self._zoom * 100))
        self._zoom_slider.setFixedWidth(140)
        self._zoom_slider.valueChanged.connect(self._on_zoom_slider_changed)
        toolbar.addWidget(self._zoom_slider)

        self._zoom_in_btn = QPushButton("+")
        self._zoom_in_btn.setFixedWidth(28)
        self._zoom_in_btn.clicked.connect(self.zoom_in)
        toolbar.addWidget(self._zoom_in_btn)

        self._fit_width_btn = QPushButton("Fit Width")
        self._fit_width_btn.clicked.connect(self.fit_width)
        toolbar.addWidget(self._fit_width_btn)

        self._fit_page_btn = QPushButton("Fit Page")
        self._fit_page_btn.clicked.connect(self.fit_page)
        toolbar.addWidget(self._fit_page_btn)

        self._zoom_label = QLabel("135%")
        self._zoom_label.setFixedWidth(44)
        self._zoom_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        toolbar.addWidget(self._zoom_label)

        toolbar.addStretch()

        self._page_label = QLabel("Page 0 / 0")
        self._page_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        toolbar.addWidget(self._page_label)

        layout.addLayout(toolbar)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(self._scroll.Shape.NoFrame)

        self._image_label = QLabel("Open a PDF to view raw pages")
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_label.setMinimumHeight(300)
        self._scroll.setWidget(self._image_label)
        self._scroll.viewport().installEventFilter(self)
        self._image_label.installEventFilter(self)

        layout.addWidget(self._scroll)

        self._update_controls()

    def clear(self) -> None:
        self._close_document()
        self._image_label.setPixmap(QPixmap())
        self._image_label.setText("Open a PDF to view raw pages")
        self._current_page = 0
        self._fit_mode = "manual"
        self._set_zoom(1.35, rerender=False, fit_mode="manual")
        self._page_label.setText("Page 0 / 0")
        self._update_controls()

    def load_pdf(self, path: str) -> bool:
        self._close_document()

        try:
            import fitz
            self._document = fitz.open(path)
        except Exception as exc:
            self._document = None
            self._path = None
            self.load_failed.emit(f"Unable to load PDF viewer: {exc}")
            self.clear()
            return False

        self._path = path
        self._current_page = 0
        self._fit_mode = "fit_width"
        return self._render_current_page()

    def set_page(self, page_index: int) -> None:
        if self._document is None:
            return

        if page_index < 0 or page_index >= self.page_count:
            return

        if page_index == self._current_page and self._image_label.pixmap() is not None:
            return

        self._current_page = page_index
        self._render_current_page()

    def next_page(self) -> None:
        if self._document is None:
            return
        self.set_page(self._current_page + 1)

    def previous_page(self) -> None:
        if self._document is None:
            return
        self.set_page(self._current_page - 1)

    def zoom_in(self) -> None:
        self._set_zoom(self._zoom + 0.1, fit_mode="manual")

    def zoom_out(self) -> None:
        self._set_zoom(self._zoom - 0.1, fit_mode="manual")

    def fit_width(self) -> None:
        self._set_zoom(self._zoom, fit_mode="fit_width")

    def fit_page(self) -> None:
        self._set_zoom(self._zoom, fit_mode="fit_page")

    @property
    def page_count(self) -> int:
        if self._document is None:
            return 0
        return self._document.page_count

    def _render_current_page(self) -> bool:
        if self._document is None or self.page_count == 0:
            self.clear()
            return False

        try:
            import fitz

            page = self._document[self._current_page]
            self._refresh_fit_zoom(page)
            matrix = fitz.Matrix(self._zoom, self._zoom)
            pix = page.get_pixmap(matrix=matrix, alpha=False)

            bytes_per_line = pix.width * pix.n
            fmt = QImage.Format.Format_RGB888 if pix.n == 3 else QImage.Format.Format_RGBA8888
            image = QImage(pix.samples, pix.width, pix.height, bytes_per_line, fmt).copy()
            self._image_label.setPixmap(QPixmap.fromImage(image))
            self._image_label.setText("")

            self._page_label.setText(f"Page {self._current_page + 1} / {self.page_count}")
            self._update_controls()
            self.page_changed.emit(self._current_page)
            return True
        except Exception as exc:
            self.load_failed.emit(f"Unable to render PDF page: {exc}")
            return False

    def _update_controls(self) -> None:
        has_pdf = self._document is not None and self.page_count > 0
        self._prev_btn.setEnabled(has_pdf and self._current_page > 0)
        self._next_btn.setEnabled(has_pdf and self._current_page < self.page_count - 1)
        self._zoom_in_btn.setEnabled(has_pdf)
        self._zoom_out_btn.setEnabled(has_pdf)
        self._fit_width_btn.setEnabled(has_pdf)
        self._fit_page_btn.setEnabled(has_pdf)
        self._zoom_slider.setEnabled(has_pdf)

    def _set_zoom(self, zoom: float, *, rerender: bool = True, fit_mode: str | None = None) -> None:
        self._zoom = max(0.25, min(4.0, zoom))
        if fit_mode is not None:
            self._fit_mode = fit_mode
        self._sync_zoom_ui()
        if rerender and self._document is not None:
            self._render_current_page()

    def _sync_zoom_ui(self) -> None:
        self._updating_zoom_ui = True
        self._zoom_slider.setValue(int(round(self._zoom * 100)))
        self._zoom_label.setText(f"{int(round(self._zoom * 100))}%")
        self._updating_zoom_ui = False

    def _on_zoom_slider_changed(self, value: int) -> None:
        if self._updating_zoom_ui:
            return
        self._set_zoom(value / 100.0, fit_mode="manual")

    def _refresh_fit_zoom(self, page) -> None:
        if self._fit_mode == "manual":
            return

        viewport_width = max(1, self._scroll.viewport().width() - 20)
        viewport_height = max(1, self._scroll.viewport().height() - 20)
        page_width = max(1.0, float(page.rect.width))
        page_height = max(1.0, float(page.rect.height))

        width_zoom = viewport_width / page_width
        height_zoom = viewport_height / page_height

        if self._fit_mode == "fit_page":
            target_zoom = min(width_zoom, height_zoom)
        else:
            target_zoom = width_zoom

        self._set_zoom(target_zoom, rerender=False, fit_mode=self._fit_mode)

    def eventFilter(self, watched, event) -> bool:
        if (
            watched in (self._scroll.viewport(), self._image_label)
            and event.type() == QEvent.Type.Wheel
            and event.modifiers() & Qt.KeyboardModifier.ControlModifier
        ):
            delta = event.angleDelta().y()
            if delta > 0:
                self.zoom_in()
            elif delta < 0:
                self.zoom_out()
            event.accept()
            return True
        return super().eventFilter(watched, event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._document is not None and self._fit_mode in {"fit_width", "fit_page"}:
            self._render_current_page()

    def _close_document(self) -> None:
        if self._document is not None:
            try:
                self._document.close()
            except Exception:
                pass
        self._document = None

    def closeEvent(self, event) -> None:
        self._close_document()
        super().closeEvent(event)


class VoiceHubDialog(QDialog):
    """Dialog for discovering and downloading Kokoro voices by id."""

    download_requested = pyqtSignal(str)

    def __init__(
        self,
        *,
        installed_voices: Sequence[str],
        downloadable_voices: Sequence[str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Voice Hub")
        self.setMinimumSize(560, 420)
        self._setup_ui()
        self.set_installed_voices(installed_voices)
        self.set_downloadable_voices(downloadable_voices)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        layout.addWidget(QLabel("Installed voices"))
        self._installed_list = QListWidget()
        layout.addWidget(self._installed_list)

        layout.addWidget(QLabel("Downloadable / known voices"))
        self._downloadable_list = QListWidget()
        layout.addWidget(self._downloadable_list)

        custom_row = QHBoxLayout()
        custom_row.addWidget(QLabel("Custom voice id:"))
        self._custom_voice_input = QLineEdit()
        self._custom_voice_input.setPlaceholderText("e.g. af_heart")
        custom_row.addWidget(self._custom_voice_input)

        add_custom_btn = QPushButton("Add")
        add_custom_btn.clicked.connect(self._on_add_custom_voice)
        custom_row.addWidget(add_custom_btn)
        layout.addLayout(custom_row)

        action_row = QHBoxLayout()
        self._download_btn = QPushButton("Download Selected")
        self._download_btn.clicked.connect(self._on_download_selected)
        action_row.addWidget(self._download_btn)

        self._close_btn = QPushButton("Close")
        self._close_btn.clicked.connect(self.accept)
        action_row.addWidget(self._close_btn)
        action_row.addStretch()
        layout.addLayout(action_row)

        layout.addWidget(QLabel("Activity"))
        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumBlockCount(300)
        layout.addWidget(self._log)

    def set_installed_voices(self, voices: Sequence[str]) -> None:
        self._installed_list.clear()
        self._installed_list.addItems(sorted({v for v in voices if v}))

    def set_downloadable_voices(self, voices: Sequence[str]) -> None:
        self._downloadable_list.clear()
        self._downloadable_list.addItems(sorted({v for v in voices if v}))

    def add_log(self, message: str) -> None:
        self._log.appendPlainText(message)

    def set_busy(self, busy: bool) -> None:
        self._download_btn.setEnabled(not busy)
        self._close_btn.setEnabled(not busy)

    def _on_add_custom_voice(self) -> None:
        voice_id = self._custom_voice_input.text().strip()
        if not voice_id:
            return

        existing = {self._downloadable_list.item(i).text() for i in range(self._downloadable_list.count())}
        if voice_id not in existing:
            self._downloadable_list.addItem(voice_id)
            self.add_log(f"Added custom voice id: {voice_id}")

        self._custom_voice_input.clear()

    def _on_download_selected(self) -> None:
        item = self._downloadable_list.currentItem()
        if item is None:
            self.add_log("Select a voice to download.")
            return

        voice_id = item.text().strip()
        if not voice_id:
            self.add_log("Selected voice id is empty.")
            return

        self.download_requested.emit(voice_id)
