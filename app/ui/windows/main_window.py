from __future__ import annotations
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QLabel,
    QMenuBar,
    QStatusBar,
    QFileDialog,
    QMessageBox,
    QToolBar,
    QPushButton,
)
from app.core.models import Licitacion, Empresa, Lote
from app.core.db_adapter import DatabaseAdapter
from app.ui.windows.licitation_details_window import VentanaDetallesLicitacion
from app.ui.dialogs.select_licitacion_dialog import DialogoSeleccionarLicitacion


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gestor de Licitaciones (PyQt6) — Base")
        self.resize(1100, 700)

        self.db: DatabaseAdapter | None = None

        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.addWidget(QLabel("Bienvenido. Esta es la base PyQt6.\nUsa el menú o la barra para abrir diálogos.", alignment=Qt.AlignmentFlag.AlignCenter))
        self.setCentralWidget(central)

        self._create_menubar()
        self._create_toolbar()
        self.setStatusBar(QStatusBar(self))
        self._update_actions_enabled(False)

    def _create_menubar(self):
        menubar = QMenuBar(self)
        self.setMenuBar(menubar)

        m_archivo = menubar.addMenu("Archivo")
        m_archivo.addAction("Abrir DB...", self._accion_abrir_db)
        m_archivo.addSeparator()
        m_archivo.addAction("Salir", self.close)

        self.m_licit = menubar.addMenu("Licitaciones")
        self.act_nueva = self.m_licit.addAction("Nueva...", self._accion_nueva_licitacion)
        self.act_abrir = self.m_licit.addAction("Abrir...", self._accion_abrir_licitacion)

        m_ver = menubar.addMenu("Ver")
        m_ver.addAction("Detalles de Licitación (Demo)...", self._accion_detalles_licitacion_demo)

        m_reportes = menubar.addMenu("Reportes")
        m_reportes.addAction("Reporte Licitación (próximo)...", self._no_implementado)

        m_herr = menubar.addMenu("Herramientas")
        m_herr.addAction("Sanity Check (próximo)...", self._no_implementado)

    def _create_toolbar(self):
        tb = QToolBar("Acciones", self)
        self.addToolBar(tb)

        btn_detalles = QPushButton("Detalles Licitación…", self)
        btn_detalles.clicked.connect(self._accion_detalles_licitacion_demo)
        tb.addWidget(btn_detalles)

        btn_nueva = QPushButton("Nueva Licitación…", self)
        btn_nueva.clicked.connect(self._accion_nueva_licitacion)
        tb.addWidget(btn_nueva)

        btn_abrir = QPushButton("Abrir Licitación…", self)
        btn_abrir.clicked.connect(self._accion_abrir_licitacion)
        tb.addWidget(btn_abrir)

    def _update_actions_enabled(self, enabled: bool):
        self.act_nueva.setEnabled(enabled)
        self.act_abrir.setEnabled(enabled)

    def _accion_abrir_db(self):
        path, _ = QFileDialog.getOpenFileName(self, "Seleccionar Base de Datos", filter="Database (*.db *.sqlite *.sqlite3)")
        if not path:
            return
        try:
            self.db = DatabaseAdapter(path)
            self.db.open()
            schema = getattr(self.db, "schema", "normalized")
            self.statusBar().showMessage(f"DB abierta: {path} — esquema: {schema}", 8000)
            self._update_actions_enabled(True)
        except Exception as e:
            self.db = None
            self._update_actions_enabled(False)
            QMessageBox.critical(self, "Error", f"No se pudo abrir la DB.\n{e}")

    def _accion_nueva_licitacion(self):
        if not self.db:
            QMessageBox.information(self, "DB", "Abre una base de datos primero.")
            return
        lic = Licitacion(
            nombre_proceso="",
            numero_proceso="",
            institucion="",
            empresas_nuestras=[],
        )
        dlg = VentanaDetallesLicitacion(self, lic, db=self.db)
        if dlg.resultado is not None:
            try:
                lic_guardada = dlg.resultado
                new_id = self.db.save_licitacion(lic_guardada)
                QMessageBox.information(self, "Guardado", f"Licitación guardada con ID {new_id}.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"No se pudo guardar.\n{e}")

    def _accion_abrir_licitacion(self):
        if not self.db:
            QMessageBox.information(self, "DB", "Abre una base de datos primero.")
            return
        sel = DialogoSeleccionarLicitacion(self, self.db)
        if sel.exec() == sel.DialogCode.Accepted and sel.selected_id is not None:
            try:
                lic = self.db.load_licitacion_by_id(sel.selected_id)
                if not lic:
                    QMessageBox.warning(self, "Abrir", "No se encontró la licitación.")
                    return
                dlg = VentanaDetallesLicitacion(self, lic, db=self.db)
                if dlg.resultado is not None:
                    self.db.save_licitacion(dlg.resultado)
                    QMessageBox.information(self, "Guardado", "Licitación actualizada.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Fallo al abrir/guardar.\n{e}")

    def _accion_detalles_licitacion_demo(self):
        lic = Licitacion(
            nombre_proceso="Rehabilitación Vial - Zona Norte",
            numero_proceso="LPN-2025-0001",
            institucion="MOPC",
            empresas_nuestras=[Empresa("ZOEC CIVIL"), Empresa("BARNHOUSE")],
            lotes=[
                Lote(numero="1", nombre="Tramo A", monto_base=12000000, monto_base_personal=11800000, monto_ofertado=11950000, empresa_nuestra="ZOEC CIVIL"),
                Lote(numero="2", nombre="Tramo B", monto_base=9000000, monto_base_personal=0, monto_ofertado=8800000, empresa_nuestra="BARNHOUSE"),
            ],
        )
        dlg = VentanaDetallesLicitacion(self, lic, db=self.db)
        if dlg.resultado is not None:
            lic_actualizada = dlg.resultado
            resumen = (
                f"Número: {lic_actualizada.numero_proceso}\n"
                f"Nombre: {lic_actualizada.nombre_proceso}\n"
                f"Institución: {lic_actualizada.institucion}\n"
                f"Lotes: {len(lic_actualizada.lotes)} — Oferta Total: {lic_actualizada.get_oferta_total():,.2f}"
            )
            QMessageBox.information(self, "Licitación guardada (Demo)", resumen)

    def _no_implementado(self):
        QMessageBox.information(self, "Próximo", "Esta función se migrará en los siguientes pasos.")