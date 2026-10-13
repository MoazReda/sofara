"""Part ج — how much do experts agree, and what do they disagree about?

Two pieces:

1. `load_opinion_reasons` reads data/raw/opinion_reasons.csv
       case_id, expert, reason
   one row = one ground an expert cited in one opinion (see reason_codes in the
   schema). Must run AFTER the case library.

2. The measures (decision 0016):

   split score   2 × minority / n          0 = all agree, 1 = an even split
                 (symmetric: 4-3 and 3-4 give the same value; never divides by 0)
   Wilson range  where the true share of "the decision was right" plausibly
                 lies, given only n opinions (95%). Wide range = we can't tell.
   label         n < 3                 -> small_sample (no claim either way)
                 minority >= 1/3       -> contested
                 otherwise             -> consensus

Only independent experts count: the committee and unnamed committee sources
are left out of expert agreement (the committee's own view is the official
ruling, compared separately). "unclear" opinions are not counted for or
against.
"""

from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from sofara.normalize import normalize_name
from sofara.registry import DataError, read_csv

FILE = "opinion_reasons"
COLUMNS = ["case_id", "expert", "reason"]
NOT_INDEPENDENT = ("committee", "committee_source")
MIN_OPINIONS = 3  # below this a case gets no label
MIN_RULED = 10  # below this no agreement rate is shown for an expert


# ---- the measures -----------------------------------------------------------


def split_score(agree: int, disagree: int) -> float | None:
    """2 × minority / n.

    >>> split_score(4, 3)
    0.857
    >>> split_score(3, 4) == split_score(4, 3)
    True
    >>> split_score(7, 0)
    0.0
    >>> split_score(0, 0) is None
    True
    """
    n = agree + disagree
    if n == 0:
        return None
    return round(2 * min(agree, disagree) / n, 3)


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float] | None:
    """95% Wilson interval for k successes out of n.

    >>> wilson(1, 2)
    (0.095, 0.905)
    >>> wilson(4, 7)
    (0.25, 0.842)
    >>> wilson(0, 0) is None
    True
    """
    if n == 0:
        return None
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return round(max(0.0, centre - half), 3), round(min(1.0, centre + half), 3)


def label(agree: int, disagree: int) -> str:
    """consensus / contested / small_sample.

    >>> label(1, 1)
    'small_sample'
    >>> label(2, 1), label(3, 1), label(4, 0)
    ('contested', 'consensus', 'consensus')
    """
    n = agree + disagree
    if n < MIN_OPINIONS:
        return "small_sample"
    return "contested" if 3 * min(agree, disagree) >= n else "consensus"


# ---- queries ----------------------------------------------------------------


@dataclass
class CaseAgreement:
    incident_id: int
    agree: int
    disagree: int
    unclear: int

    @property
    def n(self) -> int:
        return self.agree + self.disagree

    @property
    def split(self) -> float | None:
        return split_score(self.agree, self.disagree)

    @property
    def range(self) -> tuple[float, float] | None:
        return wilson(self.agree, self.n)

    @property
    def label(self) -> str:
        return label(self.agree, self.disagree)


def case_agreement(conn: sqlite3.Connection, min_opinions: int = 2) -> list[CaseAgreement]:
    """Cases with at least `min_opinions` independent opinions, most split first."""
    marks = ",".join("?" * len(NOT_INDEPENDENT))
    rows = conn.execute(
        f"""SELECT o.incident_id, SUM(o.stance = 'agree'), SUM(o.stance = 'disagree'),
                   SUM(o.stance = 'unclear')
            FROM expert_opinions o JOIN experts e USING (expert_id)
            WHERE COALESCE(e.background, '') NOT IN ({marks})
            GROUP BY o.incident_id HAVING COUNT(*) >= ?""",
        (*NOT_INDEPENDENT, min_opinions),
    ).fetchall()
    cases = [CaseAgreement(*r) for r in rows]
    return sorted(cases, key=lambda c: (-(c.split or 0), -c.n, c.incident_id))


def reasons_by_side(conn: sqlite3.Connection, incident_id: int) -> dict[str, list[str]]:
    """{'agree': [...kinds...], 'disagree': [...]} — what each side argued from."""
    out: dict[str, list[str]] = {"agree": [], "disagree": [], "unclear": []}
    for stance, kind in conn.execute(
        """SELECT o.stance, rc.kind FROM expert_opinions o
           JOIN opinion_reasons r USING (opinion_id)
           JOIN reason_codes rc ON rc.code = r.reason
           WHERE o.incident_id = ? ORDER BY 1, 2""",
        (incident_id,),
    ):
        if kind not in out[stance]:
            out[stance].append(kind)
    return out


def expert_vs_committee(conn: sqlite3.Connection) -> list[tuple[str, int, int]]:
    """(expert, ruled cases with a view, same view as the committee).

    An opinion about the card only (its grounds are all sanction_level, maybe
    with var_protocol) is compared with the committee's card_verdict; any other
    opinion with its call_verdict. So "right penalty, should have been red" is
    not counted as disagreeing with a committee that also backs the penalty.
    An expert who says the decision was right matches a 'correct' verdict, and
    the other way round. Unclear views are left out.
    """
    marks = ",".join("?" * len(NOT_INDEPENDENT))
    return conn.execute(
        f"""WITH target AS (
                SELECT o.opinion_id,
                       CASE WHEN SUM(r.reason = 'sanction_level') > 0
                             AND SUM(r.reason NOT IN ('sanction_level', 'var_protocol')) = 0
                            THEN 'card' ELSE 'call' END AS about
                FROM expert_opinions o
                LEFT JOIN opinion_reasons r USING (opinion_id)
                GROUP BY o.opinion_id)
            SELECT e.name_ar, COUNT(*),
                   SUM((o.stance = 'agree') = (CASE t.about WHEN 'card' THEN s.card_verdict
                                                            ELSE s.call_verdict END = 'correct'))
            FROM expert_opinions o JOIN experts e USING (expert_id)
            JOIN target t USING (opinion_id)
            JOIN v_incident_summary s USING (incident_id)
            WHERE s.call_verdict IS NOT NULL AND o.stance <> 'unclear'
              AND COALESCE(e.background, '') NOT IN ({marks})
            GROUP BY e.name_ar ORDER BY e.name_ar""",
        NOT_INDEPENDENT,
    ).fetchall()


# ---- loader -----------------------------------------------------------------


def load_opinion_reasons(conn: sqlite3.Connection, raw_dir: Path) -> dict[str, int]:
    """Load opinion_reasons.csv in one transaction (all or nothing)."""
    problems: list[str] = []
    rows = read_csv(raw_dir / f"{FILE}.csv", COLUMNS, problems)
    sql = "SELECT name_ar, expert_id FROM experts"
    experts = {normalize_name(n): i for n, i in conn.execute(sql)}
    codes = {c for (c,) in conn.execute("SELECT code FROM reason_codes")}
    conn.execute("BEGIN")
    try:
        for row in rows:
            where = row["_line"]
            expert_id = experts.get(normalize_name(row["expert"] or ""))
            if expert_id is None:
                problems.append(f"{where}: unknown expert '{row['expert']}'")
                continue
            if row["reason"] not in codes:
                problems.append(f"{where}: unknown reason '{row['reason']}' (see reason_codes)")
                continue
            found = conn.execute(
                "SELECT opinion_id FROM expert_opinions WHERE incident_id = ? AND expert_id = ?",
                (row["case_id"], expert_id),
            ).fetchall()
            if len(found) != 1:
                what = "no opinion" if not found else f"{len(found)} opinions"
                problems.append(f"{where}: {row['expert']} has {what} on case {row['case_id']}")
                continue
            try:
                conn.execute(
                    "INSERT INTO opinion_reasons (opinion_id, reason) VALUES (?, ?)",
                    (found[0][0], row["reason"]),
                )
            except sqlite3.IntegrityError as e:
                problems.append(f"{where}: rejected by database — {e}")
        if problems:
            raise DataError(problems)
    except Exception:
        conn.rollback()
        raise
    conn.commit()
    return {"opinion_reasons": conn.execute("SELECT COUNT(*) FROM opinion_reasons").fetchone()[0]}
