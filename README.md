# Sofara (صفارة) — Egyptian Refereeing Analytics

[![CI](https://github.com/MoazReda/sofara/actions/workflows/ci.yml/badge.svg)](https://github.com/MoazReda/sofara/actions/workflows/ci.yml)

Data tools for **developing** refereeing in the Egyptian Premier League,
built on **real, public data only** — and honest about what public data can
and cannot say.

## Why

Refereeing analysis is standard in top football bodies, and almost absent in
Egypt. The data that would measure referee accuracy (assessor reports, VAR
logs, training records) is internal to the Referees Committee. This project
builds what is possible from public sources and shows, concretely, what the
committee's own data could add.

## What's here (season 2026/27, rounds 1–6)

| | |
|---|---|
| Matches | **51** — every match of rounds 1–5, all 20 teams, and round 6 as crews are announced |
| Officials | **109** people (6 of them a foreign crew, [kept apart](docs/decisions/0014-foreign-crews.md)), **306** crew assignments |
| Match coverage | **19 of 51** matches reviewed by at least one source ([why we count this](docs/decisions/0013-measure-coverage-not-case-count.md)) |
| Key Match Incidents | **45** cases from those 19 matches, with on-field / post-VAR decisions; **20** with an official committee ruling |
| Expert opinions | **52** from 14 sources (ex-referees, analysts, pundits, the committee as reported) |
| Expert commendations | **14** "best of the round" picks (rounds 1, 2, 4), each verified against the crews |
| Tests | 131, run in CI on Windows + Ubuntu, Python 3.10 + 3.13 |

The crew data was independently confirmed: every official named in Nasser
Abbas's round reviews matches our records (match and role).

## Roadmap

- [x] Database schema, rules enforced in SQL
- [x] Officials registry and crews, rounds 1–5
- [x] Expert commendations ("best of the round"), verified against the crews
- [~] **B. Case library** — 19 / 51 matches reviewed, 45 cases; Arabic search + video-quiz export done
- [ ] **A. Appointment assistant** — needs match-level cards and penalties (see Known gaps)
- [ ] **C. Expert-opinion analysis** — agreement between experts, by background
- [ ] **D. "What your data would add"** — clearly labelled mockups + methodology

## Quick start

Recommended: Python 3.10+ from python.org (or Colab / Kaggle) in a virtual env.

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows  (Linux/macOS: source .venv/bin/activate)
pip install -e ".[dev]"           # the package + pytest + ruff
sofara-build                      # rebuild data/sofara.db from data/raw/*.csv
sofara-report                     # coverage, bias and open issues, as Markdown
pytest
```

## Searching the case library

Ask in everyday Arabic; the vocabulary maps it to the data
([`data/vocab/terms.csv`](data/vocab/terms.csv)), and every result says why it matched.

```bash
sofara-search "بلنتي"                      # penalties given first, then refused claims
sofara-search "هاند" --round 2
sofara-search "الأهلي بلنتي"                # team names and referee names act as filters
sofara-search "راح الشاشة" --quiz quiz.md  # video quiz: question first, answer folded away
```

The search is recall-first: it is built for an instructor who must not miss a
case ([decision 0012](docs/decisions/0012-recall-first-search.md)).

The package itself uses only the Python standard library. On MSYS2 Python,
`ruff` can't install (no prebuilt wheel); use `pip install -e .` instead —
CI still runs the linter.

## How it works

```
data/raw/*.csv  ──sofara-build──▶  data/sofara.db  ──▶  analysis / demo
(source of truth, in git)          (derived, git-ignored)
```

- **CSV is the source of truth.** Fix data by editing a CSV and rebuilding; never edit the database.
- **Strict loaders.** Every problem in every file is reported at once, and nothing is written until all are fixed.
- **Names are never guessed.** Spelling noise is normalized (أ/إ/ا، ة/ه، ى/ي، diacritics, عبد/أبو spacing); anything else is a recorded alias with evidence.
- **Facts and opinions are separate.** "Controversial", "VAR changed it" and "correct/incorrect" are computed, never stored.

```
teams ──< matches >── match_officials >── officials ──< official_aliases
             │
             ├──< match_events                 (goals & cards — not collected yet)
             └──< incidents ──< incident_decisions ──< incident_sanctions
                      └──< expert_opinions >── experts
```

## Repository layout

```
src/sofara/          the package
  sql/schema.sql     tables, triggers, views — the rules live here
  normalize.py       Arabic name normalization
  registry.py        loads teams, officials, crews
  cases.py           loads the case library
  reviews.py         loads match reviews (coverage)
  build.py           `sofara-build`
  report.py          `sofara-report`
  search.py          `sofara-search` + video-quiz export
data/raw/            hand-collected CSVs (source of truth)
data/vocab/          search vocabulary: everyday term → field → value
docs/                decisions, data dictionary, sources
tests/               pytest suite
tools/pull_bundle.bat  apply a commit bundle on Windows: pull → test → build → ask → push
```

## Documentation

- [Decision records](docs/decisions/README.md) — the 15 decisions that shape the project, and why
- [Data dictionary](docs/data_dictionary.md) — every table, what one row means
- [Sources](docs/SOURCES.md) — where every piece of data comes from

## Known gaps and limitations

- **Selection bias.** Cases come from the press and from one expert's reviews,
  not from watching every match. 19 of 45 cases involve Al Ahly and 19 Zamalek.
  Only 19 of 51 matches have been reviewed so far; `sofara-report` lists the rest. Every case records how it was found (`found_via`).
- **No match events yet.** Goals and cards per match (`match_events`) are not
  collected; a legal source is still open. The appointment assistant needs it.
- **Verdicts cover debated cases only.** 20 cases have a ruling from the
  committee's own round videos ([decision 0015](docs/decisions/0015-committee-round-videos-are-rulings.md));
  they were picked because they were debated, so they are never an error rate.
- Run `sofara-report` for the current numbers behind every item below.
- **One unresolved name.** "محمد الشناوي" (VAR in R5 بترول أسيوط × مودرن سبورت)
  is stored as its own official but is almost certainly "محمد أحمد الشناوي" or
  "محمد علي الشناوي". (R2 بيراميدز × أبو قير was resolved to محمد علي الشناوي
  from Nasser Abbas's review video.) Fix: add an alias and delete the row from
  `officials.csv`.
- **Commissioner / assessor** are not on Premier League crew cards, so those roles are empty.

## Ethics

No scraping against any site's terms. Videos are timestamped links only.
Expert views are summarised in our own words, with a source. No number from
public data is presented as a referee's accuracy, and real referees never
appear in a public best-to-worst ranking. Details: [decision 0009](docs/decisions/0009-ethics-public-data.md).

## License

Code: MIT. Data: facts with their sources and our own summaries; images and
articles from the EFA and the press are not stored here.
