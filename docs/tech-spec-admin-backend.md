---
title: tech-spec yoachi admin 后台
source: ai-agent
status: draft
project: yoachi
created: 2026-06-25
updated: 2026-06-25
author: coder agent
---

# tech-spec: Yoachi Admin 后台

> **AI 标注:** 本技术方案由 coder agent 生成, YAML `source: ai-agent`.
> 配套 plan: `.hermes/plans/yoachi-admin-plan.md` v1.1.

---

## 0. 范围与依赖

### 0.1 范围

本技术方案覆盖 yoachi admin 后台 3 个阶段:

| 阶段 | 范围 | 依赖 |
|------|------|------|
| **Phase 1** | Badge 内容管理后台 (migration + admin 路由 + 模板 + CRUD API) | 无 |
| **Phase 2** | Badge 设计工作流 (复制 dizical draft/generator, 新建 yoachi badge-image skill) | Phase 1 |
| **Phase 3** | 前端页面灵活编排 (page_sections CRUD + 前端渲染) | Phase 1 |

### 0.2 设计依据

- **生产现状**: yoachi MVP 已上线 — Flask + SQLite + dizicute 风格勋章墙 + GSAP modal, 39 个"乐"分类 badge 从 dizical 同步
- **复用资产**:
  - dizical badge_draft.py (文件契约 + 状态机)
  - dizical badge_generator.py (6 步流水线 + hermes subprocess)
  - dizical badge-image skill (enamel pin prompt + PIL 阈值 245 + rembg 兜底)
  - dizicute CSS tokens (6 色: primary #FF6B6B, secondary #2C3E50, tertiary #FFF8F0, neutral #FFFFFF, muted #666666, accent #FF8C5A)
  - sync/manager.py (APScheduler 每 5 分钟从 dizical DB 同步)
- **约束**: 无认证 (本地网络 only), SQLite 单文件, 不破坏现有同步机制

### 0.3 文件改动清单

| 动作 | 文件 | 阶段 | 说明 |
|------|------|------|------|
| **新增** | `routes/__init__.py` | P1 | Blueprint 包 |
| **新增** | `routes/admin.py` | P1 | Admin Blueprint (~300 行) |
| **新增** | `templates/admin/base.html` | P1 | Admin 布局 |
| **新增** | `templates/admin/badge_list.html` | P1 | Badge 列表页 |
| **新增** | `templates/admin/badge_form.html` | P1 | 新建/编辑表单 |
| **新增** | `static/css/admin.css` | P1 | Admin 专用样式 |
| **新增** | `migrations/001_admin_fields.py` | P1 | 幂等 migration |
| **新增** | `workflow/__init__.py` | P2 | Workflow 包 |
| **新增** | `workflow/draft.py` | P2 | 复制自 dizical badge_draft.py |
| **新增** | `workflow/generator.py` | P2 | 复制自 dizical badge_generator.py |
| **新增** | `workflow/prompts.py` | P2 | Prompt 模板 |
| **新增** | `templates/admin/badge_design.html` | P2 | 设计工作流表单 |
| **新增** | `data/badge_data/` | P2 | Draft JSON 文件目录 |
| **修改** | `app.py` | P1 | 注册 admin blueprint + migration hook |
| **修改** | `config.py` | P1 | 新增 migration/paths 配置 |
| **修改** | `templates/badge_wall.html` | P3 | 渲染 page_sections |
| **修改** | `sync/manager.py` | P1 | post-sync hook 保留 yoachi 扩展字段 |

### 0.4 关键架构决策

1. **Flask Blueprint**: admin 路由独立 `routes/admin.py`, 不污染 `app.py` 主路由
2. **dizicute 设计系统复用**: admin 模板继承 dizicute 6 色 token, 不另建设计语言
3. **文件契约模式**: 从 dizical 复制 badge_draft.py, draft JSON 放 `data/badge_data/`, 跟 dizical 同构但路径独立
4. **同步兼容**: sync/manager.py 每次 sync 后 `_post_sync_hook` 重新确保 yoachi 扩展字段存在 (ALTER TABLE IF NOT EXISTS 语义)

---

## 1. 数据模型变更

### 1.1 achievements 表扩展 (ALTER TABLE)

```sql
-- 幂等: 每个 ALTER 都用 try/except 忽略 "duplicate column" 错误
ALTER TABLE achievements ADD COLUMN rarity TEXT DEFAULT 'common';
ALTER TABLE achievements ADD COLUMN cond_text TEXT;
ALTER TABLE achievements ADD COLUMN unlock_strategy TEXT DEFAULT 'calc';
ALTER TABLE achievements ADD COLUMN achieved_at_override TEXT;
```

**字段说明:**

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `rarity` | TEXT | `'common'` | 稀有度: `common` / `rare` / `epic` / `legendary` |
| `cond_text` | TEXT | NULL | 解锁条件文案 (modal-cond 显示, 区别于 description) |
| `unlock_strategy` | TEXT | `'calc'` | 解锁策略: `calc` (自动计算) / `manual` (手动) / `immediate` (立即) |
| `achieved_at_override` | TEXT | NULL | 手动设置的解锁时间 (manual 模式用, ISO 8601) |

> **注意**: `sort_order` 已存在于原表 (dizical 同步过来), 不需重复添加.

### 1.2 badge_images 表 (新建)

```sql
CREATE TABLE IF NOT EXISTS badge_images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    achievement_id TEXT NOT NULL,
    rarity TEXT NOT NULL,                    -- common/rare/epic/legendary/locked
    url TEXT NOT NULL,                       -- /static/badges/{id}_{rarity}_v{n}.png
    version INTEGER DEFAULT 1,
    is_current INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (achievement_id) REFERENCES achievements(id)
);

CREATE INDEX IF NOT EXISTS idx_badge_images_achievement
    ON badge_images(achievement_id, is_current);
```

**设计说明:**
- 一个 achievement 可有多张图片 (不同 rarity 版本)
- `rarity` 区分同一 badge 的不同稀有度图片
- `is_current=1` 标记当前生效图片, 同一 `(achievement_id, rarity)` 只有一个 `is_current=1`
- 版本管理: 换新图时 `UPDATE is_current=0` + `INSERT version+1, is_current=1`

### 1.3 page_sections 表 (Phase 3)

```sql
CREATE TABLE IF NOT EXISTS page_sections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    page TEXT NOT NULL DEFAULT 'home',       -- 'home', 'badges'
    section_type TEXT NOT NULL,              -- 'badge-wall', 'carousel', 'stats-card', 'hero-banner'
    title TEXT,                              -- 区块标题
    config TEXT DEFAULT '{}',                -- JSON 配置
    sort_order INTEGER DEFAULT 0,
    visible INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_page_sections_page
    ON page_sections(page, sort_order);
```

### 1.4 sync 兼容性

sync/manager.py 的 `_post_sync_hook` 在每次同步后运行, 负责:
1. 确保 `categories` 表存在并 seed
2. 确保 achievements 扩展字段存在 (ALTER TABLE idempotent)
3. **不覆盖** yoachi 独有的 `badge_images` / `page_sections` 表 (sync 只覆盖 dizical 来源表)

> 关键: sync 是 `sqlite3.backup()` 全量覆盖, 但 `_post_sync_hook` 会重建 yoachi 扩展. badge_images 表数据会丢失 — 需在 Phase 1 实施时考虑: (a) badge_images 存独立 DB, 或 (b) sync 后 re-seed. **推荐方案 (a)**: badge_images 和 page_sections 存 `data/yoachi_admin.db` (独立于 sync 覆盖的 `yoachi.db`).

---

## 2. API 端点

### 2.1 Phase 1 — Badge CRUD

所有端点挂载在 `/api/admin/` 前缀, 返回 JSON.

| 方法 | 路径 | 说明 | 请求体 | 响应 |
|------|------|------|--------|------|
| GET | `/admin` | 管理后台首页 | — | HTML (badge_list.html) |
| GET | `/admin/badge/new` | 新建表单页 | — | HTML (badge_form.html) |
| GET | `/admin/badge/<id>/edit` | 编辑表单页 | — | HTML (badge_form.html) |
| GET | `/api/admin/badges` | 全部 badge 列表 | — | `{"badges": [...], "total": N}` |
| GET | `/api/admin/badge/<id>` | 单个 badge 详情 | — | `{"badge": {...}}` |
| POST | `/api/admin/badge` | 创建 badge | JSON (见下) | `{"ok": true, "badge": {...}}` |
| PUT | `/api/admin/badge/<id>` | 更新 badge | JSON (见下) | `{"ok": true, "badge": {...}}` |
| DELETE | `/api/admin/badge/<id>` | 删除 badge | — | `{"ok": true}` |
| POST | `/api/admin/badge/<id>/unlock` | 手动解锁/锁定 | `{"achieved": true/false}` | `{"ok": true}` |
| POST | `/api/admin/badge/<id>/image` | 上传图片 | multipart (file + rarity) | `{"ok": true, "url": "..."}` |

#### POST /api/admin/badge 请求体:

```json
{
    "id": "reading_100_books",
    "name": "百书斩",
    "type": "突破",
    "category": "shu",
    "rarity": "epic",
    "description": "读完100本书，如同...",
    "cond_text": "累计阅读100本课外书",
    "unlock_strategy": "calc",
    "threshold": 100,
    "display_format": "count",
    "sort_order": 10,
    "seasonal_type": null
}
```

#### PUT /api/admin/badge/<id> 请求体:

跟 POST 一致, 但 `id` 字段不可改 (用 URL 路径中的 id).

#### POST /api/admin/badge/<id>/unlock 请求体:

```json
{
    "achieved": true,
    "achieved_at": "2026-06-25T10:00:00Z"
}
```

### 2.2 Phase 2 — Badge 设计工作流

| 方法 | 路径 | 说明 | 请求体 | 响应 |
|------|------|------|--------|------|
| GET | `/admin/badge/design` | 设计工作流页面 | — | HTML (badge_design.html) |
| GET | `/api/admin/badge/drafts` | 列出所有 draft | ?status=draft_created | `{"drafts": [...]}` |
| POST | `/api/admin/badge/draft` | 创建 draft | JSON (meta) | `{"ok": true, "draft_id": "..."}` |
| GET | `/api/admin/badge/draft/<draft_id>` | 获取 draft 详情 | — | `{"draft": {...}}` |
| POST | `/api/admin/badge/draft/<draft_id>/generate` | 触发生图 | — | SSE stream |
| POST | `/api/admin/badge/draft/<draft_id>/confirm` | 确认 draft | — | `{"ok": true}` |
| POST | `/api/admin/badge/draft/<draft_id>/commit` | commit 到 DB | — | `{"ok": true, "badge_id": "..."}` |
| DELETE | `/api/admin/badge/draft/<draft_id>` | 放弃 draft | — | `{"ok": true}` |

#### POST /api/admin/badge/draft 请求体:

```json
{
    "id": "reading_100_books",
    "name": "百书斩",
    "type": "突破",
    "category": "shu",
    "placeholder": "a cute chibi girl reading a tall stack of colorful books, surrounded by floating pages and stars",
    "zh_story": "古人读万卷书行万里路...",
    "cond_text": "累计阅读100本课外书",
    "rarity": "epic"
}
```

### 2.3 Phase 3 — Page Sections

| 方法 | 路径 | 说明 | 请求体 | 响应 |
|------|------|------|--------|------|
| GET | `/admin/pages` | 页面管理页 | — | HTML |
| GET | `/api/admin/sections` | 列出 sections | ?page=home | `{"sections": [...]}` |
| POST | `/api/admin/section` | 创建 section | JSON | `{"ok": true, "section": {...}}` |
| PUT | `/api/admin/section/<id>` | 更新 section | JSON | `{"ok": true}` |
| DELETE | `/api/admin/section/<id>` | 删除 section | — | `{"ok": true}` |
| PUT | `/api/admin/sections/reorder` | 批量排序 | `{"ids": [3,1,2]}` | `{"ok": true}` |

---

## 3. 文件结构

```
yoachi/
├── app.py                          # 修改: 注册 admin blueprint + migration hook
├── config.py                       # 修改: 新增 ADMIN_DB_PATH
├── routes/
│   ├── __init__.py                 # 新增
│   └── admin.py                    # 新增: Admin Blueprint (~300 行)
├── templates/
│   ├── badge_wall.html             # 现有 (Phase 3 可能修改)
│   └── admin/
│       ├── base.html               # 新增: admin 布局 (dizicute 侧边栏)
│       ├── badge_list.html         # 新增: badge 列表 (Alpine.js 表格)
│       ├── badge_form.html         # 新增: 新建/编辑表单
│       └── badge_design.html       # 新增 (Phase 2): 设计工作流
├── static/
│   ├── css/
│   │   ├── style.css               # 现有
│   │   └── admin.css               # 新增: admin 专用样式
│   └── badges/                     # 现有 (badge PNG)
├── workflow/                        # 新增 (Phase 2)
│   ├── __init__.py
│   ├── draft.py                    # 复制自 dizical badge_draft.py (适配路径)
│   ├── generator.py                # 复制自 dizical badge_generator.py (适配路径)
│   └── prompts.py                  # Prompt 模板
├── data/
│   ├── yoachi.db                   # 现有 (sync 覆盖)
│   ├── yoachi_admin.db             # 新增: badge_images + page_sections (不受 sync 影响)
│   └── badge_data/                 # 新增 (Phase 2): draft JSON 文件
├── migrations/
│   └── 001_admin_fields.py         # 新增: 幂等 migration
└── sync/
    └── manager.py                  # 修改: post-sync hook 增加 admin 字段确保
```

---

## 4. Phase 1 实施: Migration + Admin 路由 + 模板

### 4.1 Migration (`migrations/001_admin_fields.py`)

```python
"""幂等 migration: achievements 扩展字段 + badge_images 表 + admin DB"""
import sqlite3
import os

def run(db_path: str, admin_db_path: str):
    """运行 migration. 可重复调用, 不报错."""
    # ── achievements 扩展字段 (主 DB, sync 覆盖后 post-sync 重建) ──
    conn = sqlite3.connect(db_path)
    try:
        for sql in [
            "ALTER TABLE achievements ADD COLUMN rarity TEXT DEFAULT 'common'",
            "ALTER TABLE achievements ADD COLUMN cond_text TEXT",
            "ALTER TABLE achievements ADD COLUMN unlock_strategy TEXT DEFAULT 'calc'",
            "ALTER TABLE achievements ADD COLUMN achieved_at_override TEXT",
        ]:
            try:
                conn.execute(sql)
            except sqlite3.OperationalError:
                pass  # "duplicate column name" → 已存在, 跳过
        conn.commit()
    finally:
        conn.close()

    # ── admin 独立 DB (不受 sync 覆盖) ──
    conn = sqlite3.connect(admin_db_path)
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS badge_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                achievement_id TEXT NOT NULL,
                rarity TEXT NOT NULL,
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
    finally:
        conn.close()
```

### 4.2 Admin Blueprint (`routes/admin.py`)

```python
"""Yoachi Admin Blueprint — Badge 内容管理"""
import json
import os
import sqlite3
from pathlib import Path
from flask import Blueprint, render_template, request, jsonify, g, current_app

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')
admin_api_bp = Blueprint('admin_api', __name__, url_prefix='/api/admin')

# ── DB helpers ──────────────────────────────────────────────

def get_admin_db():
    """获取 admin 独立 DB 连接"""
    if 'admin_db' not in g:
        db_path = current_app.config['ADMIN_DATABASE_PATH']
        g.admin_db = sqlite3.connect(db_path)
        g.admin_db.row_factory = sqlite3.Row
    return g.admin_db

def get_main_db():
    """获取主 DB 连接 (achievements 表)"""
    if 'db' not in g:
        g.db = sqlite3.connect(current_app.config['DATABASE_PATH'])
        g.db.row_factory = sqlite3.Row
    return g.db

@admin_bp.teardown_request
@admin_api_bp.teardown_request
def close_dbs(exception):
    for key in ('admin_db', 'db'):
        db = g.pop(key, None)
        if db is not None:
            db.close()

# ── 页面路由 ────────────────────────────────────────────────

@admin_bp.route('/')
def badge_list():
    return render_template('admin/badge_list.html')

@admin_bp.route('/badge/new')
def badge_new():
    return render_template('admin/badge_form.html', badge=None)

@admin_bp.route('/badge/<badge_id>/edit')
def badge_edit(badge_id):
    return render_template('admin/badge_form.html', badge_id=badge_id)

# ── API: Badge CRUD ─────────────────────────────────────────

@admin_api_bp.route('/badges')
def api_list_badges():
    db = get_main_db()
    rows = db.execute('''
        SELECT a.*, b.url as badge_url, b.is_locked
        FROM achievements a
        LEFT JOIN achievement_badges b ON a.id = b.achievement_id AND b.is_current = 1
        ORDER BY a.sort_order, a.name
    ''').fetchall()
    badges = [dict(r) for r in rows]
    return jsonify({'badges': badges, 'total': len(badges)})

@admin_api_bp.route('/badge/<badge_id>')
def api_get_badge(badge_id):
    db = get_main_db()
    row = db.execute('''
        SELECT a.*, b.url as badge_url, b.is_locked
        FROM achievements a
        LEFT JOIN achievement_badges b ON a.id = b.achievement_id AND b.is_current = 1
        WHERE a.id = ?
    ''', (badge_id,)).fetchone()
    if not row:
        return jsonify({'error': 'not found'}), 404
    return jsonify({'badge': dict(row)})

@admin_api_bp.route('/badge', methods=['POST'])
def api_create_badge():
    data = request.get_json()
    required = ['id', 'name', 'type', 'category']
    for k in required:
        if not data.get(k):
            return jsonify({'error': f'缺少必填字段: {k}'}), 400

    db = get_main_db()
    exists = db.execute('SELECT 1 FROM achievements WHERE id=?', (data['id'],)).fetchone()
    if exists:
        return jsonify({'error': f'ID 已存在: {data["id"]}'}), 409

    max_sort = db.execute('SELECT COALESCE(MAX(sort_order),0) FROM achievements').fetchone()[0]
    db.execute('''
        INSERT INTO achievements (id, name, type, category, description, display_format,
            threshold, seasonal_type, display_on_achievements, sort_order,
            rarity, cond_text, unlock_strategy)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
    ''', (
        data['id'], data['name'], data['type'], data['category'],
        data.get('description', ''), data.get('display_format', 'count'),
        data.get('threshold'), data.get('seasonal_type'),
        max_sort + 1,
        data.get('rarity', 'common'), data.get('cond_text'),
        data.get('unlock_strategy', 'calc'),
    ))
    db.commit()
    return jsonify({'ok': True, 'badge': data}), 201

@admin_api_bp.route('/badge/<badge_id>', methods=['PUT'])
def api_update_badge(badge_id):
    data = request.get_json()
    db = get_main_db()
    exists = db.execute('SELECT 1 FROM achievements WHERE id=?', (badge_id,)).fetchone()
    if not exists:
        return jsonify({'error': 'not found'}), 404

    fields = ['name', 'type', 'category', 'description', 'display_format',
              'threshold', 'seasonal_type', 'rarity', 'cond_text',
              'unlock_strategy', 'sort_order']
    sets = []
    vals = []
    for f in fields:
        if f in data:
            sets.append(f"{f} = ?")
            vals.append(data[f])
    if not sets:
        return jsonify({'error': '无更新字段'}), 400

    vals.append(badge_id)
    db.execute(f"UPDATE achievements SET {', '.join(sets)} WHERE id = ?", vals)
    db.commit()
    return jsonify({'ok': True})

@admin_api_bp.route('/badge/<badge_id>', methods=['DELETE'])
def api_delete_badge(badge_id):
    db = get_main_db()
    db.execute('DELETE FROM achievements WHERE id = ?', (badge_id,))
    db.execute('DELETE FROM achievement_stats WHERE achievement_id = ?', (badge_id,))
    db.execute('DELETE FROM achievement_badges WHERE achievement_id = ?', (badge_id,))
    db.commit()
    # 清理 admin DB 中的图片记录
    admin_db = get_admin_db()
    admin_db.execute('DELETE FROM badge_images WHERE achievement_id = ?', (badge_id,))
    admin_db.commit()
    return jsonify({'ok': True})

@admin_api_bp.route('/badge/<badge_id>/unlock', methods=['POST'])
def api_toggle_unlock(badge_id):
    data = request.get_json()
    achieved = data.get('achieved', False)
    db = get_main_db()

    # 更新 achievement_stats
    db.execute('''
        INSERT INTO achievement_stats (achievement_id, achieved, raw_stats, computed_value)
        VALUES (?, ?, '{}', NULL)
        ON CONFLICT(achievement_id) DO UPDATE SET achieved = ?
    ''', (badge_id, 'Y' if achieved else 'N', 'Y' if achieved else 'N'))

    if achieved and data.get('achieved_at'):
        db.execute('UPDATE achievements SET achieved_at_override = ? WHERE id = ?',
                   (data['achieved_at'], badge_id))

    db.commit()
    return jsonify({'ok': True})

@admin_api_bp.route('/badge/<badge_id>/image', methods=['POST'])
def api_upload_image(badge_id):
    if 'file' not in request.files:
        return jsonify({'error': '无文件'}), 400
    file = request.files['file']
    rarity = request.form.get('rarity', 'common')

    # 保存到 static/badges/
    ext = Path(file.filename).suffix or '.png'
    filename = f"{badge_id}_{rarity}{ext}"
    save_dir = Path(current_app.root_path) / 'static' / 'badges'
    save_dir.mkdir(parents=True, exist_ok=True)
    file.save(save_dir / filename)
    url = f"/static/badges/{filename}"

    # 写 admin DB
    admin_db = get_admin_db()
    # 旧图标记 is_current=0
    admin_db.execute('''
        UPDATE badge_images SET is_current = 0
        WHERE achievement_id = ? AND rarity = ? AND is_current = 1
    ''', (badge_id, rarity))
    # 新版本号
    row = admin_db.execute('''
        SELECT COALESCE(MAX(version), 0) + 1 FROM badge_images
        WHERE achievement_id = ? AND rarity = ?
    ''', (badge_id, rarity)).fetchone()
    version = row[0]
    admin_db.execute('''
        INSERT INTO badge_images (achievement_id, rarity, url, version, is_current)
        VALUES (?, ?, ?, ?, 1)
    ''', (badge_id, rarity, url, version))
    admin_db.commit()
    return jsonify({'ok': True, 'url': url, 'version': version})
```

### 4.3 app.py 修改

```python
# 在 app 创建后添加:
from routes.admin import admin_bp, admin_api_bp
app.register_blueprint(admin_bp)
app.register_blueprint(admin_api_bp)

# 在 _ensure_yoachi_schema() 末尾添加 migration:
from migrations import 001_admin_fields as migration
migration.run(app.config['DATABASE_PATH'], app.config['ADMIN_DATABASE_PATH'])
```

### 4.4 config.py 修改

```python
class Config:
    # ... 现有 ...
    ADMIN_DATABASE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'yoachi_admin.db')
```

### 4.5 模板设计

#### `templates/admin/base.html`

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{% block title %}Yoachi Admin{% endblock %}</title>
  <script src="https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js" defer></script>
  <link rel="stylesheet" href="/static/css/style.css">
  <link rel="stylesheet" href="/static/css/admin.css">
</head>
<body class="admin-body">
  <nav class="admin-sidebar">
    <div class="admin-logo">🏆 Yoachi Admin</div>
    <a href="/admin/" class="nav-link">📋 Badge 管理</a>
    <a href="/admin/badge/design" class="nav-link">🎨 设计工作流</a>
    <a href="/" class="nav-link">← 返回前台</a>
  </nav>
  <main class="admin-content">
    {% block content %}{% endblock %}
  </main>
</body>
</html>
```

#### `templates/admin/badge_list.html`

使用 Alpine.js 实现搜索/筛选, 数据从 `/api/admin/badges` 加载.
核心功能: 表格展示 + 分类筛选 + 搜索 + 新建/编辑/删除操作.

#### `templates/admin/badge_form.html`

新建/编辑共用模板, 字段包括:
- id (readonly 编辑时), name, type (select), category (select)
- rarity (select), description (textarea), cond_text
- unlock_strategy (select), threshold, sort_order
- 图片上传区域 (可上传/预览/替换)

---

## 5. Phase 2 实施: Badge 设计工作流

### 5.1 复制策略

从 dizical 复制 3 个核心模块到 yoachi:

| dizical 来源 | yoachi 目标 | 改动 |
|-------------|------------|------|
| `src/kid_app/badge_draft.py` | `workflow/draft.py` | 路径: `_badge_data_dir()` → `yoachi/data/badge_data/` |
| `src/kid_app/badge_generator.py` | `workflow/generator.py` | DB 路径: `yoachi_admin.db`; hermes profile: `yoachi` |
| `src/kid_app/badge_prompts.py` | `workflow/prompts.py` | 无改动 (纯模板) |

### 5.2 路径适配 (`workflow/draft.py`)

```python
def _badge_data_dir() -> Path:
    """yoachi/data/badge_data/ (绝对路径)"""
    project_root = Path(__file__).resolve().parent.parent  # yoachi/
    return project_root / "data" / "badge_data"

def _tmp_dir() -> Path:
    return _badge_data_dir() / ".tmp"
```

### 5.3 DB 适配 (`workflow/generator.py`)

```python
# 改用 yoachi_admin.db
def _get_admin_db_path() -> Path:
    return Path(__file__).resolve().parent.parent / "data" / "yoachi_admin.db"

# hermes profile 改为 yoachi (新建)
_HERMES_CMD = ['hermes', 'chat', '-q', '{prompt}', '-t', 'image_gen',
               '--profile', 'yoachi', '-Q', '--yolo']
```

### 5.4 yoachi badge-image skill

在 `~/.hermes/profiles/yoachi/skills/badge-image/` 创建专用 skill:
- 基于 dizical 版改造
- enamel pin prompt 模板不变
- PIL 阈值 245 + rembg 兜底不变
- 输出路径指向 `yoachi/data/badge_data/.tmp/`

### 5.5 设计表单 (`templates/admin/badge_design.html`)

基于 dizical `config-badge.html` 改造:
- Step 1: 填 meta (id/name/type/category/placeholder/zh_story/cond_text)
- Step 2: 预览 draft JSON
- Step 3: 触发生图 (SSE 进度)
- Step 4: 预览图片 + 确认/重新生图
- Step 5: Commit 到 DB

---

## 6. Phase 3 实施: Page Sections CRUD + 前端渲染

### 6.1 数据模型

见 §1.3 `page_sections` 表.

### 6.2 API 端点

见 §2.3.

### 6.3 前端渲染

`badge_wall.html` 改造:
1. 从 `/api/sections?page=badges` 获取 section 配置
2. 按 `sort_order` 排序渲染各 section
3. 每个 section 根据 `section_type` 渲染不同组件:
   - `badge-wall`: 现有勋章墙逻辑
   - `badge-carousel`: 轮播展示
   - `stats-card`: 统计卡片
   - `hero-banner`: 顶部横幅

---

## 7. 安全考虑

| 风险 | 当前策略 | 后续方案 |
|------|---------|---------|
| 无认证 | 本地网络 only (192.168.x.x), 不暴露公网 | Phase 2+ 可加 PIN 码 (复用 dizical 模式) |
| CSRF | Flask SECRET_KEY 已设置 | Admin 表单加 CSRF token |
| SQL 注入 | 全部用参数化查询 | — |
| 文件上传 | 仅接受图片格式, 限制大小 5MB | — |
| XSS | Jinja2 自动转义, Alpine.js esc() | — |
| 数据丢失 | admin DB 独立, 不受 sync 覆盖 | 定期备份 admin DB |

---

## 8. Migration 计划

### 8.1 幂等原则

所有 migration 脚本可重复执行:
- `ALTER TABLE ADD COLUMN`: try/except 忽略 "duplicate column"
- `CREATE TABLE IF NOT EXISTS`: 幂等
- `CREATE INDEX IF NOT EXISTS`: 幂等

### 8.2 执行时机

1. `app.py` 启动时自动运行 `_ensure_yoachi_schema()`
2. sync/manager.py `_post_sync_hook` 每次同步后重新确保扩展字段
3. 手动: `python -c "from migrations import 001_admin_fields; ..."` (可选)

### 8.3 回滚

SQLite 无 DROP COLUMN (3.35 前), 回滚方式:
- 删除 `data/yoachi_admin.db` (丢弃 badge_images + page_sections)
- achievements 扩展字段保留无害 (默认值)

---

## 9. 测试策略

### 9.1 Phase 1 测试

| 测试类型 | 范围 |
|---------|------|
| Migration | 重复执行不报错; 字段存在性验证 |
| API CRUD | curl 全端点: POST 创建 → GET 查询 → PUT 更新 → DELETE 删除 |
| 图片上传 | multipart 上传 + badge_images 记录 + 文件落盘 |
| 手动解锁 | achievement_stats 写入 + 前端可见 |
| Sync 兼容 | sync 后 admin 字段仍在; admin DB 不被覆盖 |

### 9.2 Phase 2 测试

| 测试类型 | 范围 |
|---------|------|
| Draft CRUD | 创建 → 更新 image → 确认 → commit 全流程 |
| 生图流水线 | hermes subprocess 调用 + 图片下载 + 去背 |
| SSE 进度 | 实时状态推送 |
| 失败回滚 | 生图失败时临时文件清理 |

### 9.3 Phase 3 测试

| 测试类型 | 范围 |
|---------|------|
| Section CRUD | 创建/更新/删除/排序 |
| 前端渲染 | 多 section 组合渲染 |

### 9.4 测试命令参考

```bash
# Phase 1 API 测试
curl http://localhost:5001/api/admin/badges
curl -X POST http://localhost:5001/api/admin/badge \
  -H 'Content-Type: application/json' \
  -d '{"id":"test_1","name":"测试","type":"突破","category":"shu"}'
curl -X PUT http://localhost:5001/api/admin/badge/test_1 \
  -H 'Content-Type: application/json' \
  -d '{"name":"测试更新"}'
curl -X DELETE http://localhost:5001/api/admin/badge/test_1

# 图片上传测试
curl -X POST http://localhost:5001/api/admin/badge/test_1/image \
  -F 'file=@test.png' -F 'rarity=common'
```

---

## 10. 实施优先级

| 子阶段 | 内容 | 行数估计 | 难度 |
|--------|------|---------|------|
| **P1.1** | migration + config + blueprint 骨架 | ~80 | ★☆☆ |
| **P1.2** | badge CRUD API (6 端点) | ~150 | ★★☆ |
| **P1.3** | admin 模板 (base + list + form) | ~300 | ★★☆ |
| **P1.4** | 图片上传 + 手动解锁 | ~80 | ★★☆ |
| **P2.1** | 复制 draft/generator + 路径适配 | ~200 | ★★☆ |
| **P2.2** | yoachi badge-image skill | ~100 | ★★★ |
| **P2.3** | 设计表单 + SSE + 5 步流程 | ~400 | ★★★ |
| **P3** | page_sections CRUD + 前端渲染 | ~300 | ★★★ |
| **总计** | | ~1,610 行 | |
