"""Part ج: agreement measures on the real library, and the loader's checks."""

import shutil
from pathlib import Path

import pytest

from sofara.agreement import case_agreement, expert_vs_committee, load_opinion_reasons
from sofara.build import apply_schema, connect
from sofara.cases import load_cases
from sofara.registry import DataError, load_all

RAW = Path(__file__).resolve().parent.parent / "data" / "raw"


def _db(raw=RAW):
    conn = connect(":memory:")
    apply_schema(conn)
    load_all(conn, raw)
    load_cases(conn, raw)
    load_opinion_reasons(conn, raw)
    return conn


@pytest.fixture(scope="module")
def conn():
    return _db()


def test_committee_is_not_counted_as_an_expert(conn):
    # case 8: Abbas + an unnamed committee source -> only Abbas counts
    assert all(c.incident_id != 8 for c in case_agreement(conn))


def test_derby_push_is_contested(conn):
    case = {c.incident_id: c for c in case_agreement(conn)}[34]
    assert (case.agree, case.disagree, case.label) == (2, 2, "contested")


def test_two_opinions_make_no_claim(conn):
    case = {c.incident_id: c for c in case_agreement(conn)}[36]
    assert case.label == "small_sample"


def test_card_only_opinion_is_compared_with_the_card_verdict(conn):
    # case 1: Abbas backs the penalty; the committee backs it too (only the card
    # was missing) -> counted as the same view, not as a disagreement
    rows = {name: (n, same) for name, n, same in expert_vs_committee(conn)}
    assert rows["إبراهيم نور الدين"] == (1, 1)


def test_unknown_reason_is_rejected(tmp_path):
    raw = tmp_path / "raw"
    shutil.copytree(RAW, raw)
    with (raw / "opinion_reasons.csv").open("a", encoding="utf-8") as f:
        f.write("34,ناصر عباس,gut_feeling\n")
    with pytest.raises(DataError) as e:
        _db(raw)
    assert "unknown reason" in "\n".join(e.value.problems)


def test_reason_for_a_missing_opinion_is_rejected(tmp_path):
    raw = tmp_path / "raw"
    shutil.copytree(RAW, raw)
    with (raw / "opinion_reasons.csv").open("a", encoding="utf-8") as f:
        f.write("2,ناصر عباس,intent\n")
    with pytest.raises(DataError) as e:
        _db(raw)
    assert "has no opinion on case 2" in "\n".join(e.value.problems)
