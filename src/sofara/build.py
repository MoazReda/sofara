"""Build the Sofara SQLite database: schema + all hand-collected CSVs.

The database is a *derived* file: data/raw/*.csv is the source of truth.
To fix data, edit the CSV and rebuild — never edit the .db by hand.

Usage (from the repository root, after `pip install -e .`):
    sofara-build                         # -> data/sofara.db
    sofara-build --db path.db --raw data/raw
    sofara-build --schema-only           # empty database
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from importlib.resources import files
from pathlib import Path

from sofara.cases import load_cases
from sofara.registry import DataError, load_all

DEFAULT_RAW = Path("data/raw")
DEFAULT_DB = Path("data/sofara.db")


def schema_sql() -> str:
    """The schema shipped inside the package (src/sofara/sql/schema.sql)."""
    return files("sofara").joinpath("sql/schema.sql").read_text(encoding="utf-8")


def connect(db_path: str | Path = ":memory:") -> sqlite3.Connection:
    """Open a connection with foreign keys enforced (SQLite default is OFF).
    isolation_level=None: transactions are managed explicitly by the loaders."""
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def apply_schema(conn: sqlite3.Connection) -> None:
    """Create all tables, triggers, indexes and views."""
    conn.executescript(schema_sql())


def build(
    db_path: Path = DEFAULT_DB, raw_dir: Path = DEFAULT_RAW, schema_only: bool = False
) -> dict[str, int]:
    """Build into a temp file first, so a failed build never destroys a good db."""
    tmp = db_path.with_suffix(".tmp")
    tmp.unlink(missing_ok=True)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(tmp)
    try:
        apply_schema(conn)
        counts: dict[str, int] = {}
        if not schema_only:
            counts.update(load_all(conn, raw_dir))
            counts.update(load_cases(conn, raw_dir))
    finally:
        conn.close()
    tmp.replace(db_path)
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--raw", type=Path, default=DEFAULT_RAW)
    parser.add_argument("--schema-only", action="store_true")
    args = parser.parse_args(argv)
    if not args.schema_only and not args.raw.is_dir():
        print(f"No raw data folder at {args.raw.resolve()} — run from the repository root.")
        return 2
    try:
        counts = build(args.db, args.raw, args.schema_only)
    except DataError as e:
        print(f"BUILD FAILED — nothing written. Fix these in {args.raw}:\n")
        for p in e.problems:
            print(f"  - {p}")
        args.db.with_suffix(".tmp").unlink(missing_ok=True)
        return 1
    print(f"Built {args.db}")
    for table, n in counts.items():
        print(f"  {table:<20} {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
