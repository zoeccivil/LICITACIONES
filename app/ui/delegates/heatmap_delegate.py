from __future__ import annotations

from typing import Optional, Tuple

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QBrush
from PyQt6.QtWidgets import QStyledItemDelegate, QWidget, QStyleOptionViewItem


def _lerp_color(a: QColor, b: QColor, t: float) -> QColor:
    t = max(0.0, min(1.0, t))
    return QColor(
        int(a.red() + (b.red() - a.red()) * t),
        int(a.green() + (b.green() - a.green()) * t),
        int(a.blue() + (b.blue() - a.blue()) * t),
        int(a.alpha() + (b.alpha() - a.alpha()) * t),
    )


class HeatmapDelegate(QStyledItemDelegate):
    """
    Pinta un fondo térmico para un valor porcentual:
    - Negativo (mejor): hacia verde.
    - Cercano a 0: amarillo.
    - Positivo (peor): hacia rojo.

    Configuración:
    - value_role: role opcional para leer el valor (en %). Si None, parsea DisplayRole.
    - neg_range, pos_range: rangos de -X% a +Y% para normalizar el gradiente.
    - alpha: opacidad del fondo para no eclipsar color de fila (RowColorDelegate).
    - invert: si True, invierte el sentido (negativo=rojo, positivo=verde).
    """
    def __init__(
        self,
        parent: Optional[QWidget] = None,
        value_role: Optional[int] = None,
        neg_range: float = 30.0,
        pos_range: float = 30.0,
        alpha: int = 90,
        invert: bool = False,
    ):
        super().__init__(parent)
        self.value_role = value_role
        self.neg_range = abs(neg_range)
        self.pos_range = abs(pos_range)
        self.alpha = max(0, min(255, alpha))
        self.invert = invert

        self.c_neg = QColor(76, 175, 80, self.alpha)      # verde
        self.c_mid = QColor(255, 235, 59, self.alpha)     # amarillo
        self.c_pos = QColor(244, 67, 54, self.alpha)      # rojo

    def _read_value(self, index) -> Optional[float]:
        if self.value_role is not None:
            v = index.data(self.value_role)
            if isinstance(v, (int, float)):
                return float(v)
        # Parseo de DisplayRole (admite "12.3%" o "12.3")
        raw = index.data(Qt.ItemDataRole.DisplayRole)
        if raw is None:
            return None
        s = str(raw).strip().replace("%", "")
        try:
            return float(s)
        except Exception:
            return None

    def _color_for(self, value: float) -> QColor:
        v = value
        if self.invert:
            v = -v

        if v < 0.0:
            # Mapea [-neg_range .. 0] => [c_neg .. c_mid]
            t = 1.0 - min(1.0, abs(v) / self.neg_range)
            return _lerp_color(self.c_neg, self.c_mid, t)
        else:
            # Mapea [0 .. pos_range] => [c_mid .. c_pos]
            t = min(1.0, v / self.pos_range)
            return _lerp_color(self.c_mid, self.c_pos, t)

    def paint(self, painter, option: QStyleOptionViewItem, index):
        val = self._read_value(index)
        if val is not None:
            color = self._color_for(val)
            option = QStyleOptionViewItem(option)
            option.backgroundBrush = QBrush(color)
        super().paint(painter, option, index)