"""GUI tests for the PDF Audiobook PyQt6 player."""
from __future__ import annotations

import unittest


class ThemeTests(unittest.TestCase):
    def test_catppuccin_stylesheet_contains_base_colors(self) -> None:
        from ui.theme import catppuccin_stylesheet
        qss = catppuccin_stylesheet()
        self.assertIn("#1e1e2e", qss)  # base background
        self.assertIn("#cdd6f4", qss)  # text color
        self.assertIn("#89b4fa", qss)  # blue accent

    def test_catppuccin_stylesheet_is_non_empty_string(self) -> None:
        from ui.theme import catppuccin_stylesheet
        qss = catppuccin_stylesheet()
        self.assertIsInstance(qss, str)
        self.assertGreater(len(qss), 100)


class PlayerModelTests(unittest.TestCase):
    def test_model_initializes_with_empty_state(self) -> None:
        from ui.player_model import PlayerModel
        model = PlayerModel()
        self.assertEqual(model.rowCount(), 0)
        self.assertEqual(model.columnCount(), 3)

    def test_model_updates_chapters(self) -> None:
        from ui.player_model import PlayerModel
        from audiobook import ChapterDetectionResult, ChapterMarker

        model = PlayerModel()
        chapters = ChapterDetectionResult(
            marker_indexes=(0, 5, 10),
            markers=(
                ChapterMarker(chunk_index=0, heading="Chapter 1", marker_type="chapter_number"),
                ChapterMarker(chunk_index=5, heading="Chapter 2", marker_type="chapter_number"),
                ChapterMarker(chunk_index=10, heading="Chapter 3", marker_type="chapter_number"),
            ),
        )
        model.update_chapters(chapters, total_sentences=20)

        self.assertEqual(model.rowCount(), 3)
        self.assertEqual(model.data(model.index(0, 0)), "Chapter 1")
        self.assertEqual(model.data(model.index(1, 0)), "Chapter 2")

    def test_model_tracks_current_sentence(self) -> None:
        from ui.player_model import PlayerModel
        from audiobook import ChapterDetectionResult, ChapterMarker

        model = PlayerModel()
        chapters = ChapterDetectionResult(
            marker_indexes=(0, 5),
            markers=(
                ChapterMarker(chunk_index=0, heading="Chapter 1", marker_type="chapter_number"),
                ChapterMarker(chunk_index=5, heading="Chapter 2", marker_type="chapter_number"),
            ),
        )
        model.update_chapters(chapters, total_sentences=10)
        model.update_current_sentence(7)

        self.assertEqual(model.current_sentence, 7)
        self.assertEqual(model.data(model.index(1, 1)), "3 / 5")


class WidgetCreationTests(unittest.TestCase):
    def test_playback_controls_creates_all_buttons(self) -> None:
        from PyQt6.QtWidgets import QApplication
        from ui.widgets import PlaybackControls

        app = QApplication.instance() or QApplication([])
        controls = PlaybackControls()
        buttons = controls.findChildren(type(controls._play_btn))

        self.assertGreaterEqual(len(buttons), 5)

    def test_voice_speed_panel_emits_signals(self) -> None:
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtTest import QSignalSpy
        from ui.widgets import VoiceSpeedPanel

        app = QApplication.instance() or QApplication([])
        panel = VoiceSpeedPanel(voices=["af_heart", "af_bella"])

        speed_spy = QSignalSpy(panel.speed_changed)
        panel._speed_slider.setValue(15)  # 1.5x

        self.assertGreaterEqual(len(speed_spy), 1)

    def test_text_view_renders_highlighted_sentence(self) -> None:
        from PyQt6.QtWidgets import QApplication
        from ui.widgets import TextView

        app = QApplication.instance() or QApplication([])
        view = TextView()
        sentences = ["First sentence.", "Second sentence.", "Third sentence."]
        view.set_sentences(sentences)
        view.highlight_sentence(1)

        html = view.toHtml()
        self.assertIn("f9e2af", html)  # yellow highlight color

    def test_raw_pdf_view_has_zoom_controls(self) -> None:
        from PyQt6.QtWidgets import QApplication
        from ui.widgets import RawPdfView

        app = QApplication.instance() or QApplication([])
        view = RawPdfView()

        self.assertEqual(view._zoom_slider.minimum(), 25)
        self.assertEqual(view._zoom_slider.maximum(), 400)
        self.assertEqual(view._zoom_label.text(), "135%")

    def test_voice_hub_dialog_emits_download_request(self) -> None:
        from PyQt6.QtTest import QSignalSpy
        from PyQt6.QtWidgets import QApplication
        from ui.widgets import VoiceHubDialog

        app = QApplication.instance() or QApplication([])
        dialog = VoiceHubDialog(
            installed_voices=["af_heart"],
            downloadable_voices=["af_heart", "am_adam"],
        )

        spy = QSignalSpy(dialog.download_requested)
        dialog._downloadable_list.setCurrentRow(1)
        dialog._on_download_selected()

        self.assertEqual(len(spy), 1)


class MainWindowTests(unittest.TestCase):
    def test_main_window_creates_with_correct_layout(self) -> None:
        from PyQt6.QtWidgets import QApplication
        from ui.main_window import MainWindow

        app = QApplication.instance() or QApplication([])
        window = MainWindow()

        self.assertIsNotNone(window.sidebar)
        self.assertIsNotNone(window.text_view)
        self.assertIsNotNone(window.controls)
        self.assertIsNotNone(window.voice_speed_panel)

    def test_main_window_has_menu_bar(self) -> None:
        from PyQt6.QtWidgets import QApplication
        from ui.main_window import MainWindow

        app = QApplication.instance() or QApplication([])
        window = MainWindow()

        menu_bar = window.menuBar()
        self.assertIsNotNone(menu_bar)
        actions = menu_bar.actions()
        self.assertGreaterEqual(len(actions), 2)  # File, Help

    def test_main_window_has_raw_pdf_view_action(self) -> None:
        from PyQt6.QtWidgets import QApplication
        from ui.main_window import MainWindow

        app = QApplication.instance() or QApplication([])
        window = MainWindow()

        action_texts = [action.text() for action in window.menuBar().actions()]
        self.assertIn("&View", action_texts)


class ConfigTests(unittest.TestCase):
    def test_app_config_includes_view_mode_and_pdf_sync_defaults(self) -> None:
        from ui.config import AppConfig

        config = AppConfig()
        self.assertEqual(config.view_mode, "text")
        self.assertTrue(config.auto_pdf_sync)
        self.assertEqual(config.custom_voices, [])


class IntegrationTests(unittest.TestCase):
    def test_full_theme_application(self) -> None:
        from PyQt6.QtWidgets import QApplication
        from ui.main_window import MainWindow

        app = QApplication.instance() or QApplication([])
        window = MainWindow()
        qss = window.styleSheet()

        self.assertIn("#1e1e2e", qss)
        self.assertIn("#89b4fa", qss)

    def test_widget_signal_connections(self) -> None:
        from PyQt6.QtTest import QSignalSpy
        from PyQt6.QtWidgets import QApplication
        from ui.widgets import PlaybackControls, VoiceSpeedPanel

        app = QApplication.instance() or QApplication([])

        controls = PlaybackControls()
        play_spy = QSignalSpy(controls.play_clicked)
        controls._play_btn.click()
        self.assertEqual(len(play_spy), 1)

        panel = VoiceSpeedPanel(voices=["af_heart"])
        speed_spy = QSignalSpy(panel.speed_changed)
        panel._speed_slider.setValue(12)
        self.assertGreaterEqual(len(speed_spy), 1)


if __name__ == "__main__":
    unittest.main()
