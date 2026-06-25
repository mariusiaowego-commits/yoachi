---
date: 2026-06-25
doc_type:
  - mrd
tags:
  - yoachi
  - admin
  - badge
  - achievement
project:
  - yoachi
is_done: false
---

# Yoachi Admin Backend — 产品需求文档 v1.0

## 1. 背景与上下文

### 1.1 Yoachi 是什么

Yoachi（呦呦终身成就体系）是给 8 岁女儿打造的多分类成就系统。灵感源自《周礼》六艺，分为七个类别：

| 分类 ID | 中文 | 领域 |
|---------|------|------|
| li | 礼 | 待人接物、社会规范 |
| yue | 乐 | 艺术修养、竹笛（继承自 dizical） |
| she | 射 | 体能、运动 |
| yu | 御 | 生活技能、独立能力 |
| shu | 书 | 读写、阅读 |
| shu2 | 数 | 数学、逻辑 |
| ying | 英 | 英语能力 |

### 1.2 当前状态

- **已上线**：勋章墙页面（dizicute 设计系统，GSAP modal 动效）
- **已同步**：39 个「乐」分类勋章从 dizical 定时同步（5 分钟轮询）
- **技术栈**：Python 3.14 + Flask + SQLite + Alpine.js，端口 5001，Tailscale 访问
- **现有表**：`achievements`、`achievement_stats`、`achievement_badges`、`categories`
- **缺失**：无管理后台，所有勋章管理依赖直接操作数据库或 dizical 工作流

### 1.3 为什么需要 Admin

1. 除「乐」外的六个分类没有 dizical 工作流支持，需要独立的内容管理入口
2. 勋章 CRUD（创建、编辑、删除）目前无法通过 UI 完成
3. 家长需要手动控制勋章解锁状态（`unlock_strategy=manual`）
4. 稀有度系统上线后，每个勋章需管理多张图片（按稀有度分级）
5. 未来前端页面需要模块化配置能力

---

## 2. 目标与成功指标

### 2.1 核心目标

为家长提供一个 iPad/Mac 可用的 Web 管理后台，实现勋章全生命周期管理。

### 2.2 成功指标

| 指标 | 目标 |
|------|------|
| 勋章创建耗时 | < 2 分钟（不含生图） |
| 手动解锁操作 | 1 次点击完成状态翻转 |
| 图片上传成功率 | > 95% |
| 分类覆盖率 | 7/7 分类均可独立管理勋章 |
| iPad Safari 可用性 | 所有核心操作可完成 |

---

## 3. 用户画像

### 3.1 管理员：家长（爸爸）

- **场景**：Mac Chrome 或 iPad Safari 上操作
- **需求**：快速录入勋章、编辑描述、上传图片、手动翻转解锁状态
- **约束**：时间有限，操作要简洁；通过 Tailscale 远程访问
- **认证**：简单 PIN 码（localStorage 存储，参考 dizical V1.1 模式）

### 3.2 查看者：女儿（8 岁）

- **场景**：iPad Safari 浏览勋章墙
- **需求**：查看勋章、观看解锁动画、阅读勋章故事
- **约束**：字号大、交互简单、色彩明快
- **权限**：只读，不接触 admin 路由

---

## 4. 功能需求

### Phase 1：勋章内容管理（核心，优先级最高）

#### 4.1 勋章 CRUD

**路由**：`/admin`（管理后台入口）

**勋章字段定义**（扩展 `achievements` 表）：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | TEXT PK | 自动生成 | 格式：`{category}_{slug}`，如 `she_first_run` |
| name | TEXT | ✅ | 勋章名称，如「初次奔跑」 |
| category | TEXT | ✅ | 枚举：`li/yue/she/yu/shu/shu2/ying` |
| type | TEXT | ✅ | 枚举：`breakthrough/peak/persist/grade/level_up/mystery`（突破/巅峰/执着/段位/晋级/神秘） |
| rarity | TEXT | ✅ | 枚举：`common/rare/epic/legendary`，默认 `common` |
| cond_text | TEXT | ✅ | 解锁条件描述，如「连续跑步 7 天」 |
| unlock_strategy | TEXT | ✅ | 枚举：`calc/manual/immediate` |
| description | TEXT | ❌ | 典故/故事（展示在 modal 中） |
| display_format | TEXT | ❌ | 展示格式（继承 dizical） |
| threshold | INTEGER | ❌ | 计算阈值（calc 策略时使用） |
| sort_order | INTEGER | 自动 | 同分类内排序 |
| display_on_achievements | INTEGER | ✅ | 1=展示, 0=隐藏，默认 1 |
| created_at | DATETIME | 自动 | 创建时间 |
| updated_at | DATETIME | 自动 | 最后修改时间（**新增字段**） |

**新增字段**（需 ALTER TABLE）：

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| rarity | TEXT | `'common'` | 稀有度等级 |
| updated_at | DATETIME | `CURRENT_TIMESTAMP` | 最后更新时间 |
| draft_status | TEXT | `'committed'` | 草稿状态：`draft/committed` |

**操作**：

- **创建**：表单填写 → 生成 ID → 写入 `achievements` 表 → 自动创建 `achievement_stats` 记录（achieved='N'）
- **编辑**：列表筛选 → 点击进入编辑表单 → 保存
- **删除**：软删除（`display_on_achievements=0`），不物理删除
- **排序**：拖拽调整 `sort_order`，同分类内排序

#### 4.2 稀有度系统

**四档稀有度**：

| 稀有度 | 标识 | 视觉风格 |
|--------|------|----------|
| Common | 普通 | 基础样式 |
| Rare | 稀有 | 边框光效 |
| Epic | 史诗 | 动态光效 + 粒子 |
| Legendary | 传说 | 全屏特效 + 音效（预留） |

**多稀有度图片管理**：一个勋章可有多张图片，每张绑定一个稀有度等级。

#### 4.3 图片管理

**存储路径**：`static/badges/{category}/{badge_id}_{rarity}.png`

**上传流程**：
1. 管理端选择勋章 → 点击「上传图片」
2. 选择稀有度等级
3. 上传 PNG/WebP（最大 2MB）
4. 后端保存到 `static/badges/` 并写入 `badge_images` 表
5. 支持设置「当前使用」版本

**图片规格**：
- 格式：PNG（透明背景）或 WebP
- 尺寸：建议 512×512px
- 背景：透明（去背后）

#### 4.4 手动解锁

**场景**：`unlock_strategy=manual` 或 `immediate` 的勋章

**操作**：
1. 管理端勋章列表显示当前解锁状态（✅ 已解锁 / ⬜ 未解锁）
2. 点击状态图标 → 翻转 `achievement_stats.achieved`（Y↔N）
3. 解锁时自动写入 `achieved_at` 为当前时间
4. `immediate` 策略：创建即标记为已解锁

**API**：

```
POST /admin/api/badges/<id>/toggle-unlock
→ { achieved: true/false, achieved_at: "2026-06-25T10:00:00" }
```

---

### Phase 2：勋章设计工作流（中优先级）

#### 4.5 从 dizical 复制勋章

**背景**：dizical 保留「乐」分类的勋章设计工作流和展示，yoachi 未来承接其余分类。

**分工**：
- **dizical**：只生成「乐」分类勋章（竹笛相关），生成后 artifacts 同步到 yoachi
- **yoachi**：管理所有分类勋章 + 独立的设计工作流（其余 6 个分类）

**复制操作**：
1. admin 页面提供「从 dizical 导入」按钮
2. 读取 dizical SQLite 中的 `achievements` 表
3. 映射字段 → 写入 yoachi `achievements` 表（`category='yue'`）
4. 复制关联图片到 `static/badges/yue/`
5. 写入 `badge_images` 表

#### 4.6 勋章设计流水线（5 步）

复用 dizical V2.1 工作流架构，适配 yoachi：

| 步骤 | 操作 | 产出 |
|------|------|------|
| Step 1 | 表单填写元数据 | `data/lib/badge_data/{draft_id}.json` |
| Step 2 | AI 生成描述（cond_text + description） | 更新 draft JSON |
| Step 3 | AI 生图（enamel pin prompt） | 原始 PNG |
| Step 4 | PIL + rembg 去背 | 透明背景 PNG |
| Step 5 | 确认提交 | 写入三表 + 图片落盘 |

**Draft JSON schema**（`schema_version=2`）：

```json
{
  "schema_version": 2,
  "draft_id": "she_first_run_20260625",
  "source": "yoachi",
  "status": "draft|image_ready|committed",
  "meta": {
    "name": "初次奔跑",
    "category": "she",
    "type": "breakthrough",
    "rarity": "common",
    "cond_text": "完成第一次 1km 跑步",
    "description": "千里之行，始于足下。",
    "unlock_strategy": "manual"
  },
  "image": {
    "raw_path": "static/badges/_drafts/raw.png",
    "processed_path": "static/badges/_drafts/processed.png",
    "final_url": null
  },
  "created_at": "2026-06-25T10:00:00"
}
```

**路由**（admin 子路由）：

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/admin/api/badge/draft` | Step 1: 创建 draft |
| GET | `/admin/api/badge/draft/<id>` | Step 2: 读 draft（供 skill 调用） |
| POST | `/admin/api/badge/generate-image` | Step 3: 触发 AI 生图 |
| POST | `/admin/api/badge/remove-bg` | Step 4: 去背处理 |
| POST | `/admin/api/badge/commit` | Step 5: 确认提交写 DB |
| GET | `/admin/api/badge/drafts` | 列出所有 draft 状态的勋章 |

---

### Phase 3：前端页面构建器（低优先级，最后做）

#### 4.7 模块化页面区块

**概念**：勋章墙页面由可配置的「区块」(block) 组成，管理员可调整布局。

**区块类型**：

| Block Type | 说明 | 配置项 |
|------------|------|--------|
| `hero_banner` | 顶部大图 | 图片URL, 标题, 副标题 |
| `category_grid` | 分类网格 | 排序, 显示/隐藏 |
| `badge_wall` | 勋章墙 | 分类筛选, 排序方式, 每行数量 |
| `timeline` | 时间线视图 | 时间范围, 分类筛选 |
| `stats_card` | 统计卡片 | 总勋章数, 解锁率 |
| `story_section` | 故事区块 | 标题, 富文本内容 |

**数据表**：`page_sections`

**操作**：
- 拖拽排序区块
- 每个区块独立配置
- 实时预览（iframe 或 Alpine.js 即时渲染）

---

## 5. 数据模型

### 5.1 achievements 表扩展（ALTER TABLE）

```sql
ALTER TABLE achievements ADD COLUMN rarity TEXT NOT NULL DEFAULT 'common';
ALTER TABLE achievements ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE achievements ADD COLUMN draft_status TEXT DEFAULT 'committed';
CREATE INDEX IF NOT EXISTS idx_achievements_rarity ON achievements(rarity);
```

### 5.2 badge_images 表（新增）

```sql
CREATE TABLE IF NOT EXISTS badge_images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    achievement_id TEXT NOT NULL,
    rarity TEXT NOT NULL DEFAULT 'common',
    url TEXT NOT NULL,
    file_path TEXT,
    file_size INTEGER,
    width INTEGER,
    height INTEGER,
    is_current INTEGER NOT NULL DEFAULT 0,
    version INTEGER NOT NULL DEFAULT 1,
    source TEXT DEFAULT 'upload',       -- 'upload' | 'ai_gen' | 'dizical_sync'
    draft_id TEXT,                       -- 关联的 draft ID
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (achievement_id) REFERENCES achievements(id)
);

CREATE INDEX IF NOT EXISTS idx_badge_images_achievement ON badge_images(achievement_id);
CREATE INDEX IF NOT EXISTS idx_badge_images_rarity ON badge_images(rarity);
CREATE INDEX IF NOT EXISTS idx_badge_images_current ON badge_images(is_current);
```

**说明**：
- 一个 achievement 可有多条 badge_images 记录（按 rarity 分）
- `is_current=1` 标记当前使用的版本
- `source` 区分图片来源：手动上传 / AI 生成 / dizical 同步

### 5.3 page_sections 表（Phase 3，预留）

```sql
CREATE TABLE IF NOT EXISTS page_sections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    page TEXT NOT NULL DEFAULT 'home',   -- 页面标识
    section_type TEXT NOT NULL,          -- hero_banner/category_grid/badge_wall/...
    config TEXT NOT NULL DEFAULT '{}',   -- JSON 配置
    sort_order INTEGER DEFAULT 0,
    visible INTEGER DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_page_sections_page ON page_sections(page);
```

### 5.4 关系图

```
achievements (1) ──── (N) badge_images
     │
     └── (1) achievement_stats (1:1)
     
categories (1) ──── (N) achievements

page_sections (独立，配置驱动)
```

---

## 6. 非功能性需求

### 6.1 兼容性

| 环境 | 要求 |
|------|------|
| iPad Safari 16+ | 所有管理操作可用，触摸友好 |
| Mac Chrome 120+ | 主要开发/管理浏览器 |
| 响应式 | 管理端 ≥ 768px 适配（iPad 横屏） |
| 前端框架 | Alpine.js（零构建），管理端可用少量 Vanilla JS |

### 6.2 网络

- Tailscale 内网访问，端口 5001
- 不需要公网 HTTPS（Tailscale 自带加密）
- API 不做 rate limiting（家庭内部使用）

### 6.3 数据安全

- **认证**：PIN 码验证（4-6 位数字），存 localStorage
- **备份**：SQLite 文件纳入 Git 版本控制
- **图片备份**：`static/badges/` 目录纳入 Git
- **自动备份**：每次 sync 前自动备份 `data/yoachi.db` → `data/backups/yoachi_{date}.db`

### 6.4 性能

| 指标 | 目标 |
|------|------|
| 页面加载 | < 2s（iPad Safari） |
| API 响应 | < 500ms |
| 图片上传 | < 5s（2MB 文件） |
| DB 大小 | 预计 < 100MB（含图片路径，不含图片本体） |

### 6.5 代码规范

- 沿用 dizical 风格：Python type hints、docstring、日志
- 管理路由独立 blueprint：`routes/admin.py`
- 与展示路由（`app.py`）分离

---

## 7. 不在范围内

以下功能明确排除在本版本之外：

| 功能 | 理由 | 计划版本 |
|------|------|----------|
| 稀有度专属动画效果 | 需大量动效设计 | v2.0 |
| Push 通知 | 需要公网服务 | v2.0+ |
| 微信小程序 | 需要额外技术栈 | v3.0 |
| 勋章获取旅程动画（捧起辛巴效果） | 需要 Lottie/Rive 动效 | v2.0 |
| 多用户/多孩子 | 当前只有 1 个用户 | 未来按需 |
| 自动解锁（calc 计算逻辑） | 每个分类逻辑不同，暂不泛化 | 各分类独立迭代 |
| 国际化 | 仅中文 | 不计划 |

---

## 8. 开放问题

| # | 问题 | 状态 | 备注 |
|---|------|------|------|
| 1 | PIN 认证是否足够？是否需要更复杂的权限？ | 待定 | 当前只有 1 个管理员，PIN 应足够 |
| 2 | 图片存储是否需要独立于 Git？ | 待定 | 图片多了 Git 仓库会膨胀，考虑 .gitignore + 手动备份 |
| 3 | 稀有度命名方案（周礼风格）最终定案 | 待定 | MRD 提到需 research 盲盒稀有度分级 |
| 4 | dizical 同步到 yoachi 的触发方式？自动还是手动？ | 待定 | 当前 5 分钟轮询，admin 是否需要手动触发？ |
| 5 | draft 文件存放在 `data/lib/badge_data/` 还是 `data/drafts/`？ | 待定 | 复用 dizical 路径还是自定义 |
| 6 | admin 路由是否需要独立 Flask blueprint？ | 建议是 | 与展示路由解耦 |
| 7 | `achievement_badges` 表与新的 `badge_images` 表如何共存？ | 需决策 | 方案 A：废弃旧表，全用 badge_images；方案 B：两表并存，旧表给乐分类 |
| 8 | AI 生图 prompt 模板是否需要按分类差异化？ | 待定 | 当前 dizical 只有竹笛 prompt |

---

## 9. 里程碑规划

| 阶段 | 范围 | 预估工作量 |
|------|------|-----------|
| **M1: Admin 基础** | 路由框架 + PIN 认证 + 勋章列表页 | 1-2 天 |
| **M2: CRUD** | 勋章创建/编辑/删除表单 + 稀有度字段 | 2-3 天 |
| **M3: 图片管理** | 上传 + badge_images 表 + 版本管理 | 1-2 天 |
| **M4: 手动解锁** | 状态翻转 API + UI | 0.5 天 |
| **M5: dizical 导入** | 从 dizical 复制勋章 + 图片 | 1 天 |
| **M6: 设计工作流** | Draft pipeline + AI 生图集成 | 3-5 天 |
| **M7: 页面构建器** | Block 系统 + 拖拽排序 | 5-7 天 |

---

## 附录 A：与 dizical 的关系

```
dizical (竹笛练习管理)
  ├── 练习数据 → calc 解锁逻辑
  ├── 「乐」勋章设计工作流 → 生成 artifacts
  └── 同步 → yoachi (5分钟轮询)

yoachi (终身成就体系)
  ├── 接收 dizical「乐」勋章
  ├── 独立管理其余 6 个分类
  ├── 独立设计工作流（其余分类）
  └── 统一勋章墙展示
```

## 附录 B：API 端点汇总（Phase 1）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/admin/` | 管理后台首页 |
| GET | `/admin/api/badges` | 勋章列表（含筛选、分页） |
| POST | `/admin/api/badges` | 创建勋章 |
| GET | `/admin/api/badges/<id>` | 勋章详情 |
| PUT | `/admin/api/badges/<id>` | 编辑勋章 |
| DELETE | `/admin/api/badges/<id>` | 软删除勋章 |
| POST | `/admin/api/badges/<id>/toggle-unlock` | 翻转解锁状态 |
| POST | `/admin/api/badges/<id>/images` | 上传图片 |
| GET | `/admin/api/badges/<id>/images` | 获取图片列表 |
| PUT | `/admin/api/badges/<id>/images/<img_id>/current` | 设为当前版本 |
| GET | `/admin/api/categories` | 分类列表 |
| POST | `/admin/api/auth/verify` | PIN 验证 |
