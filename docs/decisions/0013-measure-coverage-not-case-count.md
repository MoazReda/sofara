# 0013 — Measure match coverage, not case count

**Context.** The early target was "~100 cases". After five rounds the league
has played 50 matches, and a match usually produces zero to two incidents
worth discussing, so 100 cases from five rounds would mean padding the library
with weak cases. Worse, a match with no case was ambiguous: either nothing
was contested, or nobody had looked. All 33 cases came from 13 matches, and
those 13 are exactly the matches Nasser Abbas chose to review — the selection
bias of [0008](0008-track-discovery-source.md), at the match level.

**Decision.** Add `match_reviews` (one row = one source that went through the
refereeing of one whole match: an expert review, a press round-up, or our own
viewing). The progress measure becomes **matches reviewed out of matches
played**, computed per round in `v_match_coverage`; the case count follows
from it and is never a target. A reviewed match with no case is recorded
information ("nothing contested in our sources"), not a gap.

**Consequences.** `sofara-report` shows coverage per round and lists the
matches nobody has reviewed yet, which is the collection to-do list. High-
profile matches (e.g. Al Ahly × Zamalek) will still produce more cases, and
that is fine: the coverage table makes the imbalance visible instead of
hiding it. "Reviewed" never means "every incident was discussed": the source
chose what to talk about.
