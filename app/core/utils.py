from __future__ import annotations
import os
import sys
import json
from typing import Any, Dict, Optional


def as_dict(value: Any, default: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Normaliza un valor a dict:
    - dict -> igual
    - str  -> json.loads si se puede; si no -> {}
    - None/otros -> {}
    """
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return {} if default is None else default
        try:
            return json.loads(s)
        except Exception:
            return {} if default is None else default
    return {} if default is None else default


def obtener_ruta_dropbox() -> Optional[str]:
    """
    Lee la configuración local de Dropbox y devuelve la ruta base si existe.
    """
    try:
        if sys.platform == "win32":
            appdata_path = os.getenv("APPDATA")
            local_appdata_path = os.getenv("LOCALAPPDATA")
            info_json_paths = [
                os.path.join(appdata_path or "", "Dropbox", "info.json"),
                os.path.join(local_appdata_path or "", "Dropbox", "info.json"),
            ]
        else:
            info_json_paths = [os.path.expanduser("~/.dropbox/info.json")]

        for json_path in info_json_paths:
            if os.path.exists(json_path):
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return (data.get("personal") or {}).get("path")
        return None
    except Exception:
        return None


def reconstruir_ruta_absoluta(ruta_guardada: str) -> Optional[str]:
    """
    Convierte una ruta guardada (posiblemente relativa a Dropbox) en una ruta absoluta utilizable.
    """
    if not ruta_guardada:
        return None
    if os.path.isabs(ruta_guardada):
        return ruta_guardada

    dropbox_base = obtener_ruta_dropbox()
    if dropbox_base:
        ruta_norm = ruta_guardada.replace("/", os.sep)
        return os.path.join(dropbox_base, ruta_norm)
    return None