# 0015 — The committee's own round videos are official rulings

**Context.** From the 2026/27 season the Referees Committee publishes a video
after each round, explaining its verdict on the round's debated incidents
(first seen for round 1; the round 5 video is the EFA Facebook reel
1039780975731497, reported by Al-Watan on 2026-09-23). Until now no case had
an official verdict ([0004](0004-facts-vs-opinions.md)), and committee
positions reached us only through the press, stored as opinions
([0007](0007-committee-reports-are-opinions.md)).

**Decision.** A verdict the committee publishes itself (its round video or an
EFA statement) fills the `official` stage of a case, with the link to that
publication in `official_source_url`. The same position reported second-hand
(an article, an unnamed source) stays an opinion of
`لجنة الحكام (بحسب الصحافة)`, as before. A committee video that covers a
match also counts as a review of that match (`match_reviews`).

**Consequences.** The library has its first computed verdicts (5 cases, all
"correct"). The verdict is the committee's, not ours, and where an expert
disagrees with it (case 27: Abbas on the VAR protocol) both stay visible.
Rounds 1–4 videos exist but we have only press reports of them, so those
positions remain opinions until the EFA links are found.
