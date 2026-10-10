# Data dictionary

Every table, what **one row** means, and its key. Column-level rules (CHECKs,
triggers) live with comments in [`src/sofara/sql/schema.sql`](../src/sofara/sql/schema.sql).

## Registry (facts about matches and people)

| Table | One row = | Key | Loaded from |
|---|---|---|---|
| `teams` | a club | `team_id` | `teams.csv` |
| `team_aliases` | another spelling of a club's name | `alias` | `team_aliases.csv` |
| `officials` | a real person: referee, assistant, VAR, commissioner or assessor | `official_id` | `officials.csv` |
| `official_aliases` | another spelling of an official's name, with evidence | `alias` | `official_aliases.csv` |
| `matches` | one match | `match_id`; unique on season + teams + date | `crews.csv` |
| `match_officials` | one person in one role in one match | (`match_id`, `role`); one role per person per match | `crews.csv` (wide → long) |
| `match_events` | one goal or card in a match | `event_id` | *not collected yet* (see Known gaps) |
| `card_reasons` | one Law 12 reason for a card, Arabic name, caution / sending-off | `code` | seeded in `schema.sql` |

Roles: `referee`, `assistant_1`, `assistant_2`, `fourth`, `var`, `avar`,
`commissioner` (مراقب المباراة), `assessor` (مقيّم الحكام).

## Case library (judgements)

| Table | One row = | Key | Loaded from |
|---|---|---|---|
| `incidents` | one Key Match Incident — what never changes | `incident_id` (= the hand-picked `case_id`) | `incidents.csv` |
| `incident_decisions` | the decision on one incident at one stage | (`incident_id`, `stage`) | `incidents.csv` (wide → long) |
| `incident_sanctions` | one card to one person at one stage | `sanction_id`; unique per incident + stage + person | `incident_cards.csv` |
| `experts` | one commentator, with background | `expert_id` | `experts.csv` |
| `expert_opinions` | one expert's view on one incident from one source | `opinion_id`; unique per incident + expert + source | `expert_opinions.csv` |
| `expert_commendations` | one expert naming one official as a best performer in one category (referee / assistant / var) in one round | `commendation_id`; match resolved from the crews | `commendations.csv` |

- **Stages:** `on_field` (the referee) → `final` (after VAR; absent = unchanged) → `official` (published committee ruling, link required).
- **Decision axes:** `offence` (none, foul, handball, offside, simulation, violent_conduct, other) · `offending_team_id` · `outcome` (play_on, penalty, free_kick, goal_awarded, goal_disallowed, other).
- **`var_review`:** unknown, none, check_only, ofr. Unknown is the default — never assume "none".
- **`found_via`:** press, expert_review, match_review ([why](decisions/0008-track-discovery-source.md)).
- **Expert background:** ex_referee, analyst, ex_player, journalist, committee (as reported by the press), committee_source (anonymous).
- **Stance:** agree / disagree / unclear with the effective final decision.

## Views

| View | Gives |
|---|---|
| `v_incident_summary` | one row per incident: referee, on-field vs final decision, `var_changed`, `status` (controversial / ruled), `verdict` (correct / incorrect / NULL) |
| `v_decision_signature` | one comparable text per decision (offence, outcome, sorted cards) — used to detect changes |
| `v_incident_problems` | incidents missing an on-field decision (must be empty; the loader checks) |
| `v_official_lookup` | any spelling (name or alias) → `official_id` |
