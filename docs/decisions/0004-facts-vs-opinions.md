# 0004 — Facts and opinions are stored apart; verdicts are computed

**Context.** "Who refereed the match" has one answer. "Was it a penalty?" may
have none: experts split, and the committee rarely publishes rulings.

**Decision.** Facts (matches, crews, goals, cards) and judgements (incidents,
expert opinions) live in separate tables. Nothing derived is stored: a case
is "controversial" when it has no official-stage decision, and "correct" or
"incorrect" is computed in `v_incident_summary` by comparing the final
decision with the official one.

**Consequences.** Two columns can never contradict each other. Adding an
official ruling later changes the verdict automatically.
