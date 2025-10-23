from __future__ import annotations
from typing import Optional, Dict, Any
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QGridLayout,
    QLabel,
    QLineEdit,
    QDialogButtonBox,
    QWidget,
)


class DialogoGestionarOferente(QDialog):
    """
    Editor simple de Oferente: nombre y comentario.
    """
    def __init__(self, parent: QWidget, title: str = "Gestionar Oferente", initial_data: Optional[Dict[str, Any]] = None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.initial_data = initial_data or {}
        self.resultado: Optional[Dict[str, Any]] = None

        self._build_ui()
        self._load_initial()

    def _build_ui(self):
        self.setMinimumWidth(420)
        vbox = QVBoxLayout(self)
        grid = QGridLayout()

        grid.addWidget(QLabel("Nombre:"), 0, 0)
        self.ed_nombre = QLineEdit(self)
        grid.addWidget(self.ed_nombre, 0, 1)

        grid.addWidget(QLabel("Comentario:"), 1, 0)
        self.ed_comentario = QLineEdit(self)
        grid.addWidget(self.ed_comentario, 1, 1)

        vbox.addLayout(grid)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            orientation=Qt.Orientation.Horizontal,
            parent=self,
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        vbox.addWidget(buttons)

    def _load_initial(self):
        self.ed_nombre.setText(self.initial_data.get("nombre", "") or "")
        self.ed_comentario.setText(self.initial_data.get("comentario", "") or "")

    def _on_accept(self):
        nombre = self.ed_nombre.text().strip()
        if not nombre:
            self.resultado = None
            self.reject()
            return
        self.resultado = {
            "nombre": nombre,
            "comentario": self.ed_comentario.text().strip(),
        }
        self.accept()