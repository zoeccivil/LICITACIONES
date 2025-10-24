from __future__ import annotations

from typing import Optional, Iterable
from weakref import proxy

from PyQt6.QtCore import (
    Qt, QSortFilterProxyModel, QModelIndex, QRegularExpression, pyqtSignal, QTimer,
    QItemSelection, QSettings, QByteArray, QUrl, QSize
)
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QTableView, QLabel, QLineEdit, QComboBox,
    QPushButton, QHeaderView, QMenu, QGroupBox, QGridLayout, QSizePolicy
)
from PyQt6.QtGui import QGuiApplication, QCloseEvent, QDesktopServices

from app.core.logic.status_engine import StatusEngine, DefaultStatusEngine, NextDeadline
from app.ui.delegates.row_color_delegate import RowColorDelegate, ROW_BG_ROLE
from app.ui.delegates.progress_bar_delegate import ProgressBarDelegate
from app.ui.delegates.heatmap_delegate import HeatmapDelegate
from app.ui.models.status_proxy_model import StatusFilterProxyModel
from app.ui.models.licitaciones_table_model import LicitacionesTableModel
from app.ui.windows.add_licitacion_window import AddLicitacionWindow
# NO pongas dlg = AddLicitacionWindow() fuera de una función o clase

ROLE_RECORD_ROLE = Qt.ItemDataRole.UserRole + 1002
ESTADO_TEXT_ROLE = Qt.ItemDataRole.UserRole + 1003
EMPRESA_TEXT_ROLE = Qt.ItemDataRole.UserRole + 1004
LOTES_TEXT_ROLE = Qt.ItemDataRole.UserRole + 1005
PROCESO_NUM_ROLE = Qt.ItemDataRole.UserRole + 1010
CARPETA_PATH_ROLE = Qt.ItemDataRole.UserRole + 1011
DOCS_PROGRESS_ROLE = Qt.ItemDataRole.UserRole + 1012
DIFERENCIA_PCT_ROLE = Qt.ItemDataRole.UserRole + 1013


class DashboardWindow(QWidget):
    countsChanged = pyqtSignal(int, int)
    detailRequested = pyqtSignal(object)

    def __init__(self, model, parent: QWidget | None = None, status_engine: Optional[StatusEngine] = None):
        super().__init__(parent)
        self._model = model
        self._status = status_engine or DefaultStatusEngine()

        self._settings = QSettings("Zoeccivil", "Licitaciones")
        self._settingsDebounce = QTimer(self)
        self._settingsDebounce.setSingleShot(True)
        self._settingsDebounce.setInterval(250)
        self._settingsDebounce.timeout.connect(self._save_settings)

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(220)

        self._docs_col: Optional[int] = 4
        self._dif_col: Optional[int] = 5
        self._docs_role: Optional[int] = DOCS_PROGRESS_ROLE
        self._dif_role: Optional[int] = DIFERENCIA_PCT_ROLE

        self._build_ui()
        self._setup_models()    # <-- IMPORTANTE: Asigna el modelo antes de conectar señales
        self._wire()            # <-- Ahora sí puedes conectar señales de selección

        self._populate_filter_values()
        self._apply_filters_to_both()
        self._update_tab_counts()

        self._restore_settings()
        self._setup_context_menus()

    def abrir_nueva_licitacion(self):
        dlg = AddLicitacionWindow(self)
        dlg.exec()

    def _wire(self):
        # Conecta señales SOLO si selectionModel ya existe (después de setModel)
        if self.tableActivas.selectionModel():
            self.tableActivas.selectionModel().selectionChanged.connect(self._sync_right_panel_with_selection)
        if self.tableFinalizadas.selectionModel():
            self.tableFinalizadas.selectionModel().selectionChanged.connect(self._sync_right_panel_with_selection)
        self.tabs.currentChanged.connect(self._sync_right_panel_with_selection)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        # Grupo Filtros y Próximo Vencimiento
        self.filtersGroup = QGroupBox("Filtros y Búsqueda", self)
        self.filtersGroup.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        fg_h = QHBoxLayout(self.filtersGroup)
        fg_h.setContentsMargins(8, 8, 8, 8)
        fg_h.setSpacing(12)

        # Filtros (zona izquierda)
        filters_layout = QGridLayout()
        filters_layout.setHorizontalSpacing(8)
        filters_layout.setVerticalSpacing(4)

        self.searchEdit = QLineEdit()
        self.loteEdit = QLineEdit()
        self.estadoCombo = QComboBox(); self.estadoCombo.addItem("Todos")
        self.empresaCombo = QComboBox(); self.empresaCombo.addItem("Todas")

        filters_layout.addWidget(QLabel("Buscar Proceso:"), 0, 0)
        filters_layout.addWidget(self.searchEdit,           0, 1)
        filters_layout.addWidget(QLabel("Contiene Lote:"),  0, 2)
        filters_layout.addWidget(self.loteEdit,             0, 3)
        filters_layout.addWidget(QLabel("Estado:"),         1, 0)
        filters_layout.addWidget(self.estadoCombo,          1, 1)
        filters_layout.addWidget(QLabel("Empresa:"),        1, 2)
        filters_layout.addWidget(self.empresaCombo,         1, 3)

        self.searchEdit.setMinimumWidth(140)
        self.loteEdit.setMinimumWidth(100)
        self.estadoCombo.setMinimumWidth(110)
        self.empresaCombo.setMinimumWidth(120)

        # Botón Limpiar Filtros junto a los filtros
        self.clearBtn = QPushButton("Limpiar Filtros")
        self.clearBtn.setFixedWidth(110)
        self.clearBtn.setFixedHeight(26)
        filters_layout.addWidget(self.clearBtn, 0, 4, 2, 1, alignment=Qt.AlignmentFlag.AlignTop)

        fg_h.addLayout(filters_layout, 5)

        # Panel derecho: Próximo Vencimiento, ahora ocupa TODO el espacio
        right = QVBoxLayout()
        right.setSpacing(6)

        self.nextDueTitle = QLabel("Próximo Vencimiento")
        self.nextDueTitle.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self.nextDueArea = QLabel("-- Selecciona una Fila --")
        self.nextDueArea.setWordWrap(True)
        self.nextDueArea.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.nextDueArea.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.nextDueArea.setTextFormat(Qt.TextFormat.RichText)
        self.nextDueArea.setStyleSheet("""
            background: #e3f2fd;
            color: #263238;
            padding: 16px;
            border-radius: 7px;
            font-size: 13px;        /* Más pequeño para que quepa más texto */
            font-weight: 500;
            /* No overflow ni ellipsis: que salga todo! */
        """)
        self.nextDueArea.setTextFormat(Qt.TextFormat.RichText)

        right.addWidget(self.nextDueTitle, alignment=Qt.AlignmentFlag.AlignLeft)
        right.addWidget(self.nextDueArea, 1)  # stretch = 1, ocupa todo el espacio vertical

        fg_h.addLayout(right, 8)  # le damos MÁS espacio al panel derecho

        root.addWidget(self.filtersGroup, 0)

        # Tabs (listado)
        self.tabs = QTabWidget()
        self.tableActivas = QTableView()
        self.tableFinalizadas = QTableView()
        for tv in (self.tableActivas, self.tableFinalizadas):
            tv.setAlternatingRowColors(True)
            tv.setSortingEnabled(True)
            tv.horizontalHeader().setStretchLastSection(True)
            tv.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
            tv.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            tv.setItemDelegate(RowColorDelegate(tv))
            tv.setIconSize(QSize(16, 16))
        self.tabs.addTab(self.tableActivas, "Licitaciones Activas (0)")
        self.tabs.addTab(self.tableFinalizadas, "Licitaciones Finalizadas (0)")
        root.addWidget(self.tabs, 1)

        # KPIs
        kpi_bar = QHBoxLayout()
        self.kpiScope = QLabel("Activas: 0")
        self.kpiGanadas = QLabel("Ganadas: 0")
        self.kpiLotesGanados = QLabel("Lotes Ganados: 0")
        self.kpiPerdidas = QLabel("Perdidas: 0")
        for w in (self.kpiScope, self.kpiGanadas, self.kpiLotesGanados, self.kpiPerdidas):
            kpi_bar.addWidget(w)
        kpi_bar.addStretch(1)
        root.addLayout(kpi_bar)

        self.filtersGroup.setMaximumHeight(self.filtersGroup.sizeHint().height() + 6)

    def _setup_models(self):
        # Asume que self._model es tu LicitacionesTableModel
        from app.ui.models.status_proxy_model import StatusFilterProxyModel

        self._proxyActivas = StatusFilterProxyModel(show_finalizadas=False, status_engine=self._status)
        self._proxyActivas.setSourceModel(self._model)
        self.tableActivas.setModel(self._proxyActivas)

        self._proxyFinalizadas = StatusFilterProxyModel(show_finalizadas=True, status_engine=self._status)
        self._proxyFinalizadas.setSourceModel(self._model)
        self.tableFinalizadas.setModel(self._proxyFinalizadas)

        # Forzar nombre del encabezado "Estatus" (col 7) por si el estilo/strech lo oculta
        try:
            self._proxyActivas.setHeaderData(7, Qt.Orientation.Horizontal, "Estatus")
            self._proxyFinalizadas.setHeaderData(7, Qt.Orientation.Horizontal, "Estatus")
        except Exception:
            pass

        for tv in (self.tableActivas, self.tableFinalizadas):
            try:
                tv.hideColumn(8)  # Lotes
            except Exception:
                pass
            # Asegurar que el header muestre el texto
            hh = tv.horizontalHeader()
            try:
                hh.setHighlightSections(False)
                hh.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                hh.setMinimumSectionSize(60)
            except Exception:
                pass
            # Ancho inicial amigable para "Estatus"
            try:
                tv.setColumnWidth(7, 140)
            except Exception:
                pass

        # Delegates
        self.apply_delegates(docs_col=4, dif_col=5,
                            docs_role=DOCS_PROGRESS_ROLE, dif_role=DIFERENCIA_PCT_ROLE,
                            heat_neg_range=30.0, heat_pos_range=30.0, heat_alpha=90, heat_invert=False)

        # Orden inicial
        self.tableActivas.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self.tableFinalizadas.sortByColumn(0, Qt.SortOrder.AscendingOrder)

        # Selección para panel derecho
        # ¡IMPORTANTE! Siempre conecta la señal después de setModel
        self.tableActivas.selectionModel().selectionChanged.connect(self._on_selection_changed)
        self.tableFinalizadas.selectionModel().selectionChanged.connect(self._on_selection_changed)

        # Persist widths y sort
        self.tableActivas.horizontalHeader().sectionResized.connect(lambda *_: self._schedule_save_settings())
        self.tableFinalizadas.horizontalHeader().sectionResized.connect(lambda *_: self._schedule_save_settings())
        self.tableActivas.horizontalHeader().sortIndicatorChanged.connect(lambda *_: self._schedule_save_settings())
        self.tableFinalizadas.horizontalHeader().sortIndicatorChanged.connect(lambda *_: self._schedule_save_settings())
        
    def _populate_filter_values(self):
        estados = set()
        empresas = set()
        model = self._model
        for r in range(model.rowCount()):
            estados.add(str(model.index(r, 7).data(Qt.ItemDataRole.DisplayRole) or "").strip())
            empresas.add(str(model.index(r, 2).data(Qt.ItemDataRole.DisplayRole) or "").strip())

        cur_e = self.estadoCombo.currentText()
        cur_emp = self.empresaCombo.currentText()

        self.estadoCombo.blockSignals(True); self.empresaCombo.blockSignals(True)
        self.estadoCombo.clear(); self.estadoCombo.addItem("Todos")
        for e in sorted(e for e in estados if e): self.estadoCombo.addItem(e)
        self.empresaCombo.clear(); self.empresaCombo.addItem("Todas")
        for e in sorted(e for e in empresas if e): self.empresaCombo.addItem(e)
        if cur_e and cur_e in [self.estadoCombo.itemText(i) for i in range(self.estadoCombo.count())]:
            self.estadoCombo.setCurrentText(cur_e)
        if cur_emp and cur_emp in [self.empresaCombo.itemText(i) for i in range(self.empresaCombo.count())]:
            self.empresaCombo.setCurrentText(cur_emp)
        self.estadoCombo.blockSignals(False); self.empresaCombo.blockSignals(False)

    def _apply_filters_to_both(self):
        text = self.searchEdit.text().strip()
        estado_sel = self.estadoCombo.currentText()
        empresa_sel = self.empresaCombo.currentText()
        lote_txt = self.loteEdit.text()

        estados = {estado_sel} if estado_sel and estado_sel.lower() != "todos" else None
        empresas = {empresa_sel} if empresa_sel and empresa_sel.lower() != "todas" else None

        for proxy in (self._proxyActivas, self._proxyFinalizadas):
            proxy.set_search_text(text)
            proxy.set_filter_estado(estados)
            proxy.set_filter_empresa(empresas)
            proxy.set_filter_lote_contains(lote_txt)

        self._update_row_colors()
        self._update_tab_counts()
        self._update_kpis_for_current_tab()

    def _update_row_colors(self):
        model = self._model
        for r in range(model.rowCount()):
            idx0 = model.index(r, 0)
            lic = idx0.data(ROLE_RECORD_ROLE)
            if lic is None:
                continue
            _, color = self._status.estatus_y_color(lic)
            model.setData(idx0, color, ROW_BG_ROLE)

    def _update_tab_counts(self):
        act = self._proxyActivas.rowCount()
        fin = self._proxyFinalizadas.rowCount()
        self.tabs.setTabText(0, f"Licitaciones Activas ({act})")
        self.tabs.setTabText(1, f"Licitaciones Finalizadas ({fin})")
        self.countsChanged.emit(act, fin)

    def _visible_licitaciones(self, proxy) -> Iterable:
        for r in range(proxy.rowCount()):
            idx_proxy = proxy.index(r, 0)
            idx_src = proxy.mapToSource(idx_proxy)
            lic = idx_src.siblingAtColumn(0).data(ROLE_RECORD_ROLE)
            print("\n=== DEBUG LICITACION ===")
            print("Objeto licitación:", lic)
            print("Atributos:", dir(lic))
            print("Nombre:", getattr(lic, "nombre_proceso", None) or getattr(lic, "nombre", None))
            cronograma = getattr(lic, "cronograma", None)
            print("Cronograma:", cronograma)
            print("========================\n")
            if lic is not None:
                yield lic

    def _update_kpis_for_current_tab(self):
        proxy = self._proxyActivas if self.tabs.currentIndex() == 0 else self._proxyFinalizadas
        visibles = list(self._visible_licitaciones(proxy))
        total = len(visibles)
        ganadas, perdidas, lotes_ganados = self._status.kpis(visibles)

        self.kpiScope.setText(("Activas" if self.tabs.currentIndex() == 0 else "Finalizadas") + f": {total}")
        self.kpiGanadas.setText(f"Ganadas: {ganadas}")
        self.kpiLotesGanados.setText(f"Lotes Ganados: {lotes_ganados}")
        self.kpiPerdidas.setText(f"Perdidas: {perdidas}")

    def _clear_filters(self):
        self.searchEdit.clear()
        self.estadoCombo.setCurrentIndex(0)
        self.empresaCombo.setCurrentIndex(0)
        self.loteEdit.clear()
        self._apply_filters_to_both()

    def _on_tab_changed(self, index: int):
        self._update_kpis_for_current_tab()
        self._sync_right_panel_with_selection()
        self._schedule_save_settings()

    def _on_selection_changed(self, selected, deselected):
        print(">>>> Cambió la selección")
        self._sync_right_panel_with_selection()

    def _sync_right_panel_with_selection(self):
        view = self.tableActivas if self.tabs.currentIndex() == 0 else self.tableFinalizadas
        if not view.selectionModel():
            self.nextDueArea.setText("-- Selecciona una Fila --")
            print("NO selectionModel")
            return

        sel = view.selectionModel().selectedRows()
        if not sel:
            # Intenta con el índice actual si no hay seleccionados
            idx = view.currentIndex()
            if not idx.isValid():
                self.nextDueArea.setText("-- Selecciona una Fila --")
                print("NO row selected y currentIndex inválido")
                return
            print("NO row selected pero hay currentIndex")
        else:
            idx = sel[0]

        model = view.model()
        if hasattr(model, "mapToSource"):
            src_idx = model.mapToSource(idx)
        else:
            src_idx = idx

        lic = src_idx.siblingAtColumn(0).data(ROLE_RECORD_ROLE)
        if lic is None:
            self.nextDueArea.setText("-- Selecciona una Fila --")
            print("NO lic found")
            return

        # ... (resto igual)

        # DEPURACIÓN
        print("\n=== DEBUG LICITACION ===")
        print("Objeto licitación:", lic)
        print("Atributos:", dir(lic))
        print("Nombre:", getattr(lic, "nombre_proceso", None) or getattr(lic, "nombre", None))
        cronograma = getattr(lic, "cronograma", None)
        print("Cronograma:", cronograma)
        print("========================\n")

        import datetime
        hoy = datetime.date.today()
        cronograma = cronograma or {}

        eventos_futuros = []
        for k, v in cronograma.items():
            print(f"Clave: {k}, Valor: {v}")
            if not isinstance(v, dict):
                print("No es dict")
                continue
            fecha_str = v.get("fecha_limite")
            estado = (v.get("estado") or "").strip().lower()
            print(f"  fecha_str: {fecha_str}, estado: {estado}")
            if not fecha_str or "pendiente" not in estado:
                print("Salta por falta de fecha o estado no pendiente")
                continue
            for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
                try:
                    fecha = datetime.datetime.strptime(str(fecha_str).strip()[:10], fmt).date()
                    eventos_futuros.append((fecha, k, fecha_str))
                    print(f"  Agrega evento: {fecha}, {k}, {fecha_str}")
                    break
                except Exception as e:
                    print(f"    Error al parsear fecha: {e}")
                    continue

        print("eventos_futuros:", eventos_futuros)

        if eventos_futuros:
            eventos_futuros.sort(key=lambda x: x[0])
            fecha, nombre_hito, fecha_str = eventos_futuros[0]
            diferencia = (fecha - hoy).days
            lic_nombre = getattr(lic, "nombre_proceso", None) or getattr(lic, "nombre", None) or ""
            if diferencia < 0:
                texto = (
                    f'<b>{lic_nombre}</b><br>'
                    f'<span style="color:#C62828;font-weight:bold">'
                    f'Vencida hace {abs(diferencia)} día{"s" if abs(diferencia)!=1 else ""} para: {nombre_hito}'
                    f'</span>'
                )
            elif diferencia == 0:
                texto = (
                    f'<b>{lic_nombre}</b><br>'
                    f'<span style="color:#F9A825;font-weight:bold">'
                    f'¡Hoy! para: {nombre_hito}'
                    f'</span>'
                )
            else:
                color = "#FBC02D" if diferencia <= 7 else "#42A5F5" if diferencia <= 30 else "#2E7D32"
                texto = (
                    f'<b>{lic_nombre}</b><br>'
                    f'<span style="color:{color};font-weight:bold">'
                    f'Faltan {diferencia} días para: {nombre_hito}'
                    f'</span>'
                )
                self.nextDueArea.setText(texto)

            print("TEXTO FINAL A MOSTRAR EN PANEL:", texto)
            self.nextDueArea.setText(texto)
            return

        print("NO hay eventos futuros válidos")
        self.nextDueArea.setText("<b>Sin cronograma</b>")        
        # ---------- Menú contextual ----------

    def _setup_context_menus(self):
        for tv in (self.tableActivas, self.tableFinalizadas):
            tv.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            tv.customContextMenuRequested.connect(lambda pos, view=tv: self._on_custom_context_menu(view, pos))

    def _on_custom_context_menu(self, view: QTableView, pos):
        idx = view.indexAt(pos)
        menu = QMenu(view)
        if not idx.isValid():
            menu.addAction("No hay elemento").setEnabled(False)
            menu.exec(view.viewport().mapToGlobal(pos))
            return

        proxy = view.model()
        src_idx = proxy.mapToSource(idx.siblingAtColumn(0))
        lic = src_idx.data(ROLE_RECORD_ROLE)
        proceso = src_idx.data(PROCESO_NUM_ROLE) or src_idx.data(Qt.ItemDataRole.DisplayRole)
        carpeta = src_idx.data(CARPETA_PATH_ROLE)

        def _emit_open():
            self.detailRequested.emit(lic if lic is not None else proceso)

        def _copy_num():
            QGuiApplication.clipboard().setText(str(proceso or ""))

        def _open_folder():
            if carpeta:
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(carpeta)))

        menu.addAction("Abrir detalle", _emit_open)
        menu.addSeparator()
        menu.addAction("Copiar número de proceso", _copy_num)
        menu.addAction("Abrir carpeta del proceso", _open_folder)
        menu.exec(view.viewport().mapToGlobal(pos))

    # ---------- Delegates ----------
    def apply_delegates(self, docs_col: Optional[int] = None, dif_col: Optional[int] = None,
                        docs_role: Optional[int] = DOCS_PROGRESS_ROLE, dif_role: Optional[int] = DIFERENCIA_PCT_ROLE,
                        heat_neg_range: float = 30.0, heat_pos_range: float = 30.0, heat_alpha: int = 90, heat_invert: bool = False):
        self._docs_col, self._dif_col = docs_col, dif_col
        self._docs_role, self._dif_role = docs_role, dif_role

        for tv in (self.tableActivas, self.tableFinalizadas):
            if docs_col is not None:
                tv.setItemDelegateForColumn(docs_col, ProgressBarDelegate(tv, value_role=docs_role))
            if dif_col is not None:
                tv.setItemDelegateForColumn(dif_col, HeatmapDelegate(tv, value_role=dif_role,
                                                                    neg_range=heat_neg_range, pos_range=heat_pos_range,
                                                                    alpha=heat_alpha, invert=heat_invert))

    # ---------- Persistencia ----------
    def _settings_key(self, sub: str) -> str:
        return f"Dashboard/{sub}"

    def _schedule_save_settings(self):
        self._settingsDebounce.start()

    def _save_table_prefs(self, key_prefix: str, table: QTableView):
        header = table.horizontalHeader()
        if header is None:
            return
        cols = header.count()
        widths = [header.sectionSize(i) for i in range(cols)]
        sort_col = header.sortIndicatorSection()
        sort_order_enum = header.sortIndicatorOrder()
        try:
            sort_ord = int(sort_order_enum)
        except TypeError:
            sort_ord = int(getattr(sort_order_enum, "value", 0))

        self._settings.setValue(self._settings_key(f"{key_prefix}/widths"), widths)
        self._settings.setValue(self._settings_key(f"{key_prefix}/sort_col"), int(sort_col))
        self._settings.setValue(self._settings_key(f"{key_prefix}/sort_ord"), int(sort_ord))

    def _restore_table_prefs(self, key_prefix: str, table: QTableView):
        header = table.horizontalHeader()
        if header is None:
            return

        widths = self._settings.value(self._settings_key(f"{key_prefix}/widths"))
        if isinstance(widths, list):
            for i, w in enumerate(widths):
                try:
                    table.setColumnWidth(i, int(w))
                except Exception:
                    pass

        sort_col = self._settings.value(self._settings_key(f"{key_prefix}/sort_col"))
        sort_ord = self._settings.value(self._settings_key(f"{key_prefix}/sort_ord"))

        def _to_int(v, default=0):
            try:
                if isinstance(v, (int, float)):
                    return int(v)
                if isinstance(v, str) and v.strip():
                    return int(v)
            except Exception:
                pass
            return default

        if sort_col is not None and sort_ord is not None:
            col = _to_int(sort_col, 0)
            ord_int = _to_int(sort_ord, 0)
            try:
                ord_enum = Qt.SortOrder(ord_int)
            except Exception:
                ord_enum = Qt.SortOrder.AscendingOrder
            try:
                table.sortByColumn(col, ord_enum)
            except Exception:
                pass

    def _save_settings(self):
        self._settings.setValue(self._settings_key("geometry"), self.saveGeometry())
        self._settings.setValue(self._settings_key("tab"), self.tabs.currentIndex())

        self._save_table_prefs("tableActivas", self.tableActivas)
        self._save_table_prefs("tableFinalizadas", self.tableFinalizadas)

    def _restore_settings(self):
        geom = self._settings.value(self._settings_key("geometry"))
        if isinstance(geom, QByteArray):
            try:
                self.restoreGeometry(geom)
            except Exception:
                pass
        tab = self._settings.value(self._settings_key("tab"))
        if tab is not None:
            try:
                self.tabs.setCurrentIndex(int(tab))
            except Exception:
                pass

        self._restore_table_prefs("tableActivas", self.tableActivas)
        self._restore_table_prefs("tableFinalizadas", self.tableFinalizadas)

    def closeEvent(self, event: QCloseEvent) -> None:
        try:
            self._save_settings()
        finally:
            super().closeEvent(event)

