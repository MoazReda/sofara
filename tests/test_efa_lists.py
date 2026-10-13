"""EFA lists: names are matched to officials, never guessed; unmatched is allowed."""

import csv
from pathlib import Path

import pytest

from sofara.build import apply_schema, connect
from sofara.efa_lists import COLUMNS, load_efa_lists
from sofara.registry import FILES, DataError, load_all

URL = "https://www.efa.com.eg/"
ALL = {**FILES, "efa_lists": COLUMNS}


def write(raw: Path, name: str, rows: list[list]) -> None:
    with (raw / f"{name}.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(ALL[name])
        w.writerows(rows)


@pytest.fixture
def raw(tmp_path):
    write(tmp_path, "teams", [["الأهلي", ""], ["الزمالك", ""]])
    write(tmp_path, "team_aliases", [])
    write(tmp_path, "officials", [["محمود ناجي", "", "", "", ""], ["السيد منير", "", "", "", ""]])
    write(tmp_path, "official_aliases", [["سيد منير", "السيد منير", "EFA list"]])
    write(tmp_path, "crews", [])
    return tmp_path


def build(raw):
    conn = connect(":memory:")
    apply_schema(conn)
    load_all(conn, raw)
    load_efa_lists(conn, raw)
    return conn


def test_names_match_through_normalization_and_aliases(raw):
    write(
        raw,
        "efa_lists",
        [
            ["international", "محمود ناجى", "", "", URL],  # ى/ي spelling
            ["first_degree_referee", "سيد منير", "المنوفية", "2025-2026", URL],  # alias
            ["main_committee", "عصام عبد الفتاح", "", "", URL],  # not an official: fine
        ],
    )
    conn = build(raw)
    matched = conn.execute("SELECT COUNT(official_id) FROM efa_lists").fetchone()[0]
    assert matched == 2


def test_unknown_list_is_rejected(raw):
    write(raw, "efa_lists", [["best_referees", "محمود ناجي", "", "", URL]])
    with pytest.raises(DataError) as e:
        build(raw)
    assert "list must be one of" in "\n".join(e.value.problems)
