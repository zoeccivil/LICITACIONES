from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, QRect, QSize
from PyQt6.QtGui import QPainter
from PyQt6.QtWidgets import QStyledItemDelegate, QStyleOptionProgressBar, QStyle, QWidget, QStyleOptionViewItem


class ProgressBarDelegate(QStyledItemDelegate):
    """
    Delegate para renderizar un porcentaje como barra de progreso.
    - value_role: si se provee, toma el valor (0..100) desde ese role.
    - Si no, intenta parsear el DisplayRole (admite '75%' o '75.0').
    """
    def __init__(self, parent: Optional[QWidget] = None, value_role: Optional[int] = None):
        super().__init__(parent)
        self.value_role = value_role

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        value = None
        if self.value_role is not None:
            v = index.data(self.value_role)
            if isinstance(v, (int, float)):
                value = float(v)
        if value is None:
            # Fallback parseo de DisplayRole
            txt = str(index.data(Qt.ItemDataRole.DisplayRole) or "").strip().replace("%", "")
            try:
                value = float(txt)
            except Exception:
                value = None

        if value is None:
            # Sin valor: render normal
            super().paint(painter, option, index)
            return

        value = max(0.0, min(100.0, value))
        # Base: pinta el fondo de celda como el estilo normal
        super().paint(painter, option, index)

        # Crea barra
        prog = QStyleOptionProgressBar()
        prog.rect = option.rect.adjusted(2, 4, -2, -4)
        prog.minimum = 0
        prog.maximum = 100
        prog.progress = int(round(value))
        prog.text = f"{int(round(value))}%"
        prog.textVisible = True
        prog.textAlignment = Qt.AlignmentFlag.AlignCenter

        # Estilo del widget padre
        style = option.widget.style() if option.widget else None
        if style:
            style.drawControl(QStyle.ControlElement.CE_ProgressBar, prog, painter)
        else:
            # Fallback simple
            painter.save()
            rect = QRect(prog.rect)
            painter.drawRect(rect)
            fill = QRect(rect)
            fill.setWidth(int(rect.width() * (value / 100.0)))
            painter.fillRect(fill, option.palette.highlight())
            painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:
        base = super().sizeHint(option, index)
        return QSize(base.width(), max(base.height(), 18))