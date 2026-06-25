# Yoachi Admin 后台 Plan (v1.1)

> 2026-06-25 | 基于用户需求 + dizical badge-image-workflow.md + badge-image skill

---

## 背景

yoachi MVP 已上线：dizicute 风格勋章墙 + GSAP modal + 39 个"乐"分类 badge 从 dizical 同步。
现在需要后台管理能力，分 3 块逐步建设。

---

## Phase 1: Badge 内容管理后台

### 目标
管理 badge 的元数据：名称、分类、稀有度、解锁条件、是否解锁、典故、图片资源。

### 数据模型扩展

当前 `achievements` 表缺字段，需 migration：

```sql
-- 新增字段
ALTER TABLE achievements ADD COLUMN rarity TEXT DEFAULT 'common';       -- common/rare/epic/legendary
ALTER TABLE achievements ADD COLUMN cond_text TEXT;                      -- 条件文案
ALTER TABLE achievements ADD COLUMN unlock_strategy TEXT DEFAULT 'calc'; -- calc/manual/immediate
ALTER TABLE achievements ADD COLUMN sort_order INTEGER DEFAULT 0;

-- rarity 图片资源表
CREATE TABLE IF NOT EXISTS badge_images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    achievement_id TEXT NOT NULL,
    rarity TEXT NOT NULL,           -- common/rare/epic/legendary/locked
    url TEXT NOT NULL,
    version INTEGER DEFAULT 1,
    is_current INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (achievement_id) REFERENCES achievements(id)
);
```

### 路由设计

| 路由 | 方法 | 说明 |
|------|------|------|
| `/admin` | GET | 管理后台首页 (badge 列表) |
| `/admin/badge/new` | GET | 新建 badge 表单 |
| `/admin/badge/<id>/edit` | GET | 编辑 badge 表单 |
| `/api/admin/badges` | GET | JSON: 全部 badge 列表 |
| `/api/admin/badge` | POST | 创建 badge |
| `/api/admin/badge/<id>` | PUT | 更新 badge |
| `/api/admin/badge/<id>` | DELETE | 删除 badge |
| `/api/admin/badge/<id>/unlock` | POST | 手动解锁/锁定 |
| `/api/admin/badge/<id>/image` | POST | 上传图片 |

### 表单字段

| 字段 | 必填 | 类型 | 说明 |
|------|------|------|------|
| id | ✓ | str | 唯一 ID (英文/数字/下划线) |
| name | ✓ | str | 中文名 |
| category | ✓ | select | 礼/乐/射/御/书/数/英 |
| type | ✓ | select | 突破/巅峰/执着/段位/晋级/神秘 |
| rarity | ✓ | select | common/rare/epic/legendary |
| description | ✓ | textarea | 典故故事 (modal-desc) |
| cond_text | - | str | 条件文案 (modal-cond) |
| unlock_strategy | ✓ | select | calc/manual/immediate |
| threshold | - | int | 阈值 (calc 用) |
| achieved | - | checkbox | 是否已解锁 (manual 模式) |
| sort_order | - | int | 排序 |

### 技术栈
- Flask + Jinja2 (复用现有)
- Alpine.js (表单交互，复用现有)
- dizicute 样式 (复用现有 CSS token)
- SQLite (复用现有 DB)

### 文件结构
```
templates/
  admin/
    base.html          -- admin 布局 (侧边栏 + 内容区)
    badge_list.html    -- badge 列表 (表格 + 搜索 + 筛选)
    badge_form.html    -- 新建/编辑表单 (共用)
static/
  css/admin.css        -- admin 专用样式 (dizicute token 基础上扩展)
routes/
  admin.py             -- admin 蓝图 (Flask Blueprint)
```

### 实施步骤

1. **migration**: 加 rarity/cond_text/unlock_strategy/sort_order 字段
2. **routes/admin.py**: Flask Blueprint 注册
3. **templates/admin/**: 列表页 + 表单页
4. **API 端点**: CRUD + 手动解锁
5. **图片上传**: 保存到 static/badges/ + 写 badge_images 表
6. **验证**: curl 全端点 + 浏览器走查

---

## Phase 2: Badge 设计工作流

### 目标
将 dizical 的 badge-image 工作流复制到 yoachi，负责非"乐"分类 badge 的设计生成。
dizical 保留原有工作流继续负责"乐"竹笛 badge。

### dizical 工作流摘要 (从 badge-image-workflow.md)

```
STEP 1 表单填 meta  →  STEP 2 草稿  →  STEP 3 生图  →  STEP 4 去白底  →  STEP 5 commit
/config/badge        /api/badge/draft  /badge-image skill  PIL+rembg       /api/badge/commit
```

关键组件：
- `data/lib/badge_data/{draft_id}.json` — 文件契约
- enamel pin prompt 模板 (V2.3 去白底)
- PIL 阈值 245 + rembg 兜底 (V2.4 双保险)
- hermes image_gen 调用 (Nous Portal)

### 复制策略

| 组件 | 来源 | yoachi 目标 |
|------|------|-------------|
| badge_draft.py | dizical/src/kid_app/ | yoachi/workflow/draft.py |
| badge_generator.py | dizical/src/kid_app/ | yoachi/workflow/generator.py |
| badge-image skill | ~/.hermes/profiles/dizical/skills/ | 新建 yoachi 专用 skill |
| config-badge.html | dizical/src/kid_app/templates/ | yoachi/templates/admin/badge_design.html |
| data/lib/badge_data/ | dizical/data/ | yoachi/data/badge_data/ |

### 分工边界

| 分类 | 设计工作流 | 生图来源 |
|------|-----------|---------|
| 乐 (竹笛) | dizical 保留 | dizical badge-image skill |
| 礼/射/御/书/数/英 | yoachi 新建 | yoachi badge-image skill (复制+改造) |

### 实施步骤

1. **复制核心模块**: badge_draft.py + badge_generator.py → yoachi/workflow/
2. **适配路径**: dizical → yoachi 的数据路径、DB 路径
3. **新建 yoachi badge-image skill**: 基于 dizical 版改造，改 profile 指向
4. **设计表单**: config-badge.html → yoachi/templates/admin/badge_design.html
5. **draft + commit 端点**: /api/admin/badge/draft + /api/admin/badge/commit
6. **验证**: 完整 5 步流程跑通一个非"乐" badge

---

## Phase 3: 前端页面灵活编排 (最后做)

### 目标
像搭积木一样管理前端展示：模块拖拽、布局配置、内容源绑定。

### 初步构想

| 模块类型 | 说明 | 配置项 |
|----------|------|--------|
| badge-wall | 勋章墙 (现有) | 分类筛选、排序方式 |
| badge-carousel | 轮播展示 | 自动播放、展示数量 |
| stats-card | 统计卡片 | 数据源、样式 |
| category-nav | 分类导航 | 显示哪些分类 |
| hero-banner | 顶部横幅 | 图片、文字、链接 |

### 数据模型
```sql
CREATE TABLE page_sections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    page TEXT NOT NULL,           -- 'home', 'badges', etc.
    section_type TEXT NOT NULL,   -- 'badge-wall', 'carousel', etc.
    config JSON,                  -- 模块配置
    sort_order INTEGER DEFAULT 0,
    visible INTEGER DEFAULT 1
);
```

### 实施 (Phase 3 详细 plan 后续出)

---

## 优先级 & 排期

| 阶段 | 范围 | 依赖 | 难度 |
|------|------|------|------|
| **Phase 1.1** | migration + admin 路由骨架 | 无 | ★☆☆ |
| **Phase 1.2** | badge 列表页 + 搜索筛选 | 1.1 | ★★☆ |
| **Phase 1.3** | badge 表单 (新建/编辑) | 1.1 | ★★☆ |
| **Phase 1.4** | 手动解锁 + 图片上传 | 1.3 | ★★☆ |
| **Phase 2.1** | 复制 draft/generator 模块 | 1.1 | ★★☆ |
| **Phase 2.2** | yoachi badge-image skill | 2.1 | ★★★ |
| **Phase 2.3** | 设计表单 + 5 步流程 | 2.2 | ★★★ |
| Phase 3 | 前端编排 | 1+2 完成后 | ★★★★ |

---

## 立即可做 (本次 session)

1. ✅ modal-desc 样式修复 (已完成)
2. → Phase 1.1: migration + admin 路由骨架
3. → Phase 1.2: badge 列表页
