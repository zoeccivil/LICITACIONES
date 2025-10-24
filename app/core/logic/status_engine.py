from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Tuple

from PyQt6.QtGui import QColor


@dataclass(frozen=True)
class NextDeadline:
    label: str
    days: Optional[int]  # None si no aplica
    color: QColor
    verbose: str


class StatusEngine:
    def is_finalizada(self, lic) -> bool: ...
    def estatus_y_color(self, lic) -> Tuple[str, QColor]: ...
    def next_deadline(self, lic) -> NextDeadline: ...
    def kpis(self, licitaciones: Iterable) -> Tuple[int, int, int]: ...


class DefaultStatusEngine(StatusEngine):
    # Paleta base
    C_INICIADA = QColor("#FFFDE7")            # amarillo pálido
    C_SOBRE_B = QColor("#FFF3E0")             # naranja pálido
    C_FASES = QColor("#E0F7FA")               # cian pálido
    C_ADJ_GANADA = QColor("#E8F5E9")          # verde pálido
    C_ADJ_PERDIDA = QColor("#FFEBEE")         # rojo pálido
    C_DESCALIFICADA = QColor("#F8BBD0")       # rosa pálido
    C_DESIERTA = QColor("#ECEFF1")            # gris
    C_CANCELADA = QColor("#F3E5F5")           # violeta pálido
    C_EN_CURSO = QColor("#FAFAFA")            # neutro claro

    def _norm(self, s: Optional[str]) -> str:
        return (s or "").strip().lower()

    def is_finalizada(self, lic) -> bool:
        """
        Finalizada si:
        - adjudicada True, o
        - estado/estatus contiene 'adjudicad', 'desierta', 'cancelada' o 'descalificad', o
        - ganada True.
        """
        try:
            if hasattr(lic, "is_finalizada") and callable(getattr(lic, "is_finalizada")):
                return bool(lic.is_finalizada())
        except Exception:
            pass

        est = self._norm(getattr(lic, "estatus", None) or getattr(lic, "estado", None))
        adjudicada_flag = bool(getattr(lic, "adjudicada", False))
        ganada_flag = getattr(lic, "ganada", None)

        if adjudicada_flag:
            return True
        if any(k in est for k in ("adjudicad", "desierta", "cancelada", "descalificad")):
            return True
        if ganada_flag is True:
            return True

        return False

    def estatus_y_color(self, lic) -> Tuple[str, QColor]:
        """
        Traduce estado -> texto + color. 
        No etiqueta como 'Adjudicada' cuando solo hay 'ganada=False' sin adjudicación.
        """
        est_raw = getattr(lic, "estatus", None) or getattr(lic, "estado", None) or ""
        est = self._norm(est_raw)
        adjudicada_flag = bool(getattr(lic, "adjudicada", False))
        ganada_flag = getattr(lic, "ganada", None)

        # Adjudicación (explícita por flag o por texto)
        if adjudicada_flag or "adjudicad" in est:
            if ganada_flag is True:
                return "Adjudicada (Ganada)", self.C_ADJ_GANADA
            if ganada_flag is False:
                return "Adjudicada (Perdida)", self.C_ADJ_PERDIDA
            return "Adjudicada", self.C_EN_CURSO

        if "descalificad" in est:
            return "Descalificada", self.C_DESCALIFICADA

        if "desierta" in est:
            return "Desierta", self.C_DESIERTA

        if "cancelada" in est:
            return "Cancelada", self.C_CANCELADA

        # 'Fases cumplidas' sigue activa
        if "fases cumplidas" in est or "fases" in est:
            return "Fases cumplidas", self.C_FASES

        if any(k in est for k in ("sobre b", "apertura", "presentación", "presentacion")):
            return "Sobre B Entregado", self.C_SOBRE_B

        if any(k in est for k in ("en curso", "iniciada")) or not est:
            return "En curso", self.C_INICIADA

        return est_raw or "En curso", self.C_EN_CURSO

    def next_deadline(self, lic) -> NextDeadline:
        try:
            if hasattr(lic, "get_next_deadline_info") and callable(getattr(lic, "get_next_deadline_info")):
                info = lic.get_next_deadline_info()
                return NextDeadline(
                    label=str(info.get("label", "")),
                    days=info.get("days", None),
                    color=QColor(info.get("color", "#BDBDBD")),
                    verbose=str(info.get("verbose", "")),
                )
        except Exception:
            pass

        dias = None
        try:
            if hasattr(lic, "get_dias_restantes") and callable(getattr(lic, "get_dias_restantes")):
                dias = lic.get_dias_restantes()
        except Exception:
            dias = None

        if dias is None:
            return NextDeadline("Sin cronograma", None, QColor("#BDBDBD"), "Sin cronograma")

        if dias < 0:
            d = abs(int(dias))
            return NextDeadline("Vencida", dias, QColor("#EF9A9A"),
                                "Vencida hace 1 día" if d == 1 else f"Vencida hace {d} días")
        if dias == 0:
            return NextDeadline("Hoy", 0, QColor("#EF9A9A"), "Hoy")
        if dias == 1:
            return NextDeadline("Próximo hito", 1, QColor("#FFE082"), "Falta 1 día")

        color = QColor("#FFF176") if dias <= 3 else QColor("#C8E6C9")
        return NextDeadline("Próximo hito", int(dias), color, f"Faltan {int(dias)} días")

    def kpis(self, licitaciones: Iterable) -> Tuple[int, int, int]:
        ganadas = 0
        perdidas = 0
        lotes_ganados = 0
        for lic in licitaciones:
            est = self._norm(getattr(lic, "estatus", None) or getattr(lic, "estado", None))
            adj = bool(getattr(lic, "adjudicada", False))
            gan = getattr(lic, "ganada", None)

            if adj or "adjudicad" in est:
                if gan is True:
                    ganadas += 1
                    try:
                        lotes_ganados += sum(1 for l in getattr(lic, "lotes", []) if getattr(l, "ganado_por_nosotros", False))
                    except Exception:
                        pass
                elif gan is False:
                    perdidas += 1
            elif "descalificad" in est:
                # Descalificadas cuentan como perdidas
                perdidas += 1

        return ganadas, perdidas, lotes_ganados