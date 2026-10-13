"""Load the official EFA referee lists from data/raw/efa_lists.csv.

Must run AFTER the registry (names are matched to officials).

    efa_lists.csv   one row = one name on one EFA list
        list, name_ar, region, season_label, source_url

    list: main_committee | international | first_degree_referee

A name is matched to an official through the usual normalization and aliases.
No match is not an error: the lists include people outside our data (women's
football, futsal, committee members). The report shows who is unmatched, so a
spelling difference is noticed and fixed with a recorded alias, never guessed.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from sofara.normalize import normalize_name
from sofara.registry import DataError, read_csv

FILE = "efa_lists"
COLUMNS = ["list", "name_ar", "region", "season_label", "source_url"]
LISTS = ("main_committee", "international", "first_degree_referee")


def load_efa_lists(conn: sqlite3.Connection, raw_dir: Path) -> dict[str, int]:
    """Load efa_lists.csv in one transaction (all or nothing)."""
    problems: list[str] = []
    rows = read_csv(raw_dir / f"{FILE}.csv", COLUMNS, problems)
    lookup = {
        normalize_name(n): i
        for n, i in conn.execute("SELECT name, official_id FROM v_official_lookup")
    }
    conn.execute("BEGIN")
    try:
        for row in rows:
            where = row["_line"]
            if row["list"] not in LISTS:
                problems.append(f"{where}: list must be one of {', '.join(LISTS)}")
                continue
            if not row["name_ar"] or not row["source_url"]:
                problems.append(f"{where}: name_ar and source_url are required")
                continue
            try:
                conn.execute(
                    """INSERT INTO efa_lists (list, name_ar, official_id, region,
                                              season_label, source_url)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        row["list"],
                        row["name_ar"],
                        lookup.get(normalize_name(row["name_ar"])),
                        row["region"],
                        row["season_label"],
                        row["source_url"],
                    ),
                )
            except sqlite3.IntegrityError as e:
                problems.append(f"{where}: rejected by database — {e}")
        if problems:
            raise DataError(problems)
    except Exception:
        conn.rollback()
        raise
    conn.commit()
    return {"efa_lists": conn.execute("SELECT COUNT(*) FROM efa_lists").fetchone()[0]}
