"""Search tests on the real case library.

GOLD is an evaluation set: for each query, the cases an instructor would
expect. The search is recall-first, so every expected case must be found.
When the library grows, add queries here before changing the search.
"""

from pathlib import Path

import pytest

from sofara.build import apply_schema, connect
from sofara.cases import load_cases
from sofara.commendations import load_commendations
from sofara.registry import load_all
from sofara.search import format_quiz, load_vocab, main, parse, search

ROOT = Path(__file__).resolve().parent.parent
RAW, VOCAB = ROOT / "data" / "raw", ROOT / "data" / "vocab" / "terms.csv"


@pytest.fixture(scope="module")
def conn():
    c = connect(":memory:")
    apply_schema(c)
    load_all(c, RAW)
    load_cases(c, RAW)
    load_commendations(c, RAW)
    return c


@pytest.fixture(scope="module")
def vocab():
    return load_vocab(VOCAB)


def ids(conn, vocab, text, **filters):
    q = parse(conn, text, vocab)
    for k, v in filters.items():
        setattr(q, k, v)
    return [c.incident_id for c in search(conn, q)]


GOLD = {
    # query: cases that must be found
    "بلنتي": {1, 2, 3, 7, 8, 9, 11, 13, 14, 16, 17, 19, 20, 21, 22, 34, 35, 37, 38, 39, 40},
    "ركلة جزاء": {1, 2, 3, 7, 8, 9, 11, 13, 14, 16, 17, 19, 20, 21, 22, 34, 35, 37, 38, 39, 40},
    "لمسة يد": {2, 3, 12, 25, 32, 36, 38, 39},
    "هاند": {2, 3, 12, 25, 32, 36, 38, 39},
    "تسلل": {5, 10, 26, 41},
    "هدف ملغي": {5, 10, 18, 41, 42},
    "طرد": {6, 15, 23, 24, 11, 29, 31},
    "راح الشاشة": {15, 16},
    "الفار غير القرار": {15, 26},
    "استارز": {24},
    "حارس": {15, 22, 35},
    "الأهلي بلنتي": {1, 2, 3, 7, 8, 9, 13, 34, 35, 37, 38},
    "إعادة البلنتي": {22},
    "تقدم الحارس": {22},
    "ركنية": {27},
    "ركلة مرمى": {27, 36, 37},
    "الكرة بيده": {36},
    "إنذار": {11, 23, 29, 31, 36},
    "المعايير": {30},
}


@pytest.mark.parametrize("query,expected", GOLD.items())
def test_gold_recall(conn, vocab, query, expected):
    found = set(ids(conn, vocab, query))
    assert expected <= found, f"missed {sorted(expected - found)}"


def test_synonyms_give_the_same_results(conn, vocab):
    assert set(ids(conn, vocab, "بلنتي")) == set(ids(conn, vocab, "ضربة جزاء"))
    assert set(ids(conn, vocab, "لمسة يد")) == set(ids(conn, vocab, "هاند"))


def test_given_penalties_rank_above_claims(conn, vocab):
    found = ids(conn, vocab, "الأهلي بلنتي")
    assert set(found[:4]) == {1, 8, 9, 13}  # outcome = penalty at some stage


def test_text_only_term_does_not_match_fields(conn, vocab):
    # case 15 is a serious-foul-play red card, but not a studs-up challenge
    assert 15 not in ids(conn, vocab, "استارز")


def test_supported_is_not_his_hand(conn, vocab):
    # "وأيّده الـVAR" (VAR supported him) normalizes like "إيده" (his hand):
    # a shirt-pull case must not appear in a handball search
    assert 28 not in ids(conn, vocab, "لمسة يد")


def test_arm_in_a_foul_is_not_handball(conn, vocab):
    # case 23: Fattouh used his arm in a challenge — a foul, not a handball
    assert 23 not in ids(conn, vocab, "هاند")


def test_longest_team_name_wins(conn, vocab):
    q = parse(conn, "البنك الأهلي بلنتي", vocab)
    names = {
        r[0]
        for r in conn.execute(
            f"SELECT name_ar FROM teams WHERE team_id IN ({','.join(map(str, q.team_ids))})"
        )
    }
    assert names == {"البنك الأهلي"}


def test_referee_name_filters(conn, vocab):
    assert set(ids(conn, vocab, "محمود ناجي")) == {1, 2, 13, 30, 31, 32, 33}


def test_different_kinds_are_anded(conn, vocab):
    # penalty AND VAR changed the decision: none in the current library
    assert ids(conn, vocab, "بلنتي الفار غير القرار") == []


def test_round_filter(conn, vocab):
    found = ids(conn, vocab, "بلنتي", round=3)
    assert found and all(c in {7, 19, 20, 21, 22, 40} for c in found)


def test_unknown_word_must_appear_in_text(conn, vocab):
    assert ids(conn, vocab, "كلمةغيرموجودة") == []


def test_quiz_hides_answers_and_flags_controversy(conn, vocab):
    q = parse(conn, "راح الشاشة", vocab)
    quiz = format_quiz(q, search(conn, q))
    assert quiz.count("<details>") == 2
    assert "حالة جدلية" in quiz
    assert "بعد مراجعة الـVAR" in quiz


def test_cli_writes_quiz(tmp_path, capsys):
    out = tmp_path / "quiz.md"
    assert main(["طرد", "--raw", str(RAW), "--vocab", str(VOCAB), "--quiz", str(out)]) == 0
    assert out.read_text(encoding="utf-8").startswith("# اختبار فيديو: طرد")
    assert "حالة" in capsys.readouterr().out
