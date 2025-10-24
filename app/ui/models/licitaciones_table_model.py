from __future__ import annotations

from typing import Any, List, Optional, Sequence, Dict
from PyQt6.QtCore import Qt, QAbstractTableModel, QModelIndex, QVariant, QRect
from PyQt6.QtGui import QColor, QBrush, QIcon, QPixmap, QPainter, QFont, QPen

IS_FINALIZADA_ROLE = Qt.ItemDataRole.UserRole + 1001
ROLE_RECORD_ROLE = Qt.ItemDataRole.UserRole + 1002
ESTADO_TEXT_ROLE = Qt.ItemDataRole.UserRole + 1003
EMPRESA_TEXT_ROLE = Qt.ItemDataRole.UserRole + 1004
LOTES_TEXT_ROLE = Qt.ItemDataRole.UserRole + 1005
PROCESO_NUM_ROLE = Qt.ItemDataRole.UserRole + 1010
CARPETA_PATH_ROLE = Qt.ItemDataRole.UserRole + 1011
DOCS_PROGRESS_ROLE = Qt.ItemDataRole.UserRole + 1012
DIFERENCIA_PCT_ROLE = Qt.ItemDataRole.UserRole + 1013
ROW_BG_ROLE = Qt.ItemDataRole.UserRole + 1201


class LicitacionesTableModel(QAbstractTableModel):
    HEADERS = [
        "Código",
        "Nombre Proceso",
        "Empresa",
        "Restan",
        "% Docs",
        "% Dif.",
        "Monto Ofertado",
        "Estatus",
        "Lotes",
    ]

    def __init__(self, status_engine, parent=None):
        super().__init__(parent)
        self._rows: List[Any] = []
        self._status_engine = status_engine
        # Cache de íconos por clave
        self._icon_cache: Dict[str, QIcon] = {}

    def set_rows(self, licitaciones: Sequence[Any]):
        self.beginResetModel()
        self._rows = list(licitaciones or [])
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.HEADERS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            try:
                return self.HEADERS[section]
            except Exception:
                return QVariant()
        return QVariant()

    def flags(self, index: QModelIndex):
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled

    def _empresas_text(self, lic) -> str:
        emps = getattr(lic, "empresas_nuestras", None) or getattr(lic, "empresas", None) or []
        names = []
        for e in emps:
            n = getattr(e, "nombre", None) or (e if isinstance(e, str) else None)
            if n:
                names.append(str(n))
        return ", ".join(names)

    def _lotes_text(self, lic) -> str:
        lotes = getattr(lic, "lotes", []) or []
        try:
            return ", ".join([str(getattr(l, "numero", "")) for l in lotes if getattr(l, "numero", "")])
        except Exception:
            return ""

    # ---------------- Íconos para Estatus ----------------
    def _badge_icon(self, color: QColor, glyph: str, size: int = 16) -> QIcon:
        # Clave de cache
        key = f"{color.name()}|{glyph}|{size}"
        if key in self._icon_cache:
            return self._icon_cache[key]

        pm = QPixmap(size, size)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)

        # Círculo
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color)
        p.drawEllipse(0, 0, size - 1, size - 1)

        # Glifo en blanco
        pen = QPen(QColor("#FFFFFF"))
        p.setPen(pen)
        font = QFont()
        # Ajusto tamaño relativo al badge
        font.setPointSize(max(8, int(size * 0.68)))
        font.setBold(True)
        p.setFont(font)
        p.drawText(QRect(0, 0, size, size), Qt.AlignmentFlag.AlignCenter, glyph)
        p.end()

        icon = QIcon(pm)
        self._icon_cache[key] = icon
        return icon

    def _status_icon_for_text(self, text: str) -> Optional[QIcon]:
        n = (text or "").lower()
        # Verde ✓ para ganada
        if "adjudicada" in n and "ganada" in n:
            return self._badge_icon(QColor("#2E7D32"), "✓")
        # Rojo ✕ para perdida/cancelada/descalificada
        if any(k in n for k in ("perdida", "cancel", "descalific")):
            return self._badge_icon(QColor("#C62828"), "✕")
        # Gris – para desierta
        if "desierta" in n:
            return self._badge_icon(QColor("#616161"), "–")
        # Sin ícono para el resto
        return None

    # -----------------------------------------------------

    def get_dias_restantes(self, lic) -> Optional[int]:
        """
        Devuelve la cantidad de días hasta el próximo hito relevante del cronograma de la licitación 'lic'.
        Soporta cronogramas donde cada valor es un dict con 'fecha_limite'.
        """
        import datetime

        cronograma = getattr(lic, "cronograma", None) or {}

        prioridad = [
            "presentacion_ofertas", "presentación_ofertas", "apertura_ofertas",
            "apertura", "ofertas", "adjudicacion", "adjudicación"
        ]
        hoy = datetime.date.today()

        fechas = []
        # Busca claves prioritarias
        for key in prioridad:
            for k, v in (cronograma or {}).items():
                if key in str(k).lower() and v:
                    fecha_str = None
                    # Si es dict, busca 'fecha_limite'
                    if isinstance(v, dict):
                        fecha_str = v.get("fecha_limite")
                    else:
                        fecha_str = v
                    if fecha_str:
                        for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
                            try:
                                d = datetime.datetime.strptime(str(fecha_str).strip()[:10], fmt).date()
                                fechas.append((d, k))
                                break
                            except Exception:
                                continue
        # Si no hay por prioridad, busca cualquier fecha válida
        if not fechas:
            for k, v in (cronograma or {}).items():
                fecha_str = None
                if isinstance(v, dict):
                    fecha_str = v.get("fecha_limite")
                else:
                    fecha_str = v
                if fecha_str:
                    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
                        try:
                            d = datetime.datetime.strptime(str(fecha_str).strip()[:10], fmt).date()
                            fechas.append((d, k))
                            break
                        except Exception:
                            continue

        if not fechas:
            return None

        fechas_ordenadas = sorted(fechas, key=lambda x: x[0])
        for fecha, _ in fechas_ordenadas:
            if fecha >= hoy:
                return (fecha - hoy).days
        return (fechas_ordenadas[-1][0] - hoy).days

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return QVariant()
        lic = self._rows[index.row()]

        # Roles personalizados
        if role == ROLE_RECORD_ROLE:
            return lic
        if role == PROCESO_NUM_ROLE:
            return getattr(lic, "numero_proceso", None) or getattr(lic, "numero", None)
        if role == CARPETA_PATH_ROLE:
            return getattr(lic, "carpeta_destino", None) or getattr(lic, "carpeta", None)
        if role == ESTADO_TEXT_ROLE:
            texto, _color = self._status_engine.estatus_y_color(lic)
            return texto
        if role == EMPRESA_TEXT_ROLE:
            return self._empresas_text(lic)
        if role == LOTES_TEXT_ROLE:
            return self._lotes_text(lic)
        if role == DOCS_PROGRESS_ROLE:
            try:
                pct = float(getattr(lic, "get_porcentaje_completado")())
            except Exception:
                pct = 0.0
            return pct
        if role == DIFERENCIA_PCT_ROLE:
            try:
                pct = float(getattr(lic, "get_diferencia_porcentual")(usar_base_personal=True))
            except Exception:
                pct = float("nan")
            return pct
        if role == IS_FINALIZADA_ROLE:
            try:
                return bool(self._status_engine.is_finalizada(lic))
            except Exception:
                return False
        if role == ROW_BG_ROLE:
            return getattr(lic, "__row_bg__", None)

        # Color de texto en Estatus (idx 7)
        if role == Qt.ItemDataRole.ForegroundRole and index.column() == 7:
            try:
                txt = str(self.data(index, ESTADO_TEXT_ROLE) or "")
                norm = txt.lower()
                if "adjudicada" in norm and "ganada" in norm:
                    return QBrush(QColor("#2E7D32"))
                if any(k in norm for k in ("perdida", "cancel", "descalific")):
                    return QBrush(QColor("#C62828"))
                if "desierta" in norm:
                    return QBrush(QColor("#616161"))
            except Exception:
                pass

        # Ícono en Estatus (idx 7)
        if role == Qt.ItemDataRole.DecorationRole and index.column() == 7:
            try:
                txt = str(self.data(index, ESTADO_TEXT_ROLE) or "")
                icon = self._status_icon_for_text(txt)
                if icon is not None:
                    return icon
            except Exception:
                pass

        # Texto mostrado
        if role == Qt.ItemDataRole.DisplayRole:
            col = index.column()
            if col == 0:
                return getattr(lic, "numero_proceso", None) or getattr(lic, "numero", "")
            if col == 1:
                return getattr(lic, "nombre_proceso", None) or getattr(lic, "nombre", "")
            if col == 2:
                return self._empresas_text(lic)
            if col == 3:
                # Aquí usamos get_dias_restantes para calcular el texto de "Restan"
                dias = self.get_dias_restantes(lic)
                if dias is None:
                    return "Sin cronograma"
                elif dias < 0:
                    return f"Vencida hace {abs(dias)} día{'s' if abs(dias) != 1 else ''}"
                elif dias == 0:
                    return "Hoy"
                elif dias == 1:
                    return "Falta 1 día"
                else:
                    return f"Faltan {dias} días"
            if col == 4:
                v = self.data(index, DOCS_PROGRESS_ROLE)
                try:
                    return f"{int(round(float(v)))}%"
                except Exception:
                    return "0%"
            if col == 5:
                v = self.data(index, DIFERENCIA_PCT_ROLE)
                try:
                    if v != v:
                        return "N/D"
                    return f"{float(v):.1f}%"
                except Exception:
                    return "N/D"
            if col == 6:
                try:
                    v = float(getattr(lic, "get_oferta_total")() or 0.0)
                except Exception:
                    v = 0.0
                if v <= 0.0:
                    return "N/D"
                return f"RD$ {v:,.2f}"
            if col == 7:
                # Solo el texto base del estatus (sin tags entre corchetes)
                return str(self.data(index, ESTADO_TEXT_ROLE) or "")
            if col == 8:
                return self._lotes_text(lic)

        return QVariant()

    def setData(self, index: QModelIndex, value, role=Qt.ItemDataRole.EditRole):
        if not index.isValid():
            return False
        if role == ROW_BG_ROLE:
            lic = self._rows[index.row()]
            setattr(lic, "__row_bg__", value)
            self.dataChanged.emit(
                index.siblingAtColumn(0),
                index.siblingAtColumn(self.columnCount() - 1),
                [ROW_BG_ROLE],
            )
            return True
        return False
    
    def proximo_vencimiento_info(lic):
        import datetime
        hoy = datetime.date.today()
        fechas = []
        prioridad = [
            "presentacion_ofertas", "presentación_ofertas", "apertura_ofertas",
            "apertura", "ofertas", "adjudicacion", "adjudicación"
        ]
        cronograma = getattr(lic, "cronograma", {}) or {}
        for key in prioridad:
            for k, v in cronograma.items():
                if key in str(k).lower() and v:
                    fecha_str = v.get("fecha_limite") if isinstance(v, dict) else v
                    if fecha_str:
                        for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
                            try:
                                d = datetime.datetime.strptime(str(fecha_str).strip()[:10], fmt).date()
                                fechas.append((d, k, fecha_str))
                                break
                            except Exception:
                                continue
        if not fechas:
            for k, v in cronograma.items():
                fecha_str = v.get("fecha_limite") if isinstance(v, dict) else v
                if fecha_str:
                    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
                        try:
                            d = datetime.datetime.strptime(str(fecha_str).strip()[:10], fmt).date()
                            fechas.append((d, k, fecha_str))
                            break
                        except Exception:
                            continue
        if not fechas:
            return None, None, None
        fechas.sort(key=lambda x: x[0])
        for fecha, nombre, fecha_str in fechas:
            if fecha >= hoy:
                return (fecha - hoy).days, nombre, fecha_str
        fecha, nombre, fecha_str = fechas[-1]
        return (fecha - hoy).days, nombre, fecha_str
    
    def _sync_right_panel_with_selection(self):
        # Selección activa o finalizada según tab
        view = self.tableActivas if self.tabs.currentIndex() == 0 else self.tableFinalizadas
        if not view.selectionModel():
            self.nextDueArea.setText("-- Selecciona una Fila --")
            return
        sel = view.selectionModel().selectedRows()
        if not sel:
            self.nextDueArea.setText("-- Selecciona una Fila --")
            return
        idx = sel[0]
        src_idx = view.model().mapToSource(idx)
        lic = src_idx.siblingAtColumn(0).data(ROLE_RECORD_ROLE)
        if lic is None:
            self.nextDueArea.setText("-- Selecciona una Fila --")
            return

        import datetime

        hoy = datetime.date.today()
        cronograma = getattr(lic, "cronograma", {}) or {}
        eventos_futuros = []
        for k, v in cronograma.items():
            fecha_str = None
            estado = None
            if isinstance(v, dict):
                fecha_str = v.get("fecha_limite")
                estado = v.get("estado", "")
            else:
                fecha_str = v

            if fecha_str and ("pendiente" in (estado or "").lower() or not estado):
                try:
                    fecha = datetime.datetime.strptime(str(fecha_str).strip()[:10], "%Y-%m-%d").date()
                    eventos_futuros.append((fecha, k, fecha_str))
                except Exception:
                    continue

        if eventos_futuros:
            eventos_futuros.sort(key=lambda x: x[0])
            fecha, nombre_hito, fecha_str = eventos_futuros[0]
            diferencia = (fecha - hoy).days
            lic_nombre = getattr(lic, "nombre_proceso", None) or getattr(lic, "nombre", None) or ""
            header = f"<b>{lic_nombre}</b><br>"

            if diferencia < 0:
                color = "#C62828"
                texto = f"{header}<span style='color:{color};font-weight:bold'>Vencida hace {abs(diferencia)} día{'s' if abs(diferencia)!=1 else ''} para:<br><b>{nombre_hito.replace('_', ' ').capitalize()}</b> <br><span style='font-size:11pt'>({fecha_str})</span></span>"
            elif diferencia == 0:
                color = "#F9A825"
                texto = f"{header}<span style='color:{color};font-weight:bold'>Hoy:<br><b>{nombre_hito.replace('_', ' ').capitalize()}</b> <br><span style='font-size:11pt'>({fecha_str})</span></span>"
            elif diferencia <= 7:
                color = "#FBC02D"
                texto = f"{header}<span style='color:{color};font-weight:bold'>Faltan {diferencia} días para:<br><b>{nombre_hito.replace('_', ' ').capitalize()}</b> <br><span style='font-size:11pt'>({fecha_str})</span></span>"
            elif diferencia <= 30:
                color = "#42A5F5"
                texto = f"{header}<span style='color:{color};font-weight:bold'>Faltan {diferencia} días para:<br><b>{nombre_hito.replace('_', ' ').capitalize()}</b> <br><span style='font-size:11pt'>({fecha_str})</span></span>"
            else:
                color = "#2E7D32"
                texto = f"{header}<span style='color:{color};font-weight:bold'>Faltan {diferencia} días para:<br><b>{nombre_hito.replace('_', ' ').capitalize()}</b> <br><span style='font-size:11pt'>({fecha_str})</span></span>"
            self.nextDueArea.setText(texto)
            return

        self.nextDueArea.setText("<b>Sin cronograma</b>")