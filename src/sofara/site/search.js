// The demo page's search: the same rules as sofara/search.py, in the browser.
//
// Python does the heavy part when the page is built: for every vocabulary term
// it records which cases match it (on a decision field or in the text). This
// file only has to read the query the same way search.py does: Arabic
// normalization, team and referee names as filters, the longest vocabulary
// terms first, AND across kinds and OR within a kind, and every leftover word
// must appear in the case text. tests/test_site.py runs it under Node and
// checks it returns the same cases as search.py on the gold queries.

const DIACRITICS = /[ؐ-ًؚ-ٰٟۖ-ۭـ]/g;
const CHAR_MAP = { "أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ة": "ه", "ى": "ي", "ؤ": "و", "ئ": "ي" };
const WORD = "[\\p{L}\\p{N}_]";
const PREFIX = "(?:[وفبلك])?(?:ال)?";
const SUFFIX = "(?:ه|ها|هم|ا|ات|ين)?";

function normalize(text) {
  if (text == null) return "";
  let t = String(text).normalize("NFKC").replace(DIACRITICS, "");
  t = t.replace(/[أإآٱةىؤئ]/g, (c) => CHAR_MAP[c]);
  t = t.toLowerCase().replace(/\s+/g, " ").trim();
  return t.replace(/(?<!\S)(عبد|ابو) (?=\S)/g, "$1");
}

function escapeRe(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

// a normalized phrase as whole word(s), allowing Arabic clitics
function pattern(phrase, flags = "u") {
  const body = normalize(phrase).split(" ").map(escapeRe).join("\\s+");
  return new RegExp(`(?<!${WORD})${PREFIX}${body}${SUFFIX}(?!${WORD})`, flags);
}

function parseQuery(text, index) {
  const q = { teams: new Set(), officials: new Set(), terms: [], words: [] };
  let rest = normalize(text);
  const take = (phrase) => {
    if (pattern(phrase).test(rest)) {
      rest = rest.replace(pattern(phrase, "gu"), " ");
      return true;
    }
    return false;
  };
  for (const [name, id] of index.teams) if (take(name)) q.teams.add(id);
  for (const [name, id] of index.officials) if (take(name)) q.officials.add(id);
  for (const term of index.terms) if (take(term.phrase)) q.terms.push(term);
  q.words = rest.split(" ").filter((w) => w.length > 1 && !index.stopwords.includes(w));
  return q;
}

// -> [{case, why: [..], fieldHits}] in the same order as search.py
function runSearch(text, cases, index, opts = {}) {
  const q = parseQuery(text, index);
  const byField = {};
  for (const t of q.terms) (byField[t.field] = byField[t.field] || []).push(t);
  const out = [];
  for (const c of cases) {
    if (opts.round && c.round !== opts.round) continue;
    if (opts.varChanged && !c.var_changed) continue;
    if (q.teams.size && !(q.teams.has(c.home_id) || q.teams.has(c.away_id))) continue;
    if (q.officials.size && !q.officials.has(c.referee_id)) continue;
    const why = [];
    let fieldHits = 0;
    let ok = true;
    for (const terms of Object.values(byField)) {
      let hit = false;
      for (const t of terms) {
        const how = t.hits[c.id];
        if (how === "field") {
          why.push(`«${t.phrase}» ← ${t.label}`);
          fieldHits += 1;
          hit = true;
        } else if (how === "text") {
          why.push(`«${t.phrase}» ← في النص`);
          hit = true;
        }
      }
      if (!hit) { ok = false; break; }
    }
    if (!ok) continue;
    for (const w of q.words) {
      if (!pattern(w).test(c.text)) { ok = false; break; }
      why.push(`«${w}» ← في النص`);
    }
    if (ok) out.push({ case: c, why, fieldHits });
  }
  const minute = (c) => (c.minute == null ? 999 : c.minute);
  out.sort(
    (a, b) =>
      b.fieldHits - a.fieldHits ||
      a.case.round - b.case.round ||
      minute(a.case) - minute(b.case) ||
      a.case.id - b.case.id,
  );
  return { query: q, results: out };
}

if (typeof module !== "undefined") module.exports = { normalize, pattern, parseQuery, runSearch };
