from __future__ import annotations
from typing import List

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTabWidget,
    QWidget,
    QMessageBox,
)

from app.core.db_adapter import DatabaseAdapter
from app.core.models import Licitacion, Lote, Documento, Oferente
from app.ui.tabs.lotes_tab import TabLotes
from app.ui.tabs.documentos_tab import TabDocumentos
from app.ui.tabs.competidores_tab import TabCompetidores


class VentanaDetallesLicitacion(QDialog):
    """
    Ventana principal de detalles de una licitación.
    Orquesta las pestañas de Lotes, Documentos y Competidores.

    Requisitos mínimos en DatabaseAdapter:
      - get_licitacion_by_id(licitacion_id: int) -> Licitacion
      - save_licitacion(licitacion: Licitacion) -> bool | None
        (Si en tu adapter el método se llama update_licitacion, ajusta en _on_save)
    """

    def __init__(self, parent, licitacion_or_id, db):
        super().__init__(parent)
        self.db = db
        if isinstance(licitacion_or_id, Licitacion):
            self.licitacion = licitacion_or_id
            self.licitacion_id = getattr(self.licitacion, "id", None)
            self._is_new = True
        else:
            self.licitacion_id = licitacion_or_id
            self.licitacion = None
            self._is_new = False
        self.resultado = None
        self._build_ui()
        self._load_data()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Encabezado con información básica (solo lectura por ahora)
        self.header = QWidget(self)
        h = QHBoxLayout(self.header)
        self.lbl_numero = QLabel("", self.header)
        self.lbl_nombre = QLabel("", self.header)
        self.lbl_institucion = QLabel("", self.header)
        self.lbl_estado = QLabel("", self.header)
        for w in (self.lbl_numero, self.lbl_nombre, self.lbl_institucion, self.lbl_estado):
            w.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        h.addWidget(self._kv("N° Proceso:", self.lbl_numero))
        h.addWidget(self._kv("Nombre:", self.lbl_nombre))
        h.addWidget(self._kv("Institución:", self.lbl_institucion))
        h.addWidget(self._kv("Estado:", self.lbl_estado))
        h.addStretch(1)
        layout.addWidget(self.header)

        # Tabs
        self.tabs = QTabWidget(self)
        self.tab_lotes = TabLotes(self, participating_companies=[])  # se setean luego
        self.tab_docs = TabDocumentos(self, responsables=[], categories=None)
        self.tab_comp = TabCompetidores(self)

        self.tabs.addTab(self.tab_lotes, "Lotes")
        self.tabs.addTab(self.tab_docs, "Documentos")
        self.tabs.addTab(self.tab_comp, "Competidores")
        layout.addWidget(self.tabs)

        # Botonera inferior
        btns = QHBoxLayout()
        btns.addStretch(1)
        self.btn_save = QPushButton("Guardar", self)
        self.btn_close = QPushButton("Cerrar", self)
        btns.addWidget(self.btn_save)
        btns.addWidget(self.btn_close)
        layout.addLayout(btns)

        # Conexiones
        self.btn_save.clicked.connect(self._on_save)
        self.btn_close.clicked.connect(self.reject)

    def _kv(self, key: str, value_widget: QLabel) -> QWidget:
        w = QWidget(self)
        l = QVBoxLayout(w)
        l.setContentsMargins(0, 0, 12, 0)
        lbl_key = QLabel(f"{key}", w)
        lbl_key.setStyleSheet("font-weight: 600;")
        l.addWidget(lbl_key)
        l.addWidget(value_widget)
        return w

    def _load_data(self):
        if self.licitacion is not None:
            lic = self.licitacion
        else:
            try:
                lic = self.db.get_licitacion_by_id(int(self.licitacion_id))
            except Exception as e:
                QMessageBox.critical(self, "Error", f"No se pudo cargar la licitación ID {self.licitacion_id}.\n{e}")
                self.reject()
                return
            if not lic:
                QMessageBox.critical(self, "No encontrada", f"No existe la licitación ID {self.licitacion_id}.")
                self.reject()
                return
            self.licitacion = lic

        # Encabezado
        self.lbl_numero.setText(lic.numero_proceso or "")
        self.lbl_nombre.setText(lic.nombre_proceso or "")
        self.lbl_institucion.setText(lic.institucion or "")
        self.lbl_estado.setText(lic.estado or "")

        # Tabs: preparar datos dependientes
        empresas_participantes = [str(e) if hasattr(e, "__str__") else getattr(e, "nombre", "") for e in (lic.empresas_nuestras or [])]
        self.tab_lotes.participating_companies = [e for e in empresas_participantes if e]
        self.tab_lotes.load_lotes(list(lic.lotes or []))

        # Responsables: derivar desde documentos existentes o toma vacía
        responsables = sorted({getattr(d, "responsable", "") or "" for d in (lic.documentos_solicitados or [])})
        self.tab_docs.responsables = [r for r in responsables if r]
        self.tab_docs.load_documentos(list(lic.documentos_solicitados or []))

        self.tab_comp.load_oferentes(list(lic.oferentes_participantes or []))

    def _on_save(self):
        if not self.licitacion:
            return

        # Recolectar cambios desde tabs
        try:
            lotes: List[Lote] = self.tab_lotes.to_lotes()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudieron leer los Lotes.\n{e}")
            return

        try:
            documentos: List[Documento] = self.tab_docs.to_documentos()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudieron leer los Documentos.\n{e}")
            return

        try:
            oferentes: List[Oferente] = self.tab_comp.to_oferentes()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudieron leer los Competidores.\n{e}")
            return

        # Actualizar objeto licitación
        self.licitacion.lotes = lotes
        self.licitacion.documentos_solicitados = documentos
        self.licitacion.oferentes_participantes = oferentes

        # Persistir
        try:
            # Si tu adapter usa 'update_licitacion', cambia esta línea:
            res = self.db.save_licitacion(self.licitacion)  # type: ignore[attr-defined]
            if res is False:
                QMessageBox.critical(self, "Error", "La base de datos rechazó la operación de guardado.")
                return
            QMessageBox.information(self, "Guardado", "Licitación actualizada correctamente.")
            self.resultado = self.licitacion  # <-- Asigna resultado si todo fue bien
            self.accept()  # <-- Cierra el diálogo como aceptado
        except AttributeError:
            # Fallback a 'update_licitacion' si no existe save_licitacion
            try:
                self.db.update_licitacion(self.licitacion)  # type: ignore[attr-defined]
                QMessageBox.information(self, "Guardado", "Licitación actualizada correctamente.")
                self.resultado = self.licitacion  # <-- Asigna resultado si todo fue bien
                self.accept()  # <-- Cierra el diálogo como aceptado
            except Exception as e:
                QMessageBox.critical(self, "Error", f"No se pudo guardar la licitación.\n{e}")
                return
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo guardar la licitación.\n{e}")
            return