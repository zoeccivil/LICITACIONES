from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QPushButton, QLabel, QComboBox, 
    QLineEdit, QTableWidget, QTableWidgetItem, QListWidget, QWidget, QGridLayout,
    QMessageBox
)

class VentanaAgregarLicitacion(QDialog):
    def __init__(self, parent, lista_empresas, lista_instituciones, kits_disponibles, callback_guardar):
        super().__init__(parent)
        self.parent = parent
        self.lista_empresas = lista_empresas
        self.lista_instituciones = lista_instituciones
        self.kits_disponibles = kits_disponibles
        self.callback_guardar = callback_guardar

        self.institucion_seleccionada = None
        self.empresas_seleccionadas = []
        self.lotes_temp = []

        self.setWindowTitle("Agregar Nueva Licitación")
        self.setMinimumSize(1350, 720)
        self.setStyleSheet("background: #f8f8f8;")

        main = QVBoxLayout(self)
        main.setContentsMargins(12, 12, 12, 12)
        main.setSpacing(14)

        # Sección principal horizontal (izquierda: institución/empresa; derecha: detalles/lotes)
        top = QHBoxLayout()
        top.setSpacing(12)

        # --- Panel A: Instituciones ---
        panelA = QGroupBox("A. Seleccione la Institución")
        vA = QVBoxLayout(panelA)
        self.institList = QListWidget()
        self.institList.setMinimumWidth(270)
        self.institList.setMaximumWidth(340)
        self.institList.addItems([i['nombre'] for i in self.lista_instituciones])
        self.institList.setStyleSheet("background: #fafafa; border: 1px solid #e0e0e0;")
        self.institList.itemSelectionChanged.connect(self.confirmar_seleccion_institucion)
        vA.addWidget(self.institList, 10)

        self.institActual = QLabel("Actual: <b>NINGUNA</b>")
        self.institActual.setStyleSheet("color: #444; font-size: 13px;")
        vA.addWidget(self.institActual)
        btnAgregarInstit = QPushButton("Agregar")
        btnAgregarInstit.clicked.connect(self._agregar_nueva_institucion)
        vA.addWidget(btnAgregarInstit, alignment=Qt.AlignmentFlag.AlignRight)
        top.addWidget(panelA, 1)

        # --- Panel B: Empresas ---
        panelB = QGroupBox("B. Seleccione su(s) Empresa(s)")
        vB = QVBoxLayout(panelB)
        self.empresasLabel = QLabel('<span style="color:#C62828">Ninguna seleccionada</span>')
        self.empresasLabel.setMinimumHeight(50)
        vB.addWidget(self.empresasLabel)
        btnSeleccionarEmpresa = QPushButton("Seleccionar Empresas...")
        btnSeleccionarEmpresa.clicked.connect(self._abrir_selector_empresas_para_agregar)
        vB.addWidget(btnSeleccionarEmpresa, alignment=Qt.AlignmentFlag.AlignLeft)
        top.addWidget(panelB, 2)

        # --- Panel C: Detalles ---
        panelC = QGroupBox("C. Complete los Detalles")
        gridC = QGridLayout(panelC)
        gridC.setColumnStretch(1, 2)
        gridC.setHorizontalSpacing(14)
        gridC.setVerticalSpacing(12)

        self.txtNombre = QLineEdit()
        self.txtCodigo = QLineEdit()
        self.comboKit = QComboBox()
        self.comboKit.addItem(" (Ninguno) ")
        for kit_id, kit_nombre in self.kits_disponibles:
            self.comboKit.addItem(kit_nombre)

        gridC.addWidget(QLabel("Nombre de la Licitación:"), 0, 0)
        gridC.addWidget(self.txtNombre, 0, 1)
        gridC.addWidget(QLabel("Código del Proceso:"), 1, 0)
        gridC.addWidget(self.txtCodigo, 1, 1)
        gridC.addWidget(QLabel("Aplicar Kit de Requisitos:"), 2, 0)
        gridC.addWidget(self.comboKit, 2, 1)
        top.addWidget(panelC, 3)

        main.addLayout(top, 3)

        # --- Panel D: Lotes ---
        panelD = QGroupBox("D. Lotes del Proceso")
        vD = QVBoxLayout(panelD)
        self.lotesTable = QTableWidget(0, 4)
        self.lotesTable.setHorizontalHeaderLabels(["N°", "Nombre Lote", "Monto Base", "Nuestra Oferta"])
        self.lotesTable.setSizePolicy(QWidget.SizePolicy.Policy.Expanding, QWidget.SizePolicy.Policy.Expanding)
        vD.addWidget(self.lotesTable, 10)

        btnsLotes = QHBoxLayout()
        btnAgregarLote = QPushButton("Agregar Lote")
        btnEditarLote = QPushButton("Editar Lote")
        btnEliminarLote = QPushButton("Eliminar Lote")
        btnAgregarLote.clicked.connect(self.agregar_lote)
        btnEditarLote.clicked.connect(self.editar_lote)
        btnEliminarLote.clicked.connect(self.eliminar_lote)
        btnsLotes.addWidget(btnAgregarLote)
        btnsLotes.addWidget(btnEditarLote)
        btnsLotes.addWidget(btnEliminarLote)
        btnsLotes.addStretch(1)
        vD.addLayout(btnsLotes)

        main.addWidget(panelD, 5)

        # --- Botón Guardar ---
        btnGuardar = QPushButton("Guardar Licitación")
        btnGuardar.setMinimumWidth(180)
        btnGuardar.setFixedHeight(36)
        btnGuardar.clicked.connect(self.guardar_licitacion)
        main.addWidget(btnGuardar, alignment=Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom)

    def _agregar_nueva_institucion(self):
        # Aquí deberías abrir tu diálogo de gestión de entidades.
        # Demo: simplemente agregamos una institución nueva.
        nueva_institucion = {"nombre": "NUEVA INSTITUCIÓN"}
        self.lista_instituciones.append(nueva_institucion)
        self.institList.addItem(nueva_institucion["nombre"])

    def _abrir_selector_empresas_para_agregar(self):
        # Debes abrir tu diálogo de selección de empresas.
        # Demo: Seleccionamos las dos primeras empresas.
        if self.lista_empresas:
            self.empresas_seleccionadas = [e['nombre'] for e in self.lista_empresas[:2]]
            self._actualizar_display_empresas()

    def _actualizar_display_empresas(self):
        if not self.empresas_seleccionadas:
            self.empresasLabel.setText('<span style="color:#C62828">Ninguna seleccionada</span>')
        else:
            texto = ", ".join(sorted(self.empresas_seleccionadas))
            self.empresasLabel.setText(texto)

    def confirmar_seleccion_institucion(self):
        items = self.institList.selectedItems()
        if not items:
            self.institucion_seleccionada = None
            self.institActual.setText("Actual: <b>NINGUNA</b>")
        else:
            self.institucion_seleccionada = items[0].text()
            self.institActual.setText(f"Actual: <b>{self.institucion_seleccionada}</b>")

    def agregar_lote(self):
        # Aquí deberías abrir tu diálogo para agregar lote.
        # Demo: agregamos un lote "dummy".
        numero = str(len(self.lotes_temp) + 1)
        nombre = f"Lote {numero}"
        monto_base = 1000000 * len(self.lotes_temp) + 500000
        monto_ofertado = monto_base - 100000
        lote = [numero, nombre, monto_base, monto_ofertado]
        self.lotes_temp.append(lote)
        self._actualizar_lotes_table()

    def editar_lote(self):
        row = self.lotesTable.currentRow()
        if row < 0 or row >= len(self.lotes_temp):
            QMessageBox.warning(self, "Sin Selección", "Selecciona un lote para editar.")
            return
        # Demo: Edita el nombre del lote
        self.lotes_temp[row][1] += " (editado)"
        self._actualizar_lotes_table()

    def eliminar_lote(self):
        row = self.lotesTable.currentRow()
        if row < 0 or row >= len(self.lotes_temp):
            QMessageBox.warning(self, "Sin Selección", "Selecciona un lote para eliminar.")
            return
        self.lotes_temp.pop(row)
        self._actualizar_lotes_table()

    def _actualizar_lotes_table(self):
        self.lotesTable.setRowCount(0)
        for lote in self.lotes_temp:
            row = self.lotesTable.rowCount()
            self.lotesTable.insertRow(row)
            for col, val in enumerate(lote):
                item = QTableWidgetItem(str(val))
                self.lotesTable.setItem(row, col, item)

    def guardar_licitacion(self):
        # Validaciones
        if not self.institucion_seleccionada:
            QMessageBox.critical(self, "Falta Institución", "Debe seleccionar una institución.")
            return
        if not self.empresas_seleccionadas:
            QMessageBox.critical(self, "Falta Empresa", "Debe seleccionar al menos una empresa.")
            return
        if not self.txtNombre.text().strip() or not self.txtCodigo.text().strip():
            QMessageBox.critical(self, "Faltan datos", "Nombre y Código no pueden estar vacíos.")
            return
        if not self.lotes_temp:
            QMessageBox.critical(self, "Falta lotes", "Debe agregar al menos un lote.")
            return

        empresas_data = [{'nombre': nombre} for nombre in self.empresas_seleccionadas]
        lotes_data = []
        for lote in self.lotes_temp:
            lotes_data.append({
                "numero": lote[0],
                "nombre": lote[1],
                "monto_base": lote[2],
                "monto_ofertado": lote[3]
            })

        datos = {
            "nombre_proceso": self.txtNombre.text().strip(),
            "numero_proceso": self.txtCodigo.text().strip(),
            "institucion": self.institucion_seleccionada,
            "empresas_nuestras": empresas_data,
            "lotes": lotes_data,
            "documentos_solicitados": []
        }
        # Manejo del kit (demo, sin lógica real)
        kit_seleccionado = self.comboKit.currentText()
        if kit_seleccionado and kit_seleccionado != " (Ninguno) ":
            # Aquí deberías cargar los documentos del kit.
            pass

        # Llama el callback con el objeto Licitacion
        if self.callback_guardar:
            self.callback_guardar(datos)
        QMessageBox.information(self, "Éxito", "Licitación agregada correctamente.")
        self.accept()