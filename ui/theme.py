"""Catppuccin Mocha theme for PyQt6."""

MOCHA = {
    "base": "#1e1e2e",
    "mantle": "#181825",
    "crust": "#11111b",
    "surface0": "#313244",
    "surface1": "#45475a",
    "surface2": "#585b70",
    "overlay0": "#6c7086",
    "overlay1": "#7f849c",
    "overlay2": "#9399b2",
    "subtext0": "#a6adc8",
    "subtext1": "#bac2de",
    "text": "#cdd6f4",
    "lavender": "#b4befe",
    "blue": "#89b4fa",
    "sapphire": "#74c7ec",
    "sky": "#89dceb",
    "teal": "#94e2d5",
    "green": "#a6e3a1",
    "yellow": "#f9e2af",
    "peach": "#fab387",
    "maroon": "#eba0ac",
    "red": "#f38ba8",
    "mauve": "#cba6f7",
    "pink": "#f5c2e7",
    "flamingo": "#f2cdcd",
    "rosewater": "#f5e0dc",
}


def catppuccin_stylesheet() -> str:
    """Generate the full Catppuccin Mocha QSS stylesheet."""
    c = MOCHA
    return f"""
    QMainWindow, QWidget {{
        background-color: {c["base"]};
        color: {c["text"]};
        font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
        font-size: 12px;
    }}

    QMenuBar {{
        background-color: {c["mantle"]};
        color: {c["text"]};
        border-bottom: 1px solid {c["surface0"]};
        padding: 4px;
    }}

    QMenuBar::item {{
        padding: 4px 8px;
        border-radius: 4px;
    }}

    QMenuBar::item:selected {{
        background-color: {c["surface0"]};
    }}

    QMenu {{
        background-color: {c["mantle"]};
        color: {c["text"]};
        border: 1px solid {c["surface0"]};
        border-radius: 6px;
        padding: 4px;
    }}

    QMenu::item {{
        padding: 6px 20px 6px 12px;
        border-radius: 4px;
    }}

    QMenu::item:selected {{
        background-color: {c["surface0"]};
    }}

    QTreeView {{
        background-color: {c["mantle"]};
        color: {c["text"]};
        border: none;
        border-right: 1px solid {c["surface0"]};
        font-size: 11px;
        show-decoration-selected: 1;
    }}

    QTreeView::item {{
        padding: 5px 8px;
        border-radius: 4px;
        margin: 1px 4px;
    }}

    QTreeView::item:selected {{
        background-color: {c["blue"]}33;
        color: {c["text"]};
        border-left: 3px solid {c["blue"]};
    }}

    QTreeView::item:hover {{
        background-color: {c["surface0"]};
    }}

    QTreeView::branch:selected {{
        background-color: {c["blue"]}33;
    }}

    QTextBrowser {{
        background-color: {c["base"]};
        color: {c["text"]};
        border: none;
        font-size: 12px;
        line-height: 1.7;
        padding: 12px;
    }}

    QScrollBar:vertical {{
        background-color: {c["mantle"]};
        width: 8px;
        border-radius: 4px;
    }}

    QScrollBar::handle:vertical {{
        background-color: {c["surface1"]};
        border-radius: 4px;
        min-height: 20px;
    }}

    QScrollBar::handle:vertical:hover {{
        background-color: {c["surface2"]};
    }}

    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}

    QScrollBar:horizontal {{
        background-color: {c["mantle"]};
        height: 8px;
        border-radius: 4px;
    }}

    QScrollBar::handle:horizontal {{
        background-color: {c["surface1"]};
        border-radius: 4px;
        min-width: 20px;
    }}

    QPushButton {{
        background-color: {c["surface0"]};
        color: {c["text"]};
        border: none;
        border-radius: 6px;
        padding: 6px 12px;
        font-size: 14px;
    }}

    QPushButton:hover {{
        background-color: {c["surface1"]};
    }}

    QPushButton:pressed {{
        background-color: {c["surface2"]};
    }}

    QComboBox {{
        background-color: {c["surface0"]};
        color: {c["text"]};
        border: 1px solid {c["surface1"]};
        border-radius: 4px;
        padding: 4px 8px;
        font-size: 11px;
    }}

    QComboBox::drop-down {{
        border: none;
        padding-right: 8px;
    }}

    QComboBox QAbstractItemView {{
        background-color: {c["mantle"]};
        color: {c["text"]};
        selection-background-color: {c["blue"]}33;
        border: 1px solid {c["surface0"]};
    }}

    QSlider::groove:horizontal {{
        background-color: {c["surface0"]};
        height: 4px;
        border-radius: 2px;
    }}

    QSlider::handle:horizontal {{
        background-color: {c["blue"]};
        width: 14px;
        height: 14px;
        border-radius: 7px;
        margin: -5px 0;
    }}

    QSlider::handle:horizontal:hover {{
        background-color: {c["lavender"]};
    }}

    QProgressBar {{
        background-color: {c["surface0"]};
        border: none;
        border-radius: 2px;
        height: 4px;
        text-align: center;
    }}

    QProgressBar::chunk {{
        background-color: {c["blue"]};
        border-radius: 2px;
    }}

    QLabel {{
        color: {c["subtext0"]};
        font-size: 10px;
    }}

    QSplitter::handle {{
        background-color: {c["surface0"]};
        width: 2px;
    }}

    QSplitter::handle:hover {{
        background-color: {c["surface1"]};
    }}

    QStatusBar {{
        background-color: {c["mantle"]};
        color: {c["subtext0"]};
        border-top: 1px solid {c["surface0"]};
        font-size: 10px;
    }}

    QToolTip {{
        background-color: {c["crust"]};
        color: {c["text"]};
        border: 1px solid {c["surface0"]};
        border-radius: 4px;
        padding: 4px 8px;
    }}
    """
