"""Search the case library in everyday Arabic, and export a video quiz.

Usage (from the repository root):
    sofara-search "لمسة يد"
    sofara-search "بلنتي الفار غير القرار" --round 2
    sofara-search "استارز" --quiz quiz.md

Built for a referee instructor preparing a lecture, so it is RECALL-FIRST:
missing a relevant case is worse than showing an extra one.

How a query is read:
  1. Vocabulary terms (data/vocab/terms.csv) become structured conditions:
     "هاند" -> offence = handball, "راح الشاشة" -> VAR = on-field review...
     Terms with field "text" describe HOW something happened ("استارز") and
     only match the case text, never a field.
  2. Team and official names (with aliases) become filters.
  3. Any other word must appear in the case text (description or an expert's
     opinion summary).

How a case matches a vocabulary term: the structured field matches at ANY
stage (on-field, after VAR, official) OR the term appears in the case text.
So "بلنتي" finds penalties given AND penalty claims that were refused.
Terms of the same kind are OR-ed ("طرد" or "إنذار"); different kinds are
AND-ed ("بلنتي" and "الفار"). Every result says why it matched.
"""

from __future__ import annotations

import argparse
import csv
import re
import sqlite3
import sys
from dataclasses import dataclass, field
from pathlib import Path

from sofara.build import DEFAULT_RAW, apply_schema, connect
from sofara.cases import load_cases
from sofara.commendations import load_commendations
from sofara.normalize import normalize_name
from sofara.registry import load_all

DEFAULT_VOCAB = Path("data/vocab/terms.csv")

# words that carry no meaning in a search ("كل حالات ... في ...")
STOPWORDS = {
    normalize_name(w)
    for w in [
        "في",
        "على",
        "من",
        "الى",
        "إلى",
        "عن",
        "مع",
        "و",
        "او",
        "أو",
        "اللي",
        "التي",
        "الذي",
        "كل",
        "حالة",
        "حالات",
        "لقطة",
        "لقطات",
        "عايز",
        "هات",
        "اعرض",
        "ضد",
        "امام",
        "أمام",
        "بين",
        "بعد",
        "قبل",
        "لما",
        "لو",
        "كان",
        "كانت",
    ]
}

# Arabic clitics around a word: و/ف/ب/ل/ك + ال before it, pronoun after it
_PREFIX = r"(?:[وفبلك])?(?:ال)?"
_SUFFIX = r"(?:ه|ها|هم|ا|ات|ين)?"

AR = {  # Arabic labels for codes shown to the user
    "none": "لا مخالفة",
    "foul": "مخالفة",
    "handball": "لمسة يد",
    "offside": "تسلل",
    "simulation": "تمثيل",
    "violent_conduct": "سلوك عنيف",
    "other": "أخرى",
    "play_on": "استمرار اللعب",
    "penalty": "ركلة جزاء",
    "free_kick": "ضربة حرة",
    "goal_awarded": "احتساب الهدف",
    "goal_disallowed": "إلغاء الهدف",
    "yellow": "إنذار",
    "second_yellow": "إنذار ثانٍ (طرد)",
    "red": "طرد",
    "unknown": "غير معروف",
    "check_only": "مراجعة دون شاشة",
    "ofr": "مراجعة على الشاشة",
}


# a vocabulary reason that stands for several Law 12 codes
REASON_GROUPS = {"denying_goal_foul": {"denying_goal_foul", "denying_goal_handball"}}


def _pattern(phrase: str) -> re.Pattern:
    """Match a normalized phrase as whole word(s), allowing Arabic clitics."""
    words = [re.escape(w) for w in normalize_name(phrase).split()]
    body = r"\s+".join(words)
    return re.compile(rf"(?<!\w){_PREFIX}{body}{_SUFFIX}(?!\w)")


@dataclass
class Term:
    phrase: str
    field: str
    value: str
    pattern: re.Pattern = field(repr=False)
    # every phrase with the same meaning; the text match uses all of them,
    # so "بلنتي" also finds a description that says "ركلة جزاء"
    synonyms: list[re.Pattern] = field(default_factory=list, repr=False)


@dataclass
class Query:
    text: str
    terms: list[Term] = field(default_factory=list)
    team_ids: set[int] = field(default_factory=set)
    official_ids: set[int] = field(default_factory=set)
    words: list[str] = field(default_factory=list)
    round: int | None = None
    var_changed: bool = False


def load_vocab(path: Path = DEFAULT_VOCAB) -> list[Term]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        terms = [
            Term(r["term"], r["field"], r["value"], _pattern(r["term"])) for r in csv.DictReader(f)
        ]
    by_meaning: dict[tuple[str, str], list[re.Pattern]] = {}
    for term in terms:
        if term.field != "text":  # text-only terms have no shared meaning
            by_meaning.setdefault((term.field, term.value), []).append(term.pattern)
    for term in terms:
        term.synonyms = by_meaning.get((term.field, term.value), [term.pattern])
    return terms


def _names(conn: sqlite3.Connection, sql: str) -> list[tuple[str, int]]:
    # longest names first, so "البنك الأهلي" wins over "الأهلي"
    return sorted(conn.execute(sql).fetchall(), key=lambda r: -len(normalize_name(r[0])))


def parse(conn: sqlite3.Connection, text: str, vocab: list[Term]) -> Query:
    """Turn free text into structured conditions + leftover words."""
    q = Query(text=text)
    rest = normalize_name(text)

    def take(pattern: re.Pattern) -> bool:
        nonlocal rest
        if pattern.search(rest):
            rest = pattern.sub(" ", rest)
            return True
        return False

    for name, tid in _names(
        conn, "SELECT name_ar, team_id FROM teams UNION SELECT alias, team_id FROM team_aliases"
    ):
        if take(_pattern(name)):
            q.team_ids.add(tid)
    for name, oid in _names(conn, "SELECT name, official_id FROM v_official_lookup"):
        if take(_pattern(name)):
            q.official_ids.add(oid)
    for term in sorted(vocab, key=lambda t: -len(normalize_name(t.phrase))):
        if take(term.pattern):
            q.terms.append(term)
    q.words = [w for w in rest.split() if len(w) > 1 and w not in STOPWORDS]
    return q


@dataclass
class Case:
    incident_id: int
    round: int
    match: str
    home_id: int
    away_id: int
    minute: int | None
    referee_id: int | None
    referee: str
    var_review: str
    var_changed: int
    status: str
    verdict: str | None
    video_url: str | None
    video_start_sec: int | None
    description: str
    decisions: dict[str, dict] = field(default_factory=dict)  # stage -> decision
    cards: dict[str, list[dict]] = field(default_factory=dict)  # stage -> cards
    opinions: list[dict] = field(default_factory=list)
    why: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        """Everything a free-text word can match: description + opinion summaries."""
        return normalize_name(" ".join([self.description, *(o["summary"] for o in self.opinions)]))


def load_library(conn: sqlite3.Connection) -> list[Case]:
    conn.row_factory = sqlite3.Row
    cases = {
        r["incident_id"]: Case(
            incident_id=r["incident_id"],
            round=r["round"],
            match=f"{r['home']} × {r['away']}",
            home_id=r["home_team_id"],
            away_id=r["away_team_id"],
            minute=r["minute"],
            referee_id=r["referee_id"],
            referee=r["referee"] or "",
            var_review=r["var_review"],
            var_changed=r["var_changed"],
            status=r["status"],
            verdict=r["verdict"],
            video_url=r["video_url"],
            video_start_sec=r["video_start_sec"],
            description=r["description_ar"],
        )
        for r in conn.execute("""
            SELECT s.*, m.round, m.home_team_id, m.away_team_id,
                   th.name_ar AS home, ta.name_ar AS away, o.name_ar AS referee
            FROM v_incident_summary s JOIN matches m USING (match_id)
            JOIN teams th ON th.team_id = m.home_team_id
            JOIN teams ta ON ta.team_id = m.away_team_id
            LEFT JOIN officials o ON o.official_id = s.referee_id""")
    }
    for r in conn.execute("SELECT * FROM incident_decisions"):
        cases[r["incident_id"]].decisions[r["stage"]] = dict(r)
    for r in conn.execute("""SELECT s.*, t.name_ar AS team, cr.name_ar AS reason_ar
                             FROM incident_sanctions s JOIN teams t USING (team_id)
                             LEFT JOIN card_reasons cr ON cr.code = s.reason"""):
        cases[r["incident_id"]].cards.setdefault(r["stage"], []).append(dict(r))
    for r in conn.execute("""SELECT o.incident_id, o.stance, o.summary_ar AS summary,
                                    o.source_url, e.name_ar AS expert, e.background
                             FROM expert_opinions o JOIN experts e USING (expert_id)"""):
        cases[r["incident_id"]].opinions.append(dict(r))
    conn.row_factory = None
    return list(cases.values())


def _structured_hit(case: Case, term: Term) -> bool:
    if term.field == "text":
        return False
    stages = case.decisions.values()
    cards = [c for cs in case.cards.values() for c in cs]
    if term.field == "offence":
        return any(d["offence"] == term.value for d in stages)
    if term.field == "outcome":
        return any(d["outcome"] == term.value for d in stages)
    if term.field == "sanction":
        wanted = {"red", "second_yellow"} if term.value == "red" else {term.value}
        return any(c["sanction"] in wanted for c in cards)
    if term.field == "reason":
        return any(c["reason"] in REASON_GROUPS.get(term.value, {term.value}) for c in cards)
    if term.field == "var":
        if term.value == "any":
            return case.var_review in ("check_only", "ofr")
        return case.var_review == term.value
    if term.field == "var_changed":
        return case.var_changed == 1
    return False


def matches(case: Case, q: Query) -> bool:
    """Apply the query; fill case.why with the reasons it matched."""
    case.why = []
    text = case.text
    if q.round is not None and case.round != q.round:
        return False
    if q.var_changed and not case.var_changed:
        return False
    if q.team_ids and not ({case.home_id, case.away_id} & q.team_ids):
        return False
    if q.official_ids and case.referee_id not in q.official_ids:
        return False

    by_field: dict[str, list[Term]] = {}
    for t in q.terms:
        by_field.setdefault(t.field, []).append(t)
    for terms in by_field.values():  # AND across kinds, OR within a kind
        hit = False
        for t in terms:
            if _structured_hit(case, t):
                case.why.append(f"«{t.phrase}» ← {t.field}={t.value}")
                hit = True
            elif any(p.search(text) for p in t.synonyms):
                case.why.append(f"«{t.phrase}» ← في النص")
                hit = True
        if not hit:
            return False
    for w in q.words:  # every leftover word must appear in the text
        if not _pattern(w).search(text):
            return False
        case.why.append(f"«{w}» ← في النص")
    return True


def search(conn: sqlite3.Connection, q: Query) -> list[Case]:
    found = [c for c in load_library(conn) if matches(c, q)]

    def structured_hits(c: Case) -> int:  # matches on fields rank above text matches
        return sum("في النص" not in w for w in c.why)

    return sorted(found, key=lambda c: (-structured_hits(c), c.round, c.minute or 999))


# ---------------------------------------------------------------------------
# output
# ---------------------------------------------------------------------------


STANCE_AR = {
    "agree": "مع قرار الحكم",
    "disagree": "ضد قرار الحكم",
    "unclear": "غير واضح",
    "correct": "صحيح",
    "incorrect": "خاطئ",
}


def _decision_ar(case: Case, stage: str) -> str:
    d = case.decisions.get(stage)
    if d is None:
        return ""
    cards = "، ".join(
        f"{AR[c['sanction']]} لـ{c['person_name']}"
        + (f" ({c['reason_ar']})" if c["reason_ar"] else "")
        for c in case.cards.get(stage, [])
    )
    return f"{AR[d['offence']]} ← {AR[d['outcome']]}" + (f" + {cards}" if cards else "")


def _video(case: Case) -> str:
    if not case.video_url:
        return "لا يوجد فيديو بعد"
    if case.video_start_sec:
        return f"{case.video_url} (من الثانية {case.video_start_sec})"
    return case.video_url


def _stances(case: Case) -> str:
    if not case.opinions:
        return "لا توجد آراء بعد"
    agree = sum(o["stance"] == "agree" for o in case.opinions)
    disagree = sum(o["stance"] == "disagree" for o in case.opinions)
    return f"{agree} مع قرار الحكم، {disagree} ضده"


def format_results(q: Query, results: list[Case]) -> str:
    lines = [f"بحث: «{q.text}» — {len(results)} حالة", ""]
    for c in results:
        minute = f"د{c.minute}" if c.minute else "الدقيقة غير معروفة"
        lines += [
            f"#{c.incident_id}  ج{c.round}  {c.match}  {minute}  الحكم: {c.referee}",
            f"    الملعب: {_decision_ar(c, 'on_field')}",
        ]
        if "final" in c.decisions:
            lines.append(f"    بعد الـVAR: {_decision_ar(c, 'final')}")
        lines += [
            f"    VAR: {AR[c.var_review]} | الخبراء: {_stances(c)} | {_video(c)}",
            f"    لماذا: {' ؛ '.join(c.why) or 'فلاتر فقط'}",
            "",
        ]
    return "\n".join(lines)


def format_quiz(q: Query, results: list[Case]) -> str:
    """A video quiz: question first, the answer folded away (GitHub Markdown)."""
    lines = [
        f"# اختبار فيديو: {q.text}",
        "",
        f"{len(results)} حالة. شاهد اللقطة، قرر، ثم افتح الإجابة.",
        "",
    ]
    for i, c in enumerate(results, start=1):
        minute = f"الدقيقة {c.minute}" if c.minute else "الدقيقة غير معروفة"
        if c.status == "controversial":
            verdict = "⚖️ حالة جدلية: لا يوجد حكم رسمي منشور من لجنة الحكام."
        else:
            verdict = f"✅ حكم رسمي من لجنة الحكام: القرار {STANCE_AR[c.verdict]}."
        lines += [
            f"## {i}. {c.match} — الجولة {c.round} — {minute}",
            "",
            f"🎥 {_video(c)}",
            "",
            "**قرارك؟** هل توجد مخالفة؟ كيف يُستأنف اللعب؟ هل يُشهر كارت؟",
            "",
            "<details><summary>الإجابة</summary>",
            "",
            f"- **قرار الحكم في الملعب:** {_decision_ar(c, 'on_field')}",
        ]
        if "final" in c.decisions:
            lines.append(f"- **بعد مراجعة الـVAR:** {_decision_ar(c, 'final')}")
        lines += [f"- **الـVAR:** {AR[c.var_review]}", f"- {verdict}", "- **آراء الخبراء:**"]
        opinions = [
            f"  - {o['expert']} ({STANCE_AR[o['stance']]}): {o['summary']}" for o in c.opinions
        ]
        lines += opinions or ["  - لا توجد آراء بعد"]
        lines += ["", "</details>", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("query", nargs="?", default="", help="بالعامية أو الفصحى")
    parser.add_argument("--round", type=int)
    parser.add_argument("--var-changed", action="store_true", help="only cases VAR changed")
    parser.add_argument("--quiz", type=Path, help="write a Markdown video quiz to this file")
    parser.add_argument("--raw", type=Path, default=DEFAULT_RAW)
    parser.add_argument("--vocab", type=Path, default=DEFAULT_VOCAB)
    args = parser.parse_args(argv)

    conn = connect(":memory:")
    apply_schema(conn)
    load_all(conn, args.raw)
    load_cases(conn, args.raw)
    load_commendations(conn, args.raw)

    q = parse(conn, args.query, load_vocab(args.vocab))
    q.round, q.var_changed = args.round, args.var_changed
    results = search(conn, q)
    sys.stdout.reconfigure(encoding="utf-8")
    print(format_results(q, results))
    if args.quiz:
        args.quiz.write_text(format_quiz(q, results), encoding="utf-8")
        print(f"Quiz written to {args.quiz}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
