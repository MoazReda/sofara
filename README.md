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

## What's here (season 2026/27, rounds 1–5)

| | |
|---|---|
| Matches | **50** — every match of rounds 1–5, all 20 teams |
| Officials | **103** people, **300** crew assignments (referee, ARs, 4th, VAR, AVAR) |
| Key Match Incidents | **24** cases from 10 matches, with on-field / post-VAR decisions |
| Expert opinions | **28** from 10 experts (ex-referees, analysts, pundits) |
| Tests | 78, run in CI on Windows + Ubuntu, Python 3.10 + 3.13 |

The crew data was independently confirmed: every official named in Nasser
Abbas's round reviews matches our records (match and role).

## Roadmap

- [x] Database schema, rules enforced in SQL
- [x] Officials registry and crews, rounds 1–5
- [~] **B. Case library** — schema + loader done; 24 / ~100 cases; Arabic search next
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
pytest
```

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
  build.py           `sofara-build`
data/raw/            hand-collected CSVs (source of truth)
docs/                decisions, data dictionary, sources
tests/               pytest suite
```

## Documentation

- [Decision records](docs/decisions/README.md) — the 10 decisions that shape the project, and why
- [Data dictionary](docs/data_dictionary.md) — every table, what one row means
- [Sources](docs/SOURCES.md) — where every piece of data comes from

## Known gaps and limitations

- **Selection bias.** Cases come from the press and from one expert's reviews,
  not from watching every match. 11 of 24 cases involve Al Ahly; 10 of 50
  matches have a case. Every case records how it was found (`found_via`).
- **No match events yet.** Goals and cards per match (`match_events`) are not
  collected; a legal source is still open. The appointment assistant needs it.
- **No official rulings yet.** The committee rarely publishes rulings, so every
  case is currently "controversial" (no verdict).
- **One unresolved name.** "محمد الشناوي" (VAR in R2 بيراميدز × أبو قير and
  R5 بترول أسيوط × مودرن سبورت) is stored as its own official but is almost
  certainly "محمد أحمد الشناوي" or "محمد علي الشناوي". Fix: add an alias and
  delete the row from `officials.csv`.
- **Commissioner / assessor** are not on Premier League crew cards, so those roles are empty.

## Ethics

No scraping against any site's terms. Videos are timestamped links only.
Expert views are summarised in our own words, with a source. No number from
public data is presented as a referee's accuracy, and real referees never
appear in a public best-to-worst ranking. Details: [decision 0009](docs/decisions/0009-ethics-public-data.md).

## License

Code: MIT. Data: facts with their sources and our own summaries; images and
articles from the EFA and the press are not stored here.
