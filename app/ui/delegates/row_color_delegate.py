from __future__ import annotations
from PyQt6.QtWidgets import QStyledItemDelegate
from PyQt6.QtGui import QBrush
from PyQt6.QtCore import Qt

ROW_BG_ROLE = Qt.ItemDataRole.UserRole + 1201


class RowColorDelegate(QStyledItemDelegate):
    """
    Pinta el fondo de la fila usando el role ROW_BG_ROLE que setea el modelo.
    """
    def paint(self, painter, option, index):
        # Aplica color de fila si está presente en la columna 0
        idx0 = index.siblingAtColumn(0)
        color = idx0.data(ROW_BG_ROLE)
        if color:
            option.backgroundBrush = QBrush(color)
        super().paint(painter, option, index)