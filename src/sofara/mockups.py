"""Part د — what the committee's own data would add: labelled mockups.

Everything here is SYNTHETIC. It shows what the project could do with data the
committee keeps and does not publish (assessor reports, VAR-room logs, the
appointment history). Rules (decision 0018):

- every name is invented ("الحكم أ", "فريق س"); no real referee, team or match
- the numbers come from a fixed seed, so the page is the same on every build
- the page labels the whole tab, and every chart, as illustrative

    >>> a, b = mockups(), mockups()
    >>> a == b
    True
    >>> all(r["name"].startswith("الحكم ") for r in a["referees"])
    True
"""

from __future__ import annotations

import random
import statistics

SEED = 2026
REFEREES = ["الحكم أ", "الحكم ب", "الحكم ج", "الحكم د", "الحكم هـ", "الحكم و"]
TEAMS = ["فريق س", "فريق ص", "فريق ع", "فريق ل", "فريق م", "فريق ن", "فريق ق", "فريق ر"]
ERROR_TYPES = [
    "قرارات داخل منطقة الجزاء",
    "درجة البطاقة",
    "إدارة الميزة",
    "التمركز والزاوية",
    "قرارات التسلل مع المساعد",
]
REVIEW_TYPES = ["ركلة جزاء", "تسلل قبل هدف", "بطاقة حمراء مباشرة", "خطأ في هوية اللاعب"]
DIFFICULTY_AR = {"high": "مرتفعة", "medium": "متوسطة", "low": "منخفضة"}


def _progress(rng: random.Random) -> dict:
    """One referee's assessor marks over a season, and his recurring error types."""
    marks, mark = [], 7.4
    for match in range(1, 15):
        mark = min(9.4, max(6.2, mark + rng.uniform(-0.35, 0.45)))
        marks.append(
            {
                "match": match,
                "mark": round(mark, 1),
                "difficulty": rng.choice(["high", "medium", "medium", "low"]),
            }
        )
    errors = [{"type": t, "count": n} for t, n in zip(ERROR_TYPES, (7, 4, 3, 2, 1), strict=True)]
    return {"referee": REFEREES[0], "marks": marks, "errors": errors}


def _appointments(rng: random.Random) -> dict:
    """Candidate referees for three fixtures, with the facts an appointer weighs."""
    referees = []
    for name in REFEREES:
        last = rng.sample(TEAMS, 2)
        referees.append(
            {
                "name": name,
                "rest_days": rng.choice([2, 3, 4, 5, 6, 7]),
                "last_teams": last,  # teams he refereed in the last two rounds
                "mark_high": round(rng.uniform(6.8, 8.9), 1),  # average in high-difficulty matches
                "mark_all": round(rng.uniform(7.2, 8.6), 1),
                "matches_this_season": rng.randint(3, 9),
                "international": name in ("الحكم أ", "الحكم ج"),
            }
        )
    fixtures = [
        {"home": "فريق س", "away": "فريق ص", "difficulty": "high"},
        {"home": "فريق ع", "away": "فريق ل", "difficulty": "medium"},
        {"home": "فريق م", "away": "فريق ن", "difficulty": "low"},
    ]
    for f in fixtures:
        f["difficulty_ar"] = DIFFICULTY_AR[f["difficulty"]]
    return {"referees": referees, "fixtures": fixtures}


def _var_room(rng: random.Random) -> dict:
    """A season of VAR reviews: how long they take and what they are about."""
    reviews = []
    for _ in range(64):
        kind = rng.choices(REVIEW_TYPES, weights=[45, 30, 15, 10])[0]
        base = {
            "ركلة جزاء": 85,
            "تسلل قبل هدف": 70,
            "بطاقة حمراء مباشرة": 95,
            "خطأ في هوية اللاعب": 50,
        }[kind]
        seconds = max(20, int(rng.lognormvariate(0, 0.45) * base))
        reviews.append({"kind": kind, "seconds": seconds, "ofr": rng.random() < 0.35})
    durations = [r["seconds"] for r in reviews]
    bins = []
    for lo in range(0, 240, 30):
        hi = lo + 30
        bins.append(
            {
                "from": lo,
                "to": hi,
                "count": sum(lo <= s < hi for s in durations)
                if hi < 240
                else sum(s >= lo for s in durations),
            }
        )
    while bins and bins[-1]["count"] == 0:  # drop empty bins at the long end
        bins.pop()
    by_kind = [
        {
            "kind": k,
            "n": len(ks := [r["seconds"] for r in reviews if r["kind"] == k]),
            "median": int(statistics.median(ks)),
        }
        for k in REVIEW_TYPES
    ]
    return {
        "n": len(reviews),
        "median": int(statistics.median(durations)),
        "ofr_share": round(sum(r["ofr"] for r in reviews) / len(reviews), 2),
        "bins": bins,
        "by_kind": by_kind,
    }


def mockups() -> dict:
    """All mockup data, from one fixed seed."""
    rng = random.Random(SEED)
    progress = _progress(rng)
    appointments = _appointments(rng)
    return {
        "progress": progress,
        "appointments": appointments,
        "var_room": _var_room(rng),
        "referees": appointments["referees"],
    }
