from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Iterable, Tuple, List, Dict
import datetime as _dt

from app.core.models import Licitacion, Documento, Lote

KNOWN_MILESTONES_ORDER = (
    "presentacion_ofertas",
    "apertura_ofertas",
    "notificacion",
    "adjudicacion",
    "firma_contrato",
)

@dataclass
class DeadlineInfo:
    key: str
    label: str
    date: _dt.date
    days_left: int

def _parse_date(val) -> Optional[_dt.date]:
    if not val:
        return None
    if isinstance(val, _dt.date):
        return val
    if isinstance(val, str):
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
            try:
                return _dt.datetime.strptime(val.strip(), fmt).date()
            except Exception:
                continue
    return None

def _today() -> _dt.date:
    return _dt.date.today()

def is_finalizada(lic: Licitacion) -> bool:
    # TODO: reemplazar por tu lógica exacta de finalización
    estado = (lic.estado or "").strip().lower()
    if getattr(lic, "adjudicada", False):
        return True
    return estado in {"adjudicada", "desierta", "cancelada", "fases cumplidas"}

def sum_montos_ofertados(lic: Licitacion) -> float:
    lotes: List[Lote] = list(getattr(lic, "lotes", []) or [])
    return float(sum((getattr(l, "monto_ofertado", 0.0) or 0.0) for l in lotes))

def percent_docs(lic: Licitacion) -> float:
    docs: List[Documento] = list(getattr(lic, "documentos_solicitados", []) or [])
    if not docs:
        return 0.0
    # TODO: Ajustar según tu definición (presentado vs revisado vs obligatorio)
    presentados = sum(1 for d in docs if getattr(d, "presentado", False))
    return 100.0 * presentados / max(1, len(docs))

def percent_diff(lic: Licitacion) -> Optional[float]:
    # TODO: Ajustar: ¿% diferencia = (oferta - base) / base? en el agregado de lotes
    lotes: List[Lote] = list(getattr(lic, "lotes", []) or [])
    base = float(sum((getattr(l, "monto_base", 0.0) or 0.0) for l in lotes))
    oferta = float(sum((getattr(l, "monto_ofertado", 0.0) or 0.0) for l in lotes))
    if base <= 0:
        return None
    return 100.0 * (oferta - base) / base

def next_deadline(lic: Licitacion) -> Optional[DeadlineInfo]:
    cronograma: Dict[str, dict] = getattr(lic, "cronograma", {}) or {}
    today = _today()
    best: Optional[Tuple[str, _dt.date]] = None

    for key in KNOWN_MILESTONES_ORDER:
        node = cronograma.get(key) or {}
        d = _parse_date(node.get("fecha") or node.get("date") or node.get("deadline"))
        if not d:
            continue
        if d >= today and (best is None or d < best[1]):
            best = (key, d)

    if not best:
        return None

    key, date = best
    days_left = (date - today).days
    labels = {
        "presentacion_ofertas": "Presentación de Ofertas",
        "apertura_ofertas": "Apertura de Ofertas",
        "notificacion": "Notificación",
        "adjudicacion": "Adjudicación",
        "firma_contrato": "Firma de Contrato",
    }
    return DeadlineInfo(key=key, label=labels.get(key, key), date=date, days_left=days_left)

def restan_text(info: Optional[DeadlineInfo]) -> str:
    if not info:
        return "Fases cumplidas"  # o "--"
    if info.days_left == 0:
        return "Hoy: " + info.label
    if info.days_left == 1:
        return f"Falta 1 día para: {info.label}"
    return f"Faltan {info.days_left} días para: {info.label}"

def urgency_color(info: Optional[DeadlineInfo]) -> str:
    # Devuelve un color CSS para el fondo según urgencia
    if not info:
        return "#e8f5e9"  # verde suave (completo o sin pendientes)
    d = info.days_left
    if d < 0:
        return "#ffebee"  # rojo claro (vencido)
    if d <= 3:
        return "#fff8e1"  # ámbar (muy próximo)
    if d <= 10:
        return "#f1f8e9"  # verde/amarillo (próximo)
    return "transparent"

def format_money(val: Optional[float], currency: str = "RD$") -> str:
    if val is None:
        return "N/D"
    return f"{currency} {val:,.2f}"

def matches_search(lic: Licitacion, s: str) -> bool:
    s = (s or "").strip().lower()
    if not s:
        return True
    haystack = " ".join([
        lic.numero_proceso or "",
        lic.nombre_proceso or "",
        lic.institucion or "",
        lic.estado or "",
    ]).lower()
    return s in haystack

def contains_lote(lic: Licitacion, lotestr: str) -> bool:
    lotestr = (lotestr or "").strip()
    if not lotestr:
        return True
    for l in lic.lotes or []:
        if lotestr in str(getattr(l, "numero", "")):
            return True
    return False

def matches_estado(lic: Licitacion, estado: str) -> bool:
    estado = (estado or "").strip()
    if not estado or estado == "(Todos)":
        return True
    return (lic.estado or "") == estado

def matches_empresa(lic: Licitacion, empresa: str) -> bool:
    empresa = (empresa or "").strip()
    if not empresa or empresa == "(Todas)":
        return True
    empresas = [(str(e) if hasattr(e, "__str__") else getattr(e, "nombre", "")) for e in (lic.empresas_nuestras or [])]
    return empresa in empresas

def sort_key_for_lic(lic: Licitacion) -> Tuple[int, _dt.date, str]:
    """
    Ordenar: primero por proximidad de hito (el más próximo primero), luego número/nombre.
    Para finalizadas: empujar al final.
    """
    fin = is_finalizada(lic)
    info = next_deadline(lic)
    date = info.date if info else _today()
    return (1 if fin else 0, date, lic.numero_proceso or lic.nombre_proceso or "")