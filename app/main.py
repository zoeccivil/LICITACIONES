import sys
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