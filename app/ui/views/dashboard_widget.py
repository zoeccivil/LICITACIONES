from __future__ import annotations

from typing import Optional, Callable, Any, List

from PyQt6.QtWidgets import QWidget, QVBoxLayout

from app.core.db_adapter import DatabaseAdapter
from app.ui.windows.dashboard_window import DashboardWindow
from app.ui.models.licitaciones_table_model import LicitacionesTableModel, DOCS_PROGRESS_ROLE, DIFERENCIA_PCT_ROLE
from app.core.logic.status_engine import DefaultStatusEngine


class DashboardWidget(QWidget):
    """
    Carga datos desde DB, monta el modelo con todas las columnas,
    y presenta el Dashboard (tabs Activas/Finalizadas, filtros, KPIs, panel de vencimiento).
    """
    def __init__(self, parent=None, db: Optional[DatabaseAdapter] = None):
        super().__init__(parent)
        self.db = db

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Engine por defecto; luego lo sincronizamos 1:1 con glicitaciones2.py
        engine = DefaultStatusEngine()

        # Modelo + Vista
        self.model = LicitacionesTableModel(status_engine=engine)
        self.view = DashboardWindow(self.model, self, status_engine=engine)
        layout.addWidget(self.view)

        # Cargar datos
        if self.db:
            self.reload_data()

        # Hook para abrir detalle si lo necesitas
        # self.view.detailRequested.connect(self._on_detail_requested)

    def _resolve_loader(self) -> Callable[[], List[Any]]:
        """
        Devuelve una función llamable para obtener todas las licitaciones desde el adapter,
        probando varios nombres de método comunes.
        """
        if not self.db:
            raise RuntimeError("No hay adaptador de base de datos asignado.")

        candidates = [
            "load_all_licitaciones",
            "load_licitaciones",
            "listar_licitaciones",
            "list_licitaciones",
            "get_all_licitaciones",
            "get_licitaciones",
            "fetch_all_licitaciones",
            # variantes que algunos adaptadores usan con 'bids'
            "load_all_bids",
            "get_all_bids",
            "list_bids",
            "listar_bids",
        ]

        for name in candidates:
            fn = getattr(self.db, name, None)
            if callable(fn):
                # Aseguramos que sea sin parámetros
                def _loader(fn=fn):
                    return fn()
                return _loader

        # Si no encontramos un método directo, último intento:
        # - algunos adapters exponen un método genérico como 'all_licitaciones' propiedad/atributo
        attr = getattr(self.db, "all_licitaciones", None)
        if callable(attr):
            def _loader():
                return attr()
            return _loader
        if isinstance(attr, list):
            return lambda: attr

        raise AttributeError(
            "El DatabaseAdapter no expone un método para listar licitaciones. "
            "Probé: " + ", ".join(candidates + ["all_licitaciones"])
        )

    def reload_data(self):
        if not self.db:
            return
        loader = self._resolve_loader()
        licitaciones = loader()
        self.model.set_rows(licitaciones)
        self.view._update_row_colors()
        self.view._populate_filter_values()
        self.view._apply_filters_to_both()

    def _on_detail_requested(self, lic_or_id):
        pass