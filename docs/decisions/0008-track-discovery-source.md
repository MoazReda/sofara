# 0008 — Every case records how it was found

**Context.** The first 11 cases came from the press, and 10 of them involved
Al Ahly. That is a fact about Egyptian sports media, not about refereeing.

**Decision.** `incidents.found_via` is `press`, `expert_review` (an expert
going through matches, e.g. Nasser Abbas) or `match_review` (we watched the
match). Every case also keeps `source_url`.

**Consequences.** Bias is measurable: adding expert-review cases cut Al Ahly's
share from 10/11 to 11/24. Any statistic can be split by discovery source, and
the gap to a full `match_review` sample is visible.
