from __future__ import annotations

import os
import shutil
import datetime as _dt
from typing import Any, Dict, List, Optional, Tuple

# Modelos de tu app (mantener estos imports)
from .models import Documento, Empresa, Licitacion, Lote, Oferente

# Intentamos importar tu DatabaseManager legado (glicitaciones2.py/db_manager.py)
try:
    # Caso común: db_manager.py está en la raíz del proyecto
    from db_manager import DatabaseManager  # type: ignore
except Exception:
    # Alternativa por si lo moviste dentro del paquete
    from app.core.db_manager import DatabaseManager  # type: ignore


def _to_bool(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    if v is None:
        return False
    try:
        return bool(int(v))
    except Exception:
        return str(v).strip().lower() in ("true", "t", "yes", "y", "1")


def _to_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v if v is not None else default)
    except Exception:
        return default


class DatabaseAdapter:
    """
    Adaptador usado por la UI PyQt6 que envuelve tu DatabaseManager legado.
    - Provee métodos esperados por la UI actual (open, close, load_all_licitaciones, load_licitacion_by_id,
      load_licitacion_by_numero, save_licitacion, etc.).
    - Mapea los dicts devueltos por DatabaseManager.get_all_data() a instancias de tus modelos
      Licitacion/Lote/Documento/Oferente/Empresa para que el Dashboard pueda calcular %Docs, %Dif., etc.
    """

    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path: Optional[str] = db_path
        self.mgr: Optional[DatabaseManager] = None

    # Compatibilidad con código que lee self.path
    @property
    def path(self) -> Optional[str]:
        return self.db_path

    @property
    def schema(self) -> str:
        # Conservamos este valor porque la UI lo muestra en la barra de estado
        return "normalized"

    # ----------------------------
    # Ciclo de vida
    # ----------------------------
    def open(self, db_path: Optional[str] = None) -> None:
        self.db_path = db_path or self.db_path
        if not self.db_path:
            raise ValueError("No se especificó la ruta de la base de datos.")
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)

        # Instancia y asegura esquema (DatabaseManager ya lo hace en __init__)
        self.mgr = DatabaseManager(self.db_path)
        # Opcional: timeout para locks
        try:
            self.mgr.set_busy_timeout(8)
        except Exception:
            pass

    def close(self) -> None:
        if self.mgr:
            try:
                self.mgr.close()
            finally:
                self.mgr = None

    @staticmethod
    def create_new_db(path: str) -> None:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        mgr = DatabaseManager(path)
        mgr.close()

    # ----------------------------
    # Lectura
    # ----------------------------
    def load_all_licitaciones(self) -> List[Licitacion]:
        """
        Carga TODAS las licitaciones con sus relaciones (similar al Tk).
        Se apoya en DatabaseManager.get_all_data() y mapea a objetos de modelo.
        """
        if not self.mgr:
            raise RuntimeError("DB no abierta.")
        data = self.mgr.get_all_data()  # [licitaciones], empresas_maestras, instituciones_maestras, ...
        raw_list = data[0] if data else []
        return [self._map_licitacion_dict_to_model(d) for d in raw_list]

    def list_licitaciones(self) -> List[Licitacion]:
        """
        Alias por compatibilidad; devuelve lo mismo que load_all_licitaciones.
        """
        return self.load_all_licitaciones()

    def load_licitacion_by_id(self, lic_id: int) -> Optional[Licitacion]:
        if not self.mgr:
            raise RuntimeError("DB no abierta.")
        licitaciones = self.load_all_licitaciones()
        for lic in licitaciones:
            if int(getattr(lic, "id", 0) or 0) == int(lic_id):
                return lic
        return None

    def get_licitacion_by_id(self, lic_id: int):
        """Compatibilidad: alias de load_licitacion_by_id para la UI."""
        return self.load_licitacion_by_id(lic_id)

    def load_licitacion_by_numero(self, numero: str) -> Optional[Licitacion]:
        if not self.mgr:
            raise RuntimeError("DB no abierta.")
        num_norm = (numero or "").strip().lower()
        for lic in self.load_all_licitaciones():
            n = (getattr(lic, "numero_proceso", "") or "").strip().lower()
            if n == num_norm:
                return lic
        return None

    # ----------------------------
    # Escritura
    # ----------------------------
    def save_licitacion(self, licitacion: Licitacion) -> int:
        """
        Persiste la licitación usando DatabaseManager.save_licitacion(licitacion).
        Tu modelo Licitacion debe implementar to_dict() (ya lo hace en tu base).
        """
        if not self.mgr:
            raise RuntimeError("DB no abierta.")
        ok = self.mgr.save_licitacion(licitacion)
        if not ok:
            raise RuntimeError("No se pudo guardar la licitación (save_licitacion retornó False).")
        return int(getattr(licitacion, "id", 0) or 0)

    # ----------------------------
    # Utilitarios
    # ----------------------------
    def create_backup(self, dst_path: str) -> None:
        if not self.db_path or not os.path.exists(self.db_path):
            raise FileNotFoundError(self.db_path or "")
        os.makedirs(os.path.dirname(dst_path) or ".", exist_ok=True)
        shutil.copy2(self.db_path, dst_path)

    def search_global(self, term: str) -> List[Dict[str, Any]]:
        if not self.mgr:
            return []
        try:
            return self.mgr.search_global(term)
        except Exception:
            return []

    def get_setting(self, clave: str, default: Optional[str] = None) -> Optional[str]:
        if not self.mgr:
            return default
        try:
            return self.mgr.get_setting(clave, default)
        except Exception:
            return default

    def set_setting(self, clave: str, valor: str) -> None:
        if not self.mgr:
            return
        try:
            self.mgr.set_setting(clave, valor)
        except Exception:
            pass

    # Opcionales (pueden ser útiles luego en la UI)
    def run_sanity_checks(self) -> Dict[str, Any]:
        if not self.mgr:
            return {}
        try:
            return self.mgr.run_sanity_checks()
        except Exception:
            return {}

    def auto_repair(self, issues: Dict[str, Any]) -> Tuple[bool, str]:
        if not self.mgr:
            return False, "DB no abierta."
        try:
            return self.mgr.auto_repair(issues)
        except Exception as e:
            return False, str(e)

    # ----------------------------
    # Mapeadores Dict -> Modelos
    # ----------------------------
    def _map_licitacion_dict_to_model(self, d: Dict[str, Any]) -> Licitacion:
        """
        Construye una instancia de Licitacion (tu modelo) a partir del dict de DatabaseManager.get_all_data().
        Incluye lotes, documentos, oferentes y empresas_nuestras.
        """
        # Cabecera
        lic = Licitacion(
            id=d.get("id"),
            nombre_proceso=d.get("nombre_proceso") or d.get("nombre") or "",
            numero_proceso=d.get("numero_proceso") or d.get("numero") or "",
            institucion=d.get("institucion") or "",
            estado=d.get("estado") or d.get("estatus") or "Iniciada",
            fase_A_superada=_to_bool(d.get("fase_A_superada")),
            fase_B_superada=_to_bool(d.get("fase_B_superada")),
            adjudicada=_to_bool(d.get("adjudicada")),
            adjudicada_a=d.get("adjudicada_a") or "",
            motivo_descalificacion=d.get("motivo_descalificacion") or "",
            fecha_creacion=d.get("fecha_creacion") or str(_dt.date.today()),
            empresas_nuestras=[],  # se setea abajo
        )

        # Cronograma y parámetros evaluación
        lic.cronograma = d.get("cronograma") or {}
        try:
            # Algunos dumps ya vienen como dict; si fuera str JSON, intentar parsear
            if isinstance(lic.cronograma, str):
                import json
                lic.cronograma = json.loads(lic.cronograma or "{}")
        except Exception:
            lic.cronograma = {}

        try:
            params = d.get("parametros_evaluacion", {})
            if isinstance(params, str):
                import json
                params = json.loads(params or "{}")
            # Algunos modelos usan un setter .parametros_evaluacion; si no existe, mantener _parametros_evaluacion
            if hasattr(lic, "parametros_evaluacion"):
                setattr(lic, "parametros_evaluacion", params)
            else:
                setattr(lic, "_parametros_evaluacion", params)
        except Exception:
            pass

        # Empresas nuestras
        en_list = d.get("empresas_nuestras") or []
        lic.empresas_nuestras = [Empresa(e["nombre"]) if isinstance(e, dict) else Empresa(str(e)) for e in en_list]

        # Lotes
        lic.lotes = [self._map_lote_dict_to_model(l) for l in (d.get("lotes") or [])]

        # Oferentes
        lic.oferentes_participantes = [self._map_oferente_dict_to_model(o) for o in (d.get("oferentes_participantes") or [])]

        # Documentos
        lic.documentos_solicitados = [self._map_documento_dict_to_model(doc) for doc in (d.get("documentos_solicitados") or [])]

        # Enriquecimiento: bandera ganada (si adjudicada_a coincide o hay lotes ganados_por_nosotros)
        try:
            emp_set = {e.nombre.strip().lower() for e in lic.empresas_nuestras}
            ganada_por_empresa = _to_bool(lic.adjudicada) and (lic.adjudicada_a or "").strip().lower() in emp_set if lic.adjudicada_a else False
            ganada_por_lote = any(getattr(l, "ganado_por_nosotros", False) for l in lic.lotes)
            setattr(lic, "ganada", bool(ganada_por_empresa or ganada_por_lote))
        except Exception:
            pass

        # last_modified si viene
        if "last_modified" in d:
            setattr(lic, "last_modified", d.get("last_modified"))

        return lic

    def _map_lote_dict_to_model(self, l: Dict[str, Any]) -> Lote:
        return Lote(
            id=l.get("id"),
            numero=str(l.get("numero") or ""),
            nombre=l.get("nombre") or "",
            monto_base=_to_float(l.get("monto_base"), 0.0),
            monto_base_personal=_to_float(l.get("monto_base_personal"), 0.0),
            monto_ofertado=_to_float(l.get("monto_ofertado"), 0.0),
            participamos=_to_bool(l.get("participamos")),
            fase_A_superada=_to_bool(l.get("fase_A_superada")),
            ganador_nombre=l.get("ganador_nombre") or "",
            empresa_nuestra=l.get("empresa_nuestra") or None,
            ganado_por_nosotros=_to_bool(l.get("ganado_por_nosotros")),
        )

    def _map_documento_dict_to_model(self, d: Dict[str, Any]) -> Documento:
        return Documento(
            id=d.get("id"),
            codigo=d.get("codigo") or "",
            nombre=d.get("nombre") or "",
            categoria=d.get("categoria") or "",
            comentario=d.get("comentario") or "",
            presentado=_to_bool(d.get("presentado")),
            subsanable=d.get("subsanable") or "Subsanable",
            ruta_archivo=d.get("ruta_archivo") or "",
            empresa_nombre=None,  # no se usa aquí
            responsable=d.get("responsable") or "Sin Asignar",
            revisado=_to_bool(d.get("revisado")),
            obligatorio=_to_bool(d.get("obligatorio")),
            orden_pliego=int(d.get("orden_pliego")) if d.get("orden_pliego") is not None else None,
            requiere_subsanacion=_to_bool(d.get("requiere_subsanacion")),
        )

    def _map_oferente_dict_to_model(self, o: Dict[str, Any]) -> Oferente:
        of = Oferente(nombre=o.get("nombre") or "", comentario=o.get("comentario") or "", ofertas_por_lote=[])
        offers = []
        for it in (o.get("ofertas_por_lote") or []):
            offers.append(
                {
                    "lote_numero": str(it.get("lote_numero") or ""),
                    "monto": _to_float(it.get("monto"), 0.0),
                    "paso_fase_A": _to_bool(it.get("paso_fase_A")),
                    "plazo_entrega": int(it.get("plazo_entrega") or 0),
                    "garantia_meses": int(it.get("garantia_meses") or 0),
                    # el flag 'ganador' lo hidrata db_manager para algunos casos; si existe, lo pasamos
                    **({"ganador": _to_bool(it.get("ganador"))} if "ganador" in it else {}),
                }
            )
        of.ofertas_por_lote = offers
        return of

