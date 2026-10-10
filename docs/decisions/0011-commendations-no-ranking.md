# 0011 — Expert commendations are stored, never ranked

**Context.** Nasser Abbas (former international referee, CAF referee
assessor) publishes a "best of the round" post naming referees, assistants
and VAR officials, with reasons. It is independent, regular and specific —
valuable for the appointment assistant (who handles pressure well) and for
comparing an expert's view with the committee's choices.

**Decision.** Store each pick in `expert_commendations` (one row = one
expert, one official, one category, one round). The match is not typed: the
loader resolves it from round + official + category and requires exactly one
match in the crew data, so every pick doubles as a check on the crews. The
data is never turned into a public leaderboard ("most commended referees");
reports show counts per round and category, without names.

**Consequences.** Positive, attributable expert signal per official, usable
as a feature in analysis. All 14 picks from rounds 1, 2 and 4 resolved to
the matches Abbas named. Consistent with [0009](0009-ethics-public-data.md).
