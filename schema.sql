-- Yoachi Database Schema
-- Children's achievement/badge system
-- Inherited from dizical

-- Achievements table
CREATE TABLE IF NOT EXISTS achievements (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'milestone',
    stat_logic TEXT NOT NULL,
    description TEXT NOT NULL,
    display_format TEXT NOT NULL,
    threshold INTEGER,
    unlocked_template TEXT,
    placeholder TEXT,
    locked_template TEXT,
    sort_order INTEGER DEFAULT 0,
    seasonal_type TEXT DEFAULT 'monthly',
    cond_text TEXT,
    unlock_strategy TEXT DEFAULT 'calc',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    achieved_at_override TEXT,
    display_on_achievements INTEGER DEFAULT 1,
    sort_order_override INTEGER
);

-- Achievement stats table
CREATE TABLE IF NOT EXISTS achievement_stats (
    achievement_id TEXT PRIMARY KEY,
    achieved TEXT NOT NULL DEFAULT 'N',
    achieved_at DATETIME,
    raw_stats TEXT NOT NULL DEFAULT '{}',
    computed_value INTEGER
);

-- Achievement badges table
CREATE TABLE IF NOT EXISTS achievement_badges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    achievement_id TEXT NOT NULL,
    url TEXT NOT NULL,
    is_locked INTEGER NOT NULL DEFAULT 0,
    version INTEGER NOT NULL DEFAULT 1,
    is_current INTEGER NOT NULL DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Categories table (new for yoachi)
CREATE TABLE IF NOT EXISTS categories (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    sort_order INTEGER DEFAULT 0
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_achievement_stats_achieved ON achievement_stats(achieved);
CREATE INDEX IF NOT EXISTS idx_achievement_badges_achievement_id ON achievement_badges(achievement_id);
CREATE INDEX IF NOT EXISTS idx_achievement_badges_is_current ON achievement_badges(is_current);
CREATE INDEX IF NOT EXISTS idx_achievements_category ON achievements(category);
CREATE INDEX IF NOT EXISTS idx_achievements_sort_order ON achievements(sort_order);
