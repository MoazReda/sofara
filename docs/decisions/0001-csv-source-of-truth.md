# 0001 — CSV files are the source of truth

**Context.** Data is collected by hand from posts, articles and videos, and
corrected often. Editing a database directly leaves no trail and can't be
reviewed in a pull request.

**Decision.** Everything lives in `data/raw/*.csv`, versioned in git. The
SQLite database is a build artifact (`sofara-build`) and is git-ignored. A
build is all-or-nothing: the loaders report every problem at once and write
nothing until all are fixed. CSVs are "wide" where a human types them (one
row per match or case); the loaders turn them into normalized tables.

**Consequences.** Every correction is a reviewable diff with a commit message.
No migrations are needed: change the schema, rebuild. CI rebuilds the real
data on every push, so a bad CSV edit fails loudly. Cost: SQLite only, and a
full rebuild each time (fine at this size).
