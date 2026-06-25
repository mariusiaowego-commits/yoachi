"""Yoachi Admin Database — separate from sync-clobbered yoachi.db.

badge_images and page_sections live here to survive dizical sync overwrites.
"""
import os
import sqlite3
import logging

logger = logging.getLogger('yoachi.admin_db')

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'yoachi_admin.db')


def get_admin_db():
    """Get a connection to the admin database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_admin_db():
    """Create admin-specific tables if they don't exist. Idempotent."""
    conn = get_admin_db()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS badge_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                achievement_id TEXT NOT NULL,
                rarity TEXT NOT NULL DEFAULT 'N',
                url TEXT NOT NULL,
                version INTEGER DEFAULT 1,
                is_current INTEGER DEFAULT 1,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_badge_images_achievement
                ON badge_images(achievement_id, is_current);

            CREATE TABLE IF NOT EXISTS page_sections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                page TEXT NOT NULL DEFAULT 'home',
                section_type TEXT NOT NULL,
                title TEXT,
                config TEXT DEFAULT '{}',
                sort_order INTEGER DEFAULT 0,
                visible INTEGER DEFAULT 1,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_page_sections_page
                ON page_sections(page, sort_order);
        """)
        conn.commit()
        logger.info(f"Admin DB initialized at {DB_PATH}")
    finally:
        conn.close()


def migrate_yoachi_db():
    """Add admin fields to achievements table in yoachi.db. Idempotent.

    Run inside _post_sync_hook so fields survive dizical sync.
    """
    from config import Config
    conn = sqlite3.connect(Config.DATABASE_PATH)
    try:
        # Add columns one by one, ignore if already exist
        migrations = [
            "ALTER TABLE achievements ADD COLUMN rarity TEXT DEFAULT 'N'",
            "ALTER TABLE achievements ADD COLUMN updated_at TEXT",
            "ALTER TABLE achievements ADD COLUMN draft_status TEXT DEFAULT 'published'",
        ]
        for sql in migrations:
            try:
                conn.execute(sql)
            except sqlite3.OperationalError as e:
                if "duplicate column" in str(e).lower():
                    pass
                else:
                    raise
        conn.commit()
        logger.info("yoachi.db admin fields migration complete")
    finally:
        conn.close()
