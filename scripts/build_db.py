"""Build the Sofara SQLite database from db/schema.sql.

Usage:
    python scripts/build_db.py                 # -> data/sofara.db
    python scripts/build_db.py --db path.db    # custom location
    python scripts/build_db.py --force         # overwrite existing file
"""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "db" / "schema.sql"
DEFAULT_DB = ROOT / "data" / "sofara.db"


def connect(db_path: str | Path = ":memory:") -> sqlite3.Connection:
    """Open a connection with foreign keys enforced (SQLite default is OFF)."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def apply_schema(conn: sqlite3.Connection, schema_path: Path = SCHEMA_PATH) -> None:
    """Create all tables, indexes and views."""
    conn.executescript(schema_path.read_text(encoding="utf-8"))
    conn.commit()


def build(db_path: Path, force: bool = False) -> Path:
    if db_path.exists():
        if not force:
            raise SystemExit(f"{db_path} already exists. Use --force to rebuild.")
        db_path.unlink()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(db_path)
    apply_schema(conn)
    conn.close()
    return db_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    path = build(args.db, args.force)
    print(f"Built {path}")


if __name__ == "__main__":
    main()
