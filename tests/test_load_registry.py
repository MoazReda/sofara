"""Loader tests: happy path, alias resolution, and every rejection rule.
Each test writes tiny CSVs into a temp folder and builds an in-memory db."""
import csv
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from build_db import apply_schema, connect  # noqa: E402
from load_registry import FILES, DataError, load_all  # noqa: E402
from normalize import normalize_name  # noqa: E402

URL = "https://example.org/round-1-crews"


def write(raw: Path, name: str, rows: list[list]) -> None:
    with (raw / f"{name}.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(FILES[name])
        w.writerows(rows)


def crew_row(home="الأهلي", away="إنبي", date="2026-08-23", rnd=1,
             referee="محمود احمد ناجي", ar1="سمير جمال سعد محمد", var=None):
    #       season,   round, date, home, away, ref, ar1, ar2, 4th, var, avar, observer, url
    return ["2026/27", rnd, date, home, away, referee, ar1, "", "", var or "", "", "", URL]


@pytest.fixture
def raw(tmp_path):
    write(tmp_path, "teams", [["الأهلي", "Al Ahly"], ["إنبي", "ENPPI"],
                              ["الزمالك", "Zamalek"], ["بيراميدز", "Pyramids"]])
    write(tmp_path, "team_aliases", [["انبى", "إنبي", "press"]])
    write(tmp_path, "officials", [
        ["محمود احمد ناجي", "", "", "الغربية", ""],
        ["سمير جمال سعد محمد", "", "", "القاهرة", ""],
        ["مصطفى عثمان", "Mostafa Othman", "", "", ""],
    ])
    write(tmp_path, "official_aliases", [["محمود ناجي", "محمود احمد ناجي", "press"]])
    return tmp_path


def build(raw):
    conn = connect(":memory:")
    apply_schema(conn)
    return conn, load_all(conn, raw)


def problems_of(raw) -> str:
    with pytest.raises(DataError) as e:
        build(raw)
    return "\n".join(e.value.problems)


# ---------------- normalization ----------------

@pytest.mark.parametrize("a,b", [
    ("إبراهيم نور الدين", "ابراهيم نور الدين"),
    ("محمد عطيّة", "محمد عطيه"),
    ("مصطفى", "مصطفي"),
    ("  محمود   ناجي ", "محمود ناجي"),
    ("Mostafa OTHMAN", "mostafa othman"),
])
def test_normalize_spelling_noise(a, b):
    assert normalize_name(a) == normalize_name(b)


def test_normalize_does_not_merge_different_names():
    assert normalize_name("Mostafa Othman") != normalize_name("Mostafa Osman")


# ---------------- happy path ----------------

def test_happy_path_counts(raw):
    write(raw, "crews", [crew_row()])
    _, counts = build(raw)
    assert counts == {"teams": 4, "officials": 3, "matches": 1, "match_officials": 2}


def test_defaults_applied_for_empty_cells(raw):
    write(raw, "crews", [crew_row()])
    conn, _ = build(raw)
    assert conn.execute(
        "SELECT nationality, official_type FROM officials WHERE official_id = 1"
    ).fetchone() == ("Egypt", "referee")


def test_alias_and_spelling_resolve_to_same_people(raw):
    # 'محمود ناجي' is an alias; 'انبى' is a team alias; 'مصطفي' differs only in ى/ي
    write(raw, "crews", [crew_row(away="انبى", referee="محمود ناجي", var="مصطفي عثمان")])
    conn, _ = build(raw)
    rows = dict(conn.execute("SELECT role, official_id FROM match_officials").fetchall())
    assert rows == {"referee": 1, "assistant_1": 2, "var": 3}


def test_english_name_resolves(raw):
    write(raw, "crews", [crew_row(var="Mostafa Othman")])
    conn, _ = build(raw)
    assert conn.execute(
        "SELECT official_id FROM match_officials WHERE role = 'var'").fetchone()[0] == 3


# ---------------- rejections (and nothing gets written) ----------------

def test_unknown_official_is_reported_not_guessed(raw):
    write(raw, "crews", [crew_row(var="Mostafa Osman")])   # close, but not registered
    msg = problems_of(raw)
    assert "Unknown official 'Mostafa Osman'" in msg
    assert "crews.csv:2 (var)" in msg


def test_all_problems_reported_together(raw):
    write(raw, "crews", [crew_row(home="فريق مجهول", referee="حكم مجهول", date="23.08.2026")])
    msg = problems_of(raw)
    assert "Unknown team 'فريق مجهول'" in msg
    assert "Unknown official 'حكم مجهول'" in msg
    assert "must be YYYY-MM-DD" in msg


def test_failed_load_writes_nothing(raw):
    write(raw, "crews", [crew_row(), crew_row(home="الزمالك", away="بيراميدز",
                                              referee="حكم مجهول", ar1="")])
    conn = connect(":memory:")
    apply_schema(conn)
    with pytest.raises(DataError):
        load_all(conn, raw)
    assert conn.execute("SELECT COUNT(*) FROM teams").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0] == 0


def test_same_person_two_roles_rejected(raw):
    write(raw, "crews", [crew_row(var="محمود احمد ناجي")])
    assert "two roles in the same match" in problems_of(raw)


def test_official_in_two_matches_same_day_rejected(raw):
    write(raw, "crews", [
        crew_row(),
        crew_row(home="الزمالك", away="بيراميدز", ar1="مصطفى عثمان"),
    ])
    assert "already assigned on 2026-08-23" in problems_of(raw)


def test_team_twice_in_same_round_rejected(raw):
    write(raw, "crews", [
        crew_row(),
        crew_row(away="الزمالك", date="2026-08-25"),
    ])
    assert "plays twice in round 1" in problems_of(raw)


def test_missing_referee_rejected(raw):
    write(raw, "crews", [crew_row(referee="")])
    assert "referee is empty" in problems_of(raw)


def test_wrong_header_rejected(raw):
    (raw / "crews.csv").write_text("season,round,date\n2026/27,1,2026-08-23\n",
                                   encoding="utf-8")
    assert "crews.csv: header is" in problems_of(raw)


def test_alias_to_unknown_name_rejected(raw):
    write(raw, "official_aliases", [["ناجي", "حكم مش موجود", "press"]])
    assert "points to unknown name" in problems_of(raw)


def test_two_officials_same_normalized_name_rejected(raw):
    write(raw, "officials", [["محمد عطية", "", "", "", ""], ["محمد عطيه", "", "", "", ""]])
    assert "already points to a different entity" in problems_of(raw)


def test_excel_bom_is_handled(raw):
    # write() already uses utf-8-sig (what Excel produces); this would fail otherwise
    write(raw, "crews", [crew_row()])
    _, counts = build(raw)
    assert counts["matches"] == 1
