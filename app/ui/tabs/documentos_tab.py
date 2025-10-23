from __future__ import annotations
from typing import List, Optional
import os
import sys
import subprocess
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QMessageBox,
    QHeaderView,
    QFileDialog,
)
from app.core.models import Documento
from app.ui.dialogs.gestionar_documento_dialog import DialogoGestionarDocumento


class TabDocumentos(QWidget):
    """
    Pestaña Documentos con QTreeWidget:
    - Añadir, editar, eliminar
    - Adjuntar, Quitar, Abrir archivo
    Columnas: Código, Nombre, Categoría, Oblig., Subsanable, Presentado, Revisado, Responsable, Archivo
    """
    COL_COD = 0
    COL_NOMBRE = 1
    COL_CAT = 2
    COL_OBLIG = 3
    COL_SUBS = 4
    COL_PRES = 5
    COL_REV = 6
    COL_RESP = 7
    COL_FILE = 8

    def __init__(self, parent: QWidget, responsables: Optional[List[str]] = None, categories: Optional[List[str]] = None):
        super().__init__(parent)
        self.responsables = responsables or []
        self.categories = categories or None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Barra de acciones
        actions = QHBoxLayout()
        self.btn_add = QPushButton("Añadir", self)
        self.btn_edit = QPushButton("Editar", self)
        self.btn_delete = QPushButton("Eliminar", self)
        self.btn_attach = QPushButton("Adjuntar…", self)
        self.btn_remove = QPushButton("Quitar archivo", self)
        self.btn_open = QPushButton("Abrir archivo", self)

        for b in (self.btn_add, self.btn_edit, self.btn_delete, self.btn_attach, self.btn_remove, self.btn_open):
            actions.addWidget(b)
        actions.addStretch(1)
        layout.addLayout(actions)

        # Árbol
        self.tree = QTreeWidget(self)
        self.tree.setColumnCount(9)
        self.tree.setHeaderLabels(["Código", "Nombre", "Categoría", "Oblig.", "Subsanable", "Presentado", "Revisado", "Responsable", "Archivo"])
        self.tree.header().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setStretchLastSection(True)
        self.tree.setSortingEnabled(True)
        layout.addWidget(self.tree)

        # Conexiones
        self.btn_add.clicked.connect(self._on_add)
        self.btn_edit.clicked.connect(self._on_edit)
        self.btn_delete.clicked.connect(self._on_delete)
        self.btn_attach.clicked.connect(self._on_attach)
        self.btn_remove.clicked.connect(self._on_remove)
        self.btn_open.clicked.connect(self._on_open)
        self.tree.itemDoubleClicked.connect(self._on_item_double_clicked)

    # Public API
    def load_documentos(self, documentos: List[Documento]):
        self.tree.clear()
        for d in documentos or []:
            self._add_item_for_doc(d)

    def to_documentos(self) -> List[Documento]:
        documentos: List[Documento] = []
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            it = root.child(i)
            doc: Documento = it.data(0, Qt.ItemDataRole.UserRole)  # type: ignore
            if doc:
                documentos.append(doc)
        return documentos

    # Helpers
    def _add_item_for_doc(self, d: Documento):
        it = QTreeWidgetItem(self.tree)
        self._fill_item(it, d)
        self.tree.addTopLevelItem(it)

    def _fill_item(self, it: QTreeWidgetItem, d: Documento):
        it.setText(self.COL_COD, d.codigo or "")
        it.setText(self.COL_NOMBRE, d.nombre or "")
        it.setText(self.COL_CAT, d.categoria or "")
        it.setText(self.COL_OBLIG, "Sí" if d.obligatorio else "No")
        it.setText(self.COL_SUBS, d.subsanable or "Subsanable")
        it.setText(self.COL_PRES, "Sí" if d.presentado else "No")
        it.setText(self.COL_REV, "Sí" if d.revisado else "No")
        it.setText(self.COL_RESP, d.responsable or "Sin Asignar")
        it.setText(self.COL_FILE, d.ruta_archivo or "")
        it.setData(0, Qt.ItemDataRole.UserRole, d)

    def _get_selected_item(self) -> Optional[QTreeWidgetItem]:
        items = self.tree.selectedItems()
        return items[0] if items else None

    def _on_add(self):
        dlg = DialogoGestionarDocumento(self, "Añadir Documento", initial_data=None, categories=self.categories, responsables=self.responsables)
        if dlg.resultado is not None:
            data = dlg.resultado or {}
            d = Documento(
                id=data.get("id"),
                codigo=data.get("codigo", ""),
                nombre=data.get("nombre", ""),
                categoria=data.get("categoria", ""),
                comentario=data.get("comentario", ""),
                presentado=bool(data.get("presentado", False)),
                subsanable=data.get("subsanable", "Subsanable"),
                ruta_archivo=data.get("ruta_archivo", ""),
                empresa_nombre=data.get("empresa_nombre"),
                responsable=data.get("responsable", "Sin Asignar"),
                revisado=bool(data.get("revisado", False)),
                obligatorio=bool(data.get("obligatorio", False)),
            )
            self._add_item_for_doc(d)

    def _on_edit(self):
        it = self._get_selected_item()
        if not it:
            QMessageBox.information(self, "Editar", "Selecciona un documento para editar.")
            return
        d: Documento = it.data(0, Qt.ItemDataRole.UserRole)  # type: ignore
        dlg = DialogoGestionarDocumento(self, "Editar Documento", initial_data=d, categories=self.categories, responsables=self.responsables)
        if dlg.resultado is not None:
            data = dlg.resultado or {}
            d.codigo = data.get("codigo", "")
            d.nombre = data.get("nombre", "")
            d.categoria = data.get("categoria", "")
            d.comentario = data.get("comentario", "")
            d.presentado = bool(data.get("presentado", False))
            d.subsanable = data.get("subsanable", "Subsanable")
            d.ruta_archivo = data.get("ruta_archivo", "")
            d.responsable = data.get("responsable", "Sin Asignar")
            d.revisado = bool(data.get("revisado", False))
            d.obligatorio = bool(data.get("obligatorio", False))
            self._fill_item(it, d)

    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int):
        self._on_edit()

    def _on_delete(self):
        it = self._get_selected_item()
        if not it:
            QMessageBox.information(self, "Eliminar", "Selecciona un documento para eliminar.")
            return
        res = QMessageBox.question(self, "Confirmar", "¿Eliminar el documento seleccionado?")
        if res == QMessageBox.StandardButton.Yes:
            idx = self.tree.indexOfTopLevelItem(it)
            self.tree.takeTopLevelItem(idx)

    def _on_attach(self):
        it = self._get_selected_item()
        if not it:
            QMessageBox.information(self, "Adjuntar", "Selecciona un documento.")
            return
        path, _ = QFileDialog.getOpenFileName(self, "Seleccionar archivo", filter="Todos (*.*)")
        if not path:
            return
        d: Documento = it.data(0, Qt.ItemDataRole.UserRole)  # type: ignore
        d.ruta_archivo = path
        self._fill_item(it, d)

    def _on_remove(self):
        it = self._get_selected_item()
        if not it:
            QMessageBox.information(self, "Quitar archivo", "Selecciona un documento.")
            return
        d: Documento = it.data(0, Qt.ItemDataRole.UserRole)  # type: ignore
        d.ruta_archivo = ""
        self._fill_item(it, d)

    def _on_open(self):
        it = self._get_selected_item()
        if not it:
            QMessageBox.information(self, "Abrir", "Selecciona un documento.")
            return
        d: Documento = it.data(0, Qt.ItemDataRole.UserRole)  # type: ignore
        path = (d.ruta_archivo or "").strip()
        if not path or not os.path.exists(path):
            QMessageBox.warning(self, "Abrir", "El archivo no existe o no hay ruta asignada.")
            return
        try:
            if sys.platform.startswith("win"):
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.call(["open", path])
            else:
                subprocess.call(["xdg-open", path])
        except Exception as e:
            QMessageBox.critical(self, "Abrir", f"No se pudo abrir el archivo.\n{e}")