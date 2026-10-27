# AI 交接纪要：Group Scheduling Prototype

更新时间：2026-10-26（Asia/Singapore）

## 给接手 AI 的一句话说明

这是一个已经可以本地运行的 Group Scheduling prototype。React 前端、FastAPI/SQLModel 后端、SQLite/PostgreSQL 数据层和独立推荐引擎已整合。当前阶段不是从零开发，而是继续用 3 个演示身份做端到端测试，厘清并修复 prototype 中的边界情况和 UX bug。

## 代码入口

- 项目根目录：本文件所在目录。
- 前端：`frontend/`（React、TypeScript、Vite、TanStack Query）。
- 后端：`backend/`（FastAPI、SQLModel）。
- 推荐引擎：`backend/app/recommender/`。
- 前后端推荐桥接与持久化：`backend/app/services/integrated_recommendation_service.py`。
- 浏览器 API：`backend/app/controllers/web_api.py`。
- SRS 覆盖情况：`SRS_TRACEABILITY.md`。
- 总体启动说明：`README.md`。

## 已完成工作

1. 已将用户提供的三份代码整合为一个应用：
   - React frontend；
   - FastAPI + database backend；
   - standalone recommender API/engine。
2. 前端已真正调用 FastAPI `/api`，不是仅依靠原始 MSW/in-page mock。
3. 已实现并连通：
   - 创建 Session；
   - 分享 invitation link；
   - 在 Sessions 页面粘贴完整邀请链接或 `/join/` code；
   - 不同用户加入同一 Session；
   - Organizer 也提交自己的 availability；
   - location geocoding、transport mode、availability 保存与修改；
   - Organizer 查看响应人数；
   - 生成、重新生成、排序、查看和确认推荐；
   - confirmed plan 页面。
4. 演示身份共有三个：
   - `Demo Organiser` / `organiser@example.test`；
   - `Amirah` / `amirah@example.test`；
   - `Wei Jie` / `weijie@example.test`。
5. DEV persona 切换后会返回 `/sessions`。多个标签页共享认证 Cookie，但现在通过 localStorage identity-change event 同步清理 React Query cache，修复了切回 Amirah 后邮箱/身份显示陈旧的问题。
6. 后端已有每个 Session 最多 12 个账户的限制。Organizer 也计入 12 人，因此最多是 1 Organizer + 11 invitees。当前只能手动演示 3 人，是因为只有三个 DEV personas，不是推荐引擎只能处理 3 人。
7. 推荐引擎已有 12 人规模测试。
8. `backend/scripts/seed_demo.py` 会幂等加载演示活动和场馆，并在场馆目录变化时让旧排名变 stale。
9. Badminton 推荐已启用至少四个场馆，包括：
   - Jurong East Sports Centre；
   - Our Tampines Hub Field；
   - Bishan Sports Hall；
   - Toa Payoh Sports Hall。
10. 修复了重新生成推荐时 `candidate_timeslots(session,start,end)` 唯一约束冲突：重新生成前会按外键安全顺序替换旧的派生结果。
11. 修复了“没有任何推荐”的两类情况：
   - 场馆全部过远：扩充了 demo Venue catalogue，并正确支持西部羽毛球场；
   - 最低人数差一点没有达到：现在返回清楚标注的 `Near match`，而不是只返回 409/空页面。
12. Availability 现在要求至少有一段连续时间可以容纳完整活动时长。例如活动时长 120 分钟，选择 90 分钟会在前端拦截，后端也会二次验证。
13. 当前推荐 fallback 规则：
   - 先严格使用 Organizer 设置的 minimum attendees；
   - 如果没有达到该人数，但至少有 2 人可以完整参加，则按“最佳可行人数”继续排名；
   - 页面明确显示 `Near match · 2 of 3`、缺席者和原因；
   - 不会把 2 人方案伪装成 3 人方案；
   - 如果最多只有 0 或 1 人，仍然不给出 group recommendation。
14. Google Login 的 OAuth 入口、callback、ID token verification 和账户保存已有代码骨架，但真实 Google Cloud credentials 尚未配置。这是下周范围，不是当前 prototype bug-fix 范围。
15. Google Calendar 权限与 Google Login 是两件事。Calendar 读取/写入需要独立 scope、consent 和正式 provider 配置。

## 当前正在厘清的 bug / 测试状态

目前主要通过三个 DEV personas 继续做实际操作测试，发现问题后再修。最近一次复现 Session 的本机 ID 是：

`33866bec-c177-4342-aa3b-f9a03a983cb9`

该 Session 的数据是：

- 名称：`G`；
- 活动：Badminton；
- 每日窗口：19:00–21:00；
- 活动时长：120 分钟；
- minimum attendees：3；
- 三人 location 都已成功 geocode 到 `609690` / Jurong East MRT 附近；
- Demo Organiser 的 active interval：19:00–20:30（只有 90 分钟）；
- Amirah：19:00–21:00；
- Wei Jie：19:00–21:00。

所以旧系统显示“没有时间满足最低人数”并不是地点算法错误，而是 Organizer 的 90 分钟无法覆盖 120 分钟活动。现在系统已经：

- 生成 Near Match；
- 第一名为 Jurong East Sports Centre；
- 时间为 19:00–21:00；
- 当前参加者为 Amirah 和 Wei Jie；
- Organizer 被明确列为 unavailable；
- 如果 Organizer 将 availability 改为 19:00–21:00，预期应生成完整的 3/3 推荐，这是下一项人工回归测试。

另一个待用户确认的数据差异：用户口头表示三个人都选择 Drive，但数据库当前保存的是：

- Demo Organiser：`DRIVE`；
- Amirah：`PUBLIC_TRANSPORT`；
- Wei Jie：`PUBLIC_TRANSPORT`。

不要擅自覆盖参与者选择。下一步应该让 Amirah 和 Wei Jie分别打开自己的 response，确认 UI 中选择 Drive 并保存，然后检查数据库与结果卡片是否同步。如果用户确实选择了 Drive 但数据库仍保存 Public Transport，才继续定位 transport-mode 保存 bug。

## 当前建议的回归测试

1. Organizer 建立一个 120 分钟、minimum attendees = 3 的 Badminton Session。
2. 三个人都通过同一 invitation link 加入。
3. 三个人都选择 `609690`、`DRIVE`、同一个连续 120 分钟区间。
4. 预期：结果页有 3/3 feasible recommendation，Jurong East Sports Centre 应靠前。
5. 将其中一人改为只有 90 分钟：
   - 新提交应被阻止，并提示连续 120 分钟；
   - 对已有历史短区间数据重新排名时，应显示 Near Match 而不是空白。
6. 在多个标签页中执行 Organizer → Amirah → Organizer → Amirah：
   - `/api/me`、顶部 persona 名称和邮箱应始终一致；
   - participant 不应停留在 Organizer-only route。
7. 修改任一 response 后重新排名：不应再出现数据库 unique constraint 错误。

## Demo 支持的 starting locations

- Ang Mo Kio MRT Station — `569811`
- Bishan MRT Station — `579827`
- Toa Payoh MRT Station — `319758`
- Tampines MRT Station — `529538`
- Jurong East MRT Station — `609690`
- Punggol MRT Station — `828868`
- Woodlands MRT Station — `738343`
- Nanyang Technological University — `639798`

`636866` 不在 mock geocoder 数据中，因此 demo 会正确返回找不到地址。不要把 demo mock 数据描述成完整的真实 OneMap 数据。

## 如何在新电脑运行

最省事的方法：

```bash
docker compose up --build
```

然后访问 `http://localhost:5173`。

本地开发模式：

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

确保 `backend/.env` 至少包含：

```dotenv
DATABASE_URL=sqlite:///./group_scheduling.db
DEBUG_AUTH_ENABLED=true
USE_MOCK_PROVIDERS=true
FRONTEND_BASE_URL=http://localhost:5173
```

启动后端：

```bash
python -m scripts.seed_demo
uvicorn app.main:app --reload
```

启动前端：

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

注意：交付 ZIP 不包含当前机器上的 SQLite `.db` 文件。因此换电脑后会有相同代码和 seed catalogue，但不会自动带上当前浏览器里创建的 Session `G`。需要重新创建测试 Session，或者明确决定另行迁移测试数据库。

## 验证命令与最近结果

```bash
cd backend
.venv/bin/python -m pytest -q

cd ../frontend
npm run lint
npm run build
```

最近一次结果：

- Backend：62 tests passed；
- Frontend：oxlint passed；
- TypeScript/Vite production build passed；
- ZIP integrity check passed。

## 下周计划（尚未实施）

1. 配置真实 Google OAuth Client、redirect URI、HTTPS 和生产 secrets。
2. 关闭 `DEBUG_AUTH_ENABLED`，DEV personas 只保留在本地 demo 环境。
3. 由经过 Google 验证的 identity 建立真实 UserAccount，并保存真实邮箱。
4. 在前端和后端显式执行总人数 2–12 的产品规则，并补充 2、3、12 和第 13 人被拒绝的测试。
5. 明确“12 人是否包含 Organizer”；当前实现是包含。
6. 如果需要真实路线，关闭 mock providers，并配置 OneMap credentials。
7. 如果需要 Google Calendar，单独完成 Calendar consent、credential vault 和最小权限 scopes。

## 接手时的重要原则

- 先复现和读取实际保存数据，再判断是推荐算法 bug、表单 UX bug还是输入数据不满足活动约束。
- 不要为了“总有结果”而悄悄改变活动时长、参与人数或参与者 transport mode。
- Near Match 必须继续清楚标注，不得伪装成达到 minimum attendees 的正式匹配。
- 其他参与者的地址和邮箱不得显示给 Organizer；结果页只显示姓名、attendance status 和 travel duration/mode。
- 用户目前只要求本周完成 prototype 和厘清 bug。真实 Google 登录与 2–12 人正式产品化属于下周工作，除非用户明确提前要求。
