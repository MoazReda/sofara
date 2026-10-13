"""`sofara-disputes`: where experts disagree, and about what — an Arabic page.

Usage (from the repository root):
    sofara-disputes                     # prints Markdown
    sofara-disputes --out disputes.md

For every case with two or more independent expert opinions that do not all
agree, it shows the decisions (on the field, after VAR, the committee's
ruling), each side's experts, the grounds they cite and what kind of
disagreement it is. Then the consistency comparisons experts have made.

Opinions are our summaries, with the source of each. Nothing here is our own
verdict: the only verdict shown is the committee's (decision 0015), and the
labels follow decision 0016.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

from sofara.agreement import (
    case_agreement,
    load_case_comparisons,
    load_opinion_reasons,
)
from sofara.build import DEFAULT_RAW, apply_schema, connect
from sofara.cases import load_cases
from sofara.registry import DataError, load_all
from sofara.search import AR

STAGE_AR = {
    "on_field": "قرار الحكم في الملعب",
    "final": "بعد الـVAR",
    "official": "حكم لجنة الحكام",
}
STANCE_AR = {"agree": "القرار صحيح", "disagree": "القرار خطأ", "unclear": "لم يحسم"}
BACKGROUND_AR = {
    "ex_referee": "حكم سابق",
    "analyst": "محلل",
    "ex_player": "لاعب سابق",
    "journalist": "صحفي",
}
KIND_AR = {
    "fact": "الوقائع (ماذا حدث)",
    "threshold": "حدّ المخالفة (هل يكفي؟)",
    "law": "نص القانون",
    "var": "بروتوكول الـVAR",
    "process": "إدارة الحكم للعبة",
    "consistency": "ثبات المعايير",
}
LABEL_AR = {
    "contested": "حالة جدلية",
    "consensus": "شبه إجماع",
    "small_sample": "عينة صغيرة (أقل من 3 آراء)",
}


def _decision(conn: sqlite3.Connection, incident_id: int, stage: str) -> str | None:
    row = conn.execute(
        "SELECT offence, outcome FROM incident_decisions WHERE incident_id = ? AND stage = ?",
        (incident_id, stage),
    ).fetchone()
    if row is None:
        return None
    offence, outcome = row
    text = AR.get(outcome, outcome)
    if offence not in ("none", "other"):
        text += f" ({AR.get(offence, offence)})"
    cards = conn.execute(
        """SELECT person_name, sanction FROM incident_sanctions
           WHERE incident_id = ? AND stage = ? ORDER BY person_name""",
        (incident_id, stage),
    ).fetchall()
    if cards:
        text += " — " + "، ".join(f"{AR.get(s, s)}: {p}" for p, s in cards)
    return text


def _header(conn: sqlite3.Connection, incident_id: int) -> tuple[str, str]:
    row = conn.execute(
        """SELECT m.round, h.name_ar, a.name_ar, i.minute, i.added_minute, i.description_ar,
                  o.name_ar, o.nationality
           FROM incidents i JOIN matches m USING (match_id)
           JOIN teams h ON h.team_id = m.home_team_id
           JOIN teams a ON a.team_id = m.away_team_id
           LEFT JOIN match_officials mo ON mo.match_id = m.match_id AND mo.role = 'referee'
           LEFT JOIN officials o USING (official_id)
           WHERE i.incident_id = ?""",
        (incident_id,),
    ).fetchone()
    rnd, home, away, minute, added, desc, referee, nationality = row
    when = ""
    if minute is not None:
        when = f" — الدقيقة {minute}" + (f"+{added}" if added else "")
    ref = referee or "غير معروف"
    if nationality and nationality != "Egypt":
        ref += " (طاقم أجنبي)"
    title = f"حالة {incident_id} — الجولة {rnd}: {home} × {away}{when}"
    return title, f"{desc}\n\nحكم المباراة: {ref}"


def _decisions_block(conn: sqlite3.Connection, incident_id: int) -> list[str]:
    lines = []
    for stage in ("on_field", "final", "official"):
        text = _decision(conn, incident_id, stage)
        if text is None:
            continue
        if stage == "official":
            (url,) = conn.execute(
                "SELECT source_url FROM incident_decisions WHERE incident_id = ? AND stage = ?",
                (incident_id, stage),
            ).fetchone()
            text += f" ([المصدر]({url}))"
        lines.append(f"- **{STAGE_AR[stage]}:** {text}")
    if not any(line.startswith(f"- **{STAGE_AR['official']}") for line in lines):
        lines.append(f"- **{STAGE_AR['official']}:** لا يوجد حكم منشور (حالة جدلية)")
    return lines


def _opinions_table(conn: sqlite3.Connection, incident_id: int) -> list[str]:
    rows = conn.execute(
        """SELECT e.name_ar, e.background, o.stance, o.summary_ar, o.source_name, o.source_url,
                  (SELECT group_concat(rc.name_ar, '، ') FROM opinion_reasons r
                   JOIN reason_codes rc ON rc.code = r.reason
                   WHERE r.opinion_id = o.opinion_id)
           FROM expert_opinions o JOIN experts e USING (expert_id)
           WHERE o.incident_id = ? AND COALESCE(e.background, '')
                 NOT IN ('committee', 'committee_source')
           ORDER BY o.stance, e.name_ar""",
        (incident_id,),
    ).fetchall()
    out = ["| الخبير | الرأي | يستند إلى | الملخص | المصدر |", "|---|---|---|---|---|"]
    for name, background, stance, summary, source_name, url, grounds in rows:
        who = name + (f" ({BACKGROUND_AR[background]})" if background in BACKGROUND_AR else "")
        out.append(
            f"| {who} | {STANCE_AR[stance]} | {grounds or '—'} | {summary} "
            f"| [{source_name}]({url}) |"
        )
    return out


def _grounds_by_side(conn: sqlite3.Connection, incident_id: int) -> list[str]:
    """One line per side: the kinds of grounds its experts cite."""
    lines = []
    for stance, who in (("agree", "من يرون القرار صحيحاً"), ("disagree", "من يرونه خطأ")):
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
                (incident_id, stance),
            )
        ]
        text = "، ".join(KIND_AR[k] for k in kinds) if kinds else "لم يذكروا أسباباً"
        lines.append(f"- {who} يستندون إلى: {text}")
    return lines


def render(conn: sqlite3.Connection) -> str:
    lines = [
        "# صفارة — حالات تحتاج توضيحاً",
        "",
        "حالات انقسمت حولها آراء الحكام السابقين والمحللين في الإعلام، وهي بذلك مرشحة لأن"
        " يتناولها فيديو التوضيح الذي تنشره لجنة الحكام بعد كل جولة. لكل حالة نعرض ما قرر"
        "ه الحكم وما نشرته اللجنة، ثم ما استند إليه كل رأي. لجنة الحكام لا تُحسب ضمن الآر"
        "اء، ومع أقل من ثلاثة آراء لا نصف الحالة بأنها جدلية أو محسومة. الآراء ملخصة بكلم"
        "اتنا مع مصدر كل رأي، ولا نضيف حكماً من عندنا.",
        "",
    ]
    split_cases = [c for c in case_agreement(conn) if c.agree and c.disagree]
    for c in split_cases:
        title, intro = _header(conn, c.incident_id)
        lines += [f"## {title}", "", intro, ""]
        lines += _decisions_block(conn, c.incident_id)
        lo, hi = c.range
        lines += [
            "",
            f"**{LABEL_AR[c.label]}:** {c.agree} يرون القرار صحيحاً و{c.disagree} يرونه خطأ "
            f"(درجة الانقسام {c.split}؛ النسبة الحقيقية لمن يرونه صحيحاً بين "
            f"{lo:.0%} و{hi:.0%} بثقة 95%).",
            "",
            *_grounds_by_side(conn, c.incident_id),
            "",
        ]
        lines += _opinions_table(conn, c.incident_id)
        lines.append("")

    comparisons = conn.execute(
        """SELECT c.incident_id, c.other_incident_id, e.name_ar, c.note_ar, c.source_url
           FROM case_comparisons c JOIN experts e USING (expert_id)
           ORDER BY c.incident_id"""
    ).fetchall()
    if comparisons:
        lines += ["## ثبات المعايير: حالات قال خبير إنها متماثلة", ""]
        for a, b, expert, note, url in comparisons:
            lines += [f"### حالة {a} مقابل حالة {b}", "", f"{expert}: {note} ([المصدر]({url}))", ""]
            lines += ["| | " + f"حالة {a}" + " | " + f"حالة {b}" + " |", "|---|---|---|"]
            ta, _ = _header(conn, a)
            tb, _ = _header(conn, b)
            lines.append(f"| المباراة | {ta.split(' — ', 1)[1]} | {tb.split(' — ', 1)[1]} |")
            for stage in ("on_field", "final", "official"):
                da, db = _decision(conn, a, stage), _decision(conn, b, stage)
                if da or db:
                    lines.append(f"| {STAGE_AR[stage]} | {da or '—'} | {db or '—'} |")
            lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--raw", type=Path, default=DEFAULT_RAW)
    parser.add_argument("--out", type=Path, help="write the Markdown here instead of printing")
    args = parser.parse_args(argv)
    conn = connect(":memory:")
    apply_schema(conn)
    try:
        load_all(conn, args.raw)
        load_cases(conn, args.raw)
        load_opinion_reasons(conn, args.raw)
        load_case_comparisons(conn, args.raw)
    except DataError as e:
        print(f"Data does not build ({len(e.problems)} problem(s)) — run sofara-build.")
        return 1
    text = render(conn)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
        print(f"Wrote {args.out}")
    else:
        sys.stdout.reconfigure(encoding="utf-8")
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
