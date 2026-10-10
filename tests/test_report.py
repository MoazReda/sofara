"""The report runs on the real data and its numbers match the database."""

from pathlib import Path

from sofara.build import apply_schema, connect
from sofara.cases import load_cases
from sofara.registry import load_all
from sofara.report import main, report

RAW = Path(__file__).resolve().parent.parent / "data" / "raw"


def _real_db():
    conn = connect(":memory:")
    apply_schema(conn)
    load_all(conn, RAW)
    load_cases(conn, RAW)
    return conn


def test_report_has_every_section():
    text = report(_real_db())
    for heading in (
        "## Matches and crews",
        "## Case library",
        "## Selection bias",
        "## Expert opinions",
        "## Open issues",
    ):
        assert heading in text


def test_report_numbers_match_database():
    conn = _real_db()
    n_cases = conn.execute("SELECT COUNT(*) FROM incidents").fetchone()[0]
    assert f"Cases: **{n_cases}**" in report(conn)


def test_report_flags_missing_match_events():
    # match_events is empty for now; the report must say so, not hide it
    assert "⚠️ match events (goals and cards) collected: 0" in report(_real_db())


def test_cli_runs(capsys):
    assert main(["--raw", str(RAW)]) == 0
    assert "# Sofara data report" in capsys.readouterr().out
