from __future__ import annotations
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtCore import Qt


def apply_light_theme(app: QApplication) -> None:
    """
    Aplica un tema claro (Fusion) con buena lectura de colores de filas/estados.
    """
    app.setStyle("Fusion")

    pal = QPalette()

    # Base blancos/grises claros
    pal.setColor(QPalette.ColorRole.Window, QColor(250, 250, 250))
    pal.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.black)
    pal.setColor(QPalette.ColorRole.Base, QColor(255, 255, 255))
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor(245, 245, 245))
    pal.setColor(QPalette.ColorRole.ToolTipBase, QColor(255, 255, 220))
    pal.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.black)
    pal.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.black)
    pal.setColor(QPalette.ColorRole.Button, QColor(245, 245, 245))
    pal.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.black)
    pal.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)

    # Selección con alto contraste
    pal.setColor(QPalette.ColorRole.Highlight, QColor(38, 132, 255))  # azul accesible
    pal.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.white)

    # Links
    pal.setColor(QPalette.ColorRole.Link, QColor(0, 102, 204))
    pal.setColor(QPalette.ColorRole.LinkVisited, QColor(102, 0, 153))

    # Sombras/deshabilitados
    disabled_fg = QColor(120, 120, 120)
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, disabled_fg)
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, disabled_fg)
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, disabled_fg)
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Highlight, QColor(200, 200, 200))
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.HighlightedText, QColor(80, 80, 80))

    app.setPalette(pal)

    # Estilos mínimos para tabs y tablas
    app.setStyleSheet("""
        QTabWidget::pane {
            border: 1px solid #d0d0d0;
            background: #ffffff;
        }
        QTabBar::tab {
            background: #f5f5f5;
            border: 1px solid #d0d0d0;
            padding: 6px 10px;
            margin-right: 2px;
        }
        QTabBar::tab:selected {
            background: #ffffff;
        }
        QHeaderView::section {
            background-color: #f5f5f5;
            padding: 4px;
            border: 1px solid #d0d0d0;
        }
        QTableView {
            gridline-color: #e0e0e0;
            alternate-background-color: #f5f5f5;
            selection-background-color: #2684ff;
            selection-color: #ffffff;
        }
    """)