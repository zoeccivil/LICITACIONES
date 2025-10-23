from __future__ import annotations
from typing import Optional, List
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QHeaderView,
    QWidget,
)
# Import relativo: desde app.ui.dialogs subir a app y entrar a core
from ...core.db_adapter import DatabaseAdapter
from ...core.models import Licitacion


class DialogoSeleccionarLicitacion(QDialog):
    """
    Muestra un listado de licitaciones de la DB para seleccionar una.
    Devuelve selected_id (int) si se acepta.
    """
    def __init__(self, parent: QWidget, db: DatabaseAdapter):
        super().__init__(parent)
        self.setWindowTitle("Abrir Licitación")
        self.resize(780, 480)
        self.db = db
        self.selected_id: Optional[int] = None

        self._build_ui()
        self._load()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        self.tree = QTreeWidget(self)
        self.tree.setColumnCount(5)
        self.tree.setHeaderLabels(["ID", "Número", "Nombre", "Institución", "Estado"])
        self.tree.header().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setStretchLastSection(True)
        layout.addWidget(self.tree)

        btns = QHBoxLayout()
        self.btn_open = QPushButton("Abrir", self)
        self.btn_cancel = QPushButton("Cancelar", self)
        btns.addStretch(1)
        btns.addWidget(self.btn_open)
        btns.addWidget(self.btn_cancel)
        layout.addLayout(btns)

        self.btn_open.clicked.connect(self._on_open)
        self.btn_cancel.clicked.connect(self.reject)
        self.tree.itemDoubleClicked.connect(self._on_item_double_clicked)

    def _load(self):
        self.tree.clear()
        licitaciones: List[Licitacion] = self.db.list_licitaciones()
        for lic in licitaciones:
            it = QTreeWidgetItem(self.tree)
            it.setText(0, str(lic.id or ""))
            it.setText(1, lic.numero_proceso or "")
            it.setText(2, lic.nombre_proceso or "")
            it.setText(3, lic.institucion or "")
            it.setText(4, lic.estado or "")
            it.setData(0, Qt.ItemDataRole.UserRole, int(lic.id or 0))
            self.tree.addTopLevelItem(it)

    def _on_open(self):
        it = self._get_selected_item()
        if not it:
            return
        self.selected_id = int(it.data(0, Qt.ItemDataRole.UserRole))
        self.accept()

    def _on_item_double_clicked(self, item: QTreeWidgetItem, col: int):
        self.selected_id = int(item.data(0, Qt.ItemDataRole.UserRole))
        self.accept()

    def _get_selected_item(self) -> Optional[QTreeWidgetItem]:
        items = self.tree.selectedItems()
        return items[0] if items else None