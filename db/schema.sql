-- =====================================================================
-- Sofara (صفارة) — Egyptian Refereeing Analytics
-- Database schema (SQLite)
--
-- Design principles:
--   1. Facts (who refereed, the score, card minutes) are kept separate
--      from opinions (was it a penalty? what did an expert say?).
--   2. Don't store what you can compute (e.g. "controversial" status
--      is derived from a missing official verdict — see v_incidents).
--   3. Every row from an outside source records where it came from.
--   4. Field layout follows the official EFA referee match report
--      (تقرير الحكم) so our data speaks the committee's language.
--
-- Run with:  PRAGMA foreign_keys = ON;  (SQLite has FKs off by default)
-- =====================================================================

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------
-- officials: one row = one real person who officiates or observes.
-- name_ar is the canonical name; spelling variants live in
-- official_aliases so the same person is never counted twice.
-- ---------------------------------------------------------------------
CREATE TABLE officials (
    official_id    INTEGER PRIMARY KEY,
    name_ar        TEXT    NOT NULL UNIQUE,
    name_en        TEXT,
    nationality    TEXT    NOT NULL DEFAULT 'Egypt',   -- separates foreign crews
    region         TEXT,                               -- المنطقة, e.g. 'الغربية'
    official_type  TEXT    NOT NULL DEFAULT 'referee'
                   CHECK (official_type IN ('referee', 'commissioner', 'assessor'))
);

-- one row = one way a name has been written somewhere
CREATE TABLE official_aliases (
    alias        TEXT    PRIMARY KEY,
    official_id  INTEGER NOT NULL REFERENCES officials(official_id),
    source       TEXT                                  -- where we saw this spelling
);

-- ---------------------------------------------------------------------
-- teams + aliases (same idea: 'انبي' / 'إنبي' / 'ENPPI' -> one team)
-- ---------------------------------------------------------------------
CREATE TABLE teams (
    team_id  INTEGER PRIMARY KEY,
    name_ar  TEXT    NOT NULL UNIQUE,
    name_en  TEXT
);

CREATE TABLE team_aliases (
    alias    TEXT    PRIMARY KEY,
    team_id  INTEGER NOT NULL REFERENCES teams(team_id),
    source   TEXT
);

-- ---------------------------------------------------------------------
-- matches: one row = one match. No referee column on purpose:
-- the full crew lives in match_officials.
-- ---------------------------------------------------------------------
CREATE TABLE matches (
    match_id           INTEGER PRIMARY KEY,
    competition        TEXT    NOT NULL DEFAULT 'Egyptian Premier League',
    season             TEXT    NOT NULL,               -- '2026/27'
    round              INTEGER CHECK (round > 0),      -- الجولة / الأسبوع
    match_number       INTEGER,                        -- رقم المباراة (official)
    match_date         TEXT    NOT NULL                -- ISO 'YYYY-MM-DD'
                       CHECK (match_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    kickoff_time       TEXT,                           -- 'HH:MM'
    stadium            TEXT,
    city               TEXT,
    home_team_id       INTEGER NOT NULL REFERENCES teams(team_id),
    away_team_id       INTEGER NOT NULL REFERENCES teams(team_id),
    home_goals         INTEGER CHECK (home_goals >= 0),
    away_goals         INTEGER CHECK (away_goals >= 0),
    ht_home_goals      INTEGER CHECK (ht_home_goals >= 0),
    ht_away_goals      INTEGER CHECK (ht_away_goals >= 0),
    source             TEXT,
    report_source_url  TEXT,
    CHECK (home_team_id <> away_team_id),
    CHECK (ht_home_goals IS NULL OR home_goals IS NULL OR ht_home_goals <= home_goals),
    CHECK (ht_away_goals IS NULL OR away_goals IS NULL OR ht_away_goals <= away_goals),
    UNIQUE (season, home_team_id, away_team_id, match_date)
);

-- ---------------------------------------------------------------------
-- match_officials: one row = one person in one role in one match.
-- A match has exactly one person per role.
-- ---------------------------------------------------------------------
CREATE TABLE match_officials (
    match_id     INTEGER NOT NULL REFERENCES matches(match_id),
    official_id  INTEGER NOT NULL REFERENCES officials(official_id),
    role         TEXT    NOT NULL CHECK (role IN (
                     'referee',       -- الحكم
                     'assistant_1',   -- الحكم المساعد الأول
                     'assistant_2',   -- الحكم المساعد الثاني
                     'fourth',        -- الحكم الاحتياطي
                     'var',           -- حكم مساعد فيديو
                     'avar',          -- حكم مساعد فيديو 2
                     'commissioner',  -- مراقب المباراة (match organisation)
                     'assessor'       -- مقيّم الحكام (writes the referee evaluation)
                 )),
    PRIMARY KEY (match_id, role),
    UNIQUE (match_id, official_id)          -- one person can't hold two roles
);

-- ---------------------------------------------------------------------
-- card_reasons: one row = one Law 12 reason for a card.
-- A lookup table instead of a CHECK list copied into two tables;
-- `kind` lets the database refuse e.g. a yellow card with a red-card reason.
-- ---------------------------------------------------------------------
CREATE TABLE card_reasons (
    code     TEXT PRIMARY KEY,
    name_ar  TEXT NOT NULL,
    kind     TEXT NOT NULL CHECK (kind IN ('caution', 'sending_off'))
);

INSERT INTO card_reasons (code, name_ar, kind) VALUES
    ('unsporting_behaviour',                'السلوك غير الرياضي',              'caution'),
    ('dissent',                             'المعارضة بالقول أو الفعل',         'caution'),
    ('persistent_offences',                 'تكرار المخالفات',                  'caution'),
    ('delaying_restart',                    'تأخير استئناف اللعب',              'caution'),
    ('failing_to_respect_distance',         'عدم احترام المسافة',               'caution'),
    ('entering_leaving_without_permission', 'الدخول أو الخروج بدون إذن',         'caution'),
    ('serious_foul_play',                   'اللعب العنيف الجسيم',              'sending_off'),
    ('violent_conduct',                     'السلوك العنيف',                    'sending_off'),
    ('spitting_biting',                     'البصق أو العض',                    'sending_off'),
    ('denying_goal_handball',               'منع هدف أو فرصة محققة بلمسة يد',    'sending_off'),
    ('denying_goal_foul',                   'منع فرصة محققة بمخالفة (DOGSO)',     'sending_off'),
    ('offensive_language',                  'ألفاظ أو إشارات مسيئة',            'sending_off'),
    ('second_caution',                      'إنذار ثانٍ في نفس المباراة',        'sending_off');

-- ---------------------------------------------------------------------
-- match_events: one row = one goal or one card.
-- Bulk facts for the whole season (feeds the appointment assistant).
-- Curated, debated situations go to `incidents`, not here.
-- '90+5' is stored as minute = 90, added_minute = 5 so we can compute on it.
-- Reasons use Law 12 categories, matching the wording on the EFA report.
-- ---------------------------------------------------------------------
CREATE TABLE match_events (
    event_id      INTEGER PRIMARY KEY,
    match_id      INTEGER NOT NULL REFERENCES matches(match_id),
    team_id       INTEGER NOT NULL REFERENCES teams(team_id),
    event_type    TEXT    NOT NULL
                  CHECK (event_type IN ('goal', 'yellow', 'second_yellow', 'red')),
    minute        INTEGER NOT NULL CHECK (minute BETWEEN 1 AND 120),
    added_minute  INTEGER NOT NULL DEFAULT 0 CHECK (added_minute >= 0),
    person_type   TEXT    NOT NULL DEFAULT 'player'
                  CHECK (person_type IN ('player', 'staff')),
    person_name   TEXT,
    shirt_number  INTEGER CHECK (shirt_number BETWEEN 1 AND 99),
    reason        TEXT    REFERENCES card_reasons(code),
    is_penalty    INTEGER NOT NULL DEFAULT 0 CHECK (is_penalty IN (0, 1)),
    is_own_goal   INTEGER NOT NULL DEFAULT 0 CHECK (is_own_goal IN (0, 1)),
    source        TEXT,
    -- added time only exists at the end of a half
    CHECK (added_minute = 0 OR minute IN (45, 90, 105, 120)),
    -- staff don't wear shirt numbers and don't score
    CHECK (person_type = 'player' OR (shirt_number IS NULL AND event_type <> 'goal')),
    -- goals have no disciplinary reason; penalty / own-goal flags only on goals
    CHECK (event_type <> 'goal' OR reason IS NULL),
    CHECK (event_type = 'goal' OR (is_penalty = 0 AND is_own_goal = 0)),
    CHECK (NOT (is_penalty = 1 AND is_own_goal = 1))
);

-- ---------------------------------------------------------------------
-- Case library (part ب) — three tables, one question each:
--   incidents           what happened (never changes)
--   incident_decisions  what was decided, at each stage
--   incident_sanctions  who got which card, at each stage
--
-- Stages: on_field (the referee) -> final (after VAR) -> official
-- (a ruling published by the committee). Adding a stage = a new value,
-- not new columns. "Was the decision correct?" is NOT stored: it is
-- computed by comparing `final` with `official` (see v_incident_summary).
-- No `official` row = controversial.
-- ---------------------------------------------------------------------

-- one row = one curated refereeing situation (a Key Match Incident)
CREATE TABLE incidents (
    incident_id      INTEGER PRIMARY KEY,
    match_id         INTEGER NOT NULL REFERENCES matches(match_id),
    minute           INTEGER NOT NULL CHECK (minute BETWEEN 1 AND 120),
    added_minute     INTEGER NOT NULL DEFAULT 0 CHECK (added_minute >= 0),
    description_ar   TEXT    NOT NULL,                 -- in our own words
    var_review       TEXT    NOT NULL DEFAULT 'none'
                     CHECK (var_review IN ('none', 'check_only', 'ofr')),
    video_url        TEXT,                             -- link only, never upload
    video_start_sec  INTEGER CHECK (video_start_sec >= 0),
    CHECK (added_minute = 0 OR minute IN (45, 90, 105, 120)),
    CHECK (video_start_sec IS NULL OR video_url IS NOT NULL)
);

-- one row = the decision on one incident at one stage.
-- No `final` row means the final decision = the on-field decision.
CREATE TABLE incident_decisions (
    incident_id        INTEGER NOT NULL REFERENCES incidents(incident_id),
    stage              TEXT    NOT NULL CHECK (stage IN ('on_field', 'final', 'official')),
    offence            TEXT    NOT NULL CHECK (offence IN (
                           'none', 'foul', 'handball', 'offside',
                           'simulation', 'violent_conduct', 'other')),
    offending_team_id  INTEGER REFERENCES teams(team_id),
    outcome            TEXT    NOT NULL CHECK (outcome IN (
                           'play_on', 'penalty', 'free_kick',
                           'goal_awarded', 'goal_disallowed', 'other')),
    source_url         TEXT,
    PRIMARY KEY (incident_id, stage),
    -- an official ruling must be public and linkable
    CHECK (stage <> 'official' OR source_url IS NOT NULL),
    -- an offence has an offending team; no offence, no team
    CHECK ((offence = 'none') = (offending_team_id IS NULL)),
    -- a penalty or a disallowed goal needs an offence
    CHECK (outcome NOT IN ('penalty', 'goal_disallowed') OR offence <> 'none'),
    -- penalties come from fouls / handballs / violent conduct only
    CHECK (outcome <> 'penalty' OR offence IN ('foul', 'handball', 'violent_conduct')),
    -- offside: free kick, or the goal is disallowed
    CHECK (offence <> 'offside' OR outcome IN ('free_kick', 'goal_disallowed'))
);

-- one row = one card to one person in one incident at one stage.
-- No card = no row.
CREATE TABLE incident_sanctions (
    sanction_id  INTEGER PRIMARY KEY,
    incident_id  INTEGER NOT NULL,
    stage        TEXT    NOT NULL,
    team_id      INTEGER NOT NULL REFERENCES teams(team_id),
    person_name  TEXT    NOT NULL,
    sanction     TEXT    NOT NULL CHECK (sanction IN ('yellow', 'second_yellow', 'red')),
    reason       TEXT    REFERENCES card_reasons(code),
    FOREIGN KEY (incident_id, stage) REFERENCES incident_decisions(incident_id, stage),
    UNIQUE (incident_id, stage, person_name)
);

-- ---------------------------------------------------------------------
-- experts + their opinions on incidents (part ج).
-- Experts are entities so we can measure agreement between them.
-- ---------------------------------------------------------------------
CREATE TABLE experts (
    expert_id   INTEGER PRIMARY KEY,
    name_ar     TEXT    NOT NULL UNIQUE,
    background  TEXT    CHECK (background IN ('ex_referee', 'journalist', 'analyst'))
);

-- one row = one expert's opinion on one incident from one source
CREATE TABLE expert_opinions (
    opinion_id      INTEGER PRIMARY KEY,
    incident_id     INTEGER NOT NULL REFERENCES incidents(incident_id),
    expert_id       INTEGER NOT NULL REFERENCES experts(expert_id),
    stance          TEXT    NOT NULL
                    CHECK (stance IN ('agree', 'disagree', 'unclear')),  -- vs the effective final decision
    summary_ar      TEXT    NOT NULL,                  -- our summary, never the article text
    source_name     TEXT    NOT NULL,
    source_url      TEXT    NOT NULL,
    published_date  TEXT,
    UNIQUE (incident_id, expert_id, source_url)
);

-- ---------------------------------------------------------------------
-- Indexes on foreign keys we will join on a lot
-- ---------------------------------------------------------------------
CREATE INDEX idx_match_officials_official ON match_officials(official_id);
CREATE INDEX idx_match_events_match       ON match_events(match_id);
CREATE INDEX idx_incidents_match          ON incidents(match_id);
CREATE INDEX idx_sanctions_decision       ON incident_sanctions(incident_id, stage);
CREATE INDEX idx_opinions_incident        ON expert_opinions(incident_id);
CREATE INDEX idx_official_aliases_off     ON official_aliases(official_id);

-- ---------------------------------------------------------------------
-- Cross-table rules (a CHECK can only see its own row; triggers can look up)
-- ---------------------------------------------------------------------

-- card reason must fit the card: yellow -> caution reason, red -> sending-off reason
CREATE TRIGGER trg_sanction_reason_fits BEFORE INSERT ON incident_sanctions
WHEN NEW.reason IS NOT NULL AND NOT EXISTS (
    SELECT 1 FROM card_reasons r WHERE r.code = NEW.reason AND (
        (NEW.sanction IN ('yellow', 'second_yellow') AND r.kind = 'caution') OR
        (NEW.sanction = 'red' AND r.kind = 'sending_off' AND r.code <> 'second_caution')))
BEGIN SELECT RAISE(ABORT, 'card reason does not fit the sanction'); END;

CREATE TRIGGER trg_event_reason_fits BEFORE INSERT ON match_events
WHEN NEW.reason IS NOT NULL AND NOT EXISTS (
    SELECT 1 FROM card_reasons r WHERE r.code = NEW.reason AND (
        (NEW.event_type = 'yellow' AND r.kind = 'caution') OR
        (NEW.event_type = 'second_yellow' AND (r.kind = 'caution' OR r.code = 'second_caution')) OR
        (NEW.event_type = 'red' AND r.kind = 'sending_off' AND r.code <> 'second_caution')))
BEGIN SELECT RAISE(ABORT, 'card reason does not fit the card'); END;

-- teams in a decision / sanction must be one of the two teams in that match
CREATE TRIGGER trg_decision_team_in_match BEFORE INSERT ON incident_decisions
WHEN NEW.offending_team_id IS NOT NULL AND NOT EXISTS (
    SELECT 1 FROM incidents i JOIN matches m ON m.match_id = i.match_id
    WHERE i.incident_id = NEW.incident_id
      AND NEW.offending_team_id IN (m.home_team_id, m.away_team_id))
BEGIN SELECT RAISE(ABORT, 'offending team did not play in this match'); END;

CREATE TRIGGER trg_sanction_team_in_match BEFORE INSERT ON incident_sanctions
WHEN NOT EXISTS (
    SELECT 1 FROM incidents i JOIN matches m ON m.match_id = i.match_id
    WHERE i.incident_id = NEW.incident_id
      AND NEW.team_id IN (m.home_team_id, m.away_team_id))
BEGIN SELECT RAISE(ABORT, 'sanctioned team did not play in this match'); END;

-- ---------------------------------------------------------------------
-- Views
-- ---------------------------------------------------------------------

-- one text "signature" per decision (offence | outcome | sorted cards),
-- so two decisions can be compared with a single `=`
CREATE VIEW v_decision_signature AS
SELECT d.incident_id, d.stage,
       d.offence || '|' || d.outcome || '|' || COALESCE((
           SELECT group_concat(card, ';') FROM (
               SELECT s.person_name || ':' || s.sanction || ':' || COALESCE(s.reason, '') AS card
               FROM incident_sanctions s
               WHERE s.incident_id = d.incident_id AND s.stage = d.stage
               ORDER BY card)), '') AS signature
FROM incident_decisions d;

-- one row per incident: on-field vs final, did VAR change it, verdict
CREATE VIEW v_incident_summary AS
SELECT
    i.*,
    mo.official_id                                         AS referee_id,
    onf.offence                                            AS on_field_offence,
    onf.outcome                                            AS on_field_outcome,
    COALESCE(fin.offence, onf.offence)                     AS final_offence,
    COALESCE(fin.outcome, onf.outcome)                     AS final_outcome,
    CASE WHEN sf.signature IS NULL THEN 0
         WHEN sf.signature <> so.signature THEN 1 ELSE 0 END AS var_changed,
    CASE WHEN off.incident_id IS NULL THEN 'controversial'
         ELSE 'ruled' END                                  AS status,
    CASE WHEN off.incident_id IS NULL THEN NULL
         WHEN COALESCE(sf.signature, so.signature) = sx.signature THEN 'correct'
         ELSE 'incorrect' END                              AS verdict,
    off.source_url                                         AS verdict_source_url
FROM incidents i
LEFT JOIN match_officials mo
       ON mo.match_id = i.match_id AND mo.role = 'referee'
LEFT JOIN incident_decisions onf ON onf.incident_id = i.incident_id AND onf.stage = 'on_field'
LEFT JOIN incident_decisions fin ON fin.incident_id = i.incident_id AND fin.stage = 'final'
LEFT JOIN incident_decisions off ON off.incident_id = i.incident_id AND off.stage = 'official'
LEFT JOIN v_decision_signature so ON so.incident_id = i.incident_id AND so.stage = 'on_field'
LEFT JOIN v_decision_signature sf ON sf.incident_id = i.incident_id AND sf.stage = 'final'
LEFT JOIN v_decision_signature sx ON sx.incident_id = i.incident_id AND sx.stage = 'official';

-- data-quality check: every incident needs an on-field decision
CREATE VIEW v_incident_problems AS
SELECT i.incident_id, 'missing on_field decision' AS problem
FROM incidents i
WHERE NOT EXISTS (SELECT 1 FROM incident_decisions d
                  WHERE d.incident_id = i.incident_id AND d.stage = 'on_field');

-- resolve any spelling (canonical name or alias) to one official_id
CREATE VIEW v_official_lookup AS
SELECT name_ar AS name, official_id FROM officials
UNION
SELECT alias   AS name, official_id FROM official_aliases;
