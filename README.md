# Sofara (صفارة) — Egyptian Refereeing Analytics

Data and ML tools for developing refereeing in the Egyptian Premier League,
built on **real, public data only**.

## Status
- [x] Database schema + tests
- [ ] Officials registry
- [ ] Case library (part B)
- [ ] Appointment assistant (part A)
- [ ] Expert-opinion analysis (part C)
- [ ] "What we could do with your data" (part D, illustrative)

## Quick start (Colab / Kaggle / local)
```bash
pip install pytest
python scripts/build_db.py          # creates data/sofara.db
python -m pytest -q                 # runs schema tests
```

## Schema
```
teams ──< matches >── match_officials >── officials ──< official_aliases
             │
             ├──< match_events          (goals & cards, whole season)
             └──< incidents ──< expert_opinions >── experts
```
Full definitions with comments: [`db/schema.sql`](db/schema.sql).
Field layout follows the official EFA referee match report.

Key rules enforced by the database itself:
- One person per role per match (referee, ARs, fourth, VAR, AVAR, observer).
- Name variants resolve to one official via `official_aliases`.
- `90+5` is stored as `minute=90, added_minute=5`; added time only at 45/90/105/120.
- Card reasons follow Law 12 categories.
- An incident gets an `official_verdict` **only** with a public source URL;
  otherwise it is *controversial* (derived in `v_incidents`, never stored).

## Data & ethics rules
- No scraping against any site's terms.
- Videos are timestamped links only; nothing is re-uploaded.
- Expert opinions are summarised in our own words, with source.
- Real referees appear in a development framing only — never a public
  best-to-worst ranking. Public outputs are league-level.
- Synthetic data is only used as clearly labelled mockups, never for analysis.
