"""Yoachi - Children's Achievement Badge System"""
import atexit
import os
import sqlite3
import json
from flask import Flask, render_template, jsonify, g
from config import Config

# Category display helpers (passed to templates)
CATEGORY_NAMES = {
    'li':   '礼',
    'yue':  '乐',
    'she':  '射',
    'yu':   '御',
    'shu':  '书',
    'shu2': '数',
    'ying': '英',
}

CATEGORY_EMOJI = {
    'li':   '🎀',
    'yue':  '🎵',
    'she':  '🏃',
    'yu':   '🚗',
    'shu':  '📚',
    'shu2': '🔢',
    'ying': '🌍',
}

app = Flask(__name__)
app.config.from_object(Config)


def _ensure_yoachi_schema():
    """Ensure yoachi-specific tables exist (categories) after sync restores the DB."""
    conn = sqlite3.connect(app.config['DATABASE_PATH'])
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                sort_order INTEGER DEFAULT 0
            )
        """)
        # Seed default categories only if empty
        count = conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
        if count == 0:
            defaults = [
                ('li',   '礼',   '待人接物、社会规范、尊重他人、公共意识', 1),
                ('yue',  '乐',   '艺术修养、舞台表现力、情感表达、美感',   2),
                ('she',  '射',   '体能、运动、竞争精神、毅力、身体协调',   3),
                ('yu',   '御',   '驾车/生活技能/独立能力/方向感',           4),
                ('shu',  '书',   '读写能力、语言表达、阅读量、文化素养',   5),
                ('shu2', '数',   '数学能力、逻辑推理、科学思维、问题解决', 6),
                ('ying', '英',   '英语能力',                               7),
            ]
            conn.executemany(
                "INSERT OR IGNORE INTO categories (id, name, description, sort_order) VALUES (?, ?, ?, ?)",
                defaults,
            )
        # Re-map dizical synced badges (milestone/seasonal) to 乐 category
        conn.execute(
            "UPDATE achievements SET category = 'yue' WHERE category IN ('milestone', 'seasonal')"
        )
        conn.commit()
    finally:
        conn.close()


# Import and start sync AFTER app is created (avoids circular import / at-import blocking)
from sync import SyncManager

_sync_manager = SyncManager(
    dizical_path=app.config['DIZICAL_DATABASE_PATH'],
    yoachi_path=app.config['DATABASE_PATH'],
    interval_seconds=app.config['SYNC_INTERVAL_SECONDS'],
)
# Hook: after each sync, re-ensure yoachi-specific tables
_sync_manager._post_sync_hook = _ensure_yoachi_schema
atexit.register(_sync_manager.stop)
# Start background sync scheduler
_sync_manager.start_background()


def get_db():
    """Get database connection for current request"""
    if 'db' not in g:
        g.db = sqlite3.connect(app.config['DATABASE_PATH'])
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception):
    """Close database connection at end of request"""
    db = g.pop('db', None)
    if db is not None:
        db.close()


@app.route('/')
def badge_wall():
    """Main badge wall page — dizicute style with data_json"""
    import json as _json
    db = get_db()

    # Get all achievements with their stats
    achievements = db.execute('''
        SELECT
            a.id,
            a.name,
            a.type,
            a.category,
            a.description,
            a.display_format,
            a.threshold,
            COALESCE(s.achieved, 'N') as achieved,
            s.achieved_at,
            s.computed_value,
            b.url as badge_url,
            b.is_locked
        FROM achievements a
        LEFT JOIN achievement_stats s ON a.id = s.achievement_id
        LEFT JOIN achievement_badges b ON a.id = b.achievement_id AND b.is_current = 1
        WHERE a.display_on_achievements = 1
        ORDER BY a.sort_order, a.name
    ''').fetchall()

    # Build badge list for client-side rendering
    badges = []
    for row in achievements:
        badges.append({
            'id': row['id'],
            'name': row['name'],
            'type': row['type'],
            'category': row['category'],
            'description': row['description'],
            'achieved': row['achieved'] == 'Y',
            'achieved_at': row['achieved_at'],
            'computed_value': row['computed_value'],
            'badge_url': row['badge_url'] or '/static/badges/medal_badge.png',
            'is_locked': row['is_locked'] == 1,
        })

    # Sort: unlocked first (by achieved_at desc), then locked
    def sort_key(b):
        if b['achieved_at'] is None:
            return (1, '')
        return (0, b['achieved_at'])
    unlocked = sorted([b for b in badges if b['achieved']], key=sort_key, reverse=True)
    locked = sorted([b for b in badges if not b['achieved']], key=sort_key, reverse=True)
    sorted_badges = unlocked + locked

    # Get categories
    categories = db.execute('SELECT * FROM categories ORDER BY sort_order').fetchall()
    categories_list = [{'id': c['id'], 'name': c['name']} for c in categories]

    return render_template('badge_wall.html',
                          data_json=_json.dumps(sorted_badges, ensure_ascii=False),
                          categories_json=_json.dumps(categories_list, ensure_ascii=False))


@app.route('/api/badges')
def api_badges():
    """JSON API for badges"""
    db = get_db()
    
    achievements = db.execute('''
        SELECT 
            a.id,
            a.name,
            a.type,
            a.category,
            a.description,
            a.display_format,
            a.threshold,
            a.seasonal_type,
            COALESCE(s.achieved, 'N') as achieved,
            s.achieved_at,
            s.computed_value,
            b.url as badge_url,
            b.is_locked
        FROM achievements a
        LEFT JOIN achievement_stats s ON a.id = s.achievement_id
        LEFT JOIN achievement_badges b ON a.id = b.achievement_id AND b.is_current = 1
        WHERE a.display_on_achievements = 1
        ORDER BY a.sort_order, a.name
    ''').fetchall()
    
    badges = []
    for row in achievements:
        badges.append({
            'id': row['id'],
            'name': row['name'],
            'type': row['type'],
            'category': row['category'],
            'description': row['description'],
            'display_format': row['display_format'],
            'threshold': row['threshold'],
            'seasonal_type': row['seasonal_type'],
            'achieved': row['achieved'] == 'Y',
            'achieved_at': row['achieved_at'],
            'computed_value': row['computed_value'],
            'badge_url': row['badge_url'],
            'is_locked': row['is_locked'] == 1
        })
    
    return jsonify({
        'badges': badges,
        'total': len(badges),
        'achieved': sum(1 for b in badges if b['achieved'])
    })


@app.route('/api/badges/<badge_id>')
def api_badge_detail(badge_id):
    """JSON API for single badge detail"""
    db = get_db()
    
    achievement = db.execute('''
        SELECT 
            a.*,
            COALESCE(s.achieved, 'N') as achieved,
            s.achieved_at,
            s.raw_stats,
            s.computed_value,
            b.url as badge_url,
            b.is_locked
        FROM achievements a
        LEFT JOIN achievement_stats s ON a.id = s.achievement_id
        LEFT JOIN achievement_badges b ON a.id = b.achievement_id AND b.is_current = 1
        WHERE a.id = ?
    ''', (badge_id,)).fetchone()
    
    if not achievement:
        return jsonify({'error': 'Badge not found'}), 404
    
    return jsonify({
        'id': achievement['id'],
        'name': achievement['name'],
        'type': achievement['type'],
        'category': achievement['category'],
        'description': achievement['description'],
        'display_format': achievement['display_format'],
        'threshold': achievement['threshold'],
        'seasonal_type': achievement['seasonal_type'],
        'achieved': achievement['achieved'] == 'Y',
        'achieved_at': achievement['achieved_at'],
        'raw_stats': json.loads(achievement['raw_stats']) if achievement['raw_stats'] else {},
        'computed_value': achievement['computed_value'],
        'badge_url': achievement['badge_url'],
        'is_locked': achievement['is_locked'] == 1
    })


@app.route('/api/categories')
def api_categories():
    """JSON API for categories"""
    db = get_db()
    
    categories = db.execute('SELECT * FROM categories ORDER BY sort_order').fetchall()
    
    return jsonify({
        'categories': [dict(cat) for cat in categories]
    })


def _format_date(date_str):
    """Format ISO date string for display in Chinese locale"""
    if not date_str:
        return ''
    try:
        from datetime import datetime
        return datetime.fromisoformat(date_str.replace('Z', '+00:00')).strftime('%Y年%m月%d日')
    except Exception:
        return date_str


app.jinja_env.globals['formatDate'] = _format_date


if __name__ == '__main__':
    app.run(
        host=app.config['HOST'],
        port=app.config['PORT'],
        debug=app.config['DEBUG']
    )
