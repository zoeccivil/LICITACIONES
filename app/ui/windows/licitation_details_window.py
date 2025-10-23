from __future__ import annotations
from typing import Optional, List
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QWidget,
    QTabWidget,
    QFormLayout,
    QLineEdit,
    QLabel,
    QDialogButtonBox,
)
from app.core.models import Licitacion
from app.core.db_adapter import DatabaseAdapter
from app.ui.tabs.lotes_tab import TabLotes
from app.ui.tabs.competidores_tab import TabCompetidores
from app.ui.tabs.documentos_tab import TabDocumentos


class VentanaDetallesLicitacion(QDialog):
    """
    Ventana de detalles de una licitación.
    Tabs:
      - Generales
      - Lotes
      - Competidores
      - Documentos
    """
    def __init__(self, parent: QWidget, licitacion: Licitacion, db: Optional[DatabaseAdapter] = None):
        super().__init__(parent)
        self.setWindowTitle(f"Detalles de Licitación — {licitacion.numero_proceso or 'Nueva'}")
        self.resize(1000, 680)
        self.licitacion = licitacion
        self.db = db
        self.resultado: Optional[Licitacion] = None

        self._build_ui()
        self._load_from_model()

    def _get_empresas_for_ui(self) -> List[str]:
        # Preferir las empresas_nuestras de la licitación; si están vacías y hay DB, usar maestras
        empresas = [e.nombre for e in (self.licitacion.empresas_nuestras or [])]
        if not empresas and self.db:
            empresas = self.db.list_empresas_maestras()
        return empresas

    def _get_responsables_for_ui(self) -> List[str]:
        if self.db:
            resps = self.db.list_responsables_maestros()
            if resps:
                return resps
        # fallback: empresas_nuestras
        return self._get_empresas_for_ui()

    def _get_categorias_for_ui(self) -> List[str]:
        if self.db:
            cats = self.db.list_categorias()
            if cats:
                return cats
        return []  # TabDocumentos tiene defaults si viene vacío

    def _build_ui(self):
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget(self)
        layout.addWidget(self.tabs)

        # Tab Generales (simple por ahora)
        self.tab_generales = QWidget(self)
        form = QFormLayout(self.tab_generales)
        self.ed_numero = QLineEdit(self.tab_generales)
        self.ed_nombre = QLineEdit(self.tab_generales)
        self.ed_institucion = QLineEdit(self.tab_generales)
        form.addRow("Número de Proceso:", self.ed_numero)
        form.addRow("Nombre del Proceso:", self.ed_nombre)
        form.addRow("Institución:", self.ed_institucion)
        self.tabs.addTab(self.tab_generales, "Generales")

        # Tab Lotes
        empresas = self._get_empresas_for_ui()
        self.tab_lotes = TabLotes(self, participating_companies=empresas)
        self.tabs.addTab(self.tab_lotes, "Lotes")

        # Tab Competidores
        self.tab_comp = TabCompetidores(self)
        self.tabs.addTab(self.tab_comp, "Competidores")

        # Tab Documentos
        responsables = self._get_responsables_for_ui()
        categorias = self._get_categorias_for_ui()
        self.tab_docs = TabDocumentos(self, responsables=responsables, categories=categorias)
        self.tabs.addTab(self.tab_docs, "Documentos")

        # Botonera
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Close,
            orientation=Qt.Orientation.Horizontal,
            parent=self,
        )
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_from_model(self):
        # Generales
        self.ed_numero.setText(self.licitacion.numero_proceso or "")
        self.ed_nombre.setText(self.licitacion.nombre_proceso or "")
        self.ed_institucion.setText(self.licitacion.institucion or "")

        # Lotes
        self.tab_lotes.load_lotes(self.licitacion.lotes or [])

        # Competidores
        self.tab_comp.load_oferentes(self.licitacion.oferentes_participantes or [])

        # Documentos
        self.tab_docs.load_documentos(self.licitacion.documentos_solicitados or [])

    def _on_save(self):
        # Guardar Generales
        self.licitacion.numero_proceso = self.ed_numero.text().strip()
        self.licitacion.nombre_proceso = self.ed_nombre.text().strip()
        self.licitacion.institucion = self.ed_institucion.text().strip()

        # Guardar Lotes
        self.licitacion.lotes = self.tab_lotes.to_lotes()

        # Guardar Competidores
        self.licitacion.oferentes_participantes = self.tab_comp.to_oferentes()

        # Guardar Documentos
        self.licitacion.documentos_solicitados = self.tab_docs.to_documentos()

        self.resultado = self.licitacion
        self.accept()