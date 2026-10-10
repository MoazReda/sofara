"""Commendations loader: the match is resolved from the crews, never guessed."""

import csv
from pathlib import Path

import pytest

from sofara.build import apply_schema, connect
from sofara.cases import CASE_FILES, load_cases
from sofara.commendations import COLUMNS, load_commendations
from sofara.registry import FILES, DataError, load_all

URL = "https://example.org/post"
ALL = {**FILES, **CASE_FILES, "commendations": COLUMNS}


def write(raw: Path, name: str, rows: list[list]) -> None:
    with (raw / f"{name}.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(ALL[name])
        w.writerows(rows)


def crew(date, home, away, ref, ar1, var):
    return ["2026/27", 1, date, "", "", home, away, ref, ar1, "", "", var, "", "", "", URL]


@pytest.fixture
def raw(tmp_path):
    write(tmp_path, "teams", [[t, ""] for t in ("الأهلي", "إنبي", "الزمالك", "الاتحاد")])
    write(tmp_path, "team_aliases", [])
    write(tmp_path, "officials", [[n, "", "", "", ""] for n in ("حكم أ", "مساعد ب", "فار ج")])
    write(tmp_path, "official_aliases", [["فار ج الطويل", "فار ج", "test"]])
    write(tmp_path, "crews", [crew("2026-08-23", "الأهلي", "إنبي", "حكم أ", "مساعد ب", "فار ج")])
    for name in CASE_FILES:
        write(tmp_path, name, [])
    write(tmp_path, "experts", [["ناصر عباس", "ex_referee"]])
    return tmp_path


def build(raw):
    conn = connect(":memory:")
    apply_schema(conn)
    load_all(conn, raw)
    load_cases(conn, raw)
    return conn, load_commendations(conn, raw)


def pick(category, official, rnd=1):
    return ["ناصر عباس", "2026/27", rnd, category, official, "أسباب", URL, ""]


def problems_of(raw) -> str:
    with pytest.raises(DataError) as e:
        build(raw)
    return "\n".join(e.value.problems)


def test_match_is_resolved_from_the_crew(raw):
    write(raw, "commendations", [pick("referee", "حكم أ"), pick("assistant", "مساعد ب")])
    conn, counts = build(raw)
    assert counts == {"expert_commendations": 2}
    assert {r[0] for r in conn.execute("SELECT match_id FROM expert_commendations")} == {1}


def test_alias_resolves(raw):
    write(raw, "commendations", [pick("var", "فار ج الطويل")])
    _, counts = build(raw)
    assert counts["expert_commendations"] == 1


def test_wrong_category_is_reported(raw):
    write(raw, "commendations", [pick("referee", "مساعد ب")])  # he was an assistant
    assert "has no match as referee in round 1" in problems_of(raw)


def test_wrong_round_is_reported(raw):
    write(raw, "commendations", [pick("referee", "حكم أ", rnd=2)])
    assert "has no match as referee in round 2" in problems_of(raw)


def test_unknown_names_are_reported(raw):
    write(raw, "commendations", [["خبير مجهول", "2026/27", 1, "referee", "حكم مجهول", "", URL, ""]])
    msg = problems_of(raw)
    assert "unknown expert 'خبير مجهول'" in msg
    assert "unknown official 'حكم مجهول'" in msg


def test_bad_category(raw):
    write(raw, "commendations", [pick("linesman", "مساعد ب")])
    assert "category must be one of" in problems_of(raw)


def test_duplicate_pick_rejected(raw):
    write(raw, "commendations", [pick("referee", "حكم أ"), pick("referee", "حكم أ")])
    assert "rejected by database" in problems_of(raw)


def test_no_file_means_no_commendations(raw):
    _, counts = build(raw)
    assert counts == {"expert_commendations": 0}
