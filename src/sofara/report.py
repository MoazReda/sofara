"""Data-quality report: coverage, bias and open issues, in one command.

Usage (from the repository root):
    sofara-report                 # builds into memory from data/raw and prints Markdown
    sofara-report --db data/sofara.db

Everything here is computed from the data, so the numbers in the README can
always be checked against it.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

from sofara.build import DEFAULT_RAW, apply_schema, connect
from sofara.cases import load_cases
from sofara.registry import DataError, load_all

ROLES_ON_CARDS = ("referee", "assistant_1", "assistant_2", "fourth", "var", "avar")


def _one(conn: sqlite3.Connection, sql: str) -> int:
    return conn.execute(sql).fetchone()[0] or 0


def _table(headers: list[str], rows: list[tuple]) -> list[str]:
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return out


def report(conn: sqlite3.Connection) -> str:
    """Return the full report as Markdown."""
    lines: list[str] = ["# Sofara data report", ""]

    # ---- coverage per round -------------------------------------------------
    lines += ["## Matches and crews", ""]
    placeholders = ",".join(f"'{r}'" for r in ROLES_ON_CARDS)
    rows = conn.execute(f"""
        SELECT m.round, COUNT(*),
               (SELECT COUNT(DISTINCT t) FROM (
                    SELECT home_team_id t FROM matches x WHERE x.round = m.round
                    UNION SELECT away_team_id FROM matches x WHERE x.round = m.round)),
               SUM((SELECT COUNT(*) FROM match_officials mo
                    WHERE mo.match_id = m.match_id AND mo.role IN ({placeholders})) = 6),
               SUM(m.source NOT LIKE 'http%' OR m.source IS NULL)
        FROM matches m GROUP BY m.round ORDER BY m.round""").fetchall()
    lines += _table(
        ["round", "matches", "teams", "full 6-person crew", "source without a link"], rows
    )
    # (no quotes reused inside f-strings: Python 3.10 doesn't allow it)
    officials = _one(conn, "SELECT COUNT(*) FROM officials")
    aliases = _one(conn, "SELECT COUNT(*) FROM official_aliases")
    referees = _one(
        conn, "SELECT COUNT(DISTINCT official_id) FROM match_officials WHERE role = 'referee'"
    )
    lines += [
        "",
        f"Officials: {officials}, aliases: {aliases}, distinct centre referees: {referees}",
        "",
    ]

    # ---- case library -------------------------------------------------------
    n_cases = _one(conn, "SELECT COUNT(*) FROM incidents")
    n_matches = _one(conn, "SELECT COUNT(*) FROM matches")
    covered = _one(conn, "SELECT COUNT(DISTINCT match_id) FROM incidents")
    lines += [
        "## Case library",
        "",
        f"Cases: **{n_cases}** from **{covered} of {n_matches}** matches.",
        "",
    ]
    lines += _table(
        ["found via", "cases"],
        conn.execute("SELECT found_via, COUNT(*) FROM incidents GROUP BY 1 ORDER BY 2 DESC"),
    )
    lines += [""]
    lines += _table(
        ["VAR involvement", "cases", "decision changed"],
        conn.execute("""SELECT var_review, COUNT(*), SUM(var_changed)
                        FROM v_incident_summary GROUP BY 1 ORDER BY 2 DESC"""),
    )
    lines += [""]
    lines += _table(
        ["status", "cases"],
        conn.execute("SELECT status, COUNT(*) FROM v_incident_summary GROUP BY 1"),
    )

    # ---- selection bias -----------------------------------------------------
    lines += ["", "## Selection bias: cases per team", ""]
    lines += _table(
        ["team", "cases", "share"],
        [
            (name, n, f"{n / n_cases:.0%}" if n_cases else "-")
            for name, n in conn.execute("""
                SELECT t.name_ar, COUNT(DISTINCT i.incident_id) FROM incidents i
                JOIN matches m USING (match_id)
                JOIN teams t ON t.team_id IN (m.home_team_id, m.away_team_id)
                GROUP BY t.name_ar ORDER BY 2 DESC, 1""")
        ],
    )

    # ---- opinions -------------------------------------------------------------
    lines += ["", "## Expert opinions", ""]
    lines += _table(
        ["background", "experts", "opinions", "agree", "disagree", "unclear"],
        conn.execute("""
            SELECT COALESCE(e.background, 'unknown'), COUNT(DISTINCT e.expert_id), COUNT(*),
                   SUM(o.stance = 'agree'), SUM(o.stance = 'disagree'), SUM(o.stance = 'unclear')
            FROM expert_opinions o JOIN experts e USING (expert_id)
            GROUP BY 1 ORDER BY 3 DESC"""),
    )

    # ---- open issues ------------------------------------------------------------
    checks = [
        ("match events (goals and cards) collected", "SELECT COUNT(*) FROM match_events", True),
        ("cases without a minute", "SELECT COUNT(*) FROM incidents WHERE minute IS NULL", False),
        (
            "cases with unknown VAR involvement",
            "SELECT COUNT(*) FROM incidents WHERE var_review = 'unknown'",
            False,
        ),
        (
            "cases without a video link",
            "SELECT COUNT(*) FROM incidents WHERE video_url IS NULL",
            False,
        ),
        (
            "cases without any expert opinion",
            "SELECT COUNT(*) FROM incidents i WHERE NOT EXISTS "
            "(SELECT 1 FROM expert_opinions o WHERE o.incident_id = i.incident_id)",
            False,
        ),
        (
            "sources marked as pending",
            "SELECT (SELECT COUNT(*) FROM matches WHERE source LIKE '%pending%')"
            " + (SELECT COUNT(*) FROM incidents WHERE source_url LIKE '%pending%')",
            False,
        ),
        (
            "experts with unknown background",
            "SELECT COUNT(*) FROM experts WHERE background IS NULL",
            False,
        ),
    ]
    lines += ["", "## Open issues", ""]
    for label, sql, want_nonzero in checks:
        n = _one(conn, sql)
        ok = (n > 0) if want_nonzero else (n == 0)
        lines.append(f"- {'✅' if ok else '⚠️'} {label}: {n}")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", type=Path, help="read an existing database instead of building")
    parser.add_argument("--raw", type=Path, default=DEFAULT_RAW)
    args = parser.parse_args(argv)
    if args.db:
        conn = connect(args.db)
    else:
        conn = connect(":memory:")
        apply_schema(conn)
        try:
            load_all(conn, args.raw)
            load_cases(conn, args.raw)
        except DataError as e:
            print("Data does not build — run sofara-build to see the problems.")
            print(f"({len(e.problems)} problem(s))")
            return 1
    sys.stdout.reconfigure(encoding="utf-8")  # Arabic on a Windows console
    print(report(conn))
    return 0


if __name__ == "__main__":
    sys.exit(main())
