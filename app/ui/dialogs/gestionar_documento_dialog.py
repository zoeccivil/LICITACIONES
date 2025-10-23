from __future__ import annotations
from typing import Optional, Dict, Any, List
import os
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QGridLayout,
    QLabel,
    QLineEdit,
    QComboBox,
    QCheckBox,
    QPushButton,
    QDialogButtonBox,
    QFileDialog,
    QWidget,
)
from app.core.models import Documento


class DialogoGestionarDocumento(QDialog):
    """
    Editor de Documento.
    Campos: código, nombre, categoría, obligatorio, subsanable, presentado, revisado, responsable, comentario, ruta_archivo
    """
    DEFAULT_CATEGORIES: List[str] = ["Legal", "Técnica", "Económica", "Otros"]
    SUBSANABLES: List[str] = ["Subsanable", "No Subsanable"]

    def __init__(
        self,
        parent: QWidget,
        title: str = "Gestionar Documento",
        initial_data: Optional[Documento] = None,
        categories: Optional[List[str]] = None,
        responsables: Optional[List[str]] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.initial_data = initial_data
        self.categories = categories or self.DEFAULT_CATEGORIES
        self.responsables = responsables or []
        self.resultado: Optional[Dict[str, Any]] = None

        self._build_ui()
        self._load_initial_data()

    def _build_ui(self):
        self.setMinimumWidth(580)
        vbox = QVBoxLayout(self)

        grid = QGridLayout()

        # Código
        grid.addWidget(QLabel("Código:"), 0, 0)
        self.ed_codigo = QLineEdit(self)
        self.ed_codigo.setPlaceholderText("p.ej. A-01")
        grid.addWidget(self.ed_codigo, 0, 1)

        # Nombre
        grid.addWidget(QLabel("Nombre:"), 1, 0)
        self.ed_nombre = QLineEdit(self)
        self.ed_nombre.setPlaceholderText("Nombre del documento")
        grid.addWidget(self.ed_nombre, 1, 1)

        # Categoría
        grid.addWidget(QLabel("Categoría:"), 2, 0)
        self.cb_categoria = QComboBox(self)
        for c in self.categories:
            self.cb_categoria.addItem(c)
        grid.addWidget(self.cb_categoria, 2, 1)

        # Obligatorio
        grid.addWidget(QLabel("Obligatorio:"), 3, 0)
        self.chk_oblig = QCheckBox(self)
        grid.addWidget(self.chk_oblig, 3, 1)

        # Subsanable
        grid.addWidget(QLabel("Subsanable:"), 4, 0)
        self.cb_subsanable = QComboBox(self)
        for s in self.SUBSANABLES:
            self.cb_subsanable.addItem(s)
        grid.addWidget(self.cb_subsanable, 4, 1)

        # Presentado
        grid.addWidget(QLabel("Presentado:"), 5, 0)
        self.chk_presentado = QCheckBox(self)
        grid.addWidget(self.chk_presentado, 5, 1)

        # Revisado
        grid.addWidget(QLabel("Revisado:"), 6, 0)
        self.chk_revisado = QCheckBox(self)
        grid.addWidget(self.chk_revisado, 6, 1)

        # Responsable
        grid.addWidget(QLabel("Responsable:"), 7, 0)
        self.cb_responsable = QComboBox(self)
        self.cb_responsable.setEditable(True)
        if self.responsables:
            for r in self.responsables:
                self.cb_responsable.addItem(r)
        else:
            self.cb_responsable.addItem("Sin Asignar")
        grid.addWidget(self.cb_responsable, 7, 1)

        # Comentario
        grid.addWidget(QLabel("Comentario:"), 8, 0)
        self.ed_comentario = QLineEdit(self)
        grid.addWidget(self.ed_comentario, 8, 1)

        # Archivo
        grid.addWidget(QLabel("Archivo:"), 9, 0)
        self.ed_archivo = QLineEdit(self)
        self.ed_archivo.setPlaceholderText("Ruta del archivo (opcional)")
        btn_examinar = QPushButton("Examinar…", self)
        btn_examinar.clicked.connect(self._on_examinar)
        grid.addWidget(self.ed_archivo, 9, 1)
        grid.addWidget(btn_examinar, 9, 2)

        vbox.addLayout(grid)

        # Botonera
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            orientation=Qt.Orientation.Horizontal,
            parent=self,
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        vbox.addWidget(buttons)

    def _load_initial_data(self):
        d = self.initial_data
        if not d:
            return
        self.ed_codigo.setText(d.codigo or "")
        self.ed_nombre.setText(d.nombre or "")
        idx_cat = max(0, self.cb_categoria.findText(d.categoria or "", Qt.MatchFlag.MatchFixedString))
        self.cb_categoria.setCurrentIndex(idx_cat)
        self.chk_oblig.setChecked(bool(d.obligatorio))
        idx_sub = max(0, self.cb_subsanable.findText(d.subsanable or "Subsanable", Qt.MatchFlag.MatchFixedString))
        self.cb_subsanable.setCurrentIndex(idx_sub)
        self.chk_presentado.setChecked(bool(d.presentado))
        self.chk_revisado.setChecked(bool(d.revisado))
        if d.responsable:
            self.cb_responsable.setEditText(d.responsable)
        self.ed_comentario.setText(d.comentario or "")
        self.ed_archivo.setText(d.ruta_archivo or "")

    def _on_examinar(self):
        path, _ = QFileDialog.getOpenFileName(self, "Seleccionar archivo", filter="Todos (*.*)")
        if path:
            self.ed_archivo.setText(path)

    def _on_accept(self):
        codigo = self.ed_codigo.text().strip()
        nombre = self.ed_nombre.text().strip()
        if not codigo or not nombre:
            # Validación mínima
            self.resultado = None
            self.reject()
            return

        data = {
            "codigo": codigo,
            "nombre": nombre,
            "categoria": self.cb_categoria.currentText(),
            "obligatorio": self.chk_oblig.isChecked(),
            "subsanable": self.cb_subsanable.currentText(),
            "presentado": self.chk_presentado.isChecked(),
            "revisado": self.chk_revisado.isChecked(),
            "responsable": self.cb_responsable.currentText().strip() or "Sin Asignar",
            "comentario": self.ed_comentario.text().strip(),
            "ruta_archivo": self.ed_archivo.text().strip(),
        }

        # Mantener id/empresa_nombre si viene en initial_data
        if self.initial_data and self.initial_data.id is not None:
            data["id"] = self.initial_data.id
        if self.initial_data and self.initial_data.empresa_nombre:
            data["empresa_nombre"] = self.initial_data.empresa_nombre

        self.resultado = data
        self.accept()