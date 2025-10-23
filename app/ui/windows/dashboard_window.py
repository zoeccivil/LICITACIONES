from __future__ import annotations
from typing import List, Optional, Tuple
import datetime
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QWidget,
    QGroupBox,
    QGridLayout,
    QLineEdit,
    QComboBox,
    QPushButton,
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QHeaderView,
    QHBoxLayout,
)

from app.core.db_adapter import DatabaseAdapter
from app.core.models import Licitacion


class DashboardWindow(QDialog):
    """
    Dashboard General de Licitaciones (iteración 1):
    - Grupos: Activas y Licitaciones Finalizadas (colapsable)
    - Filtros: Buscar Proceso, Contiene Lote, Estado, Empresa, Limpiar
    - Próximo Vencimiento: muestra el próximo hito de la licitación seleccionada
    - Columnas: Código, Nombre Proceso, Empresa, Restan, % Docs, % Dif., Monto Ofertado, Estatus

    NOTA:
    - Las reglas de estado, colores y selección de “finalizada” están aproximadas y marcadas con TODO
      para ajustarlas exactamente a tus reglas una vez nos compartas el detalle.
    """

    COL_COD = 0
    COL_NOMBRE = 1
    COL_EMPRESA = 2
    COL_RESTAN = 3
    COL_DOCS = 4
    COL_DIFF = 5
    COL_MONTO = 6
    COL_STATUS = 7

    def __init__(self, parent: QWidget, db: DatabaseAdapter):
        super().__init__(parent)
        self.setWindowTitle("Dashboard General")
        self.resize(1200, 720)
        self.db = db

        self._build_ui()
        self._load_data()

    # UI
    def _build_ui(self):
        layout = QVBoxLayout(self)

        filters = QGroupBox("Filtros y Búsqueda", self)
        g = QGridLayout(filters)

        self.ed_search = QLineEdit(filters)
        self.ed_search.setPlaceholderText("Buscar Proceso (número o nombre)")
        self.ed_lote = QLineEdit(filters)
        self.ed_lote.setPlaceholderText("Contiene Lote N°")
        self.cb_estado = QComboBox(filters)
        self.cb_estado.addItem("(Todos)")
        # TODO: reemplazar por tu lista cerrada de estados
        self.cb_estado.addItems(["Iniciada", "Sobre B Entregado", "Adjudicada", "Desierta", "Cancelada", "Fases cumplidas"])
        self.cb_empresa = QComboBox(filters)
        self.cb_empresa.setEditable(True)
        self.cb_empresa.addItem("(Todas)")

        self.btn_clear = QPushButton("Limpiar Filtros", filters)

        g.addWidget(QLabel("Buscar:"), 0, 0)
        g.addWidget(self.ed_search, 0, 1)
        g.addWidget(QLabel("Contiene Lote:"), 0, 2)
        g.addWidget(self.ed_lote, 0, 3)
        g.addWidget(QLabel("Estado:"), 1, 0)
        g.addWidget(self.cb_estado, 1, 1)
        g.addWidget(QLabel("Empresa:"), 1, 2)
        g.addWidget(self.cb_empresa, 1, 3)
        g.addWidget(self.btn_clear, 0, 4, 2, 1)
        layout.addWidget(filters)

        # Próximo vencimiento
        next_box = QGroupBox("Próximo Vencimiento", self)
        hb = QHBoxLayout(next_box)
        self.lbl_next = QLabel("-- Selecciona una Fila --", next_box)
        self.lbl_next.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_next.setStyleSheet("font-size: 18px; padding: 10px;")
        hb.addWidget(self.lbl_next)
        layout.addWidget(next_box)

        # Tabla
        self.tree = QTreeWidget(self)
        self.tree.setColumnCount(8)
        self.tree.setHeaderLabels(
            ["Código", "Nombre Proceso", "Empresa", "Restan", "% Docs", "% Dif.", "Monto Ofertado", "Estatus"]
        )
        self.tree.header().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setStretchLastSection(True)
        self.tree.setSortingEnabled(True)
        layout.addWidget(self.tree)

        # Eventos
        self.ed_search.textChanged.connect(self._apply_filters)
        self.ed_lote.textChanged.connect(self._apply_filters)
        self.cb_estado.currentTextChanged.connect(self._apply_filters)
        self.cb_empresa.currentTextChanged.connect(self._apply_filters)
        self.btn_clear.clicked.connect(self._clear_filters)
        self.tree.itemSelectionChanged.connect(self._on_selection_changed)

    # Data
    def _load_data(self):
        # Empresas maestras para combo
        try:
            empresas = self.db.list_empresas_maestras()
        except Exception:
            empresas = []
        for e in empresas:
            self.cb_empresa.addItem(e)

        # Cargar licitaciones (resumen) y luego detalles por cada una para calcular métricas
        try:
            resumen = self.db.list_licitaciones()
        except Exception:
            resumen = []

        # Guardamos en memoria una lista de modelos completos para filtrar en memoria
        self._licitaciones: List[Licitacion] = []
        for r in resumen:
            lic = self.db.load_licitacion_by_id(int(r.id))  # type: ignore[arg-type]
            if lic:
                self._licitaciones.append(lic)

        self._populate_tree()

    def _populate_tree(self):
        self.tree.clear()

        # Raíces
        root_activas = QTreeWidgetItem(self.tree, ["Licitaciones Activas"])
        root_final = QTreeWidgetItem(self.tree, ["Licitaciones Finalizadas"])
        root_activas.setFirstColumnSpanned(True)
        root_final.setFirstColumnSpanned(True)
        root_final.setExpanded(False)  # colapsada por defecto

        activas_count = 0
        final_count = 0

        for lic in self._licitaciones:
            is_final, status_text = self._is_finalizada_y_estado(lic)
            restan_text, restan_days = self._restan_text(lic)
            pct_docs = self._pct_docs(lic)
            pct_diff = self._pct_diff(lic)
            monto = self._monto_total(lic)
            empresa = ", ".join(e.nombre for e in lic.empresas_nuestras) or (lic.institucion or "")

            row = [
                lic.numero_proceso or "",
                lic.nombre_proceso or "",
                empresa,
                restan_text,
                f"{pct_docs:.1f}%",
                f"{pct_diff:+.2f}%",
                f"RD$ {monto:,.2f}",
                status_text,
            ]

            it = QTreeWidgetItem(row)
            it.setData(0, Qt.ItemDataRole.UserRole, lic)

            # Colorear según estado aproximado
            self._apply_row_color(it, status_text, is_final)

            if is_final:
                root_final.addChild(it)
                final_count += 1
            else:
                root_activas.addChild(it)
                activas_count += 1

        root_final.setText(0, f"Licitaciones Finalizadas ({final_count})")
        self.tree.addTopLevelItem(root_activas)
        self.tree.addTopLevelItem(root_final)
        self.tree.expandItem(root_activas)

    # Filtros
    def _apply_filters(self):
        search = self.ed_search.text().strip().lower()
        lote_contains = self.ed_lote.text().strip()
        estado = self.cb_estado.currentText().strip()
        empresa_sel = self.cb_empresa.currentText().strip()

        def matches(lic: Licitacion) -> bool:
            # Buscar Proceso: numero_proceso o nombre_proceso
            if search:
                hay = (search in (lic.numero_proceso or "").lower()) or (search in (lic.nombre_proceso or "").lower())
                if not hay:
                    return False

            # Contiene Lote
            if lote_contains:
                if not any((l.numero or "") == lote_contains for l in lic.lotes or []):
                    return False

            # Estado (aproximado)
            is_final, status_text = self._is_finalizada_y_estado(lic)
            if estado and estado != "(Todos)":
                if status_text != estado:
                    return False

            # Empresa
            if empresa_sel and empresa_sel != "(Todas)":
                if not any(e.nombre == empresa_sel for e in (lic.empresas_nuestras or [])):
                    return False

            return True

        self._licitaciones_filtradas = list(filter(matches, self._licitaciones))
        # Actualizar árbol con filtradas
        lic_backup = self._licitaciones
        self._licitaciones = self._licitaciones_filtradas
        self._populate_tree()
        self._licitaciones = lic_backup  # restaurar referencia original para futuras filtraciones

    def _clear_filters(self):
        self.ed_search.clear()
        self.ed_lote.clear()
        self.cb_estado.setCurrentIndex(0)
        self.cb_empresa.setCurrentIndex(0)

    # Selection
    def _on_selection_changed(self):
        items = self.tree.selectedItems()
        if not items:
            self._set_next_label("-- Selecciona una Fila --", color="#777")
            return
        it = items[0]
        # Omitir nodos raíz
        if it.childCount() >= 0 and it.data(0, Qt.ItemDataRole.UserRole) is None:
            if it.childCount() > 0:
                self._set_next_label("-- Selecciona una Fila --", color="#777")
                return
        lic: Licitacion = it.data(0, Qt.ItemDataRole.UserRole)  # type: ignore
        text, _, color = self._next_deadline_info(lic)
        self._set_next_label(text, color=color)

    def _set_next_label(self, text: str, color: str = "#444"):
        self.lbl_next.setText(text)
        self.lbl_next.setStyleSheet(f"font-size: 18px; padding: 10px; background-color: #222; color: {color};")

    # Helpers de cálculo (aproximados, para ajustar con tus reglas)
    def _is_finalizada_y_estado(self, lic: Licitacion) -> Tuple[bool, str]:
        # TODO: Reemplazar por reglas exactas
        if getattr(lic, "adjudicada", False) and (lic.adjudicada_a or "").strip():
            # Si adjudicada a nosotros o a terceros:
            es_nuestro = any(e.nombre.strip() == (lic.adjudicada_a or "").strip() for e in lic.empresas_nuestras)
            return True, "Adjudicada" if es_nuestro else "Perdida"
        if (lic.motivo_descalificacion or "").strip():
            return True, "Descalificada"
        # Estado textual si lo trae
        estado = (lic.estado or "").strip() or "Iniciada"
        # Heurística: considerar finalizada si el estado textual es Cancelada/Desierta
        if estado in ("Cancelada", "Desierta"):
            return True, estado
        return False, estado

    def _next_deadline_info(self, lic: Licitacion) -> Tuple[str, int, str]:
        """
        Devuelve: (texto, días_restantes, color_hex)
        Regla aproximada: primer hito futuro en cronograma; si ninguno, 'Fases cumplidas'.
        """
        cron = lic.cronograma or {}
        # TODO: reemplazar por tus claves exactas y orden de prioridad
        keys_order = [
            "apertura_ofertas",
            "presentacion_sobre_b",
            "notificacion_adjudicacion",
            "adjudicacion",
        ]
        today = datetime.date.today()
        futuros: List[Tuple[str, int]] = []
        for k in keys_order:
            v = cron.get(k)
            if not v:
                continue
            try:
                d = datetime.date.fromisoformat(str(v))
            except Exception:
                # Aceptar formatos comunes YYYY-MM-DD HH:MM:SS
                try:
                    d = datetime.datetime.fromisoformat(str(v)).date()
                except Exception:
                    continue
            delta = (d - today).days
            if delta >= 0:
                futuros.append((k, delta))

        if futuros:
            k, days = sorted(futuros, key=lambda x: x[1])[0]
            label = {
                "apertura_ofertas": "Apertura de Ofertas",
                "presentacion_sobre_b": "Presentación de Sobre B",
                "notificacion_adjudicacion": "Notificación de Adjudicación",
                "adjudicacion": "Adjudicación",
            }.get(k, k)
            if days == 0:
                return f"Hoy: {label}", 0, "#00D1B2"
            elif days == 1:
                return f"Falta 1 día para: {label}", days, "#E6A700"
            else:
                return f"Faltan {days} días para: {label}", days, "#E6A700"

        # Sin futuros: ver si todo cumplido o vencido
        return "Fases cumplidas", -1, "#8F8F8F"

    def _restan_text(self, lic: Licitacion) -> Tuple[str, int]:
        text, days, _ = self._next_deadline_info(lic)
        return text, days

    def _pct_docs(self, lic: Licitacion) -> float:
        try:
            return float(lic.get_porcentaje_completado())
        except Exception:
            return 0.0

    def _pct_diff(self, lic: Licitacion) -> float:
        try:
            return float(lic.get_diferencia_porcentual(solo_participados=False, usar_base_personal=True))
        except Exception:
            return 0.0

    def _monto_total(self, lic: Licitacion) -> float:
        try:
            return float(lic.get_oferta_total(solo_participados=False))
        except Exception:
            return 0.0

    def _apply_row_color(self, it: QTreeWidgetItem, status: str, is_final: bool):
        """
        Colorea filas con reglas básicas. Sustituir por tu paleta:
        - Adjudicada (a nosotros): verde
        - Perdida/Descalificada/Cancelada/Desierta: rojo tenue
        - Iniciada/Sobre B Entregado/etc.: amarillo suave
        """
        status_l = (status or "").strip().lower()
        if "adjudicada" in status_l:
            color = QColor("#0E8A3A")
            fg = QColor("#FFFFFF")
        elif any(x in status_l for x in ("perdida", "descalificada", "cancelada", "desierta")):
            color = QColor("#A94442")
            fg = QColor("#FFFFFF")
        else:
            color = QColor("#F3E7B1")
            fg = QColor("#333333")
        for col in range(self.tree.columnCount()):
            it.setBackground(col, QBrush(color))
            it.setForeground(col, QBrush(fg))