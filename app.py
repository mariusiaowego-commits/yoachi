"""Yoachi - Children's Achievement Badge System"""
import atexit
import os
import sqlite3
import json
from flask import Flask, render_template, jsonify, g
from config import Config
from sync import SyncManager

app = Flask(__name__)
app.config.from_object(Config)

# Start background sync scheduler
_sync_manager = SyncManager(
    dizical_path=app.config['DIZICAL_DATABASE_PATH'],
    yoachi_path=app.config['DATABASE_PATH'],
    interval_seconds=app.config['SYNC_INTERVAL_SECONDS'],
)
_sync_manager.start_background()
atexit.register(_sync_manager.stop)


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
    """Main badge wall page"""
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
            a.unlocked_template,
            a.locked_template,
            a.sort_order,
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
    
    # Get categories
    categories = db.execute('SELECT * FROM categories ORDER BY sort_order').fetchall()
    
    return render_template('badge_wall.html', 
                          achievements=achievements,
                          categories=categories)


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


if __name__ == '__main__':
    app.run(
        host=app.config['HOST'],
        port=app.config['PORT'],
        debug=app.config['DEBUG']
    )
