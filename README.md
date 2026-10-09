# Sofara (صفارة) — Egyptian Refereeing Analytics

Data and ML tools for developing refereeing in the Egyptian Premier League,
built on **real, public data only**.

## Status
- [x] Database schema + tests
- [~] Officials registry (rounds 1-5: 50 matches, 103 officials)
- [~] Case library (part B): 11 press-found cases from 5 matches (rounds 1-5)
- [ ] Appointment assistant (part A)
- [ ] Expert-opinion analysis (part C)
- [ ] "What we could do with your data" (part D, illustrative)

## Quick start (Colab / Kaggle / local)
```bash
pip install pytest
python scripts/build_db.py          # creates data/sofara.db
python -m pytest -q                 # runs schema tests
```

## Data workflow
`data/raw/*.csv` is the **source of truth**; `data/sofara.db` is rebuilt from it
(and is git-ignored). To fix data: edit the CSV, rebuild. Never edit the db.

| file | one row = |
|---|---|
| `teams.csv`, `team_aliases.csv` | a team / another spelling of a team |
| `officials.csv`, `official_aliases.csv` | an official / another spelling of one |
| `crews.csv` | one match and its announced crew (empty cell = role not announced) |

The loader is strict: it reports **every** problem at once and writes nothing
until all are fixed. Names are matched after normalizing spelling noise
(أ/إ/ا، ة/ه، ى/ي، diacritics, spaces) but are **never guessed** — an unknown
name must be added to `officials.csv` (new person) or `official_aliases.csv`
(new spelling of a known person).

Editing in Excel: save as **CSV UTF-8**, otherwise Arabic text breaks.

### Case library files
| file | one row = |
|---|---|
| `incidents.csv` | one case, with its on-field / final / official decisions side by side |
| `incident_cards.csv` | one card to one person at one stage |
| `experts.csv` | one expert (background: ex_referee, analyst, ex_player, journalist) |
| `expert_opinions.csv` | one expert's opinion on one case, summarised in our own words |

Leave `final_*` empty when VAR changed nothing, and `official_*` empty unless the
committee published a ruling. Full rules: top of `scripts/load_cases.py`.

## Known data issues
- **'محمد الشناوي'** (VAR, R2 بيراميدز × أبو قير, R5 بترول أسيوط × مودرن سبورت) is stored as
  its own official, but is almost certainly one of 'محمد أحمد الشناوي' / 'محمد علي الشناوي'.
  Per-official VAR counts for these three are therefore unreliable until resolved.
  Fix: add an alias in `official_aliases.csv` and delete the row from `officials.csv`.
- Commissioner / assessor are not on premier-league crew cards, so those roles are empty.

## Schema
```
teams ──< matches >── match_officials >── officials ──< official_aliases
             │
             ├──< match_events          (goals & cards, whole season)
             └──< incidents ──< incident_decisions ──< incident_sanctions
                      └──< expert_opinions >── experts
```
Full definitions with comments: [`db/schema.sql`](db/schema.sql).
Field layout follows the official EFA referee match report.

Key rules enforced by the database itself:
- One person per role per match (referee, ARs, fourth, VAR, AVAR, commissioner, assessor).
- Name variants resolve to one official via `official_aliases`.
- `90+5` is stored as `minute=90, added_minute=5`; added time only at 45/90/105/120.
- Card reasons come from the `card_reasons` table (Law 12); a yellow card can't
  carry a sending-off reason and vice versa.
- Case library: an incident has one decision per stage (`on_field` → `final` →
  `official`) and any number of cards per stage. An `official` stage needs a
  public source URL. "Correct / incorrect" and "controversial" are **computed**
  in `v_incident_summary`, never stored.

## Data & ethics rules
- No scraping against any site's terms.
- Videos are timestamped links only; nothing is re-uploaded.
- Expert opinions are summarised in our own words, with source.
- Real referees appear in a development framing only — never a public
  best-to-worst ranking. Public outputs are league-level.
- Synthetic data is only used as clearly labelled mockups, never for analysis.
