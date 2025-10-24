from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QListWidget, QPushButton,
    QLineEdit, QComboBox, QTableWidget, QTableWidgetItem, QSizePolicy, QWidget, QGroupBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QStyle
class AddLicitacionWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Agregar Nueva Licitación")
        self.setMinimumSize(1350, 720)
        self.setStyleSheet("background: #f8f8f8;")

        main = QVBoxLayout(self)
        main.setContentsMargins(12, 12, 12, 12)
        main.setSpacing(14)

        # -- Sección principal dividida horizontalmente --
        top = QHBoxLayout()
        top.setSpacing(12)

        # --- Panel A: Instituciones ---
        panelA = QGroupBox("A. Seleccione la Institución")
        panelA.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        vA = QVBoxLayout(panelA)
        self.institList = QListWidget()
        self.institList.setMinimumWidth(270)
        self.institList.setMaximumWidth(340)
        self.institList.setStyleSheet("background: #fafafa; border: 1px solid #e0e0e0;")
        vA.addWidget(self.institList, 10)

        self.institActual = QLabel("Actual: <b>NINGUNA</b>")
        self.institActual.setStyleSheet("color: #444; font-size: 13px;")
        vA.addWidget(self.institActual)
        self.btnAgregarInstit = QPushButton("Agregar")
        

        self.btnAgregarInstit.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogNewFolder))
        vA.addWidget(self.btnAgregarInstit, alignment=Qt.AlignmentFlag.AlignRight)

        top.addWidget(panelA, 1)

        # --- Panel B: Empresas ---
        panelB = QGroupBox("B. Seleccione su(s) Empresa(s)")
        panelB.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        vB = QVBoxLayout(panelB)
        self.empresasLabel = QLabel('<span style="color:#C62828">Ninguna seleccionada</span>')
        self.empresasLabel.setMinimumHeight(50)
        vB.addWidget(self.empresasLabel)
        self.btnSeleccionarEmpresa = QPushButton("Seleccionar Empresas...")
        vB.addWidget(self.btnSeleccionarEmpresa, alignment=Qt.AlignmentFlag.AlignLeft)
        top.addWidget(panelB, 2)

        # --- Panel C: Detalles ---
        panelC = QGroupBox("C. Complete los Detalles")
        panelC.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        gridC = QGridLayout(panelC)
        gridC.setColumnStretch(1, 2)
        gridC.setHorizontalSpacing(14)
        gridC.setVerticalSpacing(12)

        self.txtNombre = QLineEdit()
        self.txtCodigo = QLineEdit()
        self.comboKit = QComboBox()
        self.comboKit.addItem("No aplicar")  # Puedes cargar más dinámicamente

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
        self.lotesTable.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        vD.addWidget(self.lotesTable, 10)

        btnsLotes = QHBoxLayout()
        self.btnAgregarLote = QPushButton("Agregar Lote")
        self.btnEditarLote = QPushButton("Editar Lote")
        self.btnEliminarLote = QPushButton("Eliminar Lote")
        btnsLotes.addWidget(self.btnAgregarLote)
        btnsLotes.addWidget(self.btnEditarLote)
        btnsLotes.addWidget(self.btnEliminarLote)
        btnsLotes.addStretch(1)
        vD.addLayout(btnsLotes)

        main.addWidget(panelD, 5)

        # --- Botón Guardar ---
        self.btnGuardar = QPushButton("Guardar Licitación")
        self.btnGuardar.setMinimumWidth(180)
        self.btnGuardar.setFixedHeight(36)
        main.addWidget(self.btnGuardar, alignment=Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom)