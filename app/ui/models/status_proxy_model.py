from PyQt6.QtCore import QSortFilterProxyModel, Qt

ROLE_RECORD_ROLE = Qt.ItemDataRole.UserRole + 1002

class StatusFilterProxyModel(QSortFilterProxyModel):
    def __init__(self, show_finalizadas=False, status_engine=None, parent=None):
        super().__init__(parent)
        self.show_finalizadas = show_finalizadas
        self.status_engine = status_engine
        self._search_text = ""
        self._filter_estado = "Todos"
        self._filter_empresa = "Todas"
        self._filter_lote = ""
        self._filter_lote_contains = ""

    def set_search_text(self, text):
        self._search_text = text or ""
        self.invalidateFilter()

    def set_filter_estado(self, estado: str):
        self._filter_estado = estado or "Todos"
        self.invalidateFilter()

    def set_filter_empresa(self, empresa: str):
        self._filter_empresa = empresa or "Todas"
        self.invalidateFilter()

    def set_filter_lote(self, lote: str):
        self._filter_lote = lote or ""
        self.invalidateFilter()

    def set_filter_lote_contains(self, text: str):
        self._filter_lote_contains = text or ""
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row, source_parent):
        model = self.sourceModel()
        index = model.index(source_row, 0, source_parent)
        lic = model.data(index, role=ROLE_RECORD_ROLE)
        if lic is None:
            return False

        # Filtrado por activas/finalizadas
        if self.show_finalizadas:
            if not self.status_engine.is_finalizada(lic):
                return False
        else:
            if self.status_engine.is_finalizada(lic):
                return False

        # Filtrado por estado
        if self._filter_estado and self._filter_estado != "Todos":
            estado = getattr(lic, "estado", None)
            if not estado or self._filter_estado.lower() not in str(estado).lower():
                return False

        # Filtrado por empresa
        if self._filter_empresa and self._filter_empresa != "Todas":
            empresas = getattr(lic, "empresas_nuestras", None) or getattr(lic, "empresas", None) or []
            nombres = []
            for e in empresas:
                n = getattr(e, "nombre", None) or (e if isinstance(e, str) else None)
                if n:
                    nombres.append(str(n).lower())
            if self._filter_empresa.lower() not in [n.lower() for n in nombres]:
                return False

        # Filtrado por lote exacto
        if self._filter_lote:
            lotes = getattr(lic, "lotes", None) or []
            lote_match = False
            for l in lotes:
                num = getattr(l, "numero", None) or (l if isinstance(l, str) else None)
                if num and self._filter_lote.lower() == str(num).lower():
                    lote_match = True
                    break
            if not lote_match:
                return False

        # Filtrado por lote contiene (más flexible, ej. búsqueda parcial)
        if self._filter_lote_contains:
            lotes = getattr(lic, "lotes", None) or []
            match = False
            for l in lotes:
                num = getattr(l, "numero", None) or (l if isinstance(l, str) else None)
                if num and self._filter_lote_contains.lower() in str(num).lower():
                    match = True
                    break
            if not match:
                return False

        # Filtrado por texto de búsqueda (nombre o código)
        if self._search_text:
            texto = self._search_text.lower()
            nombre = getattr(lic, "nombre_proceso", "") or getattr(lic, "nombre", "")
            codigo = getattr(lic, "numero_proceso", "") or getattr(lic, "numero", "")
            if texto not in nombre.lower() and texto not in codigo.lower():
                return False

        return True