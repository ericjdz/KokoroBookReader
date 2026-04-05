"""QAbstractTableModel bridging audiobook core state to UI."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt

from audiobook import ChapterDetectionResult, ChapterMarker


@dataclass
class ChapterRow:
    """A single row in the chapter model."""
    marker: ChapterMarker
    sentence_count: int = 0
    start_index: int = 0


class PlayerModel(QAbstractTableModel):
    """Table model for chapter navigation and state tracking.

    Columns: 0=Chapter name, 1=Progress (sentences in chapter), 2=Status
    """

    def __init__(self) -> None:
        super().__init__()
        self._chapters: list[ChapterRow] = []
        self._total_sentences: int = 0
        self._current_sentence: int = 0
        self._current_chapter: int = 0

    @property
    def current_sentence(self) -> int:
        return self._current_sentence

    @property
    def current_chapter(self) -> int:
        return self._current_chapter

    @property
    def total_sentences(self) -> int:
        return self._total_sentences

    def update_chapters(self, chapters: ChapterDetectionResult, total_sentences: int) -> None:
        """Update the model with detected chapters."""
        self.beginResetModel()
        self._chapters = []
        self._total_sentences = total_sentences

        markers = list(chapters.markers)
        for i, marker in enumerate(markers):
            next_index = markers[i + 1].chunk_index if i + 1 < len(markers) else total_sentences
            sentence_count = next_index - marker.chunk_index
            self._chapters.append(ChapterRow(
                marker=marker,
                sentence_count=sentence_count,
                start_index=marker.chunk_index,
            ))

        self.endResetModel()

    def update_current_sentence(self, index: int) -> None:
        """Update the current sentence index and recalculate active chapter."""
        self._current_sentence = index
        old_chapter = self._current_chapter

        self._current_chapter = 0
        for i, row in enumerate(self._chapters):
            if index >= row.start_index:
                self._current_chapter = i

        if old_chapter != self._current_chapter:
            top_left = self.index(0, 1)
            bottom_right = self.index(self.rowCount() - 1, 1)
            self.dataChanged.emit(top_left, bottom_right, [Qt.ItemDataRole.DisplayRole])

        idx = self.index(self._current_chapter, 1)
        self.dataChanged.emit(idx, idx, [Qt.ItemDataRole.DisplayRole])

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._chapters)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 3

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or index.row() >= len(self._chapters):
            return None

        row = self._chapters[index.row()]

        if role == Qt.ItemDataRole.DisplayRole:
            if index.column() == 0:
                return row.marker.heading
            elif index.column() == 1:
                if self._current_chapter == index.row():
                    sentences_in_chapter = self._current_sentence - row.start_index + 1
                    return f"{sentences_in_chapter} / {row.sentence_count}"
                return f"0 / {row.sentence_count}"
            elif index.column() == 2:
                return "Playing" if self._current_chapter == index.row() else ""

        if role == Qt.ItemDataRole.FontRole and self._current_chapter == index.row():
            from PyQt6.QtGui import QFont
            font = QFont()
            font.setBold(True)
            return font

        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            headers = ["Chapter", "Progress", "Status"]
            if section < len(headers):
                return headers[section]
        return None
