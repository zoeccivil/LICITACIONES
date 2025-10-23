from __future__ import annotations
from typing import List, Optional, Dict, Any
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QGridLayout,
    QLabel,
    QLineEdit,
    QDoubleSpinBox,
    QComboBox,
    QDialogButtonBox,
    QWidget,
)
from app.core.models import Lote


class DialogoGestionarLote(QDialog):
    """
    Editor de Lote en PyQt6.
    """
    def __init__(
        self,
        parent: QWidget,
        title: str = "Gestionar Lote",
        initial_data: Optional[Lote] = None,
        participating_companies: Optional[List[str]] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.initial_data = initial_data
        self.participating_companies = participating_companies or []
        self.resultado: Optional[Dict[str, Any]] = None

        self._build_ui()
        self._load_initial_data()

    def _build_ui(self):
        self.setMinimumWidth(520)
        vbox = QVBoxLayout(self)

        grid = QGridLayout()

        # Número
        grid.addWidget(QLabel("Número de Lote:"), 0, 0)
        self.numero_edit = QLineEdit(self)
        self.numero_edit.setPlaceholderText("p.ej. 1")
        grid.addWidget(self.numero_edit, 0, 1)

        # Nombre
        grid.addWidget(QLabel("Nombre del Lote:"), 1, 0)
        self.nombre_edit = QLineEdit(self)
        self.nombre_edit.setPlaceholderText("Nombre del lote")
        grid.addWidget(self.nombre_edit, 1, 1)

        # Monto base (licitación)
        grid.addWidget(QLabel("Monto Base (Licitación):"), 2, 0)
        self.monto_base_spin = QDoubleSpinBox(self)
        self.monto_base_spin.setRange(0.0, 1e15)
        self.monto_base_spin.setDecimals(2)
        grid.addWidget(self.monto_base_spin, 2, 1)

        # Monto base personal
        grid.addWidget(QLabel("Monto Base (Presupuesto Personal):"), 3, 0)
        self.monto_personal_spin = QDoubleSpinBox(self)
        self.monto_personal_spin.setRange(0.0, 1e15)
        self.monto_personal_spin.setDecimals(2)
        grid.addWidget(self.monto_personal_spin, 3, 1)

        # Monto ofertado (nuestra oferta)
        grid.addWidget(QLabel("Nuestra Oferta para el Lote:"), 4, 0)
        self.monto_oferta_spin = QDoubleSpinBox(self)
        self.monto_oferta_spin.setRange(0.0, 1e15)
        self.monto_oferta_spin.setDecimals(2)
        grid.addWidget(self.monto_oferta_spin, 4, 1)

        # Empresa
        grid.addWidget(QLabel("Asignar a Empresa:"), 5, 0)
        self.empresa_combo = QComboBox(self)
        self.empresa_combo.addItem("(Sin Asignar)")
        for emp in self.participating_companies:
            self.empresa_combo.addItem(emp)
        grid.addWidget(self.empresa_combo, 5, 1)

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
        if not self.initial_data:
            self.empresa_combo.setCurrentIndex(0)
            return

        self.numero_edit.setText(str(self.initial_data.numero or ""))
        self.nombre_edit.setText(self.initial_data.nombre or "")
        self.monto_base_spin.setValue(float(self.initial_data.monto_base or 0.0))
        self.monto_personal_spin.setValue(float(getattr(self.initial_data, "monto_base_personal", 0.0) or 0.0))
        self.monto_oferta_spin.setValue(float(self.initial_data.monto_ofertado or 0.0))

        emp = (self.initial_data.empresa_nuestra or "").strip() or "(Sin Asignar)"
        idx = max(0, self.empresa_combo.findText(emp))
        self.empresa_combo.setCurrentIndex(idx)

    def _on_accept(self):
        try:
            lote = Lote(
                numero=self.numero_edit.text().strip(),
                nombre=self.nombre_edit.text().strip(),
                monto_base=float(self.monto_base_spin.value()),
                monto_base_personal=float(self.monto_personal_spin.value()),
                monto_ofertado=float(self.monto_oferta_spin.value()),
                empresa_nuestra=(self.empresa_combo.currentText() if self.empresa_combo.currentText() != "(Sin Asignar)" else None),
            )
            if self.initial_data and self.initial_data.id is not None:
                lote.id = self.initial_data.id

            self.resultado = lote.to_dict()
            self.accept()
        except Exception:
            self.resultado = None
            self.reject()