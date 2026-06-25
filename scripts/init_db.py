#!/usr/bin/env python3
"""
Initialize yoachi database — creates schema and seeds categories.
Run: python scripts/init_db.py
"""
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "yoachi.db"
SCHEMA_PATH = Path(__file__).parent.parent / "schema.sql"

CATEGORIES = [
    ("li",   "礼", "待人接物、社会规范、尊重他人、公共意识", 1),
    ("yue",  "乐", "艺术修养、舞台表现力、情感表达、美感",   2),
    ("she",  "射", "体能、运动、竞争精神、毅力、身体协调",   3),
    ("yu",   "御", "驾车、生活技能、独立能力、方向感",       4),
    ("shu",  "书", "读写能力、语言表达、阅读量、文化素养",   5),
    ("shu2", "数", "数学能力、逻辑推理、科学思维、问题解决", 6),
    ("ying", "英", "英语能力、学英语的方面能力提升",         7),
]


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Create schema
    sql = SCHEMA_PATH.read_text()
    cur.executescript(sql)

    # Seed categories (idempotent — INSERT OR IGNORE)
    cur.executemany(
        "INSERT OR IGNORE INTO categories (id, name, description, sort_order) VALUES (?, ?, ?, ?)",
        CATEGORIES,
    )

    conn.commit()

    # Verify
    cur.execute("SELECT COUNT(*) FROM categories")
    count = cur.fetchone()[0]
    print(f"[OK] yoachi.db initialized at {DB_PATH}")
    print(f"[OK] categories seeded: {count}/7")

    cur.execute("SELECT id, name, sort_order FROM categories ORDER BY sort_order")
    for row in cur.fetchall():
        print(f"  - {row[0]} ({row[1]}) sort={row[2]}")

    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(init_db())
