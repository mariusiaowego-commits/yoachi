# Yoachi AGENTS

> 终身成就体系，服务女儿成长记录。

## 项目路径
`/Users/mt16/dev/yoachi`

## 项目定位
从 dizical 项目生长出来的独立项目，做女儿的终身成就体系。竹笛方面的成就和勋章要和 dizical 项目联动，最终由本项目承接 dizical 的成就部分。

## 技术栈
- Python 3.14
- SQLite（本地数据库，定时从 dizical 同步）
- Flask（Web 框架）
- Alpine.js（轻量级前端交互）
- Pillow（图片处理）

## 数据库
- **yoachi.db**: `data/yoachi.db`（主数据库）
- **同步源**: `~/dev/dizical/data/dizi.db`（只读，定时复制）
- **关键表**:
  - `achievements` — 成就定义
  - `achievement_stats` — 成就统计
  - `achievement_badges` — 成就徽章图片
  - `categories` — 分类表（礼乐射御书数英）

## 成就体系分类
从《周礼》中攫取灵感：
- **礼**: 待人接物、社会规范、尊重他人、公共意识
- **乐**: 艺术修养、舞台表现力、情感表达、美感（继承 dizical 竹笛成就）
- **射**: 体能、运动、竞争精神、毅力、身体协调
- **御**: 驾车 / 生活技能 / 独立能力 / 方向感
- **书**: 读写能力、语言表达、阅读量、文化素养
- **数**: 数学能力、逻辑推理、科学思维、问题解决
- **英**: 英语能力，学英语的方面的能力提升

## 解锁模式
- **calc**: 通过计算逻辑判断（如竹笛练习时长、次数等）
- **manual**: 家长手动翻转状态
- **immediate**: 上线即完成（家长设计成就时直接标记为已完成）

## 部署信息
- **端口**: 5001
- **绑定**: `0.0.0.0`（允许 Tailscale 访问）
- **访问入口**:
  - 本机: `http://localhost:5001`
  - Tailscale: `http://100.67.215.121:5001`
- **启动**: `./scripts/start.sh`
- **停止**: `./scripts/stop.sh`

## 数据同步
- **频率**: 每 5 分钟定时同步
- **方式**: 直接复制 dizical 的 SQLite 文件
- **同步内容**: achievements、achievement_stats、achievement_badges
- **注意**: 只同步"乐"分类的数据，其他分类在 yoachi 独立管理

## 前端设计
- **目标用户**: 8 岁儿童
- **设计原则**: 字号大、交互简单、色彩明快
- **UI 框架**: 原生 HTML/CSS + Alpine.js
- **兼容性**: iPad Safari、手机浏览器
- **设计系统**: dizicute 风格（从 dizical 继承）

## MVP 范围（v1.0）
1. **数据同步**: yoachi 和 dizical 都能看到 dizical 项目里的 badge
2. **生图工作流迁移**: 把成就生图工作流从 dizical 迁移到 yoachi
3. **基础勋章墙**: 按分类展示勋章，modal 弹出详情
4. **稀有度系统**: 后续版本单独开发
5. **获取旅程动画**: 后续版本再做

## 业务约束
- **PC 优先**: iPad Safari (landscape) + Mac Safari/Chrome
- **Tailscale 访问**: 不在同一 WiFi 环境下需要 Tailscale
- **数据库备份**: Git 版本控制（数据库文件 + 代码）
- **生图工作流**: 走 Nous Portal Tool Gateway

## Git 工作流
- **分支策略**: main 分支保持稳定，功能开发走 feature branch
- **PR 命名**: `feat(xxx)` / `fix(xxx)` / `docs(xxx)`
- **合并方式**: PR merge（不要直接 push 到 main）
- **版本号格式**: `v1.0.0`（主版本.次版本.补丁版本）
  - 主版本：重大功能变更（如新增分类、稀有度系统）
  - 次版本：功能增强（如新增勋章类型、UI 改进）
  - 补丁版本：bug 修复、小改动
- **Git tag**: 每个版本都打 tag（如 `v1.0.0`）
- **Commit message**: 包含版本号（如 `feat(badge): 新增勋章墙 (v1.0.0)`）
- **STATUS.md**: 记录当前版本状态、进展、修复内容
- **收尾 checklist**:
  - □ 测试通过
  - □ commit + push
  - □ 创建 PR
  - □ merge PR
  - □ 打 tag
  - □ 更新 STATUS.md
  - □ 备份产物

## 收尾 Checklist（每次会话结束前必须执行）
```
□ AGENTS.md — 本次修改涉及的功能，对应条目是否更新
□ Git — 测通后 add → commit → feature branch → PR（未测不推）
□ 测试 — pytest 通过
□ 服务验证 — curl 页面确认 200 OK
□ 用户确认 — 展示最终结果
□ Obsidian 镜像 — 重要文档双写到 Obsidian
```

## 相关项目
- **dizical**: 竹笛课程助手，成就系统来源
- **designrepo**: 设计系统注册中心

## Repo owner
GitHub 账号: `mariusiaowego-commits`

⚠️ **拼写陷阱**: owner 中段是 5 字符 `o-w-e-g-o` (含 w), 容易被打成 4 字符 `u-e-g-o` (少 o 多 u, 漏掉 w)。任何 GH URL/repo/操作必须从本文件原样复制, 不可凭记忆打字。
