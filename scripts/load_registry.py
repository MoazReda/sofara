"""Load the hand-collected CSVs in data/raw/ into the database.

CSV files (all UTF-8; Excel: "CSV UTF-8" format):
    teams.csv              name_ar, name_en
    team_aliases.csv       alias, team_name_ar, source
    officials.csv          name_ar, name_en, nationality, region, official_type
    official_aliases.csv   alias, official_name_ar, source
    crews.csv              season, round, match_date, kickoff_time, stadium,
                           home_team, away_team, referee, assistant_1,
                           assistant_2, fourth, var, avar, commissioner,
                           assessor, source_url

Why crews.csv is "wide" (one row per match) while match_officials is
"long" (one row per person per role): the CSV is designed for a human
typing from a news article, the table is designed for queries. This
loader converts one into the other.

Strict by design: every problem in every file is collected, reported
together, and NOTHING is written. Unknown names are never guessed —
add them to officials.csv or official_aliases.csv and re-run.
"""
from __future__ import annotations

import csv
import re
import sqlite3
from collections import defaultdict
from pathlib import Path

from normalize import normalize_name

ROLES = ["referee", "assistant_1", "assistant_2", "fourth", "var", "avar",
         "commissioner", "assessor"]
DEFAULTS = {"nationality": "Egypt", "official_type": "referee"}
DATE_RE =re.compile(r"^\d{4}-\d{2}-\d{2}$")
SEASON_RE = re.compile(r"^\d{4}/\d{2}$")
TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")

FILES = {
    "teams": ["name_ar", "name_en"],
    "team_aliases": ["alias", "team_name_ar", "source"],
    "officials": ["name_ar", "name_en", "nationality", "region", "official_type"],
    "official_aliases": ["alias", "official_name_ar", "source"],
    "crews": ["season", "round", "match_date", "kickoff_time", "stadium",
              "home_team", "away_team", *ROLES, "source_url"],
}


class DataError(Exception):
    """Raised with the full list of problems found in the raw data."""

    def __init__(self, problems: list[str]):
        self.problems = problems
        super().__init__(f"{len(problems)} problem(s) in raw data:\n- " + "\n- ".join(problems))


# ---------------------------------------------------------------------------
# reading
# ---------------------------------------------------------------------------

def read_csv(path: Path, expected: list[str], problems: list[str]) -> list[dict]:
    """Read a CSV into dicts (stripped values, '' -> None). Missing file = empty."""
    if not path.exists():
        return []
    # utf-8-sig drops the BOM that Excel adds on Windows
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames or []
        if header != expected:
            problems.append(f"{path.name}: header is {header}, expected {expected}")
            return []
        rows = []
        for line_no, raw in enumerate(reader, start=2):   # line 1 is the header
            row = {k: (v.strip() or None) if isinstance(v, str) else None
                   for k, v in raw.items()}
            row["_line"] = f"{path.name}:{line_no}"
            rows.append(row)
        return rows


# ---------------------------------------------------------------------------
# lookups: normalized name -> id
# ---------------------------------------------------------------------------

def _register(lookup: dict, name: str, entity_id: int, where: str, problems: list[str]) -> None:
    key = normalize_name(name)
    if key in lookup and lookup[key] != entity_id:
        problems.append(f"{where}: '{name}' already points to a different entity")
    lookup[key] = entity_id


def _load_entities(conn, rows, aliases, table, id_col, alias_table, alias_fk,
                   alias_name_col, columns, problems):
    """Insert canonical entities + their aliases; return the lookup dict."""
    lookup: dict[str, int] = {}
    for i, row in enumerate(rows, start=1):
        if not row["name_ar"]:
            problems.append(f"{row['_line']}: name_ar is empty")
            continue
        # empty cell -> the schema's default (e.g. nationality 'Egypt')
        values = [row[c] if row[c] is not None else DEFAULTS.get(c) for c in columns]
        placeholders = ", ".join("?" * (len(columns) + 1))
        try:
            conn.execute(
                f"INSERT INTO {table} ({id_col}, {', '.join(columns)}) VALUES ({placeholders})",
                [i, *values],
            )
        except sqlite3.IntegrityError as e:
            problems.append(f"{row['_line']}: {e}")
            continue
        _register(lookup, row["name_ar"], i, row["_line"], problems)
        if row.get("name_en"):
            _register(lookup, row["name_en"], i, row["_line"], problems)

    for row in aliases:
        target = lookup.get(normalize_name(row[alias_name_col]))
        if target is None:
            problems.append(f"{row['_line']}: alias '{row['alias']}' points to "
                            f"unknown name '{row[alias_name_col]}'")
            continue
        try:
            conn.execute(
                f"INSERT INTO {alias_table} (alias, {alias_fk}, source) VALUES (?, ?, ?)",
                (row["alias"], target, row["source"]),
            )
        except sqlite3.IntegrityError as e:
            problems.append(f"{row['_line']}: {e}")
            continue
        _register(lookup, row["alias"], target, row["_line"], problems)
    return lookup


# ---------------------------------------------------------------------------
# crews
# ---------------------------------------------------------------------------

def _load_crews(conn, rows, team_lookup, official_lookup, problems):
    unknown_teams: dict[str, list[str]] = defaultdict(list)
    unknown_officials: dict[str, list[str]] = defaultdict(list)
    busy: dict[tuple, str] = {}          # (official_id, date) -> where
    team_rounds: dict[tuple, str] = {}   # (season, round, team_id) -> where
    parsed = []

    for row in rows:
        where = row["_line"]
        ok = True

        if not row["season"] or not SEASON_RE.match(row["season"]):
            problems.append(f"{where}: season '{row['season']}' must look like 2026/27")
            ok = False
        if not row["round"] or not row["round"].isdigit():
            problems.append(f"{where}: round '{row['round']}' must be a whole number")
            ok = False
        if not row["match_date"] or not DATE_RE.match(row["match_date"]):
            problems.append(f"{where}: match_date '{row['match_date']}' must be YYYY-MM-DD")
            ok = False
        if row["kickoff_time"] and not TIME_RE.match(row["kickoff_time"]):
            problems.append(f"{where}: kickoff_time '{row['kickoff_time']}' must be HH:MM (24h)")
            ok = False

        teams = {}
        for side in ("home_team", "away_team"):
            tid = team_lookup.get(normalize_name(row[side] or ""))
            if tid is None:
                unknown_teams[row[side] or "<empty>"].append(where)
                ok = False
            teams[side] = tid
        if ok and teams["home_team"] == teams["away_team"]:
            problems.append(f"{where}: home and away are the same team")
            ok = False

        crew = {}
        for role in ROLES:
            name = row[role]
            if name is None:
                continue                      # role not announced
            oid = official_lookup.get(normalize_name(name))
            if oid is None:
                unknown_officials[name].append(f"{where} ({role})")
                ok = False
                continue
            if oid in crew.values():
                problems.append(f"{where}: '{name}' appears in two roles in the same match")
                ok = False
            crew[role] = oid
        if "referee" not in crew and row["referee"] is None:
            problems.append(f"{where}: referee is empty")
            ok = False

        if not ok:
            continue

        # cross-row checks
        for oid in crew.values():
            key = (oid, row["match_date"])
            if key in busy:
                problems.append(f"{where}: an official is already assigned on "
                                f"{row['match_date']} at {busy[key]}")
            busy[key] = where
        for tid in teams.values():
            key = (row["season"], int(row["round"]), tid)
            if key in team_rounds:
                problems.append(f"{where}: a team plays twice in round {row['round']} "
                                f"(also {team_rounds[key]})")
            team_rounds[key] = where

        parsed.append((row, teams, crew))

    for name, places in sorted(unknown_teams.items()):
        problems.append(f"Unknown team '{name}' at {', '.join(places)} "
                        f"-> add to teams.csv or team_aliases.csv")
    for name, places in sorted(unknown_officials.items()):
        problems.append(f"Unknown official '{name}' at {', '.join(places)} "
                        f"-> add to officials.csv or official_aliases.csv")

    for row, teams, crew in parsed:
        try:
            cur = conn.execute(
                """INSERT INTO matches (season, round, match_date, kickoff_time, stadium,
                       home_team_id, away_team_id, source)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (row["season"], int(row["round"]), row["match_date"], row["kickoff_time"],
                 row["stadium"], teams["home_team"], teams["away_team"], row["source_url"]),
            )
        except sqlite3.IntegrityError as e:
            problems.append(f"{row['_line']}: {e}")
            continue
        conn.executemany(
            "INSERT INTO match_officials (match_id, official_id, role) VALUES (?, ?, ?)",
            [(cur.lastrowid, oid, role) for role, oid in crew.items()],
        )


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------

def load_all(conn: sqlite3.Connection, raw_dir: Path) -> dict[str, int]:
    """Load every raw CSV in one transaction. Raises DataError, writing nothing,
    if any problem is found. Returns row counts per table on success."""
    problems: list[str] = []
    data = {name: read_csv(raw_dir / f"{name}.csv", cols, problems)
            for name, cols in FILES.items()}

    conn.execute("BEGIN")
    try:
        team_lookup = _load_entities(
            conn, data["teams"], data["team_aliases"], "teams", "team_id",
            "team_aliases", "team_id", "team_name_ar", ["name_ar", "name_en"], problems)
        official_lookup = _load_entities(
            conn, data["officials"], data["official_aliases"], "officials", "official_id",
            "official_aliases", "official_id", "official_name_ar",
            ["name_ar", "name_en", "nationality", "region", "official_type"], problems)
        _load_crews(conn, data["crews"], team_lookup, official_lookup, problems)
        if problems:
            raise DataError(problems)
    except Exception:
        conn.rollback()
        raise
    conn.commit()

    return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in ("teams", "officials", "matches", "match_officials")}
