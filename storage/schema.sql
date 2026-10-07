-- WP-001 MVP schema (V0.3 plan package)
-- Natural keys + upsert semantics; snapshot lineage on every record.

CREATE TABLE IF NOT EXISTS recognized_schools (
  school_id     INTEGER PRIMARY KEY AUTOINCREMENT,
  name_zh       TEXT NOT NULL,
  name_en       TEXT,
  region        TEXT NOT NULL CHECK (region IN ('hk','sg','uk')),
  recognized    INTEGER NOT NULL DEFAULT 1 CHECK (recognized = 1),  -- positive list only
  source_url    TEXT NOT NULL,
  snapshot_ref  TEXT NOT NULL,
  fetched_at    TEXT NOT NULL,
  content_hash  TEXT NOT NULL,
  UNIQUE (name_zh, region)          -- natural key
);

CREATE TABLE IF NOT EXISTS programs (
  program_id        INTEGER PRIMARY KEY AUTOINCREMENT,
  school_id         INTEGER NOT NULL REFERENCES recognized_schools(school_id),
  university        TEXT NOT NULL,
  name              TEXT NOT NULL,
  field             TEXT NOT NULL CHECK (field IN ('business','cs')),
  degree            TEXT NOT NULL DEFAULT 'master_taught',
  duration_months   INTEGER,
  tuition_amount    REAL,
  tuition_currency  TEXT,
  gpa_requirements  TEXT,           -- JSON: [{"tier":"...","min_gpa":83.0}]
  school_list_req   TEXT,           -- JSON: list-type requirement
  ielts_req         TEXT,           -- JSON: {"overall":6.5,"min_sub":6.0}
  toefl_req         TEXT,           -- JSON, same shape
  deadlines         TEXT,           -- JSON: [{"round":1,"close_date":"2026-01-15"}]
  intake_year       INTEGER NOT NULL,
  source_url        TEXT NOT NULL,
  snapshot_ref      TEXT NOT NULL,
  source_excerpts   TEXT,           -- JSON: field -> original text excerpt
  fetched_at        TEXT NOT NULL,
  content_hash      TEXT NOT NULL,
  stale             INTEGER NOT NULL DEFAULT 0,
  UNIQUE (university, name, intake_year)   -- natural key
);

CREATE TABLE IF NOT EXISTS collect_state (
  source_id   TEXT PRIMARY KEY,
  last_cursor TEXT,
  status      TEXT NOT NULL DEFAULT 'idle',
  updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS quarantine (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  source_id   TEXT NOT NULL,
  seed_key    TEXT NOT NULL,        -- seed identifier for reconciliation (THR-SEED)
  reason_code TEXT NOT NULL,
  raw_ref     TEXT,                 -- snapshot path of the failed item
  detail      TEXT,
  created_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_programs_field ON programs(field);
CREATE INDEX IF NOT EXISTS idx_schools_region ON recognized_schools(region);

-- 中国成绩折算标准（一等公民数据：学校 × 学位等级 → 中国各层次分数线，带官方出处）
CREATE TABLE IF NOT EXISTS gpa_rules (
  rule_id           INTEGER PRIMARY KEY AUTOINCREMENT,
  university        TEXT NOT NULL,
  region            TEXT NOT NULL,
  requirement_class TEXT NOT NULL,          -- masters_general / 2:1 / 2:2 等
  tiers             TEXT NOT NULL,          -- JSON: [{"tier":"211","min_gpa":80}]
  allowed_tiers     TEXT,                   -- JSON: 名单限制（null=不限）
  preference_note   TEXT,                   -- 官方偏好说明（如"85% 优先"）
  explanation       TEXT,                   -- 面向家长的平实解释
  source_url        TEXT NOT NULL,
  excerpt           TEXT NOT NULL,          -- 官方原文逐字引用
  verified_at       TEXT NOT NULL,
  valid_intake      TEXT,                   -- 适用的入学年份
  UNIQUE (university, requirement_class)
);
