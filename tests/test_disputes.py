"""The Arabic disputes page: only split cases, the committee kept apart."""

from pathlib import Path

import pytest

from sofara.agreement import load_case_comparisons, load_opinion_reasons
from sofara.build import apply_schema, connect
from sofara.cases import load_cases
from sofara.disputes import main, render
from sofara.registry import load_all

RAW = Path(__file__).resolve().parent.parent / "data" / "raw"


@pytest.fixture(scope="module")
def page():
    conn = connect(":memory:")
    apply_schema(conn)
    load_all(conn, RAW)
    load_cases(conn, RAW)
    load_opinion_reasons(conn, RAW)
    load_case_comparisons(conn, RAW)
    return render(conn)


def test_only_split_cases_are_listed(page):
    assert "## حالة 34 " in page  # 2–2
    assert "## حالة 9 " not in page  # Abbas + a committee source: not a split


def test_committee_ruling_shown_separately_with_its_source(page):
    section = page.split("## حالة 1 ")[1].split("## ")[0]
    assert "حكم لجنة الحكام:** ركلة جزاء" in section
    assert "reel/1561638358556934" in section
    assert "لجنة الحكام (بحسب" not in section  # not listed as an expert


def test_foreign_crew_is_flagged(page):
    assert "(طاقم أجنبي)" in page.split("## حالة 34 ")[1].split("## ")[0]


def test_consistency_pair_shows_both_cases(page):
    assert "### حالة 30 مقابل حالة 1" in page


def test_cli_writes_file(tmp_path):
    out = tmp_path / "d.md"
    assert main(["--raw", str(RAW), "--out", str(out)]) == 0
    assert out.read_text(encoding="utf-8").startswith("# صفارة")
