import os
import sys

# Permite ejecutar este archivo directamente: python app/main.py
# Inserta la raíz del proyecto en sys.path para que 'import app...' funcione.
if __package__ in (None, ""):
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

from PyQt6.QtWidgets import QApplication
from app.ui.windows.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Gestor de Licitaciones (PyQt6)")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()