from __future__ import annotations
from typing import List, Optional, Dict, Any
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
)
from app.core.models import Oferente
from app.ui.dialogs.gestionar_oferente_dialog import DialogoGestionarOferente


class TabCompetidores(QWidget):
    """
    Pestaña Competidores:
    - Añadir, editar, eliminar
    Columnas: Nombre, Comentario, Ofertas Habilitadas, Ofertas Totales
    """
    COL_NOM = 0
    COL_COM = 1
    COL_HAB = 2
    COL_TOT = 3

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Acciones
        actions = QHBoxLayout()
        self.btn_add = QPushButton("Añadir", self)
        self.btn_edit = QPushButton("Editar", self)
        self.btn_delete = QPushButton("Eliminar", self)
        for b in (self.btn_add, self.btn_edit, self.btn_delete):
            actions.addWidget(b)
        actions.addStretch(1)
        layout.addLayout(actions)

        # Tabla
        self.tree = QTreeWidget(self)
        self.tree.setColumnCount(4)
        self.tree.setHeaderLabels(["Nombre", "Comentario", "Ofertas Habilitadas", "Ofertas Totales"])
        self.tree.header().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setStretchLastSection(True)
        self.tree.setSortingEnabled(True)
        layout.addWidget(self.tree)

        # Conexiones
        self.btn_add.clicked.connect(self._on_add)
        self.btn_edit.clicked.connect(self._on_edit)
        self.btn_delete.clicked.connect(self._on_delete)
        self.tree.itemDoubleClicked.connect(self._on_item_double_clicked)

    # Public API
    def load_oferentes(self, oferentes: List[Oferente]):
        self.tree.clear()
        for o in oferentes or []:
            self._add_item_for_oferente(o)

    def to_oferentes(self) -> List[Oferente]:
        res: List[Oferente] = []
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            it = root.child(i)
            o: Oferente = it.data(0, Qt.ItemDataRole.UserRole)  # type: ignore
            if o:
                res.append(o)
        return res

    # Helpers
    def _add_item_for_oferente(self, o: Oferente):
        it = QTreeWidgetItem(self.tree)
        self._fill_item(it, o)
        self.tree.addTopLevelItem(it)

    def _fill_item(self, it: QTreeWidgetItem, o: Oferente):
        it.setText(self.COL_NOM, o.nombre or "")
        it.setText(self.COL_COM, o.comentario or "")
        it.setText(self.COL_HAB, f"{o.get_monto_total_ofertado(solo_habilitados=True):,.2f}")
        it.setText(self.COL_TOT, f"{o.get_monto_total_ofertado(solo_habilitados=False):,.2f}")
        it.setData(0, Qt.ItemDataRole.UserRole, o)

    def _get_selected_item(self) -> Optional[QTreeWidgetItem]:
        items = self.tree.selectedItems()
        return items[0] if items else None

    def _on_add(self):
        dlg = DialogoGestionarOferente(self, "Añadir Oferente", initial_data=None)
        if dlg.resultado is not None:
            data = dlg.resultado or {}
            o = Oferente(nombre=data.get("nombre", ""), comentario=data.get("comentario", ""))
            self._add_item_for_oferente(o)

    def _on_edit(self):
        it = self._get_selected_item()
        if not it:
            QMessageBox.information(self, "Editar", "Selecciona un competidor para editar.")
            return
        o: Oferente = it.data(0, Qt.ItemDataRole.UserRole)  # type: ignore
        dlg = DialogoGestionarOferente(self, "Editar Oferente", initial_data={"nombre": o.nombre, "comentario": o.comentario})
        if dlg.resultado is not None:
            data = dlg.resultado or {}
            o.nombre = data.get("nombre", "")
            o.comentario = data.get("comentario", "")
            self._fill_item(it, o)

    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int):
        self._on_edit()

    def _on_delete(self):
        it = self._get_selected_item()
        if not it:
            QMessageBox.information(self, "Eliminar", "Selecciona un competidor para eliminar.")
            return
        res = QMessageBox.question(self, "Confirmar", "¿Eliminar el competidor seleccionado?")
        if res == QMessageBox.StandardButton.Yes:
            idx = self.tree.indexOfTopLevelItem(it)
            self.tree.takeTopLevelItem(idx)