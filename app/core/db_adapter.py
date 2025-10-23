from __future__ import annotations

import datetime
import json
import os
import sqlite3
from typing import Any, Dict, List, Optional

from .models import Documento, Empresa, Licitacion, Lote, Oferente


def _to_bool(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    if v is None:
        return False
    try:
        return bool(int(v))
    except Exception:
        return str(v).strip().lower() in ("true", "t", "yes", "y", "1")


def _now_iso() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


class DatabaseAdapter:
    """
    Adaptador para la base LICITACIONES_GENERALES.db (esquema normalizado).
    """

    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None

    @property
    def schema(self) -> str:
        return "normalized"

    def open(self, db_path: Optional[str] = None) -> None:
        self.db_path = db_path or self.db_path
        if not self.db_path:
            raise ValueError("No se especificó la ruta de la base de datos.")
        dirn = os.path.dirname(self.db_path)
        if dirn:
            os.makedirs(dirn, exist_ok=True)

        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")

    def close(self) -> None:
        if self.conn:
            try:
                self.conn.close()
            finally:
                self.conn = None

    # ----------------------------
    # Lectura principal
    # ----------------------------
    def list_licitaciones(self) -> List[Licitacion]:
        if not self.conn:
            raise RuntimeError("DB no abierta.")
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT
                id, numero_proceso, nombre_proceso, institucion, estado, fecha_creacion, last_modified
            FROM licitaciones
            ORDER BY COALESCE(last_modified, '') DESC, id DESC
            """
        )
        res: List[Licitacion] = []
        for r in cur.fetchall():
            res.append(
                Licitacion(
                    id=r["id"],
                    numero_proceso=r["numero_proceso"] or "",
                    nombre_proceso=r["nombre_proceso"] or "",
                    institucion=r["institucion"] or "",
                    estado=r["estado"] or "Iniciada",
                    fecha_creacion=r["fecha_creacion"] or str(datetime.date.today()),
                )
            )
        return res

    def load_licitacion_by_id(self, lic_id: int) -> Optional[Licitacion]:
        if not self.conn:
            raise RuntimeError("DB no abierta.")
        cur = self.conn.cursor()

        cur.execute("SELECT * FROM licitaciones WHERE id = ?", (lic_id,))
        row = cur.fetchone()
        if not row:
            return None

        lic = Licitacion(
            id=row["id"],
            nombre_proceso=row["nombre_proceso"] or "",
            numero_proceso=row["numero_proceso"] or "",
            institucion=row["institucion"] or "",
            estado=row["estado"] or "Iniciada",
            fase_A_superada=_to_bool(row["fase_A_superada"]) if "fase_A_superada" in row.keys() else False,
            fase_B_superada=_to_bool(row["fase_B_superada"]) if "fase_B_superada" in row.keys() else False,
            adjudicada=_to_bool(row["adjudicada"]) if "adjudicada" in row.keys() else False,
            adjudicada_a=row["adjudicada_a"] or "" if "adjudicada_a" in row.keys() else "",
            motivo_descalificacion=row["motivo_descalificacion"] or "" if "motivo_descalificacion" in row.keys() else "",
            docs_completos_manual=_to_bool(row["docs_completos_manual"]) if "docs_completos_manual" in row.keys() else False,
            last_modified=row["last_modified"] if "last_modified" in row.keys() else None,
            fecha_creacion=row["fecha_creacion"] or str(datetime.date.today()),
        )

        # JSON de licitaciones
        try:
            lic.cronograma = json.loads(row["cronograma"] or "{}") if "cronograma" in row.keys() else {}
        except Exception:
            lic.cronograma = {}
        try:
            lic._parametros_evaluacion = json.loads(row["parametros_evaluacion"] or "{}") if "parametros_evaluacion" in row.keys() else {}
        except Exception:
            lic._parametros_evaluacion = {}

        # Empresas nuestras
        cur.execute(
            "SELECT empresa_nombre FROM licitacion_empresas_nuestras WHERE licitacion_id = ? ORDER BY id ASC",
            (lic_id,),
        )
        empresas = [Empresa(r["empresa_nombre"]) for r in cur.fetchall()]
        lic.empresas_nuestras = empresas

        # Lotes
        cur.execute(
            """
            SELECT id, numero, nombre, monto_base, monto_base_personal, monto_ofertado,
                   participamos, fase_A_superada, ganador_oferente, empresa_nuestra
            FROM lotes
            WHERE licitacion_id = ?
            ORDER BY id ASC
            """,
            (lic_id,),
        )
        lotes: List[Lote] = []
        for r in cur.fetchall():
            l = Lote(
                id=r["id"],
                numero=str(r["numero"] or ""),
                nombre=r["nombre"] or "",
                monto_base=float(r["monto_base"] or 0.0),
                monto_base_personal=float(r["monto_base_personal"] or 0.0),
                monto_ofertado=float(r["monto_ofertado"] or 0.0),
                participamos=_to_bool(r["participamos"]),
                fase_A_superada=_to_bool(r["fase_A_superada"]),
                ganador_nombre=r["ganador_oferente"] or "",
                empresa_nuestra=r["empresa_nuestra"] or None,
            )
            l.ganado_por_nosotros = l.empresa_nuestra is not None and (l.ganador_nombre or "").strip() == (l.empresa_nuestra or "").strip()
            lotes.append(l)
        lic.lotes = lotes

        # Oferentes y sus ofertas
        cur.execute(
            "SELECT id, nombre, comentario FROM oferentes WHERE licitacion_id = ? ORDER BY id ASC",
            (lic_id,),
        )
        oferentes: List[Oferente] = []
        for r in cur.fetchall():
            of = Oferente(nombre=r["nombre"] or "", comentario=r["comentario"] or "", ofertas_por_lote=[])
            # Ofertas del oferente
            cur2 = self.conn.cursor()
            cur2.execute(
                """
                SELECT lote_numero, monto, paso_fase_A, plazo_entrega, garantia_meses
                FROM ofertas_lote_oferentes
                WHERE oferente_id = ?
                ORDER BY id ASC
                """,
                (r["id"],),
            )
            ofertas = []
            for ro in cur2.fetchall():
                ofertas.append(
                    {
                        "lote_numero": str(ro["lote_numero"] or ""),
                        "monto": float(ro["monto"] or 0.0),
                        "paso_fase_A": _to_bool(ro["paso_fase_A"]),
                        "plazo_entrega": int(ro["plazo_entrega"] or 0),
                        "garantia_meses": int(ro["garantia_meses"] or 0),
                    }
                )
            of.ofertas_por_lote = ofertas
            oferentes.append(of)
        lic.oferentes_participantes = oferentes

        # Documentos
        cur.execute(
            """
            SELECT id, codigo, nombre, categoria, comentario, presentado, subsanable, ruta_archivo,
                   responsable, revisado, obligatorio, orden_pliego, requiere_subsanacion
            FROM documentos
            WHERE licitacion_id = ?
            ORDER BY COALESCE(orden_pliego, 999999), id ASC
            """,
            (lic_id,),
        )
        documentos: List[Documento] = []
        for r in cur.fetchall():
            documentos.append(
                Documento(
                    id=r["id"],
                    codigo=r["codigo"] or "",
                    nombre=r["nombre"] or "",
                    categoria=r["categoria"] or "",
                    comentario=r["comentario"] or "",
                    presentado=_to_bool(r["presentado"]),
                    subsanable=r["subsanable"] or "Subsanable",
                    ruta_archivo=r["ruta_archivo"] or "",
                    empresa_nombre=None,
                    responsable=r["responsable"] or "Sin Asignar",
                    revisado=_to_bool(r["revisado"]),
                    obligatorio=_to_bool(r["obligatorio"]),
                    orden_pliego=int(r["orden_pliego"]) if r["orden_pliego"] is not None else None,
                    requiere_subsanacion=_to_bool(r["requiere_subsanacion"]),
                )
            )
        lic.documentos_solicitados = documentos

        return lic

    # ----------------------------
    # Escritura
    # ----------------------------
    def save_licitacion(self, licitacion: Licitacion) -> int:
        if not self.conn:
            raise RuntimeError("DB no abierta.")
        cur = self.conn.cursor()

        empresa_principal = (licitacion.empresas_nuestras[0].nombre if licitacion.empresas_nuestras else None)

        if licitacion.id is None:
            cur.execute(
                """
                INSERT INTO licitaciones (
                    nombre_proceso, numero_proceso, institucion, empresa_nuestra, estado,
                    fase_A_superada, fase_B_superada, adjudicada, adjudicada_a,
                    motivo_descalificacion, fecha_creacion, cronograma, docs_completos_manual,
                    bnb_score, last_modified, parametros_evaluacion
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    licitacion.nombre_proceso,
                    licitacion.numero_proceso,
                    licitacion.institucion,
                    empresa_principal,
                    licitacion.estado,
                    int(_to_bool(licitacion.fase_A_superada)),
                    int(_to_bool(licitacion.fase_B_superada)),
                    int(_to_bool(licitacion.adjudicada)),
                    licitacion.adjudicada_a,
                    licitacion.motivo_descalificacion,
                    str(licitacion.fecha_creacion),
                    json.dumps(licitacion.cronograma or {}, ensure_ascii=False),
                    int(_to_bool(licitacion.docs_completos_manual)),
                    float(getattr(licitacion, "bnb_score", -1.0) or -1.0),
                    _now_iso(),
                    json.dumps(licitacion.parametros_evaluacion or {}, ensure_ascii=False),
                ),
            )
            lic_id = int(cur.lastrowid)
        else:
            lic_id = int(licitacion.id)
            cur.execute(
                """
                UPDATE licitaciones SET
                    nombre_proceso = ?, numero_proceso = ?, institucion = ?, empresa_nuestra = ?, estado = ?,
                    fase_A_superada = ?, fase_B_superada = ?, adjudicada = ?, adjudicada_a = ?,
                    motivo_descalificacion = ?, fecha_creacion = ?, cronograma = ?, docs_completos_manual = ?,
                    bnb_score = ?, last_modified = ?, parametros_evaluacion = ?
                WHERE id = ?
                """,
                (
                    licitacion.nombre_proceso,
                    licitacion.numero_proceso,
                    licitacion.institucion,
                    empresa_principal,
                    licitacion.estado,
                    int(_to_bool(licitacion.fase_A_superada)),
                    int(_to_bool(licitacion.fase_B_superada)),
                    int(_to_bool(licitacion.adjudicada)),
                    licitacion.adjudicada_a,
                    licitacion.motivo_descalificacion,
                    str(licitacion.fecha_creacion),
                    json.dumps(licitacion.cronograma or {}, ensure_ascii=False),
                    int(_to_bool(licitacion.docs_completos_manual)),
                    float(getattr(licitacion, "bnb_score", -1.0) or -1.0),
                    _now_iso(),
                    json.dumps(licitacion.parametros_evaluacion or {}, ensure_ascii=False),
                    lic_id,
                ),
            )

        # Empresas nuestras
        cur.execute("DELETE FROM licitacion_empresas_nuestras WHERE licitacion_id = ?", (lic_id,))
        for e in licitacion.empresas_nuestras or []:
            cur.execute(
                "INSERT OR IGNORE INTO licitacion_empresas_nuestras (licitacion_id, empresa_nombre) VALUES (?, ?)",
                (lic_id, e.nombre),
            )

        # Lotes
        cur.execute("DELETE FROM lotes WHERE licitacion_id = ?", (lic_id,))
        for l in licitacion.lotes or []:
            cur.execute(
                """
                INSERT INTO lotes (
                    licitacion_id, numero, nombre, monto_base, monto_base_personal, monto_ofertado,
                    participamos, fase_A_superada, ganador_oferente, empresa_nuestra
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    lic_id,
                    str(l.numero or ""),
                    l.nombre or "",
                    float(l.monto_base or 0.0),
                    float(getattr(l, "monto_base_personal", 0.0) or 0.0),
                    float(l.monto_ofertado or 0.0),
                    int(_to_bool(getattr(l, "participamos", True))),
                    int(_to_bool(getattr(l, "fase_A_superada", True))),
                    getattr(l, "ganador_nombre", "") or "",
                    l.empresa_nuestra or None,
                ),
            )

        # Oferentes (ofertas se borran en cascada)
        cur.execute("DELETE FROM oferentes WHERE licitacion_id = ?", (lic_id,))
        for o in licitacion.oferentes_participantes or []:
            cur.execute(
                "INSERT INTO oferentes (licitacion_id, nombre, comentario) VALUES (?, ?, ?)",
                (lic_id, o.nombre or "", o.comentario or ""),
            )
            oferente_id = int(cur.lastrowid)
            for of in o.ofertas_por_lote or []:
                cur.execute(
                    """
                    INSERT INTO ofertas_lote_oferentes
                        (oferente_id, lote_numero, monto, paso_fase_A, plazo_entrega, garantia_meses)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        oferente_id,
                        str(of.get("lote_numero") or ""),
                        float(of.get("monto") or 0.0),
                        int(_to_bool(of.get("paso_fase_A"))),
                        int(of.get("plazo_entrega") or 0),
                        int(of.get("garantia_meses") or 0),
                    ),
                )

        # Documentos
        cur.execute("DELETE FROM documentos WHERE licitacion_id = ?", (lic_id,))
        for d in licitacion.documentos_solicitados or []:
            cur.execute(
                """
                INSERT INTO documentos (
                    licitacion_id, codigo, nombre, categoria, comentario, presentado, subsanable, ruta_archivo,
                    responsable, revisado, obligatorio, orden_pliego, requiere_subsanacion
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    lic_id,
                    d.codigo or "",
                    d.nombre or "",
                    d.categoria or "",
                    d.comentario or "",
                    int(_to_bool(d.presentado)),
                    d.subsanable or "Subsanable",
                    d.ruta_archivo or "",
                    d.responsable or "Sin Asignar",
                    int(_to_bool(d.revisado)),
                    int(_to_bool(d.obligatorio)),
                    int(d.orden_pliego) if d.orden_pliego is not None else None,
                    int(_to_bool(getattr(d, "requiere_subsanacion", False))),
                ),
            )

        self.conn.commit()
        return lic_id

    # ----------------------------
    # Helpers de “maestros”
    # ----------------------------
    def _list_single_col(self, sql: str) -> List[str]:
        if not self.conn:
            return []
        try:
            cur = self.conn.cursor()
            cur.execute(sql)
            return [r[0] for r in cur.fetchall() if r[0] is not None]
        except Exception:
            return []

    def list_responsables_maestros(self) -> List[str]:
        return self._list_single_col("SELECT nombre FROM responsables_maestros ORDER BY nombre ASC")

    def list_empresas_maestras(self) -> List[str]:
        return self._list_single_col("SELECT nombre FROM empresas_maestras ORDER BY nombre ASC")

    def list_categorias(self) -> List[str]:
        return self._list_single_col("SELECT nombre FROM categorias ORDER BY nombre ASC")

    def list_instituciones_maestras(self) -> List[str]:
        return self._list_single_col("SELECT nombre FROM instituciones_maestras ORDER BY nombre ASC")