#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import sys
import json
import sqlite3
from typing import Any, Dict, List, Optional


def select_db_via_tk() -> Optional[str]:
    """
    Abre un diálogo (tkinter) para seleccionar el archivo .db.
    Devuelve la ruta seleccionada o None si se cancela.
    """
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception:
        return None  # tkinter no disponible

    root = tk.Tk()
    root.withdraw()
    filetypes = [
        ("SQLite DB", "*.db *.sqlite *.sqlite3"),
        ("Todos los archivos", "*.*"),
    ]
    path = filedialog.askopenfilename(
        title="Selecciona tu base de datos SQLite",
        filetypes=filetypes,
    )
    try:
        root.update()
    except Exception:
        pass
    try:
        root.destroy()
    except Exception:
        pass
    return path or None


def rows_to_dicts(rows: List[sqlite3.Row]) -> List[Dict[str, Any]]:
    return [dict(r) for r in rows]


def quote_name(name: str) -> str:
    """
    Devuelve el nombre entre comillas simples y con comillas internas escapadas para PRAGMA.
    PRAGMA no admite parámetros para nombres de tabla, por eso hacemos el escape manual.
    """
    return "'" + (name or "").replace("'", "''") + "'"


def get_table_details(cur: sqlite3.Cursor, table_name: str) -> Dict[str, Any]:
    """
    Devuelve detalles de una tabla: table_info, table_xinfo (si existe), foreign_keys,
    índices (con columnas) y triggers.
    """
    qname = quote_name(table_name)
    out: Dict[str, Any] = {
        "name": table_name,
        "table_info": [],
        "table_xinfo": [],
        "foreign_keys": [],
        "indexes": [],
        "triggers": [],
    }

    # table_info
    cur.execute("PRAGMA table_info(" + qname + ")")
    out["table_info"] = rows_to_dicts(cur.fetchall())

    # table_xinfo (puede no existir)
    try:
        cur.execute("PRAGMA table_xinfo(" + qname + ")")
        out["table_xinfo"] = rows_to_dicts(cur.fetchall())
    except Exception:
        out["table_xinfo"] = []

    # foreign keys
    try:
        cur.execute("PRAGMA foreign_key_list(" + qname + ")")
        out["foreign_keys"] = rows_to_dicts(cur.fetchall())
    except Exception:
        out["foreign_keys"] = []

    # índices
    indexes: List[Dict[str, Any]] = []
    try:
        cur.execute("PRAGMA index_list(" + qname + ")")
        idx_list = rows_to_dicts(cur.fetchall())
        for idx in idx_list:
            idx_name = idx.get("name") or ""
            if not idx_name:
                continue
            idx_entry: Dict[str, Any] = dict(idx)
            idx_qname = quote_name(idx_name)
            try:
                cur.execute("PRAGMA index_info(" + idx_qname + ")")
                idx_entry["columns"] = rows_to_dicts(cur.fetchall())
            except Exception:
                idx_entry["columns"] = []
            indexes.append(idx_entry)
    except Exception:
        pass
    out["indexes"] = indexes

    # triggers relacionados
    try:
        cur.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='trigger' AND tbl_name=? ORDER BY name",
            (table_name,),
        )
        out["triggers"] = rows_to_dicts(cur.fetchall())
    except Exception:
        out["triggers"] = []

    return out


def dump_schema(db_path: str) -> Dict[str, Any]:
    """
    Abre la base y devuelve un dict con el esquema completo:
    - Versión de SQLite
    - Listado de tablas y vistas (name, type, sql)
    - Para cada tabla: PRAGMAs e índices/triggers
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Objetos de esquema (evitar internos sqlite_%)
    cur.execute(
        "SELECT name, type, sql FROM sqlite_master "
        "WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%' "
        "ORDER BY type, name"
    )
    objects = rows_to_dicts(cur.fetchall())

    tables = [o for o in objects if (o.get("type") == "table")]
    views = [o for o in objects if (o.get("type") == "view")]

    data: Dict[str, Any] = {
        "db_path": os.path.abspath(db_path),
        "sqlite_version": sqlite3.sqlite_version,
        "schema": {
            "tables": [],
            "views": views,
        },
    }

    for t in tables:
        t_name = t.get("name", "")
        t_sql = t.get("sql", "")
        t_dump: Dict[str, Any] = {"name": t_name, "sql": t_sql}

        # Añadir PRAGMAs por tabla
        t_dump.update(get_table_details(cur, t_name))
        data["schema"]["tables"].append(t_dump)

    conn.close()
    return data


def print_summary(result: Dict[str, Any]) -> None:
    """
    Imprime un resumen legible del esquema en consola.
    """
    tables = result.get("schema", {}).get("tables", [])
    views = result.get("schema", {}).get("views", [])

    print("SQLite versión:", result.get("sqlite_version"))
    print("Archivo DB:", result.get("db_path"))
    print("Tablas encontradas ({}): {}".format(len(tables), [t.get("name") for t in tables]))
    print("Vistas encontradas ({}): {}".format(len(views), [v.get("name") for v in views]))
    print("\n— Extracto de columnas por tabla —")
    for t in tables:
        cols = t.get("table_info", [])
        human_cols: List[str] = []
        for c in cols:
            cname = c.get("name")
            ctype = c.get("type")
            if ctype:
                human_cols.append("{} ({})".format(cname, ctype))
            else:
                human_cols.append(str(cname))
        print("- {}: {}".format(t.get("name"), ", ".join(human_cols)))


def main():
    # Admite ruta por argumento o abre diálogo si no se pasa
    if len(sys.argv) > 1 and sys.argv[1].strip():
        db_path = sys.argv[1]
    else:
        db_path = select_db_via_tk()

    if not db_path:
        print("No se seleccionó ninguna base de datos. Saliendo.")
        sys.exit(1)

    if not os.path.exists(db_path):
        print("La ruta no existe:", db_path)
        sys.exit(2)

    try:
        result = dump_schema(db_path)
    except Exception as e:
        print("Error al leer la base de datos:", e)
        sys.exit(3)

    # Guardar JSON junto al .db
    base, _ = os.path.splitext(db_path)
    out_json = base + "_schema.json"
    try:
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("No se pudo escribir el JSON:", e)
        sys.exit(4)

    print_summary(result)
    print("\nEsquema detallado guardado en:", out_json)


if __name__ == "__main__":
    main()