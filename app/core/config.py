from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional
from PyQt6.QtCore import QStandardPaths


CONFIG_BASENAME = "licitaciones_config.json"


def _config_dir() -> str:
    # Carpeta estándar para config de la app (por usuario/sistema)
    cfg_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppConfigLocation)
    if not cfg_dir:
        cfg_dir = os.path.join(os.path.expanduser("~"), ".zoeccivil", "licitaciones")
    os.makedirs(cfg_dir, exist_ok=True)
    return cfg_dir


def config_path() -> str:
    return os.path.join(_config_dir(), CONFIG_BASENAME)


def load_config() -> Dict[str, Any]:
    path = config_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_config(data: Dict[str, Any]) -> None:
    path = config_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def get_db_path_from_config() -> Optional[str]:
    cfg = load_config()
    p = cfg.get("db_path")
    if isinstance(p, str) and p.strip():
        return p
    return None


def set_db_path_in_config(db_path: str) -> None:
    cfg = load_config()
    cfg["db_path"] = db_path
    save_config(cfg)


def default_db_path() -> str:
    # Ruta por defecto para crear una DB si no existe config
    cfg_dir = _config_dir()
    return os.path.join(cfg_dir, "licitaciones.db")