from __future__ import annotations
from typing import Dict, Optional
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


class DialogoGestionarEntidad(QDialog):
    """
    Editor genérico de entidad.
    entity_type:
      - 'competidor' -> Nombre, RNC, No. RPE, Representante
      - 'empresa' -> Nombre, RNC, No. RPE, Teléfono, Correo, Dirección, Representante, Cargo del Representante
      - 'institucion' -> Nombre, RNC, Teléfono, Correo, Dirección
    """
    def __init__(self, parent: QWidget, title: str, entity_type: str, initial_data: Optional[Dict] = None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.entity_type = entity_type
        self.initial_data = initial_data or {}
        self.resultado: Optional[Dict] = None

        self._build_ui()
        self._load_initial_data()

    def _build_ui(self):
        self.setMinimumWidth(480)
        vbox = QVBoxLayout(self)

        if self.entity_type == "competidor":
            fields = [("Nombre", "nombre"), ("RNC", "rnc"), ("No. RPE", "rpe"), ("Representante", "representante")]
        elif self.entity_type == "empresa":
            fields = [
                ("Nombre", "nombre"),
                ("RNC", "rnc"),
                ("No. RPE", "rpe"),
                ("Teléfono", "telefono"),
                ("Correo", "correo"),
                ("Dirección", "direccion"),
                ("Representante", "representante"),
                ("Cargo del Representante", "cargo_representante"),
            ]
        else:  # institucion
            fields = [("Nombre", "nombre"), ("RNC", "rnc"), ("Teléfono", "telefono"), ("Correo", "correo"), ("Dirección", "direccion")]

        self._fields = fields
        grid = QGridLayout()
        self._inputs: Dict[str, QLineEdit] = {}

        for row, (label, key) in enumerate(fields):
            grid.addWidget(QLabel(f"{label}:"), row, 0)
            edit = QLineEdit(self)
            edit.setPlaceholderText(label)
            grid.addWidget(edit, row, 1)
            self._inputs[key] = edit

        vbox.addLayout(grid)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            orientation=Qt.Orientation.Horizontal,
            parent=self,
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        vbox.addWidget(buttons)

    def _load_initial_data(self):
        for key, widget in self._inputs.items():
            widget.setText(self.initial_data.get(key, "") or "")

    def _on_accept(self):
        data = {key: widget.text().strip() for key, widget in self._inputs.items()}
        if not data.get("nombre"):
            self.resultado = None
            self.reject()
            return
        self.resultado = data
        self.accept()