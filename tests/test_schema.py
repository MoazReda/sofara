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

# ---------- case library: incidents / decisions / sanctions ----------
# A test case, not a real ruling: handball in the box, on-field play on,
# VAR -> penalty + red card (DOGSO by handball) to an ENPPI defender.
# Team 1 = Al Ahly, team 2 = ENPPI.

def _incident(db) -> int:
    cur = db.execute(
        """INSERT INTO incidents (match_id, minute, description_ar, var_review,
                                 found_via, source_url)
           VALUES (1, 68, 'لمسة يد داخل منطقة الجزاء (حالة اختبار)', 'ofr',
                   'press', 'https://example.org/a')""")
    return cur.lastrowid


def _decision(db, iid, stage, offence="none", team=None, outcome="play_on", url=None):
    db.execute(
        """INSERT INTO incident_decisions
               (incident_id, stage, offence, offending_team_id, outcome, source_url)
           VALUES (?, ?, ?, ?, ?, ?)""", (iid, stage, offence, team, outcome, url))


def _card(db, iid, stage, sanction="red", reason="denying_goal_handball",
          team=2, person="مدافع إنبي"):
    db.execute(
        """INSERT INTO incident_sanctions (incident_id, stage, team_id, person_name,
               sanction, reason) VALUES (?, ?, ?, ?, ?, ?)""",
        (iid, stage, team, person, sanction, reason))


def _var_overturned(db) -> int:
    iid = _incident(db)
    _decision(db, iid, "on_field")
    _decision(db, iid, "final", "handball", 2, "penalty")
    _card(db, iid, "final")
    return iid


def _summary(db, col):
    return db.execute(f"SELECT {col} FROM v_incident_summary").fetchone()[0]


def test_summary_shows_both_stages_and_var_change(db):
    _var_overturned(db)
    row = db.execute("""SELECT on_field_outcome, final_offence, final_outcome,
                               var_changed, referee_id FROM v_incident_summary""").fetchone()
    assert row == ("play_on", "handball", "penalty", 1, 1)


def test_no_final_row_means_final_equals_on_field(db):
    iid = _incident(db)
    _decision(db, iid, "on_field", "foul", 2, "penalty")
    assert _summary(db, "final_outcome") == "penalty"
    assert _summary(db, "var_changed") == 0


def test_only_a_card_change_still_counts_as_var_change(db):
    iid = _incident(db)
    _decision(db, iid, "on_field", "foul", 2, "free_kick")
    _card(db, iid, "on_field", "yellow", "unsporting_behaviour")
    _decision(db, iid, "final", "foul", 2, "free_kick")
    _card(db, iid, "final", "red", "serious_foul_play")
    assert _summary(db, "var_changed") == 1


def test_no_official_ruling_means_controversial(db):
    _var_overturned(db)
    assert _summary(db, "status") == "controversial"
    assert _summary(db, "verdict") is None


def test_official_ruling_matching_final_is_correct(db):
    iid = _var_overturned(db)
    _decision(db, iid, "official", "handball", 2, "penalty", url="https://example.org/r")
    _card(db, iid, "official")
    assert (_summary(db, "status"), _summary(db, "verdict")) == ("ruled", "correct")


def test_official_ruling_with_different_card_is_incorrect(db):
    iid = _var_overturned(db)
    _decision(db, iid, "official", "handball", 2, "penalty", url="https://example.org/r")
    _card(db, iid, "official", "yellow", "unsporting_behaviour")   # should've been yellow
    assert _summary(db, "verdict") == "incorrect"


def test_official_ruling_requires_source(db):
    iid = _var_overturned(db)
    with pytest.raises(sqlite3.IntegrityError):
        _decision(db, iid, "official", "handball", 2, "penalty", url=None)


def test_one_decision_per_stage(db):
    iid = _var_overturned(db)
    with pytest.raises(sqlite3.IntegrityError):
        _decision(db, iid, "final", "foul", 2, "free_kick")


@pytest.mark.parametrize("offence,team,outcome", [
    ("none", None, "penalty"),          # penalty without an offence
    ("offside", 1, "penalty"),          # penalty for offside
    ("offside", 1, "play_on"),          # offside but play continued
    ("foul", None, "free_kick"),        # offence without offending team
    ("none", 1, "play_on"),             # offending team without offence
])
def test_impossible_decisions_rejected(db, offence, team, outcome):
    iid = _incident(db)
    with pytest.raises(sqlite3.IntegrityError):
        _decision(db, iid, "on_field", offence, team, outcome)


def test_offending_team_must_have_played(db):
    db.execute("INSERT INTO teams (team_id, name_ar) VALUES (3, 'الزمالك')")
    iid = _incident(db)
    with pytest.raises(sqlite3.IntegrityError, match="did not play"):
        _decision(db, iid, "on_field", "foul", 3, "free_kick")


def test_sanction_needs_its_decision_first(db):
    iid = _incident(db)                 # no 'final' decision row yet
    with pytest.raises(sqlite3.IntegrityError):
        _card(db, iid, "final")


@pytest.mark.parametrize("sanction,reason", [
    ("yellow", "violent_conduct"),      # red-card reason on a yellow
    ("red", "dissent"),                 # yellow-card reason on a red
    ("red", "second_caution"),          # that's a second_yellow, not a direct red
])
def test_card_reason_must_fit(db, sanction, reason):
    iid = _incident(db)
    _decision(db, iid, "on_field", "foul", 2, "free_kick")
    with pytest.raises(sqlite3.IntegrityError, match="does not fit"):
        _card(db, iid, "on_field", sanction, reason)


def test_two_people_carded_in_one_incident(db):
    iid = _incident(db)
    _decision(db, iid, "on_field", "violent_conduct", 2, "free_kick")
    _card(db, iid, "on_field", "red", "violent_conduct", team=2, person="مدافع")
    _card(db, iid, "on_field", "yellow", "unsporting_behaviour", team=1, person="مهاجم")
    assert db.execute("SELECT COUNT(*) FROM incident_sanctions").fetchone()[0] == 2


def test_match_event_reason_must_fit(db):
    with pytest.raises(sqlite3.IntegrityError, match="does not fit"):
        db.execute("""INSERT INTO match_events (match_id, team_id, event_type, minute, reason)
                      VALUES (1, 1, 'yellow', 50, 'violent_conduct')""")


def test_missing_on_field_decision_is_flagged(db):
    _incident(db)
    assert db.execute("SELECT problem FROM v_incident_problems").fetchone()[0] \
        == "missing on_field decision"


# ---------- expert opinions ----------

def test_stance_limited_to_three_values(db):
    iid = _incident(db)
    db.execute("INSERT INTO experts (expert_id, name_ar, background) VALUES (1, 'خبير', 'ex_referee')")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(
            """INSERT INTO expert_opinions (incident_id, expert_id, stance, summary_ar,
                   source_name, source_url) VALUES (?, 1, 'maybe', 's', 'n', 'u')""", (iid,))


def test_one_role_per_person_per_match(db):
    # official 1 is already the referee of match 1
    db.execute("DELETE FROM match_officials WHERE role = 'var'")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO match_officials VALUES (1, 1, 'var')")
