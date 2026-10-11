"""Load match reviews (which matches has someone actually checked?) from data/raw/.

Must run AFTER the registry and the case library (it needs matches and experts).

    match_reviews.csv   one row = one source that went through the refereeing
                        of one whole match
        season, round, home_team, away_team, review_type, expert, source_url,
        published_date, notes_ar

    review_type:
        expert_review -> an expert's review of the match (expert is required)
        press         -> a press round-up of the match's refereeing
        match_review  -> we watched the match ourselves

Why this file exists: without it, "a match with no cases" could mean either
"nothing happened" or "nobody looked". Coverage, and the selection bias that
comes with it, must be measurable (decision 0013).

A review row says the source looked at the match. It does not say the source
discussed every incident, so "reviewed, no cases" is "nothing contested in the
sources we have", not "a perfect match".
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from sofara.cases import _int, _team_lookup
from sofara.normalize import normalize_name
from sofara.registry import DATE_RE, SEASON_RE, DataError, read_csv

FILE = "match_reviews"
COLUMNS = [
    "season",
    "round",
    "home_team",
    "away_team",
    "review_type",
    "expert",
    "source_url",
    "published_date",
    "notes_ar",
]
REVIEW_TYPES = ("expert_review", "press", "match_review")


def load_reviews(conn: sqlite3.Connection, raw_dir: Path) -> dict[str, int]:
    """Load match_reviews.csv in one transaction (all or nothing)."""
    problems: list[str] = []
    rows = read_csv(raw_dir / f"{FILE}.csv", COLUMNS, problems)
    teams = _team_lookup(conn)
    experts = {
        normalize_name(n): i for n, i in conn.execute("SELECT name_ar, expert_id FROM experts")
    }

    conn.execute("BEGIN")
    try:
        for row in rows:
            where = row["_line"]
            ok = True
            if not row["season"] or not SEASON_RE.match(row["season"]):
                problems.append(f"{where}: season '{row['season']}' must look like 2026/27")
                ok = False
            rnd = _int(row["round"], where, "round", problems)
            home = teams.get(normalize_name(row["home_team"] or ""))
            away = teams.get(normalize_name(row["away_team"] or ""))
            for name, tid in ((row["home_team"], home), (row["away_team"], away)):
                if tid is None:
                    problems.append(f"{where}: unknown team '{name}'")
                    ok = False
            if row["review_type"] not in REVIEW_TYPES:
                problems.append(f"{where}: review_type must be one of {', '.join(REVIEW_TYPES)}")
                ok = False
            expert_id = None
            if row["expert"]:
                expert_id = experts.get(normalize_name(row["expert"]))
                if expert_id is None:
                    name = row["expert"]
                    problems.append(f"{where}: unknown expert '{name}' (add it to experts.csv)")
                    ok = False
            elif row["review_type"] == "expert_review":
                problems.append(f"{where}: an expert_review needs the expert's name")
                ok = False
            if not row["source_url"]:
                problems.append(f"{where}: source_url is required")
                ok = False
            if row["published_date"] and not DATE_RE.match(row["published_date"]):
                problems.append(f"{where}: published_date must be YYYY-MM-DD")
                ok = False
            if not ok or rnd is None:
                continue

            match = conn.execute(
                "SELECT match_id FROM matches"
                " WHERE season=? AND round=? AND home_team_id=? AND away_team_id=?",
                (row["season"], rnd, home, away),
            ).fetchone()
            if match is None:
                problems.append(
                    f"{where}: no match {row['home_team']} × {row['away_team']} "
                    f"in round {rnd} of {row['season']} (check home/away order)"
                )
                continue
            try:
                conn.execute(
                    """INSERT INTO match_reviews (match_id, review_type, expert_id,
                           source_url, published_date, notes_ar)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        match[0],
                        row["review_type"],
                        expert_id,
                        row["source_url"],
                        row["published_date"],
                        row["notes_ar"],
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
    return {"match_reviews": conn.execute("SELECT COUNT(*) FROM match_reviews").fetchone()[0]}
