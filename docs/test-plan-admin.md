---
title: "Yoachi Admin Backend 测试计划"
source: ai-agent
status: draft
project: yoachi
created: 2026-06-25
phase1_target: admin CRUD + badge management
phase2_target: AI badge generation pipeline
---

# Yoachi Admin Backend 测试计划

## 1. 测试策略

### 1.1 框架与工具

| 工具 | 用途 |
|------|------|
| pytest | 测试运行器 |
| pytest-cov | 覆盖率报告 |
| pytest-flask | Flask 测试客户端 fixture |
| pytest-mock / unittest.mock | Mock 依赖 |
| factory_boy | 测试数据工厂（可选） |
| Pillow (PIL) | 图片生成测试 fixture |
| io.BytesIO | 内存文件模拟 |

### 1.2 覆盖率目标

| 模块 | 最低覆盖率 | 目标覆盖率 |
|------|-----------|-----------|
| app.py (路由层) | 85% | 95% |
| admin 路由（新增） | 90% | 98% |
| sync/manager.py | 80% | 90% |
| 数据库操作层 | 90% | 95% |
| 工具函数 | 95% | 100% |
| **整体** | **85%** | **92%** |

### 1.3 测试目录结构

```
tests/
├── conftest.py              # 全局 fixtures
├── test_migration.py        # 数据库迁移测试
├── test_crud.py             # CRUD 操作单元测试
├── test_validation.py       # 输入验证测试
├── test_api_admin.py        # Admin API 端点测试
├── test_api_public.py       # 公共 API 回归测试
├── test_sync.py             # 同步管理器测试
├── test_integration.py      # 端到端集成测试
├── test_ui.py               # 模板渲染测试
├── test_regression.py       # 回归测试
├── fixtures/
│   ├── test_schema.sql      # 测试用 schema
│   ├── sample_badge.png     # 有效 PNG 测试图片 (128x128)
│   ├── large_badge.png      # 超尺寸测试图片
│   ├── invalid_file.txt     # 非图片文件
│   └── sample_data.json     # 测试数据集
└── factories.py             # 数据工厂（可选）
```

### 1.4 测试数据库策略

- 每个测试函数使用独立的内存 SQLite 数据库 (`:memory:`)
- 通过 `conftest.py` 中的 fixture 自动建表和填充数据
- 测试结束后自动销毁，不污染开发数据库
- 文件上传测试使用 `tmp_path` fixture

---

## 2. 测试分类

### 2.1 单元测试 (Unit Tests)

**目标**：验证最小可测试单元的正确性，不依赖外部服务或网络。

- 数据库迁移幂等性
- CRUD 操作正确性
- 输入验证逻辑
- 数据格式转换

### 2.2 API 测试 (API Tests)

**目标**：验证每个 HTTP 端点的请求/响应行为，包括成功路径和错误路径。

- 正常请求返回正确状态码和数据结构
- 缺少必填字段返回 400
- 不存在的资源返回 404
- 边界条件（空字符串、超长输入、特殊字符）

### 2.3 集成测试 (Integration Tests)

**目标**：验证多个组件协同工作，特别是 sync + admin 交互。

- 同步后 admin 能正确读取数据
- admin 修改后 badge wall 正确展示
- 完整 badge 生命周期：创建 → 上传图片 → 手动解锁 → 展示

### 2.4 UI 测试 (UI Tests)

**目标**：验证模板渲染和表单提交。

- 模板正确渲染、无 500 错误
- 表单提交后正确重定向或返回数据
- Jinja2 模板变量正确注入

### 2.5 回归测试 (Regression Tests)

**目标**：确保 admin 改动不破坏现有 badge wall 功能。

- `/` 路由正常返回
- `/api/badges` 返回格式不变
- `/api/badges/<id>` 返回格式不变
- `/api/categories` 返回格式不变
- 分类映射 (CATEGORY_NAMES, CATEGORY_EMOJI) 不变

---

## 3. Phase 1 测试用例 — Admin CRUD

### 3.1 数据库迁移测试

| # | 测试函数名 | 描述 | 断言 |
|---|-----------|------|------|
| M1 | `test_migration_creates_admin_columns` | 运行迁移，检查 achievements 表新增 admin 字段 | `PRAGMA table_info(achievements)` 包含 `created_by`, `rarity`, `is_manual` 列 |
| M2 | `test_migration_idempotent` | 连续运行迁移脚本两次，不报错 | 第二次运行不抛异常；表结构与第一次完全相同 |
| M3 | `test_migration_preserves_data` | 迁移前插入数据，迁移后数据不丢失 | `SELECT COUNT(*) FROM achievements` 迁移前后相等 |
| M4 | `test_migration_creates_admin_badges_table` | 检查 `admin_badges` 表（如有独立表）已创建 | `SELECT name FROM sqlite_master WHERE type='table' AND name='admin_badges'` 返回结果 |
| M5 | `test_migration_default_values` | 迁移后已有记录的默认值正确 | `SELECT rarity FROM achievements WHERE rarity IS NOT NULL` 每行有值；`is_manual` 默认为 0 |

### 3.2 Badge 列表测试 (GET /api/admin/badges)

| # | 测试函数名 | 描述 | 断言 |
|---|-----------|------|------|
| B1 | `test_admin_badges_empty_db` | 空数据库返回空列表 | `resp.json['badges'] == []`; `resp.json['total'] == 0` |
| B2 | `test_admin_badges_with_data` | 插入 3 条记录，返回全部 | `len(resp.json['badges']) == 3`; `resp.json['total'] == 3` |
| B3 | `test_admin_badges_pagination` | 插入 25 条，请求 `?page=1&per_page=10` | `len(resp.json['badges']) == 10`; `resp.json['total'] == 25`; `resp.json['pages'] == 3` |
| B4 | `test_admin_badges_filter_by_category` | 请求 `?category=li` | 所有返回的 badge `category == 'li'` |
| B5 | `test_admin_badges_filter_by_rarity` | 请求 `?rarity=legendary` | 所有返回的 badge `rarity == 'legendary'` |
| B6 | `test_admin_badges_search_by_name` | 请求 `?q=阅读` | 返回的 badge name 包含 '阅读' |
| B7 | `test_admin_badges_sort_order` | 默认按 `sort_order, name` 排序 | `resp.json['badges'][0]['sort_order'] <= resp.json['badges'][1]['sort_order']` |

### 3.3 Badge 创建测试 (POST /api/admin/badge)

| # | 测试函数名 | 描述 | 断言 |
|---|-----------|------|------|
| C1 | `test_create_badge_valid_input` | 提交完整合法数据 | `resp.status_code == 201`; 返回的 JSON 包含 `id`, `name` |
| C2 | `test_create_badge_missing_name` | 缺少 `name` 字段 | `resp.status_code == 400`; `resp.json['error']` 包含 'name' |
| C3 | `test_create_badge_missing_category` | 缺少 `category` 字段 | `resp.status_code == 400`; `resp.json['error']` 包含 'category' |
| C4 | `test_create_badge_missing_type` | 缺少 `type` 字段 | `resp.status_code == 400` |
| C5 | `test_create_badge_duplicate_id` | 插入重复 `id` | `resp.status_code == 409`; `resp.json['error']` 包含 'already exists' 或 'duplicate' |
| C6 | `test_create_badge_invalid_category` | `category` 不在允许列表中 | `resp.status_code == 400`; `resp.json['error']` 包含 'invalid category' |
| C7 | `test_create_badge_empty_name` | `name` 为空字符串 | `resp.status_code == 400` |
| C8 | `test_create_badge_name_too_long` | `name` 超过 100 字符 | `resp.status_code == 400` |
| C9 | `test_create_badge_special_chars_in_id` | `id` 包含特殊字符 `!@#` | `resp.status_code == 400`；或根据业务规则允许（需确认） |
| C10 | `test_create_badge_default_sort_order` | 不传 `sort_order` | 返回的 `sort_order` 有默认值（0 或自动递增） |
| C11 | `test_create_badge_appears_in_db` | 创建后直接查数据库 | `SELECT * FROM achievements WHERE id = ?` 返回 1 行 |
| C12 | `test_create_badge_appears_in_public_api` | 创建后查询 `/api/badges` | 新 badge 出现在列表中 |

### 3.4 Badge 更新测试 (PUT /api/admin/badge/<id>)

| # | 测试函数名 | 描述 | 断言 |
|---|-----------|------|------|
| U1 | `test_update_badge_change_name` | 修改 `name` | `resp.json['name'] == new_name`；数据库中 `name` 已更新 |
| U2 | `test_update_badge_change_category` | 修改 `category` 从 'li' 到 'shu' | `resp.json['category'] == 'shu'` |
| U3 | `test_update_badge_change_rarity` | 修改 `rarity` | `resp.json['rarity'] == 'legendary'` |
| U4 | `test_update_badge_change_description` | 修改 `description` | 返回的 `description` 已更新 |
| U5 | `test_update_badge_nonexistent_id` | 更新不存在的 ID | `resp.status_code == 404` |
| C1 | `test_update_badge_partial_update` | 只传 `name`，不传其他字段 | `name` 更新，其他字段不变 |
| U7 | `test_update_badge_invalid_rarity` | 传入无效 rarity 值 | `resp.status_code == 400` |
| U8 | `test_update_badge_response_format` | 检查返回结构 | 返回 JSON 包含所有 badge 字段 |

### 3.5 Badge 删除测试 (DELETE /api/admin/badge/<id>)

| # | 测试函数名 | 描述 | 断言 |
|---|-----------|------|------|
| D1 | `test_delete_badge_without_images` | 删除无图片的 badge | `resp.status_code == 200`；数据库中无此记录；`achievement_badges` 中无关联记录 |
| D2 | `test_delete_badge_with_images` | 删除有图片的 badge | `resp.status_code == 200`；图片文件已从磁盘删除（`os.path.exists(img_path) == False`） |
| D3 | `test_delete_badge_nonexistent_id` | 删除不存在的 ID | `resp.status_code == 404` |
| D4 | `test_delete_badge_cascades_stats` | 删除 badge 后 `achievement_stats` 关联记录也删除 | `SELECT COUNT(*) FROM achievement_stats WHERE achievement_id = ?` 返回 0 |
| D5 | `test_delete_badge_cascades_badges_table` | 删除 badge 后 `achievement_badges` 关联记录也删除 | `SELECT COUNT(*) FROM achievement_badges WHERE achievement_id = ?` 返回 0 |
| D6 | `test_delete_badge_not_in_public_api` | 删除后查询 `/api/badges` | 已删除 badge 不出现在列表中 |

### 3.6 手动解锁测试 (POST /api/admin/badge/<id>/unlock)

| # | 测试函数名 | 描述 | 断言 |
|---|-----------|------|------|
| L1 | `test_unlock_badge_toggle_on` | 解锁一个已锁定的 badge | `resp.json['achieved'] == True`；数据库中 `achievement_stats.achieved = 'Y'` |
| L2 | `test_unlock_badge_toggle_off` | 锁定一个已解锁的 badge | `resp.json['achieved'] == False`；数据库中 `achievement_stats.achieved = 'N'` |
| L3 | `test_unlock_badge_sets_achieved_at` | 解锁时设置 `achieved_at` | `resp.json['achieved_at']` 不为 None；时间格式正确 |
| L4 | `test_unlock_badge_clears_achieved_at` | 锁定时清除 `achieved_at` | `resp.json['achieved_at'] is None` |
| L5 | `test_unlock_badge_nonexistent_id` | 对不存在的 ID 操作 | `resp.status_code == 404` |
| L6 | `test_unlock_badge_creates_stats_if_missing` | badge 无 stats 记录时解锁 | 自动创建 `achievement_stats` 记录；`achieved = 'Y'` |
| L7 | `test_unlock_badge_reflected_in_wall` | 解锁后查询 `/` 页面 | badge 显示为已解锁状态（通过解析 `data_json` 验证） |

### 3.7 图片上传测试 (POST /api/admin/badge/<id>/image)

| # | 测试函数名 | 描述 | 断言 |
|---|-----------|------|------|
| I1 | `test_upload_valid_png` | 上传合法 PNG 文件 | `resp.status_code == 200`；`resp.json['badge_url']` 不为空；文件存在于 `static/badges/` |
| I2 | `test_upload_invalid_file_type` | 上传 .txt 文件 | `resp.status_code == 400`；`resp.json['error']` 包含 'file type' 或 'image' |
| I3 | `test_upload_oversized_file` | 上传超过大小限制的文件（>5MB） | `resp.status_code == 413` 或 `400` |
| I4 | `test_upload_empty_file` | 上传 0 字节文件 | `resp.status_code == 400` |
| I5 | `test_upload_nonexistent_badge` | 对不存在的 badge ID 上传 | `resp.status_code == 404` |
| I6 | `test_upload_creates_badge_record` | 上传后 `achievement_badges` 表有新记录 | `SELECT * FROM achievement_badges WHERE achievement_id = ? AND is_current = 1` 返回 1 行 |
| I7 | `test_upload_replaces_old_image` | 上传两次，旧图片被标记为非 current | 第一次上传的 `is_current = 0`；第二次上传的 `is_current = 1` |
| I8 | `test_upload_generates_unique_filename` | 上传两次同名文件 | 两个文件路径不同，不互相覆盖 |
| I9 | `test_upload_jpg_allowed` | 上传 .jpg 文件 | `resp.status_code == 200`（如果允许 JPG）或 `400`（如果不允许） |

---

## 4. Phase 2 测试用例 — AI Badge 生成管线

### 4.1 Draft 创建测试 (POST /api/admin/badge/draft)

| # | 测试函数名 | 描述 | 断言 |
|---|-----------|------|------|
| DR1 | `test_create_draft_valid_meta` | 提交完整 draft metadata（name, category, description, rarity） | `resp.status_code == 201`；返回 `draft_id`；draft 数据存入内存/临时存储 |
| DR2 | `test_create_draft_missing_name` | 缺少 name | `resp.status_code == 400` |
| DR3 | `test_create_draft_missing_category` | 缺少 category | `resp.status_code == 400` |
| DR4 | `test_create_draft_auto_generates_id` | 不传 id，自动生成 | 返回的 `id` 不为空；格式符合 `ai_<timestamp>` 或 UUID |
| DR5 | `test_create_draft_idempotent` | 相同参数创建两次 | 返回不同的 `draft_id`（或第二次返回 409，取决于设计） |

### 4.2 图片生成测试 (POST /api/admin/badge/draft/<draft_id>/generate)

| # | 测试函数名 | 描述 | 断言 |
|---|-----------|------|------|
| G1 | `test_generate_image_success` | Mock hermes/FAL 响应，返回有效图片 URL | `resp.status_code == 200`；`resp.json['image_url']` 不为空 |
| G2 | `test_generate_image_service_error` | Mock hermes 返回 500 | `resp.status_code == 502` 或 `500`；`resp.json['error']` 包含 'generation failed' |
| G3 | `test_generate_image_timeout` | Mock hermes 超时 | `resp.status_code == 504`；不阻塞请求 |
| G4 | `test_generate_image_saves_preview` | 成功生成后图片保存到临时目录 | `os.path.exists(preview_path)` 为 True |
| G5 | `test_generate_image_invalid_draft` | 对不存在的 draft_id 操作 | `resp.status_code == 404` |
| G6 | `test_generate_image_prompt_construction` | 检查发送给 hermes 的 prompt 包含 badge 元数据 | Mock 的 `generate` 方法被调用时，参数包含 name, category, description |

### 4.3 背景移除测试 (POST /api/admin/badge/draft/<draft_id>/remove-bg)

| # | 测试函数名 | 描述 | 断言 |
|---|-----------|------|------|
| RB1 | `test_remove_bg_pil_threshold` | 使用 PIL 阈值法移除白色背景 | 输出图片有透明通道（`mode == 'RGBA'`）；白色像素变为透明 |
| RB2 | `test_remove_bg_rembg_fallback` | Mock PIL 失败，fallback 到 rembg | `resp.status_code == 200`；返回处理后的图片路径 |
| RB3 | `test_remove_bg_already_transparent` | 输入已是 RGBA 的图片 | 不报错；输出仍为 RGBA |
| RB4 | `test_remove_bg_invalid_draft` | 对不存在的 draft 操作 | `resp.status_code == 404` |
| RB5 | `test_remove_bg_no_image_yet` | draft 还没生成图片就移除背景 | `resp.status_code == 400`；error 提示先生成图片 |

### 4.4 Commit 测试 (POST /api/admin/badge/draft/<draft_id>/commit)

| # | 测试函数名 | 描述 | 断言 |
|---|-----------|------|------|
| CM1 | `test_commit_draft_to_db` | 将 draft 写入 `achievements` 表 | `SELECT * FROM achievements WHERE id = ?` 返回 1 行；字段值与 draft 一致 |
| CM2 | `test_commit_updates_stats` | commit 后 `achievement_stats` 有对应记录 | `SELECT * FROM achievement_stats WHERE achievement_id = ?` 返回 1 行 |
| CM3 | `test_commit_saves_image` | 图片从 draft 临时目录移到 `static/badges/` | `os.path.exists(final_path)` 为 True；临时文件已清理 |
| CM4 | `test_commit_increases_total_count` | commit 后 `/api/badges` 的 total +1 | `resp_after.json['total'] == resp_before.json['total'] + 1` |
| CM5 | `test_commit_invalid_draft` | 对不存在的 draft commit | `resp.status_code == 404` |
| CM6 | `test_commit_incomplete_draft` | draft 缺少图片时 commit | `resp.status_code == 400`；error 提示缺少图片 |
| CM7 | `test_commit_cleans_up_draft` | commit 后 draft 数据被清除 | 再次查询 draft 返回 404 |
| CM8 | `test_commit_duplicate_id` | draft 的 id 与已有 badge 冲突 | `resp.status_code == 409` |

---

## 5. 测试 Fixtures 定义

### 5.1 conftest.py 核心 fixtures

```python
import pytest
import sqlite3
import os
import io
from PIL import Image
from app import app as flask_app

@pytest.fixture
def app(tmp_path):
    """创建测试用 Flask 应用，使用临时 SQLite 数据库"""
    db_path = tmp_path / "test_yoachi.db"
    flask_app.config['DATABASE_PATH'] = str(db_path)
    flask_app.config['TESTING'] = True

    # 建表
    conn = sqlite3.connect(str(db_path))
    conn.executescript(open('schema.sql').read())
    conn.executescript(open('migrations/add_admin_fields.sql').read())
    conn.commit()
    conn.close()

    yield flask_app

@pytest.fixture
def client(app):
    """Flask 测试客户端"""
    return app.test_client()

@pytest.fixture
def db(app):
    """获取测试数据库连接"""
    conn = sqlite3.connect(app.config['DATABASE_PATH'])
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()

@pytest.fixture
def seed_categories(db):
    """填充默认分类数据"""
    categories = [
        ('li', '礼', '待人接物', 1),
        ('yue', '乐', '艺术修养', 2),
        ('she', '射', '体能运动', 3),
        ('yu', '御', '生活技能', 4),
        ('shu', '书', '读写能力', 5),
        ('shu2', '数', '数学能力', 6),
        ('ying', '英', '英语能力', 7),
    ]
    db.executemany(
        "INSERT OR IGNORE INTO categories VALUES (?, ?, ?, ?)",
        categories
    )
    db.commit()

@pytest.fixture
def sample_badge(db, seed_categories):
    """创建一个示例 badge"""
    db.execute("""
        INSERT INTO achievements (id, name, type, category, stat_logic, description,
            display_format, threshold, sort_order)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, ('test_badge_1', '测试徽章', 'counter', 'li',
          'count > 10', '测试描述', 'text', 10, 1))
    db.commit()
    return 'test_badge_1'

@pytest.fixture
def sample_badges_batch(db, seed_categories):
    """批量创建 25 个 badge 用于分页测试"""
    for i in range(25):
        db.execute("""
            INSERT INTO achievements (id, name, type, category, stat_logic, description,
                display_format, threshold, sort_order)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (f'batch_badge_{i:03d}', f'批量徽章{i}', 'counter', 'li',
              'count > 10', f'描述{i}', 'text', 10, i))
    db.commit()

@pytest.fixture
def valid_png_bytes():
    """生成一个合法的 128x128 PNG 图片字节流"""
    img = Image.new('RGBA', (128, 128), (255, 100, 100, 255))
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return buf

@pytest.fixture
def large_png_bytes():
    """生成一个超大 PNG 图片（模拟 >5MB）"""
    img = Image.new('RGBA', (4000, 4000), (0, 0, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return buf

@pytest.fixture
def white_bg_png_bytes():
    """生成一个白色背景的 RGB 图片，用于测试背景移除"""
    img = Image.new('RGB', (128, 128), (255, 255, 255))
    # 在中间放一个红色方块
    for x in range(32, 96):
        for y in range(32, 96):
            img.putpixel((x, y), (255, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return buf
```

### 5.2 Mock 数据

```python
# tests/fixtures/sample_data.json
{
  "achievements": [
    {
      "id": "reading_100",
      "name": "阅读百本书",
      "type": "counter",
      "category": "shu",
      "stat_logic": "count >= 100",
      "description": "累计阅读100本书",
      "display_format": "text",
      "threshold": 100,
      "sort_order": 1,
      "rarity": "legendary",
      "is_manual": 0
    },
    {
      "id": "manners_master",
      "name": "礼仪之星",
      "type": "manual",
      "category": "li",
      "stat_logic": "manual",
      "description": "在礼仪方面表现突出",
      "display_format": "badge",
      "threshold": null,
      "sort_order": 2,
      "rarity": "rare",
      "is_manual": 1
    }
  ]
}
```

---

## 6. 端到端集成测试

### 6.1 完整 Badge 生命周期

```python
class TestBadgeLifecycle:
    """端到端：创建 → 上传图片 → 解锁 → 在 wall 展示"""

    def test_full_lifecycle(self, client, seed_categories):
        """完整 badge 生命周期"""
        # 1. 创建 badge
        resp = client.post('/api/admin/badge', json={
            'id': 'e2e_test_badge',
            'name': '端到端测试',
            'type': 'manual',
            'category': 'li',
            'stat_logic': 'manual',
            'description': '端到端测试徽章',
            'display_format': 'badge',
            'rarity': 'common'
        })
        assert resp.status_code == 201

        # 2. 上传图片
        resp = client.post('/api/admin/badge/e2e_test_badge/image',
            data={'image': (io.BytesIO(b'fake png data'), 'test.png')},
            content_type='multipart/form-data')
        assert resp.status_code == 200
        badge_url = resp.json['badge_url']

        # 3. 手动解锁
        resp = client.post('/api/admin/badge/e2e_test_badge/unlock')
        assert resp.status_code == 200
        assert resp.json['achieved'] is True

        # 4. 在 public API 中可见
        resp = client.get('/api/badges')
        badge = next(b for b in resp.json['badges'] if b['id'] == 'e2e_test_badge')
        assert badge['achieved'] is True
        assert badge['badge_url'] == badge_url

        # 5. 在 wall 页面中渲染
        resp = client.get('/')
        assert resp.status_code == 200
        assert 'e2e_test_badge' in resp.data.decode()

        # 6. 删除 badge
        resp = client.delete('/api/admin/badge/e2e_test_badge')
        assert resp.status_code == 200

        # 7. 从 public API 消失
        resp = client.get('/api/badges')
        ids = [b['id'] for b in resp.json['badges']]
        assert 'e2e_test_badge' not in ids
```

### 6.2 Sync + Admin 交互测试

```python
class TestSyncAdminInteraction:
    """测试同步和 admin 修改的交互"""

    def test_admin_changes_survive_sync(self, client, db, tmp_path):
        """admin 修改不被同步覆盖（或正确合并）"""
        # 创建 admin badge
        client.post('/api/admin/badge', json={...})

        # 模拟同步
        # ... 触发 sync_once ...

        # 验证 admin badge 仍然存在（如果使用独立表）
        # 或验证 admin badge 被标记为 manual（如果共享表）
        resp = client.get('/api/badges')
        # 具体断言取决于同步策略
```

---

## 7. 回归测试

### 7.1 现有功能回归

| # | 测试函数名 | 描述 | 断言 |
|---|-----------|------|------|
| R1 | `test_regression_badge_wall_200` | GET `/` 返回 200 | `resp.status_code == 200`；包含 `badge_wall.html` 模板内容 |
| R2 | `test_regression_api_badges_format` | `/api/badges` 返回格式不变 | `resp.json` 包含 `badges`, `total`, `achieved` 键 |
| R3 | `test_regression_api_badges_detail_format` | `/api/badges/<id>` 返回格式不变 | `resp.json` 包含 `id`, `name`, `type`, `category`, `achieved` 等键 |
| R4 | `test_regression_api_categories_format` | `/api/categories` 返回格式不变 | `resp.json` 包含 `categories` 键；每个 category 有 `id`, `name` |
| R5 | `test_regression_category_mapping` | CATEGORY_NAMES 和 CATEGORY_EMOJI 映射不变 | 断言 7 个分类的中英文名和 emoji 正确 |
| R6 | `test_regression_badge_wall_sort_order` | wall 页面排序：已解锁在前，未解锁在后 | 解析 `data_json`，已解锁 badge 的索引 < 未解锁 badge 的索引 |
| R7 | `test_regression_badge_wall_default_image` | 无自定义图片时使用默认图片 | 解析 `data_json`，无图片的 badge `badge_url == '/static/badges/medal_badge.png'` |
| R8 | `test_regression_sync_does_not_break_wall` | 同步后 wall 页面仍正常 | 同步完成后 GET `/` 返回 200 |

---

## 8. CI/CD 考虑

### 8.1 GitHub Actions 配置建议

```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.12', '3.14']
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install -r requirements-dev.txt
      - name: Run tests
        run: |
          pytest tests/ -v --cov=. --cov-report=xml --cov-report=term-missing
      - name: Coverage check
        run: |
          coverage report --fail-under=85
```

### 8.2 requirements-dev.txt

```
pytest>=8.0
pytest-cov>=5.0
pytest-flask>=1.3
Pillow>=10.0
```

### 8.3 CI 检查项

- [ ] 所有测试通过（零失败）
- [ ] 覆盖率 ≥ 85%（阻断性）
- [ ] 无新增 linting 错误
- [ ] 数据库迁移脚本幂等性验证
- [ ] 测试运行时间 < 30 秒（内存数据库）

---

## 9. 各阶段验收标准

### Phase 1 验收标准 (Admin CRUD)

| # | 标准 | 验证方式 |
|---|------|---------|
| P1-1 | 所有 admin API 端点返回正确 HTTP 状态码 | `test_api_admin.py` 全部通过 |
| P1-2 | 创建 badge 后在 public API 和 wall 中可见 | `test_create_badge_appears_in_public_api` 通过 |
| P1-3 | 删除 badge 后图片文件被清理 | `test_delete_badge_with_images` 通过 |
| P1-4 | 手动解锁 toggle 在两种状态间正确切换 | `test_unlock_badge_toggle_on` + `toggle_off` 通过 |
| P1-5 | 图片上传限制有效（类型、大小） | `test_upload_invalid_file_type` + `test_upload_oversized_file` 通过 |
| P1-6 | 数据库迁移幂等，不破坏已有数据 | `test_migration_idempotent` + `test_migration_preserves_data` 通过 |
| P1-7 | 现有 badge wall 功能无回归 | `test_regression_*` 全部通过 |
| P1-8 | 覆盖率 ≥ 90%（admin 模块） | `pytest --cov=admin` 报告 |
| P1-9 | 无测试失败，CI 绿灯 | GitHub Actions 通过 |

### Phase 2 验收标准 (AI Badge 生成)

| # | 标准 | 验证方式 |
|---|------|---------|
| P2-1 | Draft 创建和管理正常 | `test_create_draft_*` 全部通过 |
| P2-2 | 图片生成 mock 测试通过（hermes 响应正确处理） | `test_generate_image_*` 全部通过 |
| P2-3 | 背景移除 PIL 阈值法和 rembg fallback 均工作 | `test_remove_bg_*` 全部通过 |
| P2-4 | Commit 将 draft 写入正式表，统计数据正确更新 | `test_commit_*` 全部通过 |
| P2-5 | 完整 AI 生成管线端到端通过 | `test_full_ai_generation_lifecycle` 通过 |
| P2-6 | 错误处理覆盖所有失败路径（服务超时、无效输入等） | 所有 error case 测试通过 |
| P2-7 | Phase 1 所有回归测试仍然通过 | `test_regression_*` 全部通过 |
| P2-8 | 覆盖率 ≥ 90%（生成管线模块） | `pytest --cov=admin_generator` 报告 |

---

## 附录：现有项目结构参考

```
yoachi/
├── app.py              # 主应用（路由、sync 初始化）
├── config.py           # 配置类
├── schema.sql          # 数据库 schema
├── data/
│   └── yoachi.db       # SQLite 数据库
├── scripts/
│   └── init_db.py      # 数据库初始化脚本
├── sync/
│   ├── __init__.py
│   └── manager.py      # 同步管理器
├── static/             # 静态资源
├── templates/
│   ├── base.html
│   └── badge_wall.html
└── tests/              # 待创建
```

### 现有 API 端点

| 路由 | 方法 | 用途 |
|------|------|------|
| `/` | GET | Badge Wall 页面 |
| `/api/badges` | GET | 所有 badge JSON |
| `/api/badges/<id>` | GET | 单个 badge 详情 |
| `/api/categories` | GET | 分类列表 |

### 计划新增 Admin 端点

| 路由 | 方法 | 用途 |
|------|------|------|
| `/admin` | GET | Admin 面板页面 |
| `/admin/badge/new` | GET | 新建 badge 表单 |
| `/admin/badge/<id>/edit` | GET | 编辑 badge 表单 |
| `/api/admin/badges` | GET | Admin badge 列表（含分页/筛选） |
| `/api/admin/badge` | POST | 创建 badge |
| `/api/admin/badge/<id>` | PUT | 更新 badge |
| `/api/admin/badge/<id>` | DELETE | 删除 badge |
| `/api/admin/badge/<id>/unlock` | POST | 手动解锁/锁定 |
| `/api/admin/badge/<id>/image` | POST | 上传图片 |
| `/api/admin/badge/draft` | POST | 创建 draft (Phase 2) |
| `/api/admin/badge/draft/<id>/generate` | POST | AI 生成图片 (Phase 2) |
| `/api/admin/badge/draft/<id>/remove-bg` | POST | 背景移除 (Phase 2) |
| `/api/admin/badge/draft/<id>/commit` | POST | Draft 提交 (Phase 2) |
