"""Yoachi Admin Blueprint — badge management routes."""
import json
import sqlite3
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, g, current_app

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')
admin_api_bp = Blueprint('admin_api', __name__, url_prefix='/api/admin')


def get_db():
    """Get yoachi.db connection (achievements + stats)."""
    if 'db' not in g:
        g.db = sqlite3.connect(current_app.config['DATABASE_PATH'])
        g.db.row_factory = sqlite3.Row
    return g.db


def get_admin_db():
    """Get yoachi_admin.db connection (badge_images)."""
    from admin_db import get_admin_db
    return get_admin_db()


@admin_bp.teardown_request
def close_db(exception):
    db = g.pop('db', None)
    if db is not None:
        db.close()


# ── Page Routes ──────────────────────────────────────────────

@admin_bp.route('/')
def badge_list():
    """Admin badge list page."""
    return render_template('admin/badge_list.html')


@admin_bp.route('/badge/new')
def badge_new():
    """New badge form."""
    return render_template('admin/badge_form.html', badge=None, mode='new')


@admin_bp.route('/badge/<badge_id>/edit')
def badge_edit(badge_id):
    """Edit badge form."""
    db = get_db()
    badge = db.execute(
        'SELECT * FROM achievements WHERE id = ?', (badge_id,)
    ).fetchone()
    if not badge:
        return 'Badge not found', 404
    return render_template('admin/badge_form.html', badge=badge, mode='edit')


# ── API Routes ───────────────────────────────────────────────

@admin_api_bp.route('/badges')
def api_badge_list():
    """List all badges with stats."""
    db = get_db()
    rows = db.execute('''
        SELECT
            a.id, a.name, a.type, a.category, a.rarity,
            a.description, a.cond_text, a.unlock_strategy,
            a.threshold, a.display_format, a.sort_order,
            a.seasonal_type, a.draft_status,
            COALESCE(s.achieved, 'N') as achieved,
            s.achieved_at,
            b.url as badge_url
        FROM achievements a
        LEFT JOIN achievement_stats s ON a.id = s.achievement_id
        LEFT JOIN achievement_badges b ON a.id = b.achievement_id AND b.is_current = 1
        ORDER BY a.sort_order, a.name
    ''').fetchall()

    badges = []
    for row in rows:
        badges.append({
            'id': row['id'],
            'name': row['name'],
            'type': row['type'],
            'category': row['category'],
            'rarity': row['rarity'] or 'N',
            'description': row['description'],
            'cond_text': row['cond_text'],
            'unlock_strategy': row['unlock_strategy'] or 'calc',
            'threshold': row['threshold'],
            'display_format': row['display_format'],
            'sort_order': row['sort_order'],
            'seasonal_type': row['seasonal_type'],
            'draft_status': row['draft_status'] or 'published',
            'achieved': row['achieved'] == 'Y',
            'achieved_at': row['achieved_at'],
            'badge_url': row['badge_url'],
        })

    return jsonify({'badges': badges, 'total': len(badges)})


@admin_api_bp.route('/badge/<badge_id>')
def api_badge_detail(badge_id):
    """Get single badge detail."""
    db = get_db()
    row = db.execute('''
        SELECT
            a.*,
            COALESCE(s.achieved, 'N') as achieved,
            s.achieved_at,
            b.url as badge_url
        FROM achievements a
        LEFT JOIN achievement_stats s ON a.id = s.achievement_id
        LEFT JOIN achievement_badges b ON a.id = b.achievement_id AND b.is_current = 1
        WHERE a.id = ?
    ''', (badge_id,)).fetchone()

    if not row:
        return jsonify({'error': 'Badge not found'}), 404

    return jsonify({
        'badge': {
            'id': row['id'],
            'name': row['name'],
            'type': row['type'],
            'category': row['category'],
            'rarity': row['rarity'] or 'N',
            'description': row['description'],
            'cond_text': row['cond_text'],
            'unlock_strategy': row['unlock_strategy'] or 'calc',
            'threshold': row['threshold'],
            'display_format': row['display_format'],
            'sort_order': row['sort_order'],
            'achieved': row['achieved'] == 'Y',
            'achieved_at': row['achieved_at'],
            'badge_url': row['badge_url'],
        }
    })


@admin_api_bp.route('/badge', methods=['POST'])
def api_badge_create():
    """Create a new badge."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    required = ['id', 'name', 'type', 'category']
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({'error': f'Missing fields: {missing}'}), 400

    db = get_db()
    try:
        db.execute('''
            INSERT INTO achievements (id, name, type, category, description, cond_text,
                unlock_strategy, threshold, display_format, rarity, sort_order, seasonal_type,
                stat_logic, placeholder, locked_template, unlocked_template)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data['id'], data['name'], data['type'], data['category'],
            data.get('description', ''), data.get('cond_text', ''),
            data.get('unlock_strategy', 'calc'), data.get('threshold'),
            data.get('display_format', 'count'), data.get('rarity', 'N'),
            data.get('sort_order', 0), data.get('seasonal_type'),
            data.get('stat_logic', ''), data.get('placeholder', ''),
            data.get('locked_template', ''), data.get('unlocked_template', ''),
        ))
        # Create stats entry
        db.execute(
            'INSERT OR IGNORE INTO achievement_stats (achievement_id, achieved) VALUES (?, ?)',
            (data['id'], 'N')
        )
        db.commit()
    except sqlite3.IntegrityError:
        return jsonify({'error': f'Badge id "{data["id"]}" already exists'}), 409

    return jsonify({'ok': True, 'badge_id': data['id']}), 201


@admin_api_bp.route('/badge/<badge_id>', methods=['PUT'])
def api_badge_update(badge_id):
    """Update an existing badge."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    db = get_db()
    existing = db.execute('SELECT id FROM achievements WHERE id = ?', (badge_id,)).fetchone()
    if not existing:
        return jsonify({'error': 'Badge not found'}), 404

    # Build dynamic UPDATE
    allowed = ['name', 'type', 'category', 'description', 'cond_text',
               'unlock_strategy', 'threshold', 'display_format', 'rarity',
               'sort_order', 'seasonal_type', 'draft_status']
    updates = []
    values = []
    for field in allowed:
        if field in data:
            updates.append(f'{field} = ?')
            values.append(data[field])

    if not updates:
        return jsonify({'error': 'No valid fields to update'}), 400

    updates.append("updated_at = datetime('now')")
    values.append(badge_id)

    db.execute(f"UPDATE achievements SET {', '.join(updates)} WHERE id = ?", values)
    db.commit()

    return jsonify({'ok': True, 'badge_id': badge_id})


@admin_api_bp.route('/badge/<badge_id>', methods=['DELETE'])
def api_badge_delete(badge_id):
    """Delete a badge and its stats/images."""
    db = get_db()
    existing = db.execute('SELECT id FROM achievements WHERE id = ?', (badge_id,)).fetchone()
    if not existing:
        return jsonify({'error': 'Badge not found'}), 404

    db.execute('DELETE FROM achievement_stats WHERE achievement_id = ?', (badge_id,))
    db.execute('DELETE FROM achievement_badges WHERE achievement_id = ?', (badge_id,))
    db.execute('DELETE FROM achievements WHERE id = ?', (badge_id,))
    db.commit()

    # Clean up admin DB images
    admin_conn = get_admin_db()
    admin_conn.execute('DELETE FROM badge_images WHERE achievement_id = ?', (badge_id,))
    admin_conn.commit()
    admin_conn.close()

    return jsonify({'ok': True})


@admin_api_bp.route('/badge/<badge_id>/unlock', methods=['POST'])
def api_badge_unlock(badge_id):
    """Manually toggle badge unlock status."""
    data = request.get_json()
    if not data or 'achieved' not in data:
        return jsonify({'error': 'achieved field required (true/false)'}), 400

    db = get_db()
    existing = db.execute('SELECT id FROM achievements WHERE id = ?', (badge_id,)).fetchone()
    if not existing:
        return jsonify({'error': 'Badge not found'}), 404

    achieved = 'Y' if data['achieved'] else 'N'
    achieved_at = data.get('achieved_at') or datetime.now().isoformat() if data['achieved'] else None

    db.execute('''
        INSERT INTO achievement_stats (achievement_id, achieved, achieved_at)
        VALUES (?, ?, ?)
        ON CONFLICT(achievement_id) DO UPDATE SET achieved = ?, achieved_at = ?
    ''', (badge_id, achieved, achieved_at, achieved, achieved_at))
    db.commit()

    return jsonify({'ok': True, 'achieved': data['achieved']})


# ── Categories API ───────────────────────────────────────────

@admin_api_bp.route('/categories')
def api_categories():
    """List all categories."""
    db = get_db()
    rows = db.execute('SELECT * FROM categories ORDER BY sort_order').fetchall()
    return jsonify({'categories': [dict(r) for r in rows]})
