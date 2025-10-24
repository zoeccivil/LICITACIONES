#!/usr/bin/env python3
import argparse
import hashlib
import importlib.util
import os
import re
import sqlite3
import sys
from datetime import datetime

MIGRATION_RE = re.compile(r"^(\d{4})_([a-zA-Z0-9_]+)\.(sql|py)$")

def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def read_file_bytes(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()

def ensure_schema_migrations(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
          id INTEGER PRIMARY KEY,
          name TEXT NOT NULL,
          applied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f','now')),
          checksum TEXT NOT NULL
        )
    """)
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_schema_migrations_id ON schema_migrations(id)")

def list_migration_files(dir_path: str):
    entries = []
    for fname in os.listdir(dir_path):
        m = MIGRATION_RE.match(fname)
        if not m:
            continue
        mig_id = int(m.group(1))
        name = m.group(2)
        kind = m.group(3)
        entries.append((mig_id, name, kind, os.path.join(dir_path, fname), fname))
    entries.sort(key=lambda x: x[0])
    return entries

def get_applied(conn: sqlite3.Connection):
    cur = conn.execute("SELECT id, name, checksum FROM schema_migrations ORDER BY id")
    return {row[0]: (row[1], row[2]) for row in cur.fetchall()}

def exec_sql_script(conn: sqlite3.Connection, sql_bytes: bytes):
    # Use executescript for multi-statement SQL
    conn.executescript(sql_bytes.decode("utf-8"))

def exec_py_migration(conn: sqlite3.Connection, file_path: str):
    spec = importlib.util.spec_from_file_location("migration_module", file_path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader, "Cannot load migration module"
    spec.loader.exec_module(mod)
    if not hasattr(mod, "upgrade") or not callable(mod.upgrade):
        raise RuntimeError(f"Python migration {file_path} must define upgrade(conn)")
    mod.upgrade(conn)

def apply_migration(conn: sqlite3.Connection, mig_id: int, name: str, kind: str, path: str, dry_run: bool):
    raw = read_file_bytes(path)
    checksum = sha256_bytes(raw)

    # Checksum drift check for already-applied migrations
    cur = conn.execute("SELECT checksum FROM schema_migrations WHERE id=?", (mig_id,))
    row = cur.fetchone()
    if row:
        if row[0] != checksum:
            raise RuntimeError(f"Checksum mismatch for migration {mig_id}_{name} (file changed).")
        # Already applied and checksum matches: skip
        return False

    if dry_run:
        print(f"[DRY-RUN] Would apply {mig_id:04d}_{name}.{kind}")
        return False

    # Apply inside a transaction
    try:
        conn.execute("BEGIN IMMEDIATE")
        if kind == "sql":
            exec_sql_script(conn, raw)
        else:
            exec_py_migration(conn, path)
        conn.execute(
            "INSERT INTO schema_migrations (id, name, applied_at, checksum) VALUES (?,?,?,?)",
            (mig_id, name, datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f"), checksum),
        )
        conn.commit()
        print(f"Applied {mig_id:04d}_{name}.{kind}")
        return True
    except Exception as e:
        conn.rollback()
        raise

def main():
    parser = argparse.ArgumentParser(description="SQLite migrations runner")
    parser.add_argument("--db", required=True, help="Ruta al archivo .db (SQLite)")
    parser.add_argument("--migrations", default="migrations", help="Directorio de migraciones")
    parser.add_argument("--dry-run", action="store_true", help="Simular sin aplicar cambios")
    parser.add_argument("--target", type=int, help="Aplicar hasta este ID inclusive (ej: 2 aplica 0001 y 0002)")
    args = parser.parse_args()

    if not os.path.exists(args.db):
        print(f"ERROR: No existe la base de datos: {args.db}", file=sys.stderr)
        sys.exit(2)
    if not os.path.isdir(args.migrations):
        print(f"ERROR: No existe el directorio de migraciones: {args.migrations}", file=sys.stderr)
        sys.exit(2)

    conn = sqlite3.connect(args.db)
    conn.execute("PRAGMA foreign_keys = ON")
    ensure_schema_migrations(conn)

    files = list_migration_files(args.migrations)
    if args.target is not None:
        files = [f for f in files if f[0] <= args.target]

    applied = get_applied(conn)
    changed = 0
    for mig_id, name, kind, path, fname in files:
        try:
            changed |= bool(apply_migration(conn, mig_id, name, kind, path, args.dry_run))
        except Exception as e:
            print(f"ERROR applying {fname}: {e}", file=sys.stderr)
            sys.exit(1)

    if not changed:
        print("No hay migraciones pendientes.")
    else:
        print("Migraciones aplicadas correctamente.")

if __name__ == "__main__":
    main()