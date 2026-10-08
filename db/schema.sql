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
                   CHECK (official_type IN ('referee', 'observer'))
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
                     'observer'       -- مراقب المباريات
                 )),
    PRIMARY KEY (match_id, role)
);

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
    reason        TEXT    CHECK (reason IN (
                      -- cautions (الإنذارات)
                      'unsporting_behaviour',     -- السلوك غير الرياضي
                      'dissent',                  -- المعارضة بالقول أو الفعل
                      'persistent_offences',
                      'delaying_restart',
                      'failing_to_respect_distance',
                      'entering_leaving_without_permission',
                      -- sendings-off (حالات الطرد)
                      'serious_foul_play',
                      'violent_conduct',          -- السلوك العنيف
                      'spitting_biting',
                      'denying_goal_handball',
                      'denying_goal_foul',        -- DOGSO
                      'offensive_language',
                      'second_caution'
                  )),
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
-- incidents: one row = one curated refereeing situation (case library).
-- official_verdict stays NULL unless the committee published a ruling;
-- a NULL verdict means "controversial" — computed in v_incidents,
-- never stored as its own column.
-- ---------------------------------------------------------------------
CREATE TABLE incidents (
    incident_id         INTEGER PRIMARY KEY,
    match_id            INTEGER NOT NULL REFERENCES matches(match_id),
    minute              INTEGER NOT NULL CHECK (minute BETWEEN 1 AND 120),
    added_minute        INTEGER NOT NULL DEFAULT 0 CHECK (added_minute >= 0),
    incident_type       TEXT    NOT NULL CHECK (incident_type IN (
                            'penalty', 'handball', 'offside', 'red_card',
                            'second_yellow', 'goal_validity', 'mistaken_identity',
                            'other'
                        )),
    description_ar      TEXT    NOT NULL,              -- in our own words
    on_field_decision   TEXT    NOT NULL,              -- what the referee gave
    var_review          TEXT    NOT NULL DEFAULT 'none'
                        CHECK (var_review IN ('none', 'check_only', 'ofr')),
    final_decision      TEXT    NOT NULL,              -- after VAR
    video_url           TEXT,                          -- link only, never upload
    video_start_sec     INTEGER CHECK (video_start_sec >= 0),
    official_verdict    TEXT    CHECK (official_verdict IN ('correct', 'incorrect')),
    verdict_source_url  TEXT,
    CHECK (added_minute = 0 OR minute IN (45, 90, 105, 120)),
    -- a verdict without a public source is not allowed
    CHECK (official_verdict IS NULL OR verdict_source_url IS NOT NULL),
    -- a timestamp without a video makes no sense
    CHECK (video_start_sec IS NULL OR video_url IS NOT NULL)
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
                    CHECK (stance IN ('agree', 'disagree', 'unclear')),  -- vs the final decision
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
CREATE INDEX idx_opinions_incident        ON expert_opinions(incident_id);
CREATE INDEX idx_official_aliases_off     ON official_aliases(official_id);

-- ---------------------------------------------------------------------
-- Views
-- ---------------------------------------------------------------------

-- incidents with the derived status + the referee on the pitch
CREATE VIEW v_incidents AS
SELECT
    i.*,
    CASE WHEN i.official_verdict IS NULL THEN 'controversial'
         ELSE 'ruled' END                         AS status,
    mo.official_id                                AS referee_id
FROM incidents i
LEFT JOIN match_officials mo
       ON mo.match_id = i.match_id AND mo.role = 'referee';

-- resolve any spelling (canonical name or alias) to one official_id
CREATE VIEW v_official_lookup AS
SELECT name_ar AS name, official_id FROM officials
UNION
SELECT alias   AS name, official_id FROM official_aliases;
