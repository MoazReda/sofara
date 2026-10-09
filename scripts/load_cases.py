"""Load the case library (part ب) from data/raw/ into the database.

Must run AFTER load_registry.load_all (cases point at matches and teams).

CSV files (UTF-8; Excel: "CSV UTF-8"):

    incidents.csv        one row = one case, all stages side by side (wide,
                         easy to type). The loader splits it into
                         incidents + incident_decisions.
        case_id, season, round, home_team, away_team, minute, added_minute,
        var_review, found_via, source_url, description_ar, video_url, video_start_sec,
        on_field_offence, on_field_offending_team, on_field_outcome,
        final_offence, final_offending_team, final_outcome,
        official_offence, official_offending_team, official_outcome,
        official_source_url

        - `case_id` is a number you choose; it never changes, so cards and
          opinions can point at it.
        - `minute` may be empty when no source reports it.
        - `var_review` empty = unknown (never assume 'none').
        - `found_via`: press | match_review; `source_url`: where the facts come from.
        - Leave all `final_*` empty when VAR changed nothing (final = on-field).
        - Leave all `official_*` empty unless the committee published a ruling.
        - `*_offending_team` is empty exactly when the offence is `none`.

    incident_cards.csv   one row = one card to one person at one stage
        case_id, stage, team, person_name, sanction, reason

    experts.csv          one row = one expert
        name_ar, background

    expert_opinions.csv  one row = one expert's opinion on one case
        case_id, expert, stance, summary_ar, source_name, source_url,
        published_date

Same rules as the registry loader: every problem in every file is reported
together, nothing is written unless everything is valid, names are never
guessed.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from load_registry import DATE_RE, SEASON_RE, DataError, read_csv
from normalize import normalize_name

STAGES = ("on_field", "final", "official")
DECISION_FIELDS = ("offence", "offending_team", "outcome")

CASE_FILES = {
    "incidents": [
        "case_id", "season", "round", "home_team", "away_team", "minute",
        "added_minute", "var_review", "found_via", "source_url", "description_ar",
        "video_url", "video_start_sec",
        *[f"{s}_{f}" for s in STAGES for f in DECISION_FIELDS],
        "official_source_url",
    ],
    "incident_cards": ["case_id", "stage", "team", "person_name", "sanction", "reason"],
    "experts": ["name_ar", "background"],
    "expert_opinions": ["case_id", "expert", "stance", "summary_ar", "source_name",
                        "source_url", "published_date"],
}


def _int(value, where, field, problems, default=None):
    if value is None:
        return default
    if not value.isdigit():
        problems.append(f"{where}: {field} '{value}' must be a whole number")
        return None
    return int(value)


def _team_lookup(conn) -> dict[str, int]:
    lookup = {normalize_name(n): i for n, i in conn.execute("SELECT name_ar, team_id FROM teams")}
    lookup.update({normalize_name(a): i for a, i in conn.execute("SELECT alias, team_id FROM team_aliases")})
    return lookup


def _insert(conn, sql, params, where, problems) -> bool:
    """Run one insert; turn a database refusal into a readable problem line."""
    try:
        conn.execute(sql, params)
        return True
    except sqlite3.IntegrityError as e:
        problems.append(f"{where}: rejected by database — {e}")
        return False


def _load_incidents(conn, rows, teams, problems) -> set[int]:
    loaded: set[int] = set()
    for row in rows:
        where = row["_line"]
        case_id = _int(row["case_id"], where, "case_id", problems)
        if case_id is None:
            continue
        if case_id in loaded:
            problems.append(f"{where}: case_id {case_id} is used twice")
            continue

        # find the match: season + round + both teams
        ok = True
        if not row["season"] or not SEASON_RE.match(row["season"]):
            problems.append(f"{where}: season '{row['season']}' must look like 2026/27"); ok = False
        rnd = _int(row["round"], where, "round", problems)
        home = teams.get(normalize_name(row["home_team"] or ""))
        away = teams.get(normalize_name(row["away_team"] or ""))
        for name, tid in ((row["home_team"], home), (row["away_team"], away)):
            if tid is None:
                problems.append(f"{where}: unknown team '{name}'"); ok = False
        if not ok or rnd is None:
            continue
        match = conn.execute(
            "SELECT match_id FROM matches WHERE season=? AND round=? AND home_team_id=? AND away_team_id=?",
            (row["season"], rnd, home, away)).fetchone()
        if match is None:
            problems.append(f"{where}: no match {row['home_team']} × {row['away_team']} "
                            f"in round {rnd} of {row['season']} (check home/away order)")
            continue

        minute = _int(row["minute"], where, "minute", problems)
        added = _int(row["added_minute"], where, "added_minute", problems, default=0)
        start = _int(row["video_start_sec"], where, "video_start_sec", problems)
        if (row["minute"] and minute is None) or added is None:
            continue
        if not _insert(conn,
                       """INSERT INTO incidents (incident_id, match_id, minute, added_minute,
                              description_ar, var_review, found_via, source_url,
                              video_url, video_start_sec)
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                       (case_id, match[0], minute, added, row["description_ar"],
                        row["var_review"] or "unknown", row["found_via"], row["source_url"],
                        row["video_url"], start), where, problems):
            continue

        # one decision row per filled stage
        for stage in STAGES:
            values = [row[f"{stage}_{f}"] for f in DECISION_FIELDS]
            if stage != "on_field" and not any(values):
                if stage == "official" and row["official_source_url"]:
                    problems.append(f"{where}: official_source_url given but no official decision")
                continue
            offence, team_name, outcome = values
            if not offence or not outcome:
                problems.append(f"{where}: {stage} needs both offence and outcome")
                continue
            team_id = None
            if team_name:
                team_id = teams.get(normalize_name(team_name))
                if team_id is None:
                    problems.append(f"{where}: {stage}_offending_team: unknown team '{team_name}'")
                    continue
            _insert(conn,
                    """INSERT INTO incident_decisions (incident_id, stage, offence,
                           offending_team_id, outcome, source_url) VALUES (?, ?, ?, ?, ?, ?)""",
                    (case_id, stage, offence, team_id, outcome,
                     row["official_source_url"] if stage == "official" else None),
                    f"{where} ({stage})", problems)
        loaded.add(case_id)
    return loaded


def _load_cards(conn, rows, teams, cases, problems) -> None:
    for row in rows:
        where = row["_line"]
        case_id = _int(row["case_id"], where, "case_id", problems)
        if case_id is None:
            continue
        if case_id not in cases:
            problems.append(f"{where}: case_id {case_id} is not in incidents.csv"); continue
        team_id = teams.get(normalize_name(row["team"] or ""))
        if team_id is None:
            problems.append(f"{where}: unknown team '{row['team']}'"); continue
        has_stage = conn.execute(
            "SELECT 1 FROM incident_decisions WHERE incident_id=? AND stage=?",
            (case_id, row["stage"])).fetchone()
        if not has_stage:
            problems.append(f"{where}: case {case_id} has no '{row['stage']}' decision "
                            f"in incidents.csv, so it can't have a card at that stage")
            continue
        _insert(conn,
                """INSERT INTO incident_sanctions (incident_id, stage, team_id, person_name,
                       sanction, reason) VALUES (?, ?, ?, ?, ?, ?)""",
                (case_id, row["stage"], team_id, row["person_name"], row["sanction"], row["reason"]),
                where, problems)


def _load_experts(conn, rows, problems) -> dict[str, int]:
    lookup: dict[str, int] = {}
    for i, row in enumerate(rows, start=1):
        key = normalize_name(row["name_ar"] or "")
        if not key:
            problems.append(f"{row['_line']}: name_ar is empty"); continue
        if key in lookup:
            problems.append(f"{row['_line']}: expert '{row['name_ar']}' listed twice"); continue
        if _insert(conn, "INSERT INTO experts (expert_id, name_ar, background) VALUES (?, ?, ?)",
                   (i, row["name_ar"], row["background"]), row["_line"], problems):
            lookup[key] = i
    return lookup


def _load_opinions(conn, rows, experts, cases, problems) -> None:
    for row in rows:
        where = row["_line"]
        case_id = _int(row["case_id"], where, "case_id", problems)
        if case_id is None:
            continue
        if case_id not in cases:
            problems.append(f"{where}: case_id {case_id} is not in incidents.csv"); continue
        expert_id = experts.get(normalize_name(row["expert"] or ""))
        if expert_id is None:
            problems.append(f"{where}: unknown expert '{row['expert']}' -> add to experts.csv"); continue
        if row["published_date"] and not DATE_RE.match(row["published_date"]):
            problems.append(f"{where}: published_date must be YYYY-MM-DD"); continue
        _insert(conn,
                """INSERT INTO expert_opinions (incident_id, expert_id, stance, summary_ar,
                       source_name, source_url, published_date) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (case_id, expert_id, row["stance"], row["summary_ar"], row["source_name"],
                 row["source_url"], row["published_date"]), where, problems)


def load_cases(conn: sqlite3.Connection, raw_dir: Path) -> dict[str, int]:
    """Load all case-library CSVs in one transaction (all or nothing)."""
    problems: list[str] = []
    data = {name: read_csv(raw_dir / f"{name}.csv", cols, problems)
            for name, cols in CASE_FILES.items()}
    conn.execute("BEGIN")
    try:
        teams = _team_lookup(conn)
        cases = _load_incidents(conn, data["incidents"], teams, problems)
        _load_cards(conn, data["incident_cards"], teams, cases, problems)
        experts = _load_experts(conn, data["experts"], problems)
        _load_opinions(conn, data["expert_opinions"], experts, cases, problems)
        for iid, problem in conn.execute("SELECT incident_id, problem FROM v_incident_problems"):
            problems.append(f"case {iid}: {problem}")
        if problems:
            raise DataError(problems)
    except Exception:
        conn.rollback()
        raise
    conn.commit()
    return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in ("incidents", "incident_decisions", "incident_sanctions",
                      "experts", "expert_opinions")}
