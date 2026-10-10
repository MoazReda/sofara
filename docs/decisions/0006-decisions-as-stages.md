# 0006 — A case's decisions are rows per stage; cards are rows per person

**Context.** The first design had one `incident_type` per case. A real case
broke it: a handball in the box is at once a handball, a penalty and a red
card. The decision can also change with VAR, and one incident can card two
players.

**Decision.** Three tables, one question each. `incidents`: what never
changes (match, minute, description, VAR involvement, links).
`incident_decisions`: one row per stage (`on_field` → `final` → `official`)
with separate axes — offence, offending team, outcome. No `final` row means
the final decision equals the on-field one. `incident_sanctions`: one row per
card per person per stage. Card reasons come from a Law 12 lookup table, and
triggers refuse a reason that doesn't fit the card.

**Consequences.** A new stage is a new value, not new columns; rules are
written once. "Did VAR change it?" and "card-only changes" are single
queries. Cost: more joins, hidden behind `v_incident_summary`.
