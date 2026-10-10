"""Load expert commendations ("best of the round" posts) from data/raw/.

Must run AFTER the registry and the case library (it needs officials, crews
and experts).

    commendations.csv   one row = one expert naming one official as a best
                        performer in one category in one round
        expert, season, round, category, official, reasons_ar, source_url,
        published_date

    category: referee | assistant | var
        referee   -> the official was the centre referee that round
        assistant -> assistant_1 or assistant_2
        var       -> var or avar

The match is not typed: it is resolved from season + round + official +
category, and must be exactly one match in the crew data. A commendation that
doesn't match the crews is reported, never guessed.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from sofara.normalize import normalize_name
from sofara.registry import DATE_RE, DataError, read_csv

FILE = "commendations"
COLUMNS = [
    "expert",
    "season",
    "round",
    "category",
    "official",
    "reasons_ar",
    "source_url",
    "published_date",
]
ROLES = {
    "referee": ("referee",),
    "assistant": ("assistant_1", "assistant_2"),
    "var": ("var", "avar"),
}


def _lookup(conn: sqlite3.Connection, sql: str) -> dict[str, int]:
    return {normalize_name(name): i for name, i in conn.execute(sql)}


def load_commendations(conn: sqlite3.Connection, raw_dir: Path) -> dict[str, int]:
    """Load commendations.csv in one transaction (all or nothing)."""
    problems: list[str] = []
    rows = read_csv(raw_dir / f"{FILE}.csv", COLUMNS, problems)
    experts = _lookup(conn, "SELECT name_ar, expert_id FROM experts")
    officials = _lookup(conn, "SELECT name, official_id FROM v_official_lookup")

    conn.execute("BEGIN")
    try:
        for row in rows:
            where = row["_line"]
            expert_id = experts.get(normalize_name(row["expert"] or ""))
            official_id = officials.get(normalize_name(row["official"] or ""))
            roles = ROLES.get(row["category"] or "")
            if expert_id is None:
                problems.append(f"{where}: unknown expert '{row['expert']}'")
            if official_id is None:
                problems.append(f"{where}: unknown official '{row['official']}'")
            if roles is None:
                problems.append(f"{where}: category must be one of {', '.join(ROLES)}")
            if not (row["round"] or "").isdigit():
                problems.append(f"{where}: round '{row['round']}' must be a whole number")
                continue
            if row["published_date"] and not DATE_RE.match(row["published_date"]):
                problems.append(f"{where}: published_date must be YYYY-MM-DD")
            if expert_id is None or official_id is None or roles is None:
                continue

            marks = ",".join("?" * len(roles))
            matches = conn.execute(
                f"""SELECT DISTINCT m.match_id FROM matches m
                    JOIN match_officials mo ON mo.match_id = m.match_id
                    WHERE m.season = ? AND m.round = ? AND mo.official_id = ?
                      AND mo.role IN ({marks})""",
                (row["season"], int(row["round"]), official_id, *roles),
            ).fetchall()
            if len(matches) != 1:
                found = "no match" if not matches else f"{len(matches)} matches"
                problems.append(
                    f"{where}: '{row['official']}' has {found} as {row['category']} "
                    f"in round {row['round']} of {row['season']} — check the crew data"
                )
                continue
            try:
                conn.execute(
                    """INSERT INTO expert_commendations (expert_id, official_id, match_id,
                           category, reasons_ar, source_url, published_date)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        expert_id,
                        official_id,
                        matches[0][0],
                        row["category"],
                        row["reasons_ar"],
                        row["source_url"],
                        row["published_date"],
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
    return {
        "expert_commendations": conn.execute(
            "SELECT COUNT(*) FROM expert_commendations"
        ).fetchone()[0]
    }
