#!/usr/bin/env python3
"""GUI entry point for the PDF Audiobook player."""
from __future__ import annotations

import sys

try:
    from PyQt6.QtWidgets import QApplication
except ImportError:
    print("Error: PyQt6 is required for the GUI.", file=sys.stderr)
    print("Install with: pip install PyQt6", file=sys.stderr)
    sys.exit(1)

from ui.main_window import MainWindow


def main(argv: list[str] | None = None) -> int:
    app = QApplication(argv or sys.argv)
    app.setApplicationName("PDF Audiobook")
    app.setOrganizationName("PDFAudiobook")

    file_path = argv[1] if argv and len(argv) > 1 else None
    window = MainWindow(file_path=file_path)
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
