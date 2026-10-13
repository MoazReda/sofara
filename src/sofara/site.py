"""`sofara-site`: build the demo page — one self-contained Arabic HTML file.

Usage (from the repository root):
    sofara-site                        # writes site/index.html
    sofara-site --out demo.html

The page has three tabs: the case library (with the same search as
sofara-search), where experts disagree (as sofara-disputes), and how the data
was made. Everything is computed here from data/raw and embedded in the page as
JSON, so the page needs no server and works offline in a meeting.

Search parity: Python works out, for every vocabulary term, which cases it hits
(on a decision field or only in the text); site/search.js reads the query the
same way search.py does. tests/test_site.py checks both give the same cases.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import date
from importlib import resources
from pathlib import Path

from sofara.agreement import (
    case_agreement,
    load_case_comparisons,
    load_opinion_reasons,
)
from sofara.build import DEFAULT_RAW, apply_schema, connect
from sofara.cases import load_cases
from sofara.commendations import load_commendations
from sofara.disputes import BACKGROUND_AR, KIND_AR, LABEL_AR, STAGE_AR, STANCE_AR
from sofara.efa_lists import load_efa_lists
from sofara.mockups import mockups
from sofara.registry import DataError, load_all
from sofara.reviews import load_reviews
from sofara.search import (
    AR,
    DEFAULT_VOCAB,
    STOPWORDS,
    _names,
    _structured_hit,
    load_library,
    load_vocab,
)

DEFAULT_OUT = Path("site/index.html")
REPO_URL = "https://github.com/MoazReda/sofara"
FIELD_AR = {
    "offence": "المخالفة",
    "outcome": "القرار",
    "sanction": "البطاقة",
    "reason": "سبب البطاقة",
    "var": "الـVAR",
    "var_changed": "الـVAR غيّر القرار",
}


def _read(name: str) -> str:
    return resources.files("sofara").joinpath("site", name).read_text(encoding="utf-8")


def _decision_ar(d: dict | None) -> str | None:
    if not d:
        return None
    text = AR.get(d["outcome"], d["outcome"])
    if d["offence"] not in ("none", "other"):
        text += f" ({AR.get(d['offence'], d['offence'])})"
    return text


def build_data(conn: sqlite3.Connection, vocab_path: Path = DEFAULT_VOCAB) -> dict:
    """Everything the page shows, as plain JSON-able structures."""
    library = load_library(conn)
    conn.row_factory = None
    extra = {
        r[0]: r[1:]
        for r in conn.execute(
            """SELECT s.incident_id, s.added_minute, s.call_verdict, s.card_verdict,
                      s.verdict_source_url, s.source_url, s.found_via, o.nationality
               FROM v_incident_summary s
               LEFT JOIN officials o ON o.official_id = s.referee_id"""
        )
    }
    grounds: dict[tuple[int, str], list[str]] = {}
    for incident_id, expert, name_ar in conn.execute(
        """SELECT o.incident_id, e.name_ar, rc.name_ar FROM expert_opinions o
           JOIN experts e USING (expert_id)
           JOIN opinion_reasons r USING (opinion_id)
           JOIN reason_codes rc ON rc.code = r.reason"""
    ):
        grounds.setdefault((incident_id, expert), []).append(name_ar)
    opinions: dict[int, list[dict]] = {}
    for incident_id, expert, background, stance, summary, source, url in conn.execute(
        """SELECT o.incident_id, e.name_ar, e.background, o.stance, o.summary_ar,
                  o.source_name, o.source_url
           FROM expert_opinions o JOIN experts e USING (expert_id)
           ORDER BY o.incident_id, o.stance, e.name_ar"""
    ):
        opinions.setdefault(incident_id, []).append(
            {
                "expert": expert,
                "background": BACKGROUND_AR.get(background or "", ""),
                "committee": background in ("committee", "committee_source"),
                "stance": stance,
                "stance_ar": STANCE_AR[stance],
                "summary": summary,
                "source": source,
                "url": url,
                "grounds": grounds.get((incident_id, expert), []),
            }
        )

    cases = []
    for c in library:
        added, call_v, card_v, ruling_url, source_url, found_via, nationality = extra[c.incident_id]
        home, away = c.match.split(" × ")
        stages = []
        for stage in ("on_field", "final", "official"):
            d = c.decisions.get(stage)
            if d is None:
                continue
            stages.append(
                {
                    "stage": stage,
                    "label": STAGE_AR[stage],
                    "decision": _decision_ar(d),
                    "cards": [
                        {"person": k["person_name"], "sanction": k["sanction"]}
                        for k in c.cards.get(stage, [])
                    ],
                }
            )
        cases.append(
            {
                "id": c.incident_id,
                "round": c.round,
                "home": home,
                "away": away,
                "home_id": c.home_id,
                "away_id": c.away_id,
                "minute": c.minute,
                "added": added or 0,
                "referee": c.referee,
                "referee_id": c.referee_id,
                "foreign_crew": bool(nationality and nationality != "Egypt"),
                "description": c.description,
                "var_review": c.var_review,
                "var_review_ar": AR.get(c.var_review, c.var_review),
                "var_changed": c.var_changed,
                "status": c.status,
                "call_verdict": call_v,
                "card_verdict": card_v,
                "ruling_url": ruling_url,
                "source_url": source_url,
                "video_url": c.video_url,
                "found_via": found_via,
                "stages": stages,
                "opinions": opinions.get(c.incident_id, []),
                "text": c.text,
            }
        )

    # search index (decision: same answers as sofara-search)
    terms = []
    for t in sorted(load_vocab(vocab_path), key=lambda t: -len(t.phrase)):
        hits = {}
        for c in library:
            if _structured_hit(c, t):
                hits[c.incident_id] = "field"
            elif any(p.search(c.text) for p in t.synonyms):
                hits[c.incident_id] = "text"
        label = FIELD_AR.get(t.field, t.field)
        if t.field not in ("text", "var_changed"):
            label += f": {AR.get(t.value, t.value)}"
        terms.append({"phrase": t.phrase, "field": t.field, "label": label, "hits": hits})
    # the longest normalized phrase first, exactly as search.parse does
    from sofara.normalize import normalize_name

    terms.sort(key=lambda t: -len(normalize_name(t["phrase"])))
    index = {
        "teams": _names(
            conn,
            "SELECT name_ar, team_id FROM teams UNION SELECT alias, team_id FROM team_aliases",
        ),
        "officials": _names(conn, "SELECT name, official_id FROM v_official_lookup"),
        "terms": terms,
        "stopwords": sorted(STOPWORDS),
    }

    disputes = []
    for a in case_agreement(conn):
        if not (a.agree and a.disagree):
            continue
        sides = {}
        for stance in ("agree", "disagree"):
            kinds = [
                k
                for (k,) in conn.execute(
                    """SELECT DISTINCT rc.kind FROM expert_opinions o
                       JOIN experts e USING (expert_id)
                       JOIN opinion_reasons r USING (opinion_id)
                       JOIN reason_codes rc ON rc.code = r.reason
                       WHERE o.incident_id = ? AND o.stance = ?
                         AND COALESCE(e.background, '') NOT IN ('committee', 'committee_source')
                       ORDER BY rc.kind""",
                    (a.incident_id, stance),
                )
            ]
            sides[stance] = [KIND_AR[k] for k in kinds]
        lo, hi = a.range
        disputes.append(
            {
                "id": a.incident_id,
                "agree": a.agree,
                "disagree": a.disagree,
                "split": a.split,
                "low": lo,
                "high": hi,
                "label": a.label,
                "label_ar": LABEL_AR[a.label],
                "grounds": sides,
            }
        )
    comparisons = [
        {"a": a, "b": b, "expert": e, "note": n, "url": u}
        for a, b, e, n, u in conn.execute(
            """SELECT c.incident_id, c.other_incident_id, e.name_ar, c.note_ar, c.source_url
               FROM case_comparisons c JOIN experts e USING (expert_id)"""
        )
    ]

    def one(sql: str) -> int:
        return conn.execute(sql).fetchone()[0] or 0

    n_cases = len(cases)
    bias = [
        {"team": t, "cases": n, "share": round(n / n_cases, 2)}
        for t, n in conn.execute(
            """SELECT t.name_ar, COUNT(DISTINCT i.incident_id) FROM incidents i
               JOIN matches m USING (match_id)
               JOIN teams t ON t.team_id IN (m.home_team_id, m.away_team_id)
               GROUP BY t.name_ar ORDER BY 2 DESC, 1 LIMIT 3"""
        )
    ]
    stats = {
        "cases": n_cases,
        "matches": one("SELECT COUNT(*) FROM matches"),
        "reviewed": one("SELECT COUNT(*) FROM v_match_coverage WHERE reviews > 0"),
        "rounds": one("SELECT MAX(round) FROM matches"),
        "ruled": one("SELECT COUNT(*) FROM v_incident_summary WHERE status = 'ruled'"),
        "opinions": one("SELECT COUNT(*) FROM expert_opinions"),
        "experts": one("SELECT COUNT(*) FROM experts"),
        "officials": one("SELECT COUNT(*) FROM officials"),
        "bias": bias,
        "built": date.today().isoformat(),
    }
    return {
        "cases": cases,
        "index": index,
        "disputes": disputes,
        "comparisons": comparisons,
        "stats": stats,
        "rounds": sorted({c["round"] for c in cases}),
        "repo": REPO_URL,
        "mock": mockups(),
    }


def render(data: dict, fragment: bool = False) -> str:
    """The page. fragment=True leaves out <!doctype>/<head>/<body> (for hosts
    that add their own skeleton); otherwise a complete HTML document."""
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    payload = payload.replace("</", "<\\/")  # never close the <script> early
    page = (
        _read("template.html")
        .replace("/*__SEARCH_JS__*/", _read("search.js"))
        .replace("/*__DATA__*/null", payload)
    )
    if fragment:
        return page
    head, body = page.split("</style>", 1)
    return (
        '<!doctype html>\n<html lang="ar" dir="rtl">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<meta name="robots" content="noindex, nofollow">\n'
        f"{head}</style>\n</head>\n<body>{body}</body>\n</html>\n"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--raw", type=Path, default=DEFAULT_RAW)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--fragment", action="store_true", help="no <html>/<head> wrapper")
    args = parser.parse_args(argv)
    conn = connect(":memory:")
    apply_schema(conn)
    try:
        load_all(conn, args.raw)
        load_cases(conn, args.raw)
        load_commendations(conn, args.raw)
        load_reviews(conn, args.raw)
        load_efa_lists(conn, args.raw)
        load_opinion_reasons(conn, args.raw)
        load_case_comparisons(conn, args.raw)
    except DataError as e:
        print(f"Data does not build ({len(e.problems)} problem(s)) — run sofara-build.")
        return 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render(build_data(conn), args.fragment), encoding="utf-8")
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
