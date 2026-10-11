"""Match reviews: coverage must tell "nothing happened" apart from "nobody looked"."""

import csv
from pathlib import Path

import pytest

from sofara.build import apply_schema, connect
from sofara.cases import CASE_FILES, load_cases
from sofara.registry import FILES, DataError, load_all
from sofara.reviews import COLUMNS, load_reviews

URL = "https://example.org/review"
ALL = {**FILES, **CASE_FILES, "match_reviews": COLUMNS}


def write(raw: Path, name: str, rows: list[list]) -> None:
    with (raw / f"{name}.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(ALL[name])
        w.writerows(rows)


def crew(date, home, away, ref):
    return ["2026/27", 1, date, "", "", home, away, ref, "", "", "", "", "", "", "", URL]


@pytest.fixture
def raw(tmp_path):
    write(tmp_path, "teams", [[t, ""] for t in ("الأهلي", "إنبي", "الزمالك", "الاتحاد")])
    write(tmp_path, "team_aliases", [])
    write(tmp_path, "officials", [[n, "", "", "", ""] for n in ("حكم أ", "حكم ب")])
    write(tmp_path, "official_aliases", [])
    write(
        tmp_path,
        "crews",
        [
            crew("2026-08-23", "الأهلي", "إنبي", "حكم أ"),
            crew("2026-08-24", "الزمالك", "الاتحاد", "حكم ب"),
        ],
    )
    for name in CASE_FILES:
        write(tmp_path, name, [])
    write(tmp_path, "experts", [["ناصر عباس", "ex_referee"]])
    return tmp_path


def build(raw):
    conn = connect(":memory:")
    apply_schema(conn)
    load_all(conn, raw)
    load_cases(conn, raw)
    return conn, load_reviews(conn, raw)


def review(home="الأهلي", away="إنبي", kind="expert_review", expert="ناصر عباس", url=URL):
    return ["2026/27", 1, home, away, kind, expert, url, "", ""]


def problems_of(raw) -> str:
    with pytest.raises(DataError) as e:
        build(raw)
    return "\n".join(e.value.problems)


def test_reviews_load_and_spelling_is_normalized(raw):
    write(
        raw, "match_reviews", [review(away="انبي"), review(kind="press", expert="", url=URL + "2")]
    )
    conn, counts = build(raw)
    assert counts == {"match_reviews": 2}


def test_coverage_separates_quiet_matches_from_unchecked_ones(raw):
    write(raw, "match_reviews", [review()])
    conn, _ = build(raw)
    rows = dict(conn.execute("SELECT home_team_id, reviews FROM v_match_coverage").fetchall())
    ahly, zamalek = (
        conn.execute("SELECT team_id FROM teams WHERE name_ar = ?", (n,)).fetchone()[0]
        for n in ("الأهلي", "الزمالك")
    )
    assert rows[ahly] == 1  # reviewed, no case: a quiet match
    assert rows[zamalek] == 0  # nobody looked yet


def test_expert_review_needs_an_expert(raw):
    write(raw, "match_reviews", [review(expert="")])
    assert "needs the expert's name" in problems_of(raw)


def test_unknown_expert_and_bad_type_are_reported_together(raw):
    write(raw, "match_reviews", [review(expert="شخص مجهول"), review(kind="tweet", url=URL + "2")])
    msg = problems_of(raw)
    assert "unknown expert" in msg
    assert "review_type must be one of" in msg


def test_wrong_home_away_order_is_not_guessed(raw):
    write(raw, "match_reviews", [review(home="إنبي", away="الأهلي")])
    assert "check home/away order" in problems_of(raw)


def test_same_source_twice_for_one_match_is_refused(raw):
    write(raw, "match_reviews", [review(), review()])
    assert "rejected by database" in problems_of(raw)
