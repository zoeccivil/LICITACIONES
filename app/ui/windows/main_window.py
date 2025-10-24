from __future__ import annotations

import os
from PyQt6.QtCore import Qt, QSettings, QByteArray
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
    QApplication,
    QDialog
)
from app.core.models import Licitacion, Empresa, Lote
from app.core.db_adapter import DatabaseAdapter
from app.ui.windows.licitation_details_window import VentanaDetallesLicitacion
from app.ui.dialogs.select_licitacion_dialog import DialogoSeleccionarLicitacion
from app.ui.views.dashboard_widget import DashboardWidget  # Usa el Dashboard que se alimenta desde DB
from app.ui.theme.light_theme import apply_light_theme
# ejemplo para probar desde tu dashboard o main
from app.ui.windows.add_licitacion_window import AddLicitacionWindow

class MainWindow(QMainWindow):
    """
    Ventana principal:
    - Tema claro (Fusion) aplicado a nivel de aplicación.
    - Menú Archivo/Ver/Reportes/Herramientas.
    - Toolbar con accesos rápidos.
    - Bienvenida por defecto; Dashboard cuando se abre una DB.
    - Acciones: abrir DB, crear/abrir licitación, demo de detalles.
    - Persistencia de geometría y último tab interno a cargo de los widgets (Dashboard maneja sus QSettings).
    """
    def __init__(self, parent=None):
        super().__init__(parent)

        # Tema claro antes de construir widgets complejos
        app = QApplication.instance()
        if app is not None:
            apply_light_theme(app)

        # Estado
        self.db: DatabaseAdapter | None = None
        self.dashboard: DashboardWidget | None = None
        self._settings = QSettings("Zoeccivil", "Licitaciones")

        # UI
        self._create_menubar()
        self._create_toolbar()
        self.setStatusBar(QStatusBar(self))
        self._build_welcome()

        self.setWindowTitle("Licitaciones - Dashboard")
        self.resize(1200, 760)

        # Acciones deshabilitadas hasta abrir DB
        self._update_actions_enabled(False)

        # Restaurar geometría de ventana si existe
        self._restore_geometry()

    # ---------------------- Construcción UI ----------------------
    def _build_welcome(self):
        self.welcome = QWidget(self)
        layout = QVBoxLayout(self.welcome)
        lbl = QLabel("Bienvenido. Esta es la base PyQt6.\nUsa el menú o la barra para abrir diálogos.")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl)
        self.setCentralWidget(self.welcome)

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
        self.act_dashboard = m_ver.addAction("Licitaciones (Dashboard)", self._ver_dashboard)
        m_ver.addAction("Detalles de Licitación (Demo)...", self._accion_detalles_licitacion_demo)

        m_reportes = menubar.addMenu("Reportes")
        m_reportes.addAction("Reporte Licitación (próximo)...", self._no_implementado)

        m_herr = menubar.addMenu("Herramientas")
        m_herr.addAction("Sanity Check (próximo)...", self._no_implementado)

    def _create_toolbar(self):
        tb = QToolBar("Acciones", self)
        self.addToolBar(tb)

        btn_dashboard = QPushButton("Licitaciones", self)
        btn_dashboard.clicked.connect(self._ver_dashboard)
        tb.addWidget(btn_dashboard)

        btn_nueva = QPushButton("Nueva Licitación…", self)
        btn_nueva.clicked.connect(self._accion_nueva_licitacion)
        tb.addWidget(btn_nueva)

        btn_abrir = QPushButton("Abrir Licitación…", self)
        btn_abrir.clicked.connect(self._accion_abrir_licitacion)
        tb.addWidget(btn_abrir)

    def _update_actions_enabled(self, enabled: bool):
        self.act_nueva.setEnabled(enabled)
        self.act_abrir.setEnabled(enabled)
        self.act_dashboard.setEnabled(enabled)

    # ---------------------- Acciones ----------------------
    def _accion_abrir_db(self):
        last_dir = str(self._settings.value("MainWindow/last_db_dir") or "")
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar Base de Datos",
            directory=last_dir if last_dir else "",
            filter="Database (*.db *.sqlite *.sqlite3)"
        )
        if not path:
            return
        try:
            # Guardar la última carpeta usada correctamente (no usar QFileDialog.directory)
            self._settings.setValue("MainWindow/last_db_dir", os.path.dirname(path))

            if self.db:
                try:
                    self.db.close()
                except Exception:
                    pass

            self.db = DatabaseAdapter(path)
            self.db.open()
            schema = getattr(self.db, "schema", "normalized")
            self.statusBar().showMessage(f"DB abierta: {path} — esquema: {schema}", 8000)
            self._update_actions_enabled(True)
            # Mostrar dashboard al abrir DB
            self._ver_dashboard()
        except Exception as e:
            self.db = None
            self._update_actions_enabled(False)
            QMessageBox.critical(self, "Error", f"No se pudo abrir la DB.\n{e}")

    def _ver_dashboard(self):
        if not self.db:
            QMessageBox.information(self, "DB", "Abre una base de datos primero.")
            return
        if self.dashboard is None:
            # DashboardWidget debe encargarse de cargar datos desde la DB y refrescar UI
            self.dashboard = DashboardWidget(self, db=self.db)
        else:
            try:
                self.dashboard.reload_data()
            except Exception:
                # Fallback: reconstruir dashboard si algo falló en recarga
                self.dashboard.setParent(None)
                self.dashboard.deleteLater()
                self.dashboard = DashboardWidget(self, db=self.db)
        self.setCentralWidget(self.dashboard)

    def _accion_nueva_licitacion(self):
        if not self.db:
            QMessageBox.information(self, "DB", "Abre una base de datos primero.")
            return

        # Crear objeto licitación vacío
        lic = Licitacion(
            nombre_proceso="",
            numero_proceso="",
            institucion="",
            empresas_nuestras=[],
            lotes=[],
            documentos_solicitados=[],
            oferentes_participantes=[]
        )

        # Abrir el diálogo en modo creación
        dlg = VentanaDetallesLicitacion(self, lic, db=self.db)
        res = dlg.exec()
        if res == QDialog.DialogCode.Accepted and dlg.resultado is not None:
            try:
                lic_guardada = dlg.resultado
                new_id = self.db.save_licitacion(lic_guardada)
                QMessageBox.information(self, "Guardado", f"Licitación guardada con ID {new_id}.")
                if self.dashboard:
                    self.dashboard.reload_data()
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
                    if self.dashboard:
                        self.dashboard.reload_data()
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
            QMessageBox.information(self, "Demo", "Cerraste la ventana de detalles (modo demo).")

    def _no_implementado(self):
        QMessageBox.information(self, "Próximo", "Esta función se migrará en los siguientes pasos.")

    # ---------------------- Persistencia de geometría ----------------------
    def _restore_geometry(self):
        geom = self._settings.value("MainWindow/geometry")
        if isinstance(geom, QByteArray):
            try:
                self.restoreGeometry(geom)
            except Exception:
                pass

    def closeEvent(self, event):
        try:
            self._settings.setValue("MainWindow/geometry", self.saveGeometry())
        finally:
            super().closeEvent(event)