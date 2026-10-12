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

**Consequences.** All five round videos are linked (EFA Facebook reels:
R1 1561638358556934, R2 1287410006693633, R3 1698670264551381,
R4 2024526304868493, R5 1039780975731497), giving 19 ruled cases. What each
video says is taken from press reports of it (Al-Watan, النهار المصري, إرم
نيوز, تليجراف مصر); watching the videos to confirm them is still to do. The
second-hand committee opinions those rulings replace were removed, so the
committee is not counted twice. The verdict is split into `call_verdict` and
`card_verdict`, so a right call with a missed card (case 1) is not read as a
wrong call. The verdict is the committee's, not ours; where an expert
disagrees with it, both stay visible. Verdicts cover debated cases only, so
they are never an error rate for a referee or a round.
