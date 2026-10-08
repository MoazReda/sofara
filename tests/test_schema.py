"""Schema tests.

The fixture is a real match: Al Ahly 3-2 ENPPI, EPL 2026/27, round 1,
taken from the official EFA referee report (facts only).
Each test checks one rule the schema must enforce.
"""
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from build_db import apply_schema, connect  # noqa: E402

SRC = "EFA referee report (via Cairo24)"


@pytest.fixture
def db():
    conn = connect(":memory:")
    apply_schema(conn)
    _seed(conn)
    yield conn
    conn.close()


def _seed(c: sqlite3.Connection) -> None:
    c.executemany(
        "INSERT INTO teams (team_id, name_ar, name_en) VALUES (?, ?, ?)",
        [(1, "الأهلي", "Al Ahly"), (2, "إنبي", "ENPPI")],
    )
    c.executemany(
        "INSERT INTO team_aliases (alias, team_id, source) VALUES (?, ?, ?)",
        [("الاهلي", 1, SRC), ("انبي", 2, SRC)],
    )
    c.executemany(
        "INSERT INTO officials (official_id, name_ar, region, official_type) VALUES (?, ?, ?, ?)",
        [
            (1, "محمود احمد ناجي", "الغربية", "referee"),
            (2, "سمير جمال سعد محمد", "القاهرة", "referee"),
            (3, "محمد مجدي محمد سليمان", "الإسماعيلية", "referee"),
            (4, "هشام اشرف فتحي احمد", "أسيوط", "referee"),
            (5, "اشرف السيد محمد مسعود", "القليوبية", "commissioner"),
            (6, "خالد جمال محمود الغندور", "القاهرة", "referee"),
            (7, "السيد ابراهيم شعبان", "الدقهلية", "referee"),
        ],
    )
    c.execute(
        """INSERT INTO matches (match_id, season, round, match_number, match_date,
               kickoff_time, stadium, city, home_team_id, away_team_id,
               home_goals, away_goals, ht_home_goals, ht_away_goals, source)
           VALUES (1, '2026/27', 1, 10, '2026-08-23', '20:00',
                   'استاد القاهرة الدولي', 'القاهرة', 1, 2, 3, 2, 1, 2, ?)""",
        (SRC,),
    )
    c.executemany(
        "INSERT INTO match_officials (match_id, official_id, role) VALUES (1, ?, ?)",
        [(1, "referee"), (2, "assistant_1"), (3, "assistant_2"), (4, "fourth"),
         (5, "commissioner"), (6, "var"), (7, "avar")],
    )
    # (team, type, minute, added, person_type, name, number, reason, is_pen)
    events = [
        (2, "goal", 17, 0, "player", "علي ايهاب احمد مختار", 19, None, 0),
        (2, "goal", 23, 0, "player", "محمد عصام عبدالصمد صقر", 30, None, 0),
        (1, "goal", 34, 0, "player", "مروان عطيه فهيم غلاب", 13, None, 0),
        (1, "goal", 68, 0, "player", "احمد مصطفي محمد سيد", 25, None, 1),
        (1, "goal", 90, 0, "player", "محمد مجدي محمد مرسي", 19, None, 0),
        (2, "yellow", 76, 0, "player", "حازم محمد ابراهيم عبدالباقي", 32, "unsporting_behaviour", 0),
        (1, "yellow", 90, 5, "player", "مروان عطيه فهيم غلاب", 13, "dissent", 0),
        (2, "yellow", 90, 6, "staff", "احمد عبدالظاهر عبد الجواد درويش", None, "dissent", 0),
        (2, "red", 90, 3, "staff", "محمد عصام حسين احمد", None, "violent_conduct", 0),
    ]
    c.executemany(
        """INSERT INTO match_events (match_id, team_id, event_type, minute, added_minute,
               person_type, person_name, shirt_number, reason, is_penalty, source)
           VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, '""" + SRC + "')",
        events,
    )
    c.commit()


# ---------- the seed itself is consistent ----------

def test_goals_match_final_score(db):
    rows = db.execute(
        """SELECT m.home_goals, m.away_goals,
                  SUM(e.team_id = m.home_team_id), SUM(e.team_id = m.away_team_id)
           FROM matches m JOIN match_events e ON e.match_id = m.match_id
           WHERE e.event_type = 'goal' GROUP BY m.match_id"""
    ).fetchone()
    assert rows == (3, 2, 3, 2)


def test_full_crew_loaded(db):
    assert db.execute("SELECT COUNT(*) FROM match_officials").fetchone()[0] == 7


# ---------- integrity rules ----------

def test_foreign_keys_enforced(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO match_officials VALUES (1, 999, 'var')")


def test_one_person_per_role(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO match_officials VALUES (1, 2, 'referee')")


def test_team_cannot_play_itself(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO matches (season, match_date, home_team_id, away_team_id) "
            "VALUES ('2026/27', '2026-08-30', 1, 1)"
        )


def test_bad_date_format_rejected(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO matches (season, match_date, home_team_id, away_team_id) "
            "VALUES ('2026/27', '23.08.2026', 1, 2)"
        )


def test_added_time_only_at_end_of_half(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO match_events (match_id, team_id, event_type, minute, added_minute) "
            "VALUES (1, 1, 'yellow', 60, 2)"
        )


def test_staff_cannot_score_or_have_number(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO match_events (match_id, team_id, event_type, minute, person_type) "
            "VALUES (1, 1, 'goal', 50, 'staff')"
        )


def test_unknown_card_reason_rejected(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO match_events (match_id, team_id, event_type, minute, reason) "
            "VALUES (1, 1, 'yellow', 50, 'bad_vibes')"
        )


def test_penalty_flag_only_on_goals(db):
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            "INSERT INTO match_events (match_id, team_id, event_type, minute, is_penalty) "
            "VALUES (1, 1, 'yellow', 50, 1)"
        )


# ---------- aliases ----------

def test_alias_resolves_to_same_official(db):
    db.execute("INSERT INTO official_aliases VALUES ('محمود ناجي', 1, 'press')")
    ids = {
        r[0] for r in db.execute(
            "SELECT official_id FROM v_official_lookup WHERE name IN (?, ?)",
            ("محمود احمد ناجي", "محمود ناجي"),
        )
    }
    assert ids == {1}


# ---------- incidents: verdict rules ----------

def _incident(db, verdict=None, url=None):
    db.execute(
        """INSERT INTO incidents (match_id, minute, incident_type, description_ar,
               on_field_decision, final_decision, official_verdict, verdict_source_url)
           VALUES (1, 68, 'penalty', 'وصف تجريبي', 'penalty', 'penalty', ?, ?)""",
        (verdict, url),
    )


def test_verdict_requires_public_source(db):
    with pytest.raises(sqlite3.IntegrityError):
        _incident(db, verdict="correct", url=None)


def test_no_verdict_means_controversial(db):
    _incident(db)
    status, ref = db.execute("SELECT status, referee_id FROM v_incidents").fetchone()
    assert status == "controversial"
    assert ref == 1


def test_published_verdict_means_ruled(db):
    _incident(db, verdict="correct", url="https://example.org/ruling")
    assert db.execute("SELECT status FROM v_incidents").fetchone()[0] == "ruled"


# ---------- expert opinions ----------

def test_stance_limited_to_three_values(db):
    _incident(db)
    db.execute("INSERT INTO experts (expert_id, name_ar, background) VALUES (1, 'خبير', 'ex_referee')")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """INSERT INTO expert_opinions (incident_id, expert_id, stance, summary_ar,
                   source_name, source_url) VALUES (1, 1, 'maybe', 's', 'n', 'u')"""
        )


def test_one_role_per_person_per_match(db):
    # official 1 is already the referee of match 1
    db.execute("DELETE FROM match_officials WHERE role = 'var'")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO match_officials VALUES (1, 1, 'var')")
