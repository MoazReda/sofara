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
        "vision": vision(),
    }


# ---- the vision tab (part د, v2) --------------------------------------------

CASE_TYPES = ["لمسة اليد", "التسلل", "ركلات الجزاء", "الإنذارات", "الطرد", "قانون الميزة"]
PERIODS = ["أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر", "يناير", "فبراير", "مارس"]

# what an assessor's free-text notes are about; three themes so every colour on
# the page stays distinguishable (decision 0018, dataviz checks)
NOTE_THEMES = {
    "positioning": (
        "التمركز وزاوية الرؤية",
        ["بعيداً عن الحالة", "زاوية رؤية", "خلف اللعب", "التمركز"],
    ),
    "timing": (
        "توقيت الصافرة",
        ["تأخر في إطلاق الصافرة", "تأخر في الصافرة", "صافرة متأخرة", "تسرّع في الصافرة"],
    ),
    "management": ("إدارة اللاعبين", ["احتجاجات", "السيطرة على", "التواصل مع اللاعبين", "تهدئة"]),
}
NOTES = [
    "كان الحكم بعيداً عن الحالة عند احتكاك منطقة الجزاء في الدقيقة ٣٤، وزاوية رؤية غير مناسبة "
    "حجبت عنه لمسة اليد. تأخر في إطلاق الصافرة بعد الالتحام، مما سمح بتصاعد احتجاجات اللاعبين.",
    "أداء جيد في السيطرة على المباراة في الشوط الأول. في الشوط الثاني لوحظ التمركز خلف اللعب في "
    "الهجمات المرتدة، وصافرة متأخرة في حالتين كان يمكن فيهما تطبيق الميزة بشكل أفضل.",
    "تواصل واضح مع المساعدين. التواصل مع اللاعبين كان هادئاً وساعد على تهدئة الأجواء بعد الهدف، "
    "مع ملاحظة تسرّع في الصافرة في حالة كان يمكن فيها ترك اللعب.",
]


def annotate(text: str) -> list[dict]:
    """Find the theme phrases in a note; returns non-overlapping spans.

    >>> [s["theme"] for s in annotate("وقف بعيداً عن الحالة ثم تأخر في الصافرة")]
    ['positioning', 'timing']
    """
    spans = []
    for theme, (_, phrases) in NOTE_THEMES.items():
        for phrase in sorted(phrases, key=len, reverse=True):
            start = text.find(phrase)
            while start != -1:
                end = start + len(phrase)
                if all(end <= s["start"] or start >= s["end"] for s in spans):
                    spans.append({"start": start, "end": end, "theme": theme})
                start = text.find(phrase, end)
    return sorted(spans, key=lambda s: s["start"])


def _pct(x: float) -> str:
    """0.71 -> '٧١٪' (Arabic-Indic digits, as on the page)."""
    return str(round(x * 100)).translate(str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")) + "٪"


def _profile(rng: random.Random) -> dict:
    """Share of correct decisions per case type and month for one referee."""
    base = {
        "لمسة اليد": 0.66,
        "التسلل": 0.9,
        "ركلات الجزاء": 0.74,
        "الإنذارات": 0.83,
        "الطرد": 0.86,
        "قانون الميزة": 0.79,
    }
    trend = {
        "لمسة اليد": 0.025,
        "التسلل": 0.004,
        "ركلات الجزاء": -0.012,
        "الإنذارات": 0.01,
        "الطرد": 0.0,
        "قانون الميزة": 0.012,
    }
    grid = []
    for t in CASE_TYPES:
        row = []
        for i, _ in enumerate(PERIODS):
            v = base[t] + trend[t] * i + rng.uniform(-0.03, 0.03)
            row.append(round(min(0.98, max(0.5, v)), 2))
        grid.append({"type": t, "values": row})
    pen = next(r["values"] for r in grid if r["type"] == "ركلات الجزاء")
    hand = next(r["values"] for r in grid if r["type"] == "لمسة اليد")
    return {
        "referee": REFEREES[0],
        "periods": PERIODS,
        "grid": grid,
        "plan": [
            {
                "focus": "ركلات الجزاء",
                "why": f"الدقة تنخفض منذ ديسمبر (من {_pct(pen[4])} إلى {_pct(pen[-1])})",
                "content": [
                    "محاضرة: الاحتكاك داخل المنطقة، ١٨ دقيقة",
                    "١٢ حالة فيديو من هذا الموسم",
                ],
            },
            {
                "focus": "لمسة اليد",
                "why": f"أكبر تحسن هذا الموسم (من {_pct(hand[0])} إلى {_pct(hand[-1])})",
                "content": ["استمرار: اختبار قصير كل شهر"],
            },
        ],
    }


def _nlp(rng: random.Random) -> dict:
    notes = [{"text": t, "spans": annotate(t)} for t in NOTES]
    totals = {"positioning": 61, "timing": 44, "management": 27}  # over 120 example reports
    return {
        "notes": notes,
        "themes": {k: v[0] for k, v in NOTE_THEMES.items()},
        "totals": totals,
        "reports": 120,
    }


def _var_timeline() -> list[dict]:
    return [
        {"t": 0, "label": "رصد الحالة"},
        {"t": 14, "label": "فحص الزوايا"},
        {"t": 38, "label": "التوصية بالمراجعة"},
        {"t": 51, "label": "الحكم أمام الشاشة"},
        {"t": 83, "label": "القرار النهائي"},
    ]


def _pilots(rng: random.Random) -> dict:
    training = {
        "topic": "لمسة اليد",
        "groups": [
            {
                "group": "حضروا المحاضرة",
                "before": 0.67,
                "after": 0.79,
                "lo": 0.72,
                "hi": 0.85,
                "n": 14,
            },
            {
                "group": "لم يحضروا بعد",
                "before": 0.68,
                "after": 0.70,
                "lo": 0.62,
                "hi": 0.77,
                "n": 11,
            },
        ],
    }
    talent = []
    for name, start, slope in (
        ("الحكم ز", 6.9, 0.11),
        ("الحكم ح", 7.3, 0.01),
        ("الحكم ط", 7.0, 0.04),
    ):
        talent.append(
            {
                "name": name,
                "marks": [
                    round(start + slope * i + rng.uniform(-0.12, 0.12), 2) for i in range(10)
                ],
            }
        )
    fatigue = [
        {"bin": b, "accuracy": a}
        for b, a in zip(
            ["٠–١٥", "١٥–٣٠", "٣٠–٤٥", "٤٥–٦٠", "٦٠–٧٥", "٧٥–٩٠+"],
            (0.86, 0.85, 0.84, 0.84, 0.81, 0.76),
            strict=True,
        )
    ]
    assessors = []
    for name, mid, spread in (
        ("المقيّم ١", 7.9, 0.5),
        ("المقيّم ٢", 7.6, 0.4),
        ("المقيّم ٣", 8.4, 0.3),
        ("المقيّم ٤", 7.7, 0.6),
        ("المقيّم ٥", 7.2, 0.4),
    ):
        assessors.append(
            {
                "name": name,
                "low": round(mid - 2 * spread, 1),
                "q1": round(mid - spread, 1),
                "median": mid,
                "q3": round(mid + spread, 1),
                "high": round(mid + 2 * spread, 1),
            }
        )
    return {"training": training, "talent": talent, "fatigue": fatigue, "assessors": assessors}


def vision() -> dict:
    """Data for the vision tab, from its own fixed seed.

    >>> v = vision()
    >>> sorted(v) == ["nlp", "pilots", "profile", "var_timeline"]
    True
    """
    rng = random.Random(SEED + 1)
    return {
        "profile": _profile(rng),
        "nlp": _nlp(rng),
        "var_timeline": _var_timeline(),
        "pilots": _pilots(rng),
    }
