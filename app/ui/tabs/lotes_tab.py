from __future__ import annotations
from typing import List, Optional
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
from ...core.models import Lote
from ..dialogs.gestionar_lote_dialog import DialogoGestionarLote


class TabLotes(QWidget):
    """
    Pestaña Lotes con QTreeWidget:
    - Añadir, editar (doble click o botón), eliminar
    - Columnas: N°, Nombre, Base (Licitación), Base (Personal), Oferta, Empresa
    """
    COL_NUM = 0
    COL_NOMBRE = 1
    COL_BASE = 2
    COL_BASE_PERS = 3
    COL_OFERTA = 4
    COL_EMPRESA = 5

    def __init__(self, parent: QWidget, participating_companies: Optional[List[str]] = None):
        super().__init__(parent)
        self.participating_companies = participating_companies or []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Barra de acciones
        actions = QHBoxLayout()
        self.btn_add = QPushButton("Añadir Lote", self)
        self.btn_edit = QPushButton("Editar", self)
        self.btn_delete = QPushButton("Eliminar", self)

        actions.addWidget(self.btn_add)
        actions.addWidget(self.btn_edit)
        actions.addWidget(self.btn_delete)
        actions.addStretch(1)

        layout.addLayout(actions)

        # Árbol
        self.tree = QTreeWidget(self)
        self.tree.setColumnCount(6)
        self.tree.setHeaderLabels(["N°", "Nombre", "Base (Lic.)", "Base (Pers.)", "Oferta", "Empresa"])
        self.tree.header().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tree.setSortingEnabled(True)
        layout.addWidget(self.tree)

        # Conexiones
        self.btn_add.clicked.connect(self._on_add)
        self.btn_edit.clicked.connect(self._on_edit)
        self.btn_delete.clicked.connect(self._on_delete)
        self.tree.itemDoubleClicked.connect(self._on_item_double_clicked)

    # Public API
    def load_lotes(self, lotes: List[Lote]):
        self.tree.clear()
        for lote in lotes or []:
            self._add_item_for_lote(lote)

    def to_lotes(self) -> List[Lote]:
        lotes: List[Lote] = []
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            item = root.child(i)
            lote_obj: Lote = item.data(0, Qt.ItemDataRole.UserRole)  # type: ignore
            if lote_obj:
                lotes.append(lote_obj)
        return lotes

    # Helpers
    def _add_item_for_lote(self, lote: Lote):
        item = QTreeWidgetItem(self.tree)
        self._fill_item(item, lote)
        self.tree.addTopLevelItem(item)

    def _fill_item(self, item: QTreeWidgetItem, lote: Lote):
        item.setText(self.COL_NUM, str(lote.numero or ""))
        item.setText(self.COL_NOMBRE, lote.nombre or "")
        item.setText(self.COL_BASE, self._fmt_money(lote.monto_base))
        item.setText(self.COL_BASE_PERS, self._fmt_money(getattr(lote, "monto_base_personal", 0.0) or 0.0))
        item.setText(self.COL_OFERTA, self._fmt_money(lote.monto_ofertado))
        item.setText(self.COL_EMPRESA, lote.empresa_nuestra or "")
        item.setData(0, Qt.ItemDataRole.UserRole, lote)

    def _fmt_money(self, value: float) -> str:
        try:
            return f"{float(value):,.2f}"
        except Exception:
            return "0.00"

    # Events
    def _on_add(self):
        dlg = DialogoGestionarLote(self, "Añadir Lote", initial_data=None, participating_companies=self.participating_companies)
        if dlg.resultado is not None:
            # Construir Lote desde dict
            data = dlg.resultado or {}
            lote = Lote(
                id=data.get("id"),
                numero=str(data.get("numero") or ""),
                nombre=data.get("nombre") or "",
                monto_base=float(data.get("monto_base") or 0.0),
                monto_base_personal=float(data.get("monto_base_personal") or 0.0),
                monto_ofertado=float(data.get("monto_ofertado") or 0.0),
                empresa_nuestra=data.get("empresa_nuestra") or None,
            )
            self._add_item_for_lote(lote)

    def _get_selected_item(self) -> Optional[QTreeWidgetItem]:
        items = self.tree.selectedItems()
        return items[0] if items else None

    def _on_edit(self):
        item = self._get_selected_item()
        if not item:
            QMessageBox.information(self, "Editar", "Selecciona un lote para editar.")
            return
        lote: Lote = item.data(0, Qt.ItemDataRole.UserRole)  # type: ignore
        dlg = DialogoGestionarLote(self, "Editar Lote", initial_data=lote, participating_companies=self.participating_companies)
        if dlg.resultado is not None:
            data = dlg.resultado or {}
            lote.numero = str(data.get("numero") or "")
            lote.nombre = data.get("nombre") or ""
            lote.monto_base = float(data.get("monto_base") or 0.0)
            lote.monto_base_personal = float(data.get("monto_base_personal") or 0.0)
            lote.monto_ofertado = float(data.get("monto_ofertado") or 0.0)
            lote.empresa_nuestra = data.get("empresa_nuestra") or None
            self._fill_item(item, lote)

    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int):
        self._on_edit()

    def _on_delete(self):
        item = self._get_selected_item()
        if not item:
            QMessageBox.information(self, "Eliminar", "Selecciona un lote para eliminar.")
            return
        res = QMessageBox.question(self, "Confirmar", "¿Eliminar el lote seleccionado?")
        if res == QMessageBox.StandardButton.Yes:
            idx = self.tree.indexOfTopLevelItem(item)
            self.tree.takeTopLevelItem(idx)