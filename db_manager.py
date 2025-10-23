import sqlite3
import json
import logging
import datetime


def debug_perfil_empresa(self, nombre_empresa: str):
    tabla_en, col_nombre = self._resolver_tabla_y_columna_empresas_nuestras()
    col_num_lote, col_monto_lote = self._resolver_cols_lotes()
    kpis, hist = self.obtener_resumen_y_historial_empresa(nombre_empresa)
    return {
        "tabla_empresas_nuestras": tabla_en,
        "col_nombre_empresa": col_nombre,
        "col_lote_numero": col_num_lote,
        "col_lote_monto": col_monto_lote,
        "kpis": kpis,
        "historial_count": len(hist)
    }

class ConcurrencyException(Exception):
    """Excepción personalizada para errores de concurrencia."""
    pass

class DatabaseManager:
    """
    Gestiona todas las interacciones con la base de datos SQLite
    utilizando una estructura relacional de múltiples tablas.
    """
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path)
        self.conn.execute("PRAGMA foreign_keys = 1")
        self.cursor = self.conn.cursor()
        self._actualizar_schema()
        self.create_tables()
        self.setup_fts()  # Inicializa/asegura los índices FTS
        self.cursor.execute("PRAGMA foreign_keys = ON")  # recomendado
        self._ensure_ganadores_schema()                  # <- ¡IMPRESCINDIBLE!


        

    def _ensure_ganadores_schema(self):
        # Esta función ahora solo crea la tabla con la clave primaria correcta y completa.
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS licitacion_ganadores_lote (
                licitacion_id   INTEGER NOT NULL,
                lote_numero     TEXT    NOT NULL,
                ganador_nombre  TEXT    NOT NULL,
                empresa_nuestra TEXT,
                -- LA CLAVE PRIMARIA CORRECTA INCLUYE AL GANADOR PARA PERMITIR VARIOS GANADORES
                PRIMARY KEY (licitacion_id, lote_numero, ganador_nombre),
                FOREIGN KEY (licitacion_id) REFERENCES licitaciones (id) ON DELETE CASCADE,
                FOREIGN KEY (empresa_nuestra) REFERENCES empresas_maestras(nombre)
            )
        ''')
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_ganadores_licitacion ON licitacion_ganadores_lote(licitacion_id)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_ganadores_nombre ON licitacion_ganadores_lote(ganador_nombre)")
        self.conn.commit()

    def _table_exists(self, name: str) -> bool:
        cur = self.conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
            (name,)
        )
        return cur.fetchone() is not None

    def _actualizar_schema(self):
        """
        Añade columnas, repara tablas y migra la estructura de la BD de forma robusta.
        Se ejecuta una vez al iniciar la aplicación.
        """
        cursor = self.conn.cursor()

        def ejecutar_cambio(descripcion, sql_alter):
            try:
                print(f"Verificando schema: {descripcion}...")
                cursor.execute(sql_alter)
                self.conn.commit()
                print(f" -> OK: {descripcion} aplicado.")
            except sqlite3.OperationalError as e:
                if "duplicate column name" in str(e) or "already exists" in str(e):
                    print(f" -> OK: {descripcion} ya existía.")
                else:
                    raise e
            except Exception as e:
                print(f"Error aplicando '{descripcion}': {e}")
                self.conn.rollback()
                raise e

        # --- INICIO DE CORRECCIÓN DEFINITIVA ---
        # Este bloque ahora maneja la migración de forma más segura y aislada.
        try:
            cursor.execute("PRAGMA table_info(documentos_maestros)")
            columnas_maestros = {info[1] for info in cursor.fetchall()}
            
            if 'empresa_nombre' in columnas_maestros:
                print("Detectada estructura antigua de plantillas. Iniciando migración a modelo global...")
                
                # La transacción ahora envuelve todo el bloque de forma segura
                self.conn.execute('BEGIN IMMEDIATE TRANSACTION')
                try:
                    cursor.execute("DROP TRIGGER IF EXISTS documentos_maestros_after_insert;")
                    cursor.execute("DROP TRIGGER IF EXISTS documentos_maestros_after_update;")
                    cursor.execute("DROP TRIGGER IF EXISTS documentos_maestros_after_delete;")

                    cursor.execute("ALTER TABLE documentos_maestros RENAME TO documentos_maestros_old")
                    cursor.execute('''
                        CREATE TABLE documentos_maestros (
                            id INTEGER PRIMARY KEY AUTOINCREMENT, codigo TEXT UNIQUE NOT NULL,
                            nombre TEXT, categoria TEXT, comentario TEXT, ruta_archivo TEXT
                        )
                    ''')
                    cursor.execute('''
                        INSERT OR IGNORE INTO documentos_maestros (codigo, nombre, categoria, comentario, ruta_archivo)
                        SELECT codigo, nombre, categoria, comentario, ruta_archivo FROM (
                            SELECT *, ROW_NUMBER() OVER(PARTITION BY codigo ORDER BY id) as rn
                            FROM documentos_maestros_old
                        ) WHERE rn = 1
                    ''')
                    cursor.execute("DROP TABLE documentos_maestros_old")
                    self.conn.commit()
                    print(" -> MIGRACIÓN COMPLETADA CON ÉXITO.")
                except Exception as migration_error:
                    print(f" -> ERROR DURANTE MIGRACIÓN: {migration_error}. Revirtiendo cambios...")
                    self.conn.rollback()
                    raise migration_error

        except Exception as e:
            # Si la tabla documentos_maestros no existe, no es un error, es una BD nueva.
            if "no such table" not in str(e):
                print(f"Error verificando schema para migración: {e}")
        # --- FIN DE CORRECCIÓN DEFINITIVA ---
        
        # --- 2. VERIFICACIÓN DE OTRAS COLUMNAS (sin cambios) ---
        ejecutar_cambio("Añadir rpe a empresas maestras", 'ALTER TABLE empresas_maestras ADD COLUMN rpe TEXT')
        ejecutar_cambio("Añadir representante a empresas maestras", 'ALTER TABLE empresas_maestras ADD COLUMN representante TEXT')
        ejecutar_cambio("Añadir cargo_representante a empresas maestras", 'ALTER TABLE empresas_maestras ADD COLUMN cargo_representante TEXT')
        
        ejecutar_cambio("Añadir bnb_score a licitaciones", 'ALTER TABLE licitaciones ADD COLUMN bnb_score REAL DEFAULT -1.0')
        ejecutar_cambio("Añadir last_modified a licitaciones", "ALTER TABLE licitaciones ADD COLUMN last_modified TEXT")
        ejecutar_cambio("Añadir parametros_evaluacion a licitaciones", "ALTER TABLE licitaciones ADD COLUMN parametros_evaluacion TEXT")
        
        ejecutar_cambio("Añadir obligatorio a documentos", 'ALTER TABLE documentos ADD COLUMN obligatorio BOOLEAN DEFAULT 0')
        ejecutar_cambio("Añadir requiere_subsanacion a documentos", 'ALTER TABLE documentos ADD COLUMN requiere_subsanacion BOOLEAN DEFAULT 0')
        ejecutar_cambio("Añadir orden_pliego a documentos", 'ALTER TABLE documentos ADD COLUMN orden_pliego INTEGER')
        
        ejecutar_cambio("Añadir plazo_entrega a ofertas", 'ALTER TABLE ofertas_lote_oferentes ADD COLUMN plazo_entrega INTEGER DEFAULT 0')
        ejecutar_cambio("Añadir garantia_meses a ofertas", 'ALTER TABLE ofertas_lote_oferentes ADD COLUMN garantia_meses INTEGER DEFAULT 0')
        
        ejecutar_cambio("Añadir rpe a competidores", 'ALTER TABLE competidores_maestros ADD COLUMN rpe TEXT')
        ejecutar_cambio("Añadir representante a competidores", 'ALTER TABLE competidores_maestros ADD COLUMN representante TEXT')

        # --- 3. REPARACIÓN DE LA TABLA 'kit_items' (sin cambios) ---
        try:
            cursor.execute("PRAGMA table_info(kit_items)")
            columnas_kit_items = cursor.fetchall()
            if columnas_kit_items and not any(col[5] for col in columnas_kit_items):
                print("Reparando la tabla 'kit_items' para añadir Primary Key y eliminar duplicados...")
                self.conn.execute('BEGIN TRANSACTION')
                cursor.execute("ALTER TABLE kit_items RENAME TO kit_items_old")
                cursor.execute('''
                    CREATE TABLE kit_items (
                        kit_id INTEGER, documento_maestro_id INTEGER,
                        PRIMARY KEY (kit_id, documento_maestro_id),
                        FOREIGN KEY (kit_id) REFERENCES kits_de_requisitos (id) ON DELETE CASCADE,
                        FOREIGN KEY (documento_maestro_id) REFERENCES documentos_maestros (id) ON DELETE CASCADE
                    )
                ''')
                cursor.execute("INSERT OR IGNORE INTO kit_items (kit_id, documento_maestro_id) SELECT DISTINCT kit_id, documento_maestro_id FROM kit_items_old")
                cursor.execute("DROP TABLE kit_items_old")
                self.conn.commit()
        except sqlite3.OperationalError as e:
            if "no such table" not in str(e):
                self.conn.rollback()
                raise e
        except Exception as e:
            print(f"Error reparando 'kit_items': {e}")
            self.conn.rollback()
            raise
 
    def create_tables(self):
        """Crea/migra todas las tablas necesarias de forma segura (idempotente)."""

        # === BASE ===
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS licitaciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre_proceso TEXT NOT NULL,
                numero_proceso TEXT UNIQUE NOT NULL,
                institucion TEXT,
                empresa_nuestra TEXT,
                estado TEXT,
                fase_A_superada BOOLEAN,
                fase_B_superada BOOLEAN,
                adjudicada BOOLEAN,
                adjudicada_a TEXT,
                motivo_descalificacion TEXT,
                fecha_creacion TEXT,
                cronograma TEXT,
                docs_completos_manual BOOLEAN DEFAULT 0,
                bnb_score REAL DEFAULT -1.0,
                last_modified TEXT DEFAULT (strftime('%Y-%m-%d %H:%M:%f', 'now'))
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS licitacion_empresas_nuestras (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                licitacion_id INTEGER NOT NULL,
                empresa_nombre TEXT NOT NULL,
                UNIQUE(licitacion_id, empresa_nombre),
                FOREIGN KEY (licitacion_id) REFERENCES licitaciones(id) ON DELETE CASCADE,
                FOREIGN KEY (empresa_nombre) REFERENCES empresas_maestras(nombre) ON DELETE CASCADE
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS lotes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                licitacion_id INTEGER,
                numero TEXT,
                nombre TEXT,
                monto_base REAL,
                monto_base_personal REAL,
                monto_ofertado REAL,
                participamos BOOLEAN,
                fase_A_superada BOOLEAN,
                empresa_nuestra TEXT,
                FOREIGN KEY (licitacion_id) REFERENCES licitaciones (id) ON DELETE CASCADE
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS documentos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                licitacion_id INTEGER,
                codigo TEXT,
                nombre TEXT,
                categoria TEXT,
                comentario TEXT,
                presentado BOOLEAN,
                subsanable TEXT,
                ruta_archivo TEXT,
                responsable TEXT,
                revisado BOOLEAN DEFAULT 0,
                obligatorio BOOLEAN DEFAULT 0,
                FOREIGN KEY (licitacion_id) REFERENCES licitaciones (id) ON DELETE CASCADE
            )
        ''')
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS descalificaciones_fase_a (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                licitacion_id INTEGER NOT NULL,
                participante_nombre TEXT NOT NULL,
                documento_id INTEGER NOT NULL,
                comentario TEXT,
                es_nuestro BOOLEAN DEFAULT 0,
                FOREIGN KEY (licitacion_id) REFERENCES licitaciones (id) ON DELETE CASCADE,
                FOREIGN KEY (documento_id) REFERENCES documentos (id) ON DELETE CASCADE
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS oferentes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                licitacion_id INTEGER,
                nombre TEXT,
                comentario TEXT,
                FOREIGN KEY (licitacion_id) REFERENCES licitaciones (id) ON DELETE CASCADE
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS ofertas_lote_oferentes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                oferente_id INTEGER,
                lote_numero TEXT,
                monto REAL,
                paso_fase_A BOOLEAN,
                plazo_entrega INTEGER DEFAULT 0,
                garantia_meses INTEGER DEFAULT 0,
                FOREIGN KEY (oferente_id) REFERENCES oferentes(id) ON DELETE CASCADE
            )
        ''')

        self.cursor.execute('CREATE TABLE IF NOT EXISTS empresas_maestras (nombre TEXT PRIMARY KEY, rnc TEXT, telefono TEXT, correo TEXT, direccion TEXT, rpe TEXT, representante TEXT, cargo_representante TEXT)')
        self.cursor.execute('CREATE TABLE IF NOT EXISTS instituciones_maestras (nombre TEXT PRIMARY KEY, rnc TEXT, telefono TEXT, correo TEXT, direccion TEXT)')
        self.cursor.execute('CREATE TABLE IF NOT EXISTS competidores_maestros (nombre TEXT PRIMARY KEY, rnc TEXT, rpe TEXT, representante TEXT)')
        self.cursor.execute('CREATE TABLE IF NOT EXISTS responsables_maestros (nombre TEXT PRIMARY KEY)')

        # ... (El resto de las tablas se mantiene igual)

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS documentos_maestros (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo TEXT UNIQUE NOT NULL,
                nombre TEXT,
                categoria TEXT,
                comentario TEXT,
                ruta_archivo TEXT
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS criterios_bnb (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT UNIQUE NOT NULL,
                peso REAL NOT NULL CHECK (peso > 0 AND peso <= 1),
                activo BOOLEAN DEFAULT 1
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS bnb_evaluaciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                licitacion_id INTEGER,
                criterio_id INTEGER,
                puntaje INTEGER NOT NULL CHECK (puntaje >= 0 AND puntaje <= 10),
                FOREIGN KEY (licitacion_id) REFERENCES licitaciones (id) ON DELETE CASCADE,
                FOREIGN KEY (criterio_id) REFERENCES criterios_bnb (id) ON DELETE CASCADE,
                UNIQUE(licitacion_id, criterio_id)
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS kits_de_requisitos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre_kit TEXT NOT NULL,
                institucion_nombre TEXT NOT NULL,
                UNIQUE(nombre_kit, institucion_nombre),
                FOREIGN KEY (institucion_nombre) REFERENCES instituciones_maestras (nombre) ON DELETE CASCADE
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS kit_items (
                kit_id INTEGER,
                documento_maestro_id INTEGER,
                PRIMARY KEY (kit_id, documento_maestro_id),
                FOREIGN KEY (kit_id) REFERENCES kits_de_requisitos (id) ON DELETE CASCADE,
                FOREIGN KEY (documento_maestro_id) REFERENCES documentos_maestros (id) ON DELETE CASCADE
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS backups_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                ruta_archivo TEXT NOT NULL,
                comentario TEXT
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS config_app (
                clave TEXT PRIMARY KEY,
                valor TEXT
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS expedientes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                licitacion_id INTEGER NOT NULL,
                titulo TEXT NOT NULL,
                creado_en TEXT DEFAULT (strftime('%Y-%m-%d %H:%M:%f','now')),
                creado_por TEXT,
                FOREIGN KEY (licitacion_id) REFERENCES licitaciones(id) ON DELETE CASCADE
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS expediente_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                expediente_id INTEGER NOT NULL,
                orden INTEGER NOT NULL,
                doc_version_id INTEGER NOT NULL,
                titulo TEXT NOT NULL,
                FOREIGN KEY (expediente_id) REFERENCES expedientes(id) ON DELETE CASCADE,
                FOREIGN KEY (doc_version_id) REFERENCES documentos(id) ON DELETE CASCADE
            )
        ''')

        # --- INICIO DE CORRECCIÓN ---
        # Se elimina la definición duplicada y errónea de 'licitacion_ganadores_lote' de esta función.
        # La única definición válida ahora es la que está en _ensure_ganadores_schema.
        # También se elimina la creación de índices duplicados.
        # --- FIN DE CORRECCIÓN ---
        
        self.cursor.execute("PRAGMA table_info(lotes)")
        _l_cols = [r[1] for r in self.cursor.fetchall()]
        if 'empresa_nuestra' not in _l_cols:
            self.cursor.execute("ALTER TABLE lotes ADD COLUMN empresa_nuestra TEXT")

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS subsanacion_historial (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                licitacion_id INTEGER NOT NULL,
                documento_id INTEGER NOT NULL,
                fecha_solicitud TEXT NOT NULL,
                fecha_limite_entrega TEXT,
                fecha_entrega_real TEXT,
                comentario TEXT,
                estado TEXT DEFAULT 'Pendiente',
                FOREIGN KEY (licitacion_id) REFERENCES licitaciones (id) ON DELETE CASCADE,
                FOREIGN KEY (documento_id) REFERENCES documentos (id) ON DELETE CASCADE
            )
        ''')
        self.conn.commit()

        self.cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS uniq_subsanacion_pendiente
            ON subsanacion_historial(licitacion_id, documento_id)
            WHERE UPPER(TRIM(estado)) = 'PENDIENTE'
        """)
        self.conn.commit()



    def update_lote_empresa(self, licitacion_id: int, lote_numero: str, empresa_nuestra: str | None):
        self.cursor.execute("""
            UPDATE lotes
            SET empresa_nuestra = ?
            WHERE licitacion_id = ? AND CAST(numero AS TEXT) = CAST(? AS TEXT)
        """, (empresa_nuestra or None, licitacion_id, str(lote_numero)))
        self.conn.commit()

    def update_lote_flags(self, licitacion_id: int, lote_numero: str, participamos: bool, fase_a_ok: bool, monto_ofertado: float | None):
        self.cursor.execute("""
            UPDATE lotes
            SET participamos = ?, fase_A_superada = ?, monto_ofertado = ?
            WHERE licitacion_id = ? AND CAST(numero AS TEXT) = CAST(? AS TEXT)
        """, (1 if participamos else 0, 1 if fase_a_ok else 0, float(monto_ofertado or 0.0), licitacion_id, str(lote_numero)))
        self.conn.commit()


    def obtener_todas_las_fallas(self):
            """
            Devuelve una lista de tuplas con todas las fallas registradas,
            uniendo las tablas para obtener los nombres en lugar de solo los IDs.
            Formato: (institucion, participante_nombre, documento_nombre, es_nuestro(bool), comentario)
            """
            # --- INICIO DE LA CORRECCIÓN ---
            # 1. Se usa la tabla correcta: 'descalificaciones_fase_a'
            # 2. Se hacen JOINs con 'licitaciones' y 'documentos' para obtener los nombres
            sql = """
                SELECT
                    l.institucion,
                    dfa.participante_nombre,
                    d.nombre AS documento_nombre,
                    COALESCE(dfa.es_nuestro, 0) AS es_nuestro,
                    COALESCE(dfa.comentario, '')
                FROM descalificaciones_fase_a AS dfa
                JOIN licitaciones AS l ON l.id = dfa.licitacion_id
                JOIN documentos AS d ON d.id = dfa.documento_id
                ORDER BY l.institucion ASC, d.nombre ASC, dfa.participante_nombre ASC
            """
            try:
                cur = self.conn.execute(sql)
                filas = cur.fetchall()
                # Normalizamos el valor de 'es_nuestro' a un booleano
                return [
                    (inst, part, doc, bool(en), com)
                    for (inst, part, doc, en, com) in filas
                ]
            except sqlite3.OperationalError as e:
                # Si la tabla 'descalificaciones_fase_a' no existe, devolvemos una lista vacía
                # para evitar que la aplicación falle al iniciar con una BD antigua.
                if "no such table" in str(e):
                    print(f"Advertencia: La tabla 'descalificaciones_fase_a' no existe. Se devolverá una lista vacía.")
                    return []
                # Si es otro error, lo lanzamos para que se pueda depurar.
                raise e
            # --- FIN DE LA CORRECCIÓN ---
    def eliminar_falla_por_campos(self, institucion, participante, documento):
        """
        Borra una o más filas que coincidan con (institucion, participante, documento).
        Retorna la cantidad de filas afectadas.
        """
        sql = """
            DELETE FROM fallas_fase_a
            WHERE institucion = ? AND participante_nombre = ? AND documento_nombre = ?
        """
        cur = self.conn.execute(sql, (institucion, participante, documento))
        self.conn.commit()
        return cur.rowcount


    def _update_or_insert_documentos(self, licitacion_id, documentos_en_memoria):
        """
        Actualiza, inserta o elimina documentos de forma inteligente para no romper
        las claves foráneas que dependen de ellos.
        """
        # Obtenemos los IDs de los documentos que existen en la BD para esta licitación
        self.cursor.execute("SELECT id FROM documentos WHERE licitacion_id = ?", (licitacion_id,))
        ids_en_db = {row[0] for row in self.cursor.fetchall()}
        
        ids_en_memoria = {doc.id for doc in documentos_en_memoria if doc.id is not None}

        # 1. Documentos para BORRAR
        ids_para_borrar = ids_en_db - ids_en_memoria
        if ids_para_borrar:
            placeholders = ",".join("?" * len(ids_para_borrar))
            # Importante: Borramos primero las fallas dependientes para evitar errores.
            self.cursor.execute(f"DELETE FROM descalificaciones_fase_a WHERE documento_id IN ({placeholders})", list(ids_para_borrar))
            self.cursor.execute(f"DELETE FROM documentos WHERE id IN ({placeholders})", list(ids_para_borrar))

        # 2. Documentos para ACTUALIZAR o INSERTAR
        
        # --- INICIO DE LA CORRECCIÓN ---
        # Añadimos 'requiere_subsanacion' a la lista de columnas que se guardan.
        cols = ['codigo', 'nombre', 'categoria', 'comentario', 'presentado', 'subsanable',  
                'ruta_archivo', 'responsable', 'revisado', 'obligatorio', 'orden_pliego',
                'requiere_subsanacion']
        # --- FIN DE LA CORRECCIÓN ---
        
        for doc in documentos_en_memoria:
            if doc.id in ids_en_db:
                # Si el ID ya existe, es un UPDATE
                update_sql = f"UPDATE documentos SET {', '.join(f'{c}=?' for c in cols)} WHERE id=?"
                values = [getattr(doc, c, None) for c in cols] + [doc.id]
                self.cursor.execute(update_sql, values)
            else:
                # Si el ID es nuevo o no existe, es un INSERT
                insert_cols = ['licitacion_id'] + cols
                placeholders = ",".join("?" * len(insert_cols))
                insert_sql = f"INSERT INTO documentos ({', '.join(insert_cols)}) VALUES ({placeholders})"
                values = [licitacion_id] + [getattr(doc, c, None) for c in cols]
                self.cursor.execute(insert_sql, values)
                # Actualizamos el objeto en memoria con el nuevo ID generado por la BD.
                doc.id = self.cursor.lastrowid


    def get_empresas_maestras(self):
        """
        Devuelve empresas maestras como lista de dicts:
        [{'nombre': ..., 'rnc': ..., 'telefono': ..., 'correo': ..., 'direccion': ...}, ...]
        """
        try:
            self.cursor.execute("""
                SELECT nombre, rnc, telefono, correo, direccion
                FROM empresas_maestras
                ORDER BY nombre COLLATE NOCASE
            """)
            filas = self.cursor.fetchall()
            return [
                {
                    "nombre":     (f[0] or "").strip(),
                    "rnc":        (f[1] or "").strip() if len(f) > 1 and f[1] else "",
                    "telefono":   (f[2] or "").strip() if len(f) > 2 and f[2] else "",
                    "correo":     (f[3] or "").strip() if len(f) > 3 and f[3] else "",
                    "direccion":  (f[4] or "").strip() if len(f) > 4 and f[4] else "",
                }
                for f in filas
            ]
        except Exception as e:
            print("[WARN] get_empresas_maestras falló:", e)
            return []



    # ================= GANADORES POR LOTE =================

    def save_ganadores_por_lote(self, licitacion_id: int, mapping: list[tuple]):
        """
        mapping: lista de tuplas (lote_numero, ganador_nombre, es_nuestro_bool)
        Si es_nuestro_bool is True => empresa_nuestra = ganador_nombre.
        """
        try:
            if not mapping:
                return True  # nada que hacer

            # 0) asegurar catálogo para las empresas nuestras
            for _, ganador_nombre, es_nuestro in mapping:
                if es_nuestro and ganador_nombre:
                    self.cursor.execute(
                        "INSERT OR IGNORE INTO empresas_maestras (nombre) VALUES (?)",
                        (ganador_nombre.strip(),)
                    )

            # 1) reemplazo completo de filas de esta licitación
            self.cursor.execute(
                "DELETE FROM licitacion_ganadores_lote WHERE licitacion_id = ?",
                (licitacion_id,)
            )

            rows = []
            for lote_num, ganador_nombre, es_nuestro in mapping:
                empresa_nuestra = ganador_nombre if es_nuestro else None
                rows.append((licitacion_id, str(lote_num), str(ganador_nombre), empresa_nuestra))

            self.cursor.executemany(
                """INSERT INTO licitacion_ganadores_lote (licitacion_id, lote_numero, ganador_nombre, empresa_nuestra)
                VALUES (?,?,?,?)
                ON CONFLICT(licitacion_id, lote_numero) DO UPDATE SET
                    ganador_nombre=excluded.ganador_nombre,
                    empresa_nuestra=excluded.empresa_nuestra""",
                rows
            )
            self.conn.commit()
            return True
        except Exception as e:
            self.conn.rollback()
            logging.error(f"[DB] save_ganadores_por_lote falló: {e}")
            return False

        
    def _ensure_ganadores_empresa_col(self):
        """Asegura que la tabla licitacion_ganadores_lote tenga la columna empresa_nuestra."""
        try:
            self.cursor.execute("PRAGMA table_info(licitacion_ganadores_lote)")
            cols = [r[1] for r in self.cursor.fetchall()]
            if "empresa_nuestra" not in cols:
                # Migración mínima: agregar la columna
                self.cursor.execute("ALTER TABLE licitacion_ganadores_lote ADD COLUMN empresa_nuestra TEXT")
                # (Opcional) si quieres inicializar algo, haz UPDATE aquí.
                self.conn.commit()
        except Exception as e:
            # No interrumpas el arranque por la migración; solo infórmalo en consola
            print(f"[WARN] No se pudo asegurar columna empresa_nuestra en licitacion_ganadores_lote: {e}")


    def marcar_ganador_lote(self, licitacion_id, lote_numero, ganador_nombre, empresa_nuestra=None):
        """
        Guarda/actualiza el ganador de un lote.
        Garantiza 1 ganador por (licitacion_id, lote_numero).
        """
        # si es nuestra empresa, primero asegúrala en el catálogo
        if empresa_nuestra:
            self.cursor.execute(
                "INSERT OR IGNORE INTO empresas_maestras (nombre) VALUES (?)",
                (empresa_nuestra.strip(),)
            )

        self.cursor.execute("""
            INSERT INTO licitacion_ganadores_lote(licitacion_id, lote_numero, ganador_nombre, empresa_nuestra)
            VALUES(?,?,?,?)
            ON CONFLICT(licitacion_id, lote_numero) DO UPDATE SET
                ganador_nombre  = excluded.ganador_nombre,
                empresa_nuestra = excluded.empresa_nuestra
        """, (licitacion_id, str(lote_numero), (ganador_nombre or ""), (empresa_nuestra or None)))
        self.conn.commit()
        return True


    def borrar_ganador_lote(self, licitacion_id, lote_numero):
        """Elimina el registro de ganador para ese lote (deja 'sin ganador')."""
        self.cursor.execute(
            "DELETE FROM licitacion_ganadores_lote WHERE licitacion_id=? AND lote_numero=?",
            (licitacion_id, str(lote_numero))
        )
        self.conn.commit()
        return True



    def save_empresas_nuestras(self, licitacion_id: int, empresas: list[str]):
        """
        Vincula empresas con la licitación.
        FIX: antes de insertar en la tabla relacional, nos aseguramos
        de que cada empresa exista en el catálogo 'empresas_maestras'
        para no violar la FK.
        """
        # 1) normalizamos nombres
        empresas_norm = [(e or "").strip() for e in empresas if (e or "").strip()]

        # 2) aseguramos catálogo
        for nombre in empresas_norm:
            self.cursor.execute(
                "INSERT OR IGNORE INTO empresas_maestras (nombre) VALUES (?)",
                (nombre,)
            )

        # 3) borramos vínculos anteriores y creamos los nuevos
        self.cursor.execute(
            "DELETE FROM licitacion_empresas_nuestras WHERE licitacion_id = ?",
            (licitacion_id,)
        )
        for nombre in empresas_norm:
            self.cursor.execute(
                "INSERT OR IGNORE INTO licitacion_empresas_nuestras (licitacion_id, empresa_nombre) VALUES (?, ?)",
                (licitacion_id, nombre)
            )
        self.conn.commit()


    def agregar_empresa_maestra(self, nombre: str):
        """Inserta una empresa en el catálogo de empresas maestras."""
        if not nombre:
            return False
        try:
            self.cursor.execute(
                "INSERT OR IGNORE INTO empresas_maestras (nombre) VALUES (?)",
                (nombre.strip(),)
            )
            self.conn.commit()
            return True
        except Exception as e:
            print("Error al agregar empresa:", e)
            return False



    def get_all_data(self):
        """
        Recupera todas las licitaciones y TODAS sus entidades relacionadas,
        incluyendo las fallas de fase A.
        """
        # === LICITACIONES ===
        self.cursor.execute("SELECT * FROM licitaciones")
        lic_cols = [d[0] for d in self.cursor.description]
        licitaciones_dict = {}

        for row in self.cursor.fetchall():
            lic = dict(zip(lic_cols, row)) 
            lic_id = lic.get("id")

            legacy_company_name = None
            if isinstance(lic.get("empresa_nuestra"), str) and lic["empresa_nuestra"]:
                legacy_company_name = lic["empresa_nuestra"]

            lic["empresa_nuestra"] = None 

            if isinstance(lic.get("cronograma"), str):
                try: lic["cronograma"] = json.loads(lic["cronograma"] or "{}")
                except Exception: lic["cronograma"] = {}
            else:
                lic["cronograma"] = lic.get("cronograma") or {}

            lic.update({
                "lotes": [], "documentos_solicitados": [], "oferentes_participantes": [],
                "bnb_evaluacion": [], "riesgos": [], "empresas_nuestras": [], "fallas_fase_a": [],
                "_legacy_company": legacy_company_name 
            })
            licitaciones_dict[lic_id] = lic

        if not licitaciones_dict:
            return [], [], [], [], [], []

        # === EMPRESAS NUESTRAS (Tabla nueva) ===
        self.cursor.execute("SELECT licitacion_id, empresa_nombre FROM licitacion_empresas_nuestras")
        emp_por_lic = {}
        for lic_id, nombre in self.cursor.fetchall():
            if nombre:
                emp_por_lic.setdefault(lic_id, set()).add(nombre.strip())

        # === ASIGNACIÓN FINAL DE EMPRESAS ===
        for lic_id, lic in licitaciones_dict.items():
            nombres_empresas = emp_por_lic.get(lic_id, set())
            if not nombres_empresas and lic.get("_legacy_company"):
                nombres_empresas.add(lic["_legacy_company"])
            lic["empresas_nuestras"] = [{"nombre": nombre} for nombre in sorted(list(nombres_empresas))]
            if "_legacy_company" in lic:
                del lic["_legacy_company"]
        
        # === LOTES ===
        cols_lotes = {r[1] for r in self.cursor.execute("PRAGMA table_info(lotes)").fetchall()}
        tiene_emp_lote = "empresa_nuestra" in cols_lotes
        self.cursor.execute(f"SELECT id, licitacion_id, numero, nombre, monto_base, monto_base_personal, monto_ofertado, participamos, fase_A_superada{', empresa_nuestra' if tiene_emp_lote else ''} FROM lotes ORDER BY CASE WHEN numero GLOB '*[0-9]*' THEN CAST(numero AS INTEGER) ELSE NULL END, numero")
        lot_cols = [d[0] for d in self.cursor.description]
        for row in self.cursor.fetchall():
            l = dict(zip(lot_cols, row)); lic_id = l.get("licitacion_id")
            if lic_id not in licitaciones_dict: continue
            l["monto_base"] = float(l.get("monto_base") or 0.0); l["monto_base_personal"] = float(l.get("monto_base_personal") or 0.0); l["monto_ofertado"] = float(l.get("monto_ofertado") or 0.0)
            l["participamos"] = bool(l.get("participamos")); l["fase_A_superada"] = bool(l.get("fase_A_superada"))
            if tiene_emp_lote: l["empresa_nuestra"] = (l.get("empresa_nuestra") or "").strip() or None
            else: l["empresa_nuestra"] = None
            l.setdefault("ganador_nombre", ""); l.setdefault("ganado_por_nosotros", False)
            licitaciones_dict[lic_id]["lotes"].append(l)

        # === DOCUMENTOS ===
        self.cursor.execute("SELECT * FROM documentos"); doc_cols = [d[0] for d in self.cursor.description]
        for row in self.cursor.fetchall():
            d = dict(zip(doc_cols, row)); lic_id = d.get("licitacion_id")
            if lic_id in licitaciones_dict: licitaciones_dict[lic_id]["documentos_solicitados"].append(d)

        # === BNB EVALUACIONES ===
        self.cursor.execute("SELECT * FROM bnb_evaluaciones"); bnb_cols = [d[0] for d in self.cursor.description]
        for row in self.cursor.fetchall():
            b = dict(zip(bnb_cols, row)); lic_id = b.get("licitacion_id")
            if lic_id in licitaciones_dict: licitaciones_dict[lic_id]["bnb_evaluacion"].append(b)

        # === FALLAS FASE A (BLOQUE CORREGIDO) ===
        try:
            self.cursor.execute("SELECT id, licitacion_id, participante_nombre, documento_id, comentario, es_nuestro FROM descalificaciones_fase_a")
            dfa_cols = ['id', 'licitacion_id', 'participante_nombre', 'documento_id', 'comentario', 'es_nuestro']
            for row in self.cursor.fetchall():
                dfa = dict(zip(dfa_cols, row))
                lic_id = dfa.get("licitacion_id")
                if lic_id in licitaciones_dict:
                    licitaciones_dict[lic_id]["fallas_fase_a"].append(dfa)
        except sqlite3.OperationalError:
            print("Advertencia: Tabla 'descalificaciones_fase_a' no encontrada durante la carga.")
            pass
        
        # === OFERENTES Y OFERTAS ===
        self.cursor.execute("SELECT o.id, o.licitacion_id, o.nombre, o.comentario, ol.lote_numero, ol.monto, ol.paso_fase_A FROM oferentes o LEFT JOIN ofertas_lote_oferentes ol ON o.id = ol.oferente_id")
        oferentes_temp = {}
        for oferente_id, lic_id, nombre, comentario, lote_num, monto, paso_a in self.cursor.fetchall():
            if lic_id not in licitaciones_dict: continue
            if oferente_id not in oferentes_temp: oferentes_temp[oferente_id] = {"licitacion_id": lic_id, "nombre": nombre, "comentario": comentario, "ofertas_por_lote": []}
            if lote_num is not None: oferentes_temp[oferente_id]["ofertas_por_lote"].append({"lote_numero": lote_num, "monto": float(monto or 0.0), "paso_fase_A": bool(paso_a), "ganador": False})
        for ofr in oferentes_temp.values():
            lic_id = ofr["licitacion_id"]
            if lic_id in licitaciones_dict: licitaciones_dict[lic_id]["oferentes_participantes"].append(ofr)
        
        # === GANADORES POR LOTE ===
        try:
            cols_g = {r[1] for r in self.cursor.execute("PRAGMA table_info(licitacion_ganadores_lote)").fetchall()}
            if "empresa_nuestra" in cols_g: self.cursor.execute("SELECT licitacion_id, lote_numero, ganador_nombre, empresa_nuestra FROM licitacion_ganadores_lote"); ganador_rows = self.cursor.fetchall(); esquema = "nuevo"
            else: self.cursor.execute("SELECT licitacion_id, lote_numero, ganador_nombre, es_nuestro FROM licitacion_ganadores_lote"); ganador_rows = self.cursor.fetchall(); esquema = "viejo"
        except Exception: ganador_rows = []; esquema = "ninguno"
        gan_por_lic = {}
        if esquema == "nuevo":
            for lic_id, lote_num, ganador_nombre, empresa_nuestra in ganador_rows:
                gan_por_lic.setdefault(lic_id, []).append({
                    "lote_numero": lote_num,
                    "ganador_nombre": (ganador_nombre or "").strip(),
                    "empresa_nuestra": (empresa_nuestra or "").strip()
                })
        for lic_id, lic in licitaciones_dict.items():
            if lic_id not in gan_por_lic: continue
            for g in gan_por_lic[lic_id]:
                loteno  = str(g.get("lote_numero"))
                ganador = (g.get("ganador_nombre") or "").strip()
                for L in lic["lotes"]:
                    if str(L.get("numero")) != loteno: continue
                    L["ganador_nombre"] = ganador
                    if esquema == "nuevo":
                        emp_n_row = (g.get("empresa_nuestra") or "").strip()
                        emp_lote  = (L.get("empresa_nuestra") or "").strip()
                        L["ganado_por_nosotros"] = bool(emp_n_row) or (emp_lote and ganador and ganador == emp_lote)
                    else:
                        es_nuestro = bool(g.get("es_nuestro"))
                        if es_nuestro:
                            L["ganado_por_nosotros"] = True
                        else:
                            emp_lote = (L.get("empresa_nuestra") or "").strip()
                            L["ganado_por_nosotros"] = bool(emp_lote and ganador and ganador == emp_lote)
                    break

            for g in gan_por_lic[lic_id]:
                loteno = str(g.get("lote_numero")); ganador = (g.get("ganador_nombre") or "").strip()
                for comp in lic["oferentes_participantes"]:
                    if comp.get("nombre") == ganador:
                        for o in comp.get("ofertas_por_lote", []):
                            if str(o.get("lote_numero")) == loteno: o["ganador"] = True
                    else:
                        for o in comp.get("ofertas_por_lote", []): o.setdefault("ganador", False)
        
        # === DATOS MAESTROS ===
        master_tables = ["empresas_maestras", "instituciones_maestras", "documentos_maestros", "competidores_maestros", "responsables_maestros"]
        master_data = [self._get_master_table(tbl) for tbl in master_tables]
        return list(licitaciones_dict.values()), *master_data
    def _get_master_table(self, table_name):
        self.cursor.execute(f'SELECT * FROM {table_name}')
        cols = [d[0] for d in self.cursor.description]
        return [dict(zip(cols, row)) for row in self.cursor.fetchall()]

    def save_licitacion(self, licitacion):
            """
            Guarda una licitación y todos sus datos relacionados, con control
            de concurrencia 'suave' (un reintento si el timestamp cambió).
            """
            is_new = not hasattr(licitacion, 'id') or not licitacion.id
            manage_transaction = not self.conn.in_transaction

            def _do_update():
                new_timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%f')
                
                # Usamos el método to_dict() de la licitación para obtener todos los datos
                lic_data_full = licitacion.to_dict()
                print(f"DEBUG [Paso 2 - BD]: Guardando Parámetros -> {lic_data_full.get('parametros_evaluacion')}")

                lic_data = {
                    'nombre_proceso': lic_data_full.get('nombre_proceso'),
                    'numero_proceso': lic_data_full.get('numero_proceso'),
                    'institucion': lic_data_full.get('institucion'),
                    'estado': lic_data_full.get('estado'),
                    'fase_A_superada': lic_data_full.get('fase_A_superada'),
                    'fase_B_superada': lic_data_full.get('fase_B_superada'),
                    'adjudicada': lic_data_full.get('adjudicada'),
                    'adjudicada_a': lic_data_full.get('adjudicada_a'),
                    'motivo_descalificacion': lic_data_full.get('motivo_descalificacion'),
                    'fecha_creacion': lic_data_full.get('fecha_creacion'),
                    'cronograma': json.dumps(lic_data_full.get('cronograma', {})),
                    'docs_completos_manual': lic_data_full.get('docs_completos_manual'),
                    'last_modified': new_timestamp,
                    # --- LÍNEA CORREGIDA ---
                    # Toma los parámetros del objeto licitacion, no de self (DatabaseManager)
                    "parametros_evaluacion": json.dumps(lic_data_full.get('parametros_evaluacion', {}))
                }

                if not is_new:
                    licitacion_id = licitacion.id
                    columns_to_update = ', '.join(f'{k}=?' for k in lic_data)
                    self.cursor.execute(
                        f"UPDATE licitaciones SET {columns_to_update} WHERE id=?",
                        list(lic_data.values()) + [licitacion_id]
                    )
                else:
                    insert_query = f"INSERT INTO licitaciones ({', '.join(lic_data.keys())}) VALUES ({','.join('?'*len(lic_data))})"
                    self.cursor.execute(insert_query, list(lic_data.values()))
                    licitacion.id = self.cursor.lastrowid

                licitacion.last_modified = new_timestamp

            try:
                if manage_transaction:
                    self.cursor.execute('BEGIN IMMEDIATE TRANSACTION')

                if not is_new:
                    # Control de concurrencia
                    self.cursor.execute('SELECT last_modified FROM licitaciones WHERE id = ?', (licitacion.id,))
                    row = self.cursor.fetchone()
                    db_ts = row[0] if row else None
                    if db_ts is not None and licitacion.last_modified is not None and db_ts != licitacion.last_modified:
                        # Si alguien más guardó mientras editábamos, lanzamos un error para evitar sobreescribir
                        raise ConcurrencyException("Esta licitación ha sido modificada por otro usuario. Por favor, recargue los datos.")

                # === Escritura principal ===
                _do_update()

                # ==== RELACIONADOS ====
                self.save_empresas_nuestras(licitacion.id, [str(e) for e in licitacion.empresas_nuestras])
                
                self._save_related_data('lotes', licitacion.id, licitacion.lotes,
                                        ['licitacion_id','numero','nombre','monto_base','monto_base_personal',
                                        'monto_ofertado','participamos','fase_A_superada','empresa_nuestra'])
                
                self._update_or_insert_documentos(licitacion.id, licitacion.documentos_solicitados)
                
                self._save_related_data('descalificaciones_fase_a', licitacion.id, getattr(licitacion, 'fallas_fase_a', []),
                                        ['licitacion_id','participante_nombre','documento_id','comentario','es_nuestro'])

                self.cursor.execute('DELETE FROM oferentes WHERE licitacion_id = ?', (licitacion.id,))
                if licitacion.oferentes_participantes:
                    for oferente in licitacion.oferentes_participantes:
                        self.cursor.execute(
                            'INSERT INTO oferentes (licitacion_id, nombre, comentario) VALUES (?,?,?)',
                            (licitacion.id, oferente.nombre, oferente.comentario)
                        )
                        oferente_id = self.cursor.lastrowid
                        if getattr(oferente, 'ofertas_por_lote', None):
                            ofertas_to_save = [
                                (oferente_id, o['lote_numero'], o['monto'], o.get('paso_fase_A', True),
                                o.get('plazo_entrega', 0), o.get('garantia_meses', 0))
                                for o in oferente.ofertas_por_lote
                            ]
                            self.cursor.executemany(
                                'INSERT INTO ofertas_lote_oferentes (oferente_id, lote_numero, monto, paso_fase_A, plazo_entrega, garantia_meses) VALUES (?,?,?,?,?,?)',
                                ofertas_to_save
                            )

                if manage_transaction:
                    self.conn.commit()

                return True

            except Exception as e:
                if manage_transaction:
                    self.conn.rollback()
                raise e


    def get_last_modified(self, licitacion_id: int):
        self.cursor.execute('SELECT last_modified FROM licitaciones WHERE id=?', (licitacion_id,))
        row = self.cursor.fetchone()
        return row[0] if row else None


    def save_single_institucion(self, institucion_data):
        """Guarda o actualiza una sola institución en la tabla maestra."""
        try:
            sql = """
                INSERT INTO instituciones_maestras (nombre, rnc, telefono, correo, direccion)
                VALUES (:nombre, :rnc, :telefono, :correo, :direccion)
                ON CONFLICT(nombre) DO UPDATE SET
                    rnc=excluded.rnc,
                    telefono=excluded.telefono,
                    correo=excluded.correo,
                    direccion=excluded.direccion
            """
            self.cursor.execute(sql, institucion_data)
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error al guardar institución individual: {e}")
            self.conn.rollback()
            return False


    # ===== Helpers para ganadores por lote =====
    def get_ganadores_por_lote(self, licitacion_id: int):
        self.cursor.execute("""
            SELECT lote_numero, ganador_nombre, empresa_nuestra
            FROM licitacion_ganadores_lote
            WHERE licitacion_id = ?
            ORDER BY CAST(lote_numero AS INTEGER)
        """, (licitacion_id,))
        rows = self.cursor.fetchall()
        return [
            {
                "lote_numero": r[0],
                "ganador_nombre": r[1],
                "es_nuestro": 1 if r[2] else 0,
                "empresa_nuestra": r[2]
            }
            for r in rows
        ]


    def ganador_de_competidor_en_licitacion(self, licitacion_id: int, competidor_nombre: str) -> bool:
        self.cursor.execute("""
            SELECT 1
            FROM licitacion_ganadores_lote
            WHERE licitacion_id = ? AND ganador_nombre = ?
            LIMIT 1
        """, (licitacion_id, competidor_nombre))
        return self.cursor.fetchone() is not None

    def cantidad_lotes_ganados_por_competidor(self, licitacion_id: int, competidor_nombre: str) -> int:
        self.cursor.execute("""
            SELECT COUNT(*)
            FROM licitacion_ganadores_lote
            WHERE licitacion_id = ? AND ganador_nombre = ?
        """, (licitacion_id, competidor_nombre))
        row = self.cursor.fetchone()
        return int(row[0]) if row else 0






    def _save_related_data(self, table_name, licitacion_id, data_list, columns):
        """Borra e inserta datos en tablas relacionadas."""
        self.cursor.execute(f'DELETE FROM {table_name} WHERE licitacion_id = ?', (licitacion_id,))
        if data_list:
            to_save = [
                tuple(item.get(col) if isinstance(item, dict) else getattr(item, col) for col in columns[1:])
                for item in data_list
            ]
            to_save_with_id = [(licitacion_id,) + row for row in to_save]
            placeholders = ','.join('?' * len(columns))
            self.cursor.executemany(
                f'INSERT INTO {table_name} ({",".join(columns)}) VALUES ({placeholders})',
                to_save_with_id
            )


    def _save_master_table(self, table_name, data_list, columns, unique_cols, replace=False):
        """
        Guarda una lista maestra de forma segura.
        - Por defecto hace UPSERT (NO destructivo).
        - Si replace=True, borra todo antes de insertar.
        - columns: columnas a escribir en INSERT.
        - unique_cols: columnas que definen la clave única para ON CONFLICT.
        """
        if replace:
            self.cursor.execute(f"DELETE FROM {table_name}")

        if not data_list:
            return

        filas = []
        for item in data_list:
            if not isinstance(item, dict):
                try:
                    item = item.to_dict()
                except Exception:
                    item = getattr(item, "__dict__", {})
            filas.append(tuple(item.get(c) for c in columns))

        placeholders = ",".join("?" * len(columns))
        cols_joined = ",".join(columns)
        conflict_target = ",".join(unique_cols)

        update_cols = [c for c in columns if c not in unique_cols]
        if update_cols:
            set_clause = ", ".join([f"{c}=excluded.{c}" for c in update_cols])
            sql = f"""
                INSERT INTO {table_name} ({cols_joined})
                VALUES ({placeholders})
                ON CONFLICT({conflict_target}) DO UPDATE SET
                {set_clause}
            """
        else:
            sql = f"""
                INSERT INTO {table_name} ({cols_joined})
                VALUES ({placeholders})
                ON CONFLICT({conflict_target}) DO NOTHING
            """
        self.cursor.executemany(sql, filas)


    def save_master_lists(self, empresas, instituciones, documentos_maestros,
                            competidores_maestros, responsables_maestros, replace_tables=None):
        """
        Guarda todas las listas maestras.
        - UPSERT por defecto (no borra).
        - Usa replace_tables={'tabla1','tabla2',...} solo si necesitas reemplazo total.
        """
        try:
            replace_tables = set(replace_tables or [])

            def safe_replace(flag, data_list, tabla):
                if flag and not data_list:
                    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    print(f"[{ts}] [SAFEGUARD] Ignorando replace en {tabla}: lista vacía.")
                    return False
                return flag

            self._save_master_table(
                table_name='empresas_maestras',
                data_list=empresas,
                columns=['nombre', 'rnc', 'telefono', 'correo', 'direccion', 'rpe', 'representante', 'cargo_representante'],
                unique_cols=['nombre'],
                replace=safe_replace('empresas_maestras' in replace_tables, empresas, 'empresas_maestras')
            )

            self._save_master_table(
                table_name='instituciones_maestras',
                data_list=instituciones,
                columns=['nombre', 'rnc', 'telefono', 'correo', 'direccion'],
                unique_cols=['nombre'],
                replace=safe_replace('instituciones_maestras' in replace_tables, instituciones, 'instituciones_maestras')
            )

            self._save_master_table(
                table_name='competidores_maestros',
                data_list=competidores_maestros,
                columns=['nombre', 'rnc', 'rpe', 'representante'],
                unique_cols=['nombre'],
                replace=safe_replace('competidores_maestros' in replace_tables, competidores_maestros, 'competidores_maestros')
            )

            self._save_master_table(
                table_name='responsables_maestros',
                data_list=responsables_maestros,
                columns=['nombre'],
                unique_cols=['nombre'],
                replace=safe_replace('responsables_maestros' in replace_tables, responsables_maestros, 'responsables_maestros')
            )

            docs_to_save = [d.to_dict() if hasattr(d, 'to_dict') else dict(d) for d in documentos_maestros]
            
            self._save_master_table(
                table_name='documentos_maestros',
                data_list=docs_to_save,
                columns=['codigo', 'nombre', 'categoria', 'comentario', 'ruta_archivo'],
                unique_cols=['codigo'], 
                replace=safe_replace('documentos_maestros' in replace_tables, docs_to_save, 'documentos_maestros')
            )

            self.conn.commit()

        except Exception as e:
            import logging
            logging.error(f"Error al guardar listas maestras: {e}")
            self.conn.rollback()
            raise

    # ================= EXPEDIENTES (DB) =================
    def crear_expediente(self, licitacion_id, titulo, creado_por):
        self.cursor.execute(
            "INSERT INTO expedientes (licitacion_id, titulo, creado_por) VALUES (?,?,?)",
            (licitacion_id, titulo, creado_por)
        )
        self.conn.commit()
        return self.cursor.lastrowid

    def agregar_items_expediente(self, expediente_id, items):
        """
        items: lista de dicts o tuplas con:
            - orden (int)
            - doc_version_id (int -> documentos.id)
            - titulo (str)
        """
        rows = []
        for it in items:
            if isinstance(it, dict):
                rows.append((expediente_id, it['orden'], it['doc_version_id'], it['titulo']))
            else:
                # tupla (orden, doc_id, titulo)
                rows.append((expediente_id, it[0], it[1], it[2]))
        self.cursor.executemany(
            "INSERT INTO expediente_items (expediente_id, orden, doc_version_id, titulo) VALUES (?,?,?,?)",
            rows
        )
        self.conn.commit()

    def obtener_documentos_de_licitacion(self, licitacion_id):
        """Devuelve documentos (dicts) incluyendo 'orden_pliego'."""
        self.cursor.execute("""
            SELECT id, codigo, nombre, categoria, comentario, presentado,
                   subsanable, ruta_archivo, responsable, revisado, obligatorio,
                   orden_pliego
            FROM documentos
            WHERE licitacion_id = ?
            ORDER BY COALESCE(orden_pliego, 999999), categoria, codigo
        """, (licitacion_id,))
        cols = [d[0] for d in self.cursor.description]
        return [dict(zip(cols, row)) for row in self.cursor.fetchall()]
    
    def guardar_orden_documentos(self, licitacion_id, pares_docid_orden):
        """
        Persiste el orden elegido por el usuario.
        pares_docid_orden: lista de (doc_id:int, orden_pliego:int) en el orden final (1..N)
        """
        try:
            self.cursor.executemany(
                "UPDATE documentos SET orden_pliego=? WHERE id=? AND licitacion_id=?",
                [(orden, doc_id, licitacion_id) for (doc_id, orden) in pares_docid_orden]
            )
            self.conn.commit()
            return True
        except Exception as e:
            print("[ERROR] guardar_orden_documentos:", e)
            return False


    def obtener_expediente(self, expediente_id):
        """Devuelve cabecera + items (ya ordenados)."""
        self.cursor.execute("SELECT * FROM expedientes WHERE id=?", (expediente_id,))
        exp_cols = [d[0] for d in self.cursor.description]
        exp = dict(zip(exp_cols, self.cursor.fetchone()))
        self.cursor.execute("""
            SELECT ei.id, ei.orden, ei.doc_version_id, ei.titulo, d.ruta_archivo
            FROM expediente_items ei
            JOIN documentos d ON d.id = ei.doc_version_id
            WHERE ei.expediente_id = ?
            ORDER BY ei.orden ASC
        """, (expediente_id,))
        cols = [d[0] for d in self.cursor.description]
        exp['items'] = [dict(zip(cols, row)) for row in self.cursor.fetchall()]
        return exp


    def delete_licitacion(self, numero_proceso):
        try:
            self.cursor.execute('DELETE FROM licitaciones WHERE numero_proceso = ?', (numero_proceso,))
            self.conn.commit()
            return self.cursor.rowcount > 0
        except sqlite3.Error as e:
            logging.error(f"Error al eliminar la licitación {numero_proceso}: {e}")
            self.conn.rollback()
            return False

    def run_sanity_checks(self):
        """Ejecuta chequeos de integridad en la base de datos."""
        issues = {'orphans': {}, 'missing_indexes': []}
        # 1. Huérfanos
        orphan_checks = {
            'lotes': ('id', 'licitacion_id', 'licitaciones'),
            'documentos': ('id', 'licitacion_id', 'licitaciones'),
            'oferentes': ('id', 'licitacion_id', 'licitaciones'),
            'riesgos': ('id', 'licitacion_id', 'licitaciones'),
            'ofertas_lote_oferentes': ('id', 'oferente_id', 'oferentes'),
            # Caso especial para tablas sin columna 'id'
            'kit_items': (['kit_id', 'documento_maestro_id'], 'kit_id', 'kits_de_requisitos')
        }
        for table, config in orphan_checks.items():
            pk_column, fk_column, parent_table = config
            select_col = "id" if isinstance(pk_column, str) else fk_column
            query = f"""
                SELECT t1.{select_col} FROM {table} AS t1
                LEFT JOIN {parent_table} AS t2 ON t1.{fk_column} = t2.id
                WHERE t2.id IS NULL
            """
            self.cursor.execute(query)
            orphans = [row[0] for row in self.cursor.fetchall()]
            if orphans:
                issues['orphans'][table] = orphans

        # 2. Índices faltantes
        expected_indexes = {
            'idx_lotes_licitacion_id': ('lotes', 'licitacion_id'),
            'idx_documentos_licitacion_id': ('documentos', 'licitacion_id'),
            'idx_oferentes_licitacion_id': ('oferentes', 'licitacion_id'),
            'idx_riesgos_licitacion_id': ('riesgos', 'licitacion_id'),
            'idx_ofertas_oferente_id': ('ofertas_lote_oferentes', 'oferente_id'),
        }
        for index_name, (table, column) in expected_indexes.items():
            self.cursor.execute(f"PRAGMA index_list('{table}')")
            if not any(index_name in idx for idx in self.cursor.fetchall()):
                issues['missing_indexes'].append({'name': index_name, 'table': table, 'column': column})
        return issues

    def begin_transaction(self):
        """Inicia una transacción explícita."""
        try:
            self.cursor.execute('BEGIN IMMEDIATE TRANSACTION')
        except sqlite3.OperationalError as e:
            print(f"Advertencia al iniciar transacción: {e}")

    def rollback_transaction(self):
        """Revierte la transacción actual."""
        self.conn.rollback()

    def auto_repair(self, issues):
        """Intenta reparar los problemas encontrados por run_sanity_checks."""
        report = []
        try:
            # 1. Reparar huérfanos
            if issues.get('orphans'):
                for table, ids in issues['orphans'].items():
                    delete_column = 'kit_id' if table == 'kit_items' else 'id'
                    placeholders = ','.join('?' for _ in ids)
                    self.cursor.execute(f"DELETE FROM {table} WHERE {delete_column} IN ({placeholders})", ids)
                    report.append(f"  - Se eliminaron {len(ids)} registros huérfanos de la tabla '{table}'.")
            # 2. Crear índices faltantes
            if issues.get('missing_indexes'):
                for index_info in issues['missing_indexes']:
                    name, table, column = index_info['name'], index_info['table'], index_info['column']
                    self.cursor.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {table}({column})")
                    report.append(f"  - Se creó el índice faltante '{name}' en la tabla '{table}'.")
            self.conn.commit()
            return True, "Reparación completada con éxito:\n" + "\n".join(report)
        except Exception as e:
            self.conn.rollback()
            return False, f"La reparación falló: {e}"

    def get_setting(self, clave, default=None):
        """Obtiene un valor de la tabla de configuración."""
        self.cursor.execute("SELECT valor FROM config_app WHERE clave = ?", (clave,))
        result = self.cursor.fetchone()
        return result[0] if result else default

    def set_setting(self, clave, valor):
        """Guarda o actualiza un valor en la tabla de configuración."""
        self.cursor.execute("INSERT OR REPLACE INTO config_app (clave, valor) VALUES (?, ?)", (clave, valor))
        self.conn.commit()

    def close(self):
        if self.conn:
            self.conn.close()

    # ======================== FTS ========================
    def setup_fts(self):
        # 1) Limpia triggers antiguos
        for trigger_name in [
            'licitaciones_after_insert', 'licitaciones_after_delete', 'licitaciones_after_update',
            'documentos_after_insert', 'documentos_after_delete', 'documentos_after_update'
        ]:
            self.cursor.execute(f"DROP TRIGGER IF EXISTS {trigger_name};")

        # 2) Asegura el esquema correcto del FTS
        self.cursor.execute("DROP TABLE IF EXISTS fts_licitaciones;")
        self.cursor.execute("DROP TABLE IF EXISTS fts_documentos;")

        # 3) FTS licitaciones (usa rowid = id)
        self.cursor.execute('''
            CREATE VIRTUAL TABLE fts_licitaciones USING fts5(
                numero_proceso,
                nombre_proceso,
                institucion,
                motivo_descalificacion,
                content='licitaciones',
                content_rowid='id'
            );
        ''')

        # Triggers licitaciones
        self.cursor.execute('''
            CREATE TRIGGER licitaciones_after_insert AFTER INSERT ON licitaciones BEGIN
                INSERT OR IGNORE INTO fts_licitaciones(rowid, numero_proceso, nombre_proceso, institucion, motivo_descalificacion)
                VALUES (new.id, new.numero_proceso, new.nombre_proceso, new.institucion, new.motivo_descalificacion);
            END;
        ''')
        self.cursor.execute('''
            CREATE TRIGGER licitaciones_after_update AFTER UPDATE ON licitaciones BEGIN
                INSERT OR REPLACE INTO fts_licitaciones(rowid, numero_proceso, nombre_proceso, institucion, motivo_descalificacion)
                VALUES (new.id, new.numero_proceso, new.nombre_proceso, new.institucion, new.motivo_descalificacion);
            END;
        ''')
        self.cursor.execute('''
            CREATE TRIGGER licitaciones_after_delete AFTER DELETE ON licitaciones BEGIN
                DELETE FROM fts_licitaciones WHERE rowid = old.id;
            END;
        ''')

        # 4) FTS documentos (sin columnas inexistentes; usaremos JOIN para IDs)
        self.cursor.execute('''
            CREATE VIRTUAL TABLE fts_documentos USING fts5(
                codigo,
                nombre,
                comentario,
                content='documentos',
                content_rowid='id'
            );
        ''')

        # Triggers documentos
        self.cursor.execute('''
            CREATE TRIGGER documentos_after_insert AFTER INSERT ON documentos BEGIN
                INSERT OR IGNORE INTO fts_documentos(rowid, codigo, nombre, comentario)
                VALUES (new.id, new.codigo, new.nombre, COALESCE(new.comentario, ''));
            END;
        ''')
        self.cursor.execute('''
            CREATE TRIGGER documentos_after_update AFTER UPDATE ON documentos BEGIN
                INSERT OR REPLACE INTO fts_documentos(rowid, codigo, nombre, comentario)
                VALUES (new.id, new.codigo, new.nombre, COALESCE(new.comentario, ''));
            END;
        ''')
        self.cursor.execute('''
            CREATE TRIGGER documentos_after_delete AFTER DELETE ON documentos BEGIN
                DELETE FROM fts_documentos WHERE rowid = old.id;
            END;
        ''')
        self.conn.commit()


    def set_busy_timeout(self, seconds: int):
        """Ajusta PRAGMA busy_timeout (ms)."""
        try:
            ms = int(seconds * 1000)
            self.conn.execute(f"PRAGMA busy_timeout = {ms}")
        except Exception as e:
            import logging
            logging.warning(f"[DB] No se pudo ajustar busy_timeout: {e}")

    def search_global(self, search_term):
        """Busca en FTS y devuelve resultados unificados con IDs reales."""
        if not search_term:
            return []
        query_term = f'"{search_term}"*'

        # Licitaciones desde FTS
        query_lic = """
            SELECT
                'Licitación' AS tipo,
                snippet(fts_licitaciones, 1, '➡️', '⬅️', '...', 15) AS contexto,
                fts_licitaciones.nombre_proceso AS referencia,
                fts_licitaciones.rowid AS licitacion_id,
                NULL AS documento_id,
                bm25(fts_licitaciones) AS rank
            FROM fts_licitaciones
            WHERE fts_licitaciones MATCH ?
        """

        # Documentos desde FTS (JOIN para mapear a licitacion_id y documento_id reales)
        query_doc = """
            SELECT
                'Documento' AS tipo,
                snippet(fts_documentos, 1, '➡️', '⬅️', '...', 15) AS contexto,
                d.nombre AS referencia,
                d.licitacion_id AS licitacion_id,
                d.id AS documento_id,
                bm25(fts_documentos) AS rank
            FROM fts_documentos
            JOIN documentos d ON d.id = fts_documentos.rowid
            WHERE fts_documentos MATCH ?
        """

        final_query = f"""
            {query_lic}
            UNION ALL
            {query_doc}
            ORDER BY rank
        """

        self.cursor.execute(final_query, (query_term, query_term))
        cols = ['tipo', 'contexto', 'referencia', 'licitacion_id', 'documento_id']
        return [dict(zip(cols, row)) for row in self.cursor.fetchall()]


    def integrity_check(self):
        """Ejecuta PRAGMA integrity_check y devuelve (ok: bool, mensaje: str)."""
        try:
            self.cursor.execute("PRAGMA integrity_check;")
            res = self.cursor.fetchone()
            msg = res[0] if res else "sin respuesta"
            return (msg == "ok"), msg
        except Exception as e:
            return False, f"Error en integrity_check: {e}"

    def rebuild_fts_index(self):
        """Reconstruye FTS evitando tocar estructuras dañadas."""
        try:
            # Transacción
            self.cursor.execute("BEGIN IMMEDIATE TRANSACTION;")

            # Elimina por completo las tablas FTS y recrea todo el esquema/trigger
            self.cursor.execute("DROP TABLE IF EXISTS fts_licitaciones;")
            self.cursor.execute("DROP TABLE IF EXISTS fts_documentos;")
            self.setup_fts()

            # Relleno vía comando especial 'rebuild' (si falla, fallback manual)
            try:
                self.cursor.execute("INSERT INTO fts_licitaciones(fts_licitaciones) VALUES('rebuild');")
                self.cursor.execute("INSERT INTO fts_documentos(fts_documentos) VALUES('rebuild');")
            except Exception:
                self.cursor.execute('''
                    INSERT INTO fts_licitaciones(rowid, numero_proceso, nombre_proceso, institucion, motivo_descalificacion)
                    SELECT id, numero_proceso, nombre_proceso, institucion, COALESCE(motivo_descalificacion,'')
                    FROM licitaciones;
                ''')
                self.cursor.execute('''
                    INSERT INTO fts_documentos(rowid, codigo, nombre, comentario)
                    SELECT id, COALESCE(codigo,''), COALESCE(nombre,''), COALESCE(comentario,'')
                    FROM documentos;
                ''')

            self.conn.commit()
            # Conteo
            self.cursor.execute("SELECT count(*) FROM fts_licitaciones;")
            c1 = self.cursor.fetchone()[0]
            self.cursor.execute("SELECT count(*) FROM fts_documentos;")
            c2 = self.cursor.fetchone()[0]
            return True, c1 + c2
        except Exception as e:
            self.conn.rollback()
            return False, str(e)

    def eliminar_falla_por_campos(self, institucion, participante, documento):
        """
        Borra 1..n filas en descalificaciones_fase_a que correspondan
        a (institucion, participante, documento) por NOMBRE.
        Retorna filas afectadas.
        """
        sql = """
            DELETE FROM descalificaciones_fase_a
            WHERE licitacion_id IN (
                SELECT id FROM licitaciones WHERE institucion = ?
            )
            AND participante_nombre = ?
            AND documento_id IN (
                SELECT d.id
                FROM documentos d
                JOIN licitaciones l ON l.id = d.licitacion_id
                WHERE d.nombre = ? AND l.institucion = ?
            )
        """
        cur = self.conn.execute(sql, (institucion, participante, documento, institucion))
        self.conn.commit()
        return cur.rowcount


    def actualizar_comentario_falla(self, institucion, participante, documento, comentario):
        """
        Actualiza el comentario en descalificaciones_fase_a para (institucion, participante, documento) por NOMBRE.
        Retorna filas afectadas.
        """
        sql = """
            UPDATE descalificaciones_fase_a
            SET comentario = ?
            WHERE licitacion_id IN (
                SELECT id FROM licitaciones WHERE institucion = ?
            )
            AND participante_nombre = ?
            AND documento_id IN (
                SELECT d.id
                FROM documentos d
                JOIN licitaciones l ON l.id = d.licitacion_id
                WHERE d.nombre = ? AND l.institucion = ?
            )
        """
        cur = self.conn.execute(sql, (comentario, institucion, participante, documento, institucion))
        self.conn.commit()
        return cur.rowcount


    # (Opcional) utilitario por si quieres insertar rápidamente:
    def insertar_falla(self, institucion, participante, documento, es_nuestro=False, comentario=""):
        """
        Inserta una fila de falla. Útil para pruebas o cargas manuales.
        """
        sql = """
            INSERT INTO fallas_fase_a (institucion, participante_nombre, documento_nombre, es_nuestro, comentario)
            VALUES (?, ?, ?, ?, ?)
        """
        self.conn.execute(sql, (institucion, participante, documento, int(bool(es_nuestro)), comentario))
        self.conn.commit()

    def asegurar_indices_fallas(self):
        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_fallas_by_lic_doc_part
            ON descalificaciones_fase_a(licitacion_id, documento_id, participante_nombre)
        """)
        self.conn.commit()


    # ===== FIN BLOQUE =====
# ===== SUBSANACIONES =====
    def registrar_eventos_subsanacion(self, licitacion_id, eventos):
        """Registra una lista de nuevos eventos de subsanación.
        'eventos' es una lista de tuplas: (documento_id, fecha_limite, comentario)
        """
        sql = """
            INSERT INTO subsanacion_historial 
            (licitacion_id, documento_id, fecha_solicitud, fecha_limite_entrega, comentario, estado)
            VALUES (?, ?, ?, ?, ?, 'Pendiente')
        """
        fecha_solicitud = datetime.date.today().isoformat()
        datos_para_insertar = [
            (licitacion_id, doc_id, fecha_solicitud, fecha_limite, comentario)
            for doc_id, fecha_limite, comentario in eventos
        ]
        self.cursor.executemany(sql, datos_para_insertar)
        self.conn.commit()

    def completar_evento_subsanacion(self, licitacion_id, documento_id, doc_codigo=None):
        """
        Marca como 'Completado' todos los eventos de subsanación 'Pendiente'
        para (licitacion_id, documento_id). Si no encuentra por documento_id,
        intenta por código de documento (doc_codigo) para el caso de IDs cambiados.
        También registra fecha_entrega_real.
        """
        import datetime
        fecha_entrega = datetime.date.today().isoformat()

        # 1) Intento directo por documento_id
        sql1 = """
            UPDATE subsanacion_historial
            SET estado = 'Completado',
                fecha_entrega_real = ?
            WHERE licitacion_id = ?
            AND documento_id = ?
            AND UPPER(TRIM(estado)) = 'PENDIENTE'
        """
        cur = self.cursor.execute(sql1, (fecha_entrega, licitacion_id, int(documento_id)))
        afectados = cur.rowcount or 0

        # 2) Si no tocó nada y me pasaron doc_codigo, intento por código (por si cambió el ID)
        if afectados == 0 and doc_codigo:
            sql2 = """
                UPDATE subsanacion_historial
                SET estado = 'Completado',
                    fecha_entrega_real = ?
                WHERE licitacion_id = ?
                AND documento_id IN (
                        SELECT id
                        FROM documentos
                        WHERE licitacion_id = ?
                        AND codigo = ?
                    )
                AND UPPER(TRIM(estado)) = 'PENDIENTE'
            """
            cur2 = self.cursor.execute(sql2, (fecha_entrega, licitacion_id, licitacion_id, doc_codigo))
            afectados = cur2.rowcount or 0

        self.conn.commit()

        # Log simple para depurar si no encontró filas
        if afectados == 0:
            print(f"[WARN] No se encontraron eventos 'Pendiente' para lic={licitacion_id}, "
                f"doc_id={documento_id}, codigo={doc_codigo}")




    def obtener_historial_subsanacion(self, licitacion_id):
        """Obtiene el historial de subsanaciones para una licitación."""
        sql = """
            SELECT h.fecha_solicitud, d.codigo, d.nombre, h.fecha_limite_entrega, h.estado, h.comentario
            FROM subsanacion_historial h
            JOIN documentos d ON d.id = h.documento_id
            WHERE h.licitacion_id = ?
            ORDER BY h.fecha_solicitud DESC, d.nombre ASC
        """
        self.cursor.execute(sql, (licitacion_id,))
        return self.cursor.fetchall()


    def existe_evento_subsanacion_pendiente(self, licitacion_id, documento_id):
        """Verifica si ya existe un evento de subsanación pendiente para un documento específico."""
        sql = "SELECT 1 FROM subsanacion_historial WHERE licitacion_id = ? AND documento_id = ? AND estado = 'Pendiente' LIMIT 1"
        self.cursor.execute(sql, (licitacion_id, documento_id))
        return self.cursor.fetchone() is not None
    

    def backfill_empresa_nuestra_en_ganadores(self):
        """
        Completa empresa_nuestra en licitacion_ganadores_lote cuando esté NULL,
        normaliza 'ganador_nombre' y usa la tabla/columna REAL de empresas_nuestras.
        Retorna tupla: (normalizados, exactos, por_coincidencia)
        """
        # 0) Normalizar strings comunes en ganador_nombre
        cur1 = self.conn.execute("""
            UPDATE licitacion_ganadores_lote
            SET ganador_nombre = TRIM(REPLACE(ganador_nombre, ' (Nuestra Oferta)', ''))
            WHERE ganador_nombre LIKE '%(Nuestra Oferta)%'
        """)
        normalizados = cur1.rowcount if cur1.rowcount is not None else 0

        # 1) Resolver tabla y columna de empresas_nuestras
        tabla_en, col_nombre = self._resolver_tabla_y_columna_empresas_nuestras()

        # 2) Asignación EXACTA: ganador_nombre == una de nuestras empresas participantes
        sql_exacta = f"""
            UPDATE licitacion_ganadores_lote AS g
            SET empresa_nuestra = (
                SELECT en.{col_nombre}
                FROM {tabla_en} en
                WHERE en.licitacion_id = g.licitacion_id
                AND LOWER(TRIM(en.{col_nombre})) = LOWER(TRIM(g.ganador_nombre))
            )
            WHERE g.empresa_nuestra IS NULL
        """
        cur2 = self.conn.execute(sql_exacta)
        exactos = cur2.rowcount if cur2.rowcount is not None else 0

        # 3) Asignación por COINCIDENCIA (contiene)
        sql_like = f"""
            UPDATE licitacion_ganadores_lote AS g
            SET empresa_nuestra = (
                SELECT en.{col_nombre}
                FROM {tabla_en} en
                WHERE en.licitacion_id = g.licitacion_id
                AND INSTR(LOWER(g.ganador_nombre), LOWER(en.{col_nombre})) > 0
                LIMIT 1
            )
            WHERE g.empresa_nuestra IS NULL
        """
        cur3 = self.conn.execute(sql_like)
        por_coincidencia = cur3.rowcount if cur3.rowcount is not None else 0

        self.conn.commit()
        return normalizados, exactos, por_coincidencia

    def _normalizar_nombre(self, s: str) -> str:
        return (s or "").strip().lower().replace(" (nuestra oferta)", "")

    def obtener_resumen_y_historial_empresa(self, nombre_empresa: str):
        """
        KPIs + historial para una empresa nuestra.
        Auto-detecta tabla/columna de empresas_nuestras y columnas de 'lotes'.
        """
        tabla_en, col_nombre = self._resolver_tabla_y_columna_empresas_nuestras()
        col_num_lote, col_monto_lote = self._resolver_cols_lotes()
        nombre_emp_norm = self._normalizar_nombre(nombre_empresa)

        # --- Historial: lotes ganados por esta empresa ---
        # g.empresa_nuestra preferida; si está NULL, caer a ganador_nombre normalizado o 'contiene'
        sql_hist = f"""
            WITH ganados AS (
                SELECT
                    g.licitacion_id,
                    g.lote_numero,
                    COALESCE(g.empresa_nuestra, g.ganador_nombre) AS ganador_resuelto
                FROM licitacion_ganadores_lote g
                WHERE
                    LOWER(TRIM(COALESCE(g.empresa_nuestra, ''))) = ?
                    OR LOWER(TRIM(REPLACE(g.ganador_nombre, ' (Nuestra Oferta)', ''))) = ?
                    OR INSTR(LOWER(g.ganador_nombre), ?) > 0
            )
            SELECT
                li.numero_proceso        AS proceso,
                li.institucion           AS institucion,
                li.nombre_proceso        AS nombre_licitacion,
                COALESCE(lo.{col_monto_lote}, 0.0) AS monto_adjudicado,
                'Ganador (1 lote)'       AS resultado,
                g.licitacion_id,
                g.lote_numero
            FROM ganados g
            JOIN licitaciones li
            ON li.id = g.licitacion_id
            LEFT JOIN lotes lo
            ON lo.licitacion_id = g.licitacion_id
            AND CAST(lo.{col_num_lote} AS TEXT) = CAST(g.lote_numero AS TEXT)
            ORDER BY COALESCE(li.fecha_creacion, li.id) DESC
        """
        cur = self.conn.execute(sql_hist, (nombre_emp_norm, nombre_emp_norm, nombre_emp_norm))
        historial = [{
            "proceso": r[0],
            "institucion": r[1],
            "nombre_licitacion": r[2],
            "monto_adjudicado": float(r[3] or 0.0),
            "resultado": r[4],
            "licitacion_id": r[5],
            "lote_numero": r[6],
        } for r in cur.fetchall()]

        # --- Participaciones: donde la empresa figura como participante ---
        sql_part = f"""
            SELECT COUNT(DISTINCT en.licitacion_id)
            FROM {tabla_en} en
            WHERE LOWER(TRIM(en.{col_nombre})) = ?
        """
        cur = self.conn.execute(sql_part, (nombre_emp_norm,))
        participaciones = int(cur.fetchone()[0] or 0)

        lotes_ganados = len(historial)
        licitaciones_ganadas = len({h["licitacion_id"] for h in historial})
        monto_total = sum(h["monto_adjudicado"] for h in historial)

        # Institución frecuente
        institucion_frecuente = "N/A"
        if historial:
            from collections import Counter
            inst = Counter([h["institucion"] for h in historial]).most_common(1)
            if inst:
                institucion_frecuente = inst[0][0] or "N/A"

        # Tasa de éxito simple = licitaciones_ganadas / participaciones
        tasa = (licitaciones_ganadas / participaciones * 100.0) if participaciones > 0 else 0.0

        kpis = {
            "participaciones": participaciones,
            "licitaciones_ganadas": licitaciones_ganadas,
            "lotes_ganados": lotes_ganados,
            "monto_total_adjudicado": monto_total,
            "institucion_frecuente": institucion_frecuente,
            "tasa_exito": tasa,
        }
        return kpis, historial

    def _resolver_tabla_y_columna_empresas_nuestras(self):
        """
        Devuelve (tabla_empresas, col_nombre) para la tabla que guarda
        las 'empresas_nuestras' por licitación.
        Busca entre nombres comunes y detecta la columna de 'nombre'.
        Lanza ValueError si no encuentra nada razonable.
        """
        # Candidatos de nombre de tabla (ajusta si usas otro)
        posibles_tablas = [
            "licitacion_empresas_nuestras",
            "empresas_nuestras",
            "licitaciones_empresas_nuestras",
            "lic_empresas_nuestras",
        ]

        # 1) Qué tablas existen en la BD
        cur = self.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existentes = {r[0] for r in cur.fetchall()}

        # 2) Elige la primera que exista
        tabla_ok = None
        for t in posibles_tablas:
            if t in existentes:
                tabla_ok = t
                break
        if not tabla_ok:
            raise ValueError("No se encontró la tabla de 'empresas_nuestras'. Revisa el nombre real en tu esquema.")

        # 3) Detectar la columna de 'nombre'
        cur = self.conn.execute(f"PRAGMA table_info({tabla_ok})")
        cols = [r[1] for r in cur.fetchall()]

        # candidatos habituales para la columna "nombre de la empresa"
        candidatos_nombre = [
            "nombre",
            "empresa_nuestra",
            "empresa",
            "empresa_nombre",
            "nombre_empresa",
            "razon_social",
        ]
        col_nombre = None
        for c in candidatos_nombre:
            if c in cols:
                col_nombre = c
                break
        if not col_nombre:
            raise ValueError(f"No se encontró la columna 'nombre' en la tabla {tabla_ok}. Columnas: {cols}")

        # Verificar que exista licitacion_id también
        if "licitacion_id" not in cols:
            raise ValueError(f"La tabla {tabla_ok} no tiene columna 'licitacion_id'.")

        return tabla_ok, col_nombre

    def _resolver_cols_lotes(self):
        """
        Detecta cómo se llaman las columnas clave en 'lotes':
        - numero del lote
        - monto adjudicado (o sus alternativas)
        Retorna: (col_numero, col_monto)
        """
        cur = self.conn.execute("PRAGMA table_info(lotes)")
        cols = {r[1] for r in cur.fetchall()}

        # posibles nombres para "numero de lote"
        cand_num = ["numero", "lote_numero", "num_lote", "lote", "nro", "nro_lote"]
        col_num = next((c for c in cand_num if c in cols), None)
        if not col_num:
            raise ValueError(f"No se encontró columna de número de lote en 'lotes'. Columnas: {sorted(cols)}")

        # posibles nombres para "monto adjudicado" (caeremos a otras si no existe)
        cand_monto = ["monto_adjudicado", "monto_ofertado", "monto_base", "monto"]
        col_monto = next((c for c in cand_monto if c in cols), None)
        if not col_monto:
            # último recurso: no reventar
            col_monto = "monto_base"

        return col_num, col_monto

    def debug_dump_ganadores_por_licitacion(self, licitacion_id: int):
        out = {"db": []}
        cur = self.conn.execute("""
            SELECT licitacion_id, lote_numero, ganador_nombre, empresa_nuestra
            FROM licitacion_ganadores_lote
            WHERE licitacion_id = ?
            ORDER BY CAST(lote_numero AS INTEGER)
        """, (licitacion_id,))
        out["db"] = [dict(licitacion_id=r[0], lote_numero=str(r[1]), ganador_nombre=r[2], empresa_nuestra=r[3]) for r in cur.fetchall()]
        return out

    def hidratar_ganadores_en_lotes(self, licitacion_obj):
        """Pasa lo guardado en la tabla de ganadores → a los atributos de cada lote del objeto."""
        if not licitacion_obj or not getattr(licitacion_obj, "id", None):
            return
        self.cursor.execute("""
            SELECT lote_numero, ganador_nombre, empresa_nuestra
            FROM licitacion_ganadores_lote
            WHERE licitacion_id = ?
        """, (licitacion_obj.id,))
        mapa = {str(r[0]): {"ganador_nombre": r[1], "empresa_nuestra": r[2]} for r in self.cursor.fetchall()}

        # setear en cada lote
        nuestras = {str(e).strip() for e in getattr(licitacion_obj, "empresas_nuestras", [])}
        for l in getattr(licitacion_obj, "lotes", []):
            key = str(getattr(l, "numero", ""))
            if key in mapa:
                info = mapa[key]
                setattr(l, "ganador_nombre", info["ganador_nombre"])
                setattr(l, "empresa_nuestra", info["empresa_nuestra"])
                setattr(l, "ganado_por_nosotros", info["empresa_nuestra"] in nuestras if info["empresa_nuestra"] else False)
   
