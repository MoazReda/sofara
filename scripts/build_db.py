"""Build the Sofara SQLite database: schema + all hand-collected CSVs.

The database is a *derived* file: data/raw/*.csv is the source of truth.
To fix data, edit the CSV and rebuild — never edit the .db by hand.

Usage:
    python scripts/build_db.py                 # -> data/sofara.db (overwrites)
    python scripts/build_db.py --db path.db
    python scripts/build_db.py --schema-only   # empty database
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

from load_registry import DataError, load_all

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "db" / "schema.sql"
RAW_DIR = ROOT / "data" / "raw"
DEFAULT_DB = ROOT / "data" / "sofara.db"


def connect(db_path: str | Path = ":memory:") -> sqlite3.Connection:
    """Open a connection with foreign keys enforced (SQLite default is OFF).
    isolation_level=None: we manage transactions explicitly."""
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def apply_schema(conn: sqlite3.Connection, schema_path: Path = SCHEMA_PATH) -> None:
    """Create all tables, indexes and views."""
    conn.executescript(schema_path.read_text(encoding="utf-8"))


def build(db_path: Path, raw_dir: Path = RAW_DIR, schema_only: bool = False) -> dict:
    # build into a temp file first, so a failed build never destroys a good db
    tmp = db_path.with_suffix(".tmp")
    tmp.unlink(missing_ok=True)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(tmp)
    try:
        apply_schema(conn)
        counts = {} if schema_only else load_all(conn, raw_dir)
    finally:
        conn.close()
    tmp.replace(db_path)
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--raw", type=Path, default=RAW_DIR)
    parser.add_argument("--schema-only", action="store_true")
    args = parser.parse_args()
    try:
        counts = build(args.db, args.raw, args.schema_only)
    except DataError as e:
        print(f"BUILD FAILED — nothing written. Fix these in {args.raw}:\n")
        for p in e.problems:
            print(f"  - {p}")
        args.db.with_suffix(".tmp").unlink(missing_ok=True)
        sys.exit(1)
    print(f"Built {args.db}")
    for table, n in counts.items():
        print(f"  {table:<16} {n}")


if __name__ == "__main__":
    main()
