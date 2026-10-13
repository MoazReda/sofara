"""The demo page: data is complete, and its JavaScript search gives the same
cases as sofara-search on every gold query (run under Node when available)."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from sofara.agreement import load_case_comparisons, load_opinion_reasons
from sofara.build import apply_schema, connect
from sofara.cases import load_cases
from sofara.registry import load_all
from sofara.reviews import load_reviews
from sofara.search import load_vocab, parse, search
from sofara.site import build_data, main, render

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
SEARCH_JS = ROOT / "src" / "sofara" / "site" / "search.js"
sys.path.insert(0, str(Path(__file__).parent))
from test_search import GOLD  # noqa: E402

EXTRA = ["الزمالك", "محمود ناجي بلنتي", "شيكو بانزا", "دفع", "الجولة", "الأهلي الزمالك"]


@pytest.fixture(scope="module")
def conn():
    c = connect(":memory:")
    apply_schema(c)
    load_all(c, RAW)
    load_cases(c, RAW)
    load_reviews(c, RAW)
    load_opinion_reasons(c, RAW)
    load_case_comparisons(c, RAW)
    return c


@pytest.fixture(scope="module")
def data(conn):
    return build_data(conn)


def test_every_case_is_on_the_page(conn, data):
    n = conn.execute("SELECT COUNT(*) FROM incidents").fetchone()[0]
    assert len(data["cases"]) == n
    assert data["stats"]["ruled"] == sum(c["status"] == "ruled" for c in data["cases"])


def test_page_has_no_unfilled_placeholders(data):
    page = render(data)
    assert "/*__DATA__*/" not in page and "/*__SEARCH_JS__*/" not in page
    assert page.startswith("<!doctype html>")
    assert "</script>" not in json.dumps(data, ensure_ascii=False).replace("</", "<\\/")


def test_fragment_has_no_document_wrapper(data):
    assert not render(data, fragment=True).lstrip().startswith("<!doctype")


@pytest.mark.skipif(shutil.which("node") is None, reason="Node is not installed")
def test_javascript_search_matches_python(conn, data, tmp_path):
    vocab = load_vocab()
    queries = list(GOLD) + EXTRA
    expected = {
        q: sorted(c.incident_id for c in search(conn, parse(conn, q, vocab))) for q in queries
    }
    (tmp_path / "data.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "queries.json").write_text(
        json.dumps(queries, ensure_ascii=False), encoding="utf-8"
    )
    script = f"""
      const s = require({json.dumps(str(SEARCH_JS))});
      const fs = require("fs");
      const data = JSON.parse(fs.readFileSync({json.dumps(str(tmp_path / "data.json"))}, "utf8"));
      const qs = JSON.parse(fs.readFileSync({json.dumps(str(tmp_path / "queries.json"))}, "utf8"));
      const out = {{}};
      for (const q of qs) out[q] = s.runSearch(q, data.cases, data.index).results
        .map((r) => r.case.id).sort((a, b) => a - b);
      process.stdout.write(JSON.stringify(out));
    """
    run = subprocess.run(["node", "-e", script], capture_output=True, text=True, encoding="utf-8")
    assert run.returncode == 0, run.stderr
    got = json.loads(run.stdout)
    assert got == expected


def test_cli_writes_page(tmp_path):
    out = tmp_path / "index.html"
    assert main(["--raw", str(RAW), "--out", str(out)]) == 0
    assert "صفارة" in out.read_text(encoding="utf-8")
