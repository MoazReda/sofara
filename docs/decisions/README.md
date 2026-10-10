# Decision records

Short notes on the decisions that shape this project: what we decided, why,
and what it costs. Each one was made on real data, usually after something
broke. Format: Context → Decision → Consequences.

| # | Decision |
|---|---|
| [0001](0001-csv-source-of-truth.md) | CSV files are the source of truth; the database is rebuilt from them |
| [0002](0002-never-guess-names.md) | Names are normalized but never guessed |
| [0003](0003-canonical-names-from-efa.md) | Canonical names are the form on EFA crew cards |
| [0004](0004-facts-vs-opinions.md) | Facts and opinions are stored apart; verdicts are computed |
| [0005](0005-key-match-incidents.md) | The case library covers Key Match Incidents only |
| [0006](0006-decisions-as-stages.md) | A case's decisions are rows per stage; cards are rows per person |
| [0007](0007-committee-reports-are-opinions.md) | Committee positions reported by the press are opinions, not rulings |
| [0008](0008-track-discovery-source.md) | Every case records how it was found, to expose selection bias |
| [0009](0009-ethics-public-data.md) | Public data is never presented as referee accuracy |
| [0010](0010-premier-league-only.md) | Scope is the Egyptian Premier League only |
| [0011](0011-commendations-no-ranking.md) | Expert commendations are stored, never ranked |
| [0012](0012-recall-first-search.md) | Search is recall-first and explains every match |
