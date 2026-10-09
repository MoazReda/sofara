"""Case-library loader tests: one happy path, then every rejection rule.
Each test writes tiny CSVs into a temp folder and builds an in-memory db."""
import csv
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from build_db import apply_schema, connect  # noqa: E402
from load_cases import CASE_FILES, load_cases  # noqa: E402
from load_registry import FILES, DataError, load_all  # noqa: E402

ALL_FILES = {**FILES, **CASE_FILES}
URL = "https://example.org/source"


def write(raw: Path, name: str, rows: list[list]) -> None:
    with (raw / f"{name}.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(ALL_FILES[name])
        w.writerows(rows)


def incident(case_id=1, home="الأهلي", away="إنبي", minute=68, var="check_only",
             on_field=("foul", "إنبي", "penalty"), final=("", "", ""),
             official=("", "", ""), official_url=""):
    return [case_id, "2026/27", 1, home, away, minute, 0, var, "press", URL, "وصف", "", "",
            *on_field, *final, *official, official_url]


@pytest.fixture
def raw(tmp_path):
    write(tmp_path, "teams", [["الأهلي", ""], ["الشرقية إنبي", ""], ["الزمالك", ""]])
    write(tmp_path, "team_aliases", [["إنبي", "الشرقية إنبي", "test"]])
    write(tmp_path, "officials", [["محمود ناجي", "", "", "", ""]])
    write(tmp_path, "official_aliases", [])
    write(tmp_path, "crews", [["2026/27", 1, "2026-08-23", "20:00", "", "الأهلي", "إنبي",
                               "محمود ناجي", "", "", "", "", "", "", "", URL]])
    write(tmp_path, "incidents", [incident()])
    write(tmp_path, "incident_cards", [])
    write(tmp_path, "experts", [["جهاد جريشة", "ex_referee"]])
    write(tmp_path, "expert_opinions", [[1, "جهاد جريشة", "disagree", "ملخص", "مصدر", URL, "2026-08-24"]])
    return tmp_path


def build(raw):
    conn = connect(":memory:")
    apply_schema(conn)
    load_all(conn, raw)
    return conn, load_cases(conn, raw)


def problems_of(raw) -> str:
    with pytest.raises(DataError) as e:
        build(raw)
    return "\n".join(e.value.problems)


# ---------------- happy path ----------------

def test_happy_path(raw):
    conn, counts = build(raw)
    assert counts["incidents"] == 1 and counts["expert_opinions"] == 1
    row = conn.execute("SELECT final_outcome, var_changed, status, referee_id "
                       "FROM v_incident_summary").fetchone()
    assert row == ("penalty", 0, "controversial", 1)


def test_var_overturn_with_card(raw):
    write(raw, "incidents", [incident(var="ofr", on_field=("none", "", "play_on"),
                                      final=("handball", "إنبي", "penalty"))])
    write(raw, "incident_cards", [[1, "final", "إنبي", "مدافع", "red", "denying_goal_handball"]])
    conn, counts = build(raw)
    assert counts["incident_sanctions"] == 1
    assert conn.execute("SELECT var_changed FROM v_incident_summary").fetchone()[0] == 1


def test_official_ruling_gives_verdict(raw):
    write(raw, "incidents", [incident(official=("foul", "إنبي", "penalty"), official_url=URL)])
    conn, _ = build(raw)
    assert conn.execute("SELECT status, verdict FROM v_incident_summary").fetchone() \
        == ("ruled", "correct")


# ---------------- rejections (nothing is written) ----------------

def test_match_not_found_mentions_home_away(raw):
    write(raw, "incidents", [incident(home="إنبي", away="الأهلي")])   # reversed
    assert "check home/away order" in problems_of(raw)


def test_unknown_team(raw):
    write(raw, "incidents", [incident(away="فريق مجهول")])
    assert "unknown team 'فريق مجهول'" in problems_of(raw)


def test_half_filled_stage(raw):
    write(raw, "incidents", [incident(final=("handball", "إنبي", ""))])
    assert "final needs both offence and outcome" in problems_of(raw)


def test_official_without_source_rejected(raw):
    write(raw, "incidents", [incident(official=("foul", "إنبي", "penalty"))])
    assert "rejected by database" in problems_of(raw)


def test_source_without_official_decision(raw):
    write(raw, "incidents", [incident(official_url=URL)])
    assert "official_source_url given but no official decision" in problems_of(raw)


def test_offending_team_not_in_match(raw):
    write(raw, "incidents", [incident(on_field=("foul", "الزمالك", "penalty"))])
    assert "did not play in this match" in problems_of(raw)


def test_card_at_stage_without_decision(raw):
    write(raw, "incident_cards", [[1, "final", "إنبي", "مدافع", "red", "denying_goal_foul"]])
    assert "has no 'final' decision" in problems_of(raw)


def test_card_reason_must_fit(raw):
    write(raw, "incident_cards", [[1, "on_field", "إنبي", "مدافع", "yellow", "violent_conduct"]])
    assert "does not fit" in problems_of(raw)


def test_duplicate_case_id(raw):
    write(raw, "incidents", [incident(), incident(minute=71)])
    assert "case_id 1 is used twice" in problems_of(raw)


def test_unknown_expert_not_guessed(raw):
    write(raw, "expert_opinions", [[1, "جهاد جريشه ", "agree", "s", "n", URL, ""]])   # ه/ة + space
    conn, _ = build(raw)                                                            # normalizes fine
    write(raw, "expert_opinions", [[1, "جهاد", "agree", "s", "n", URL, ""]])        # a different name
    assert "unknown expert 'جهاد'" in problems_of(raw)


def test_opinion_for_missing_case(raw):
    write(raw, "expert_opinions", [[9, "جهاد جريشة", "agree", "s", "n", URL, ""]])
    assert "case_id 9 is not in incidents.csv" in problems_of(raw)


def test_failed_load_writes_nothing(raw):
    write(raw, "expert_opinions", [[1, "خبير مجهول", "agree", "s", "n", URL, ""]])
    conn = connect(":memory:")
    apply_schema(conn)
    load_all(conn, raw)
    with pytest.raises(DataError):
        load_cases(conn, raw)
    assert conn.execute("SELECT COUNT(*) FROM incidents").fetchone()[0] == 0


def test_minute_and_var_may_be_unknown(raw):
    write(raw, "incidents", [incident(minute="", var="")])
    conn, _ = build(raw)
    assert conn.execute("SELECT minute, var_review FROM incidents").fetchone() == (None, "unknown")


def test_found_via_is_required(raw):
    row = incident()
    row[8] = ""                                   # found_via
    write(raw, "incidents", [row])
    assert "rejected by database" in problems_of(raw)
