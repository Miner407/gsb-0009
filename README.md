# 校园失物招领看板

校园失物招领信息发布与管理系统，提供发布、审核、认领、关闭全流程管理，支持消息追踪和多维度筛选。

---

## 🚀 快速启动

### 环境要求
- Python 3.8+
- 浏览器（Chrome / Edge / Firefox / Safari 最新版）

### 安装依赖
```bash
cd 项目目录
pip install -r requirements.txt
```

### 启动服务
```bash
python app.py
```

服务启动后访问：**http://127.0.0.1:5000/**

> 💡 首次启动会自动创建 `lost_found.db`（SQLite 数据库）并执行数据迁移（兼容已有数据，旧数据自动视为已审核）。

---

## ✨ 核心功能

### 1. 公开看板
- 展示所有**审核通过**的失物 / 招领信息
- 以公告卡片形式排列，信息层次清晰
- 点击任意卡片进入详情页

### 2. 我的发布
- 通过**联系方式**查询自己发布的所有信息
- 可查看审核状态、认领状态、关闭状态
- 查看审核备注和处理进度

### 3. 审核中心
- 管理员可查看所有待审核信息
- 支持审核通过 / 驳回（驳回需填写原因）
- 顶部标签栏显示待审核数量徽章
- 支持按审核状态筛选（待审核 / 已通过 / 已驳回）

### 4. 发布流程
1. 点击 **「+ 发布信息」**
2. 填写信息类型（失物/招领）、物品名称、详细描述、地点、时间、联系方式、图片链接
3. 提交后进入**待审核**状态
4. 管理员审核通过后出现在公开看板

### 5. 审核流程
- **待审核** → 新发布的信息默认进入此状态
- **已通过** → 管理员审核通过，出现在公开看板
- **已驳回** → 管理员驳回，需填写驳回原因（返回给发布者查看）

### 6. 认领与关闭
- **认领**：开放中的信息可被认领，需提供认领人姓名和联系方式
- **关闭**：已认领或无需再展示的信息可关闭，关闭后状态不可再修改

### 7. 消息追踪
每条信息都有完整的时间线追踪：
- 发布时间与操作人
- 审核时间、操作人与备注
- 认领时间与认领人
- 关闭时间
- 任意阶段可添加处理备注

### 8. 搜索与筛选
支持以下维度**组合筛选**，筛选条件自动保存在 URL query 中：
- 关键词（搜索名称、描述、地点）
- 类型（失物 / 招领）
- 地点
- 业务状态（开放中 / 已认领 / 已关闭）
- 审核状态（我的发布、审核中心视图可用）
- 发布日期范围（起始日期 ~ 截止日期）

---

## 📡 API 列表

### 公共接口

| 方法 | 路径 | 说明 |
|-----|------|------|
| GET | `/api/items` | 获取信息列表（默认只返回审核通过的） |
| GET | `/api/items/<id>` | 获取单条信息详情 |
| POST | `/api/items` | 发布新信息（状态默认 open，审核状态默认 pending） |
| PUT | `/api/items/<id>/status` | 更新业务状态（认领/关闭/重新开放） |
| GET | `/api/items/<id>/logs` | 获取状态追踪日志 |
| POST | `/api/items/<id>/remark` | 添加处理备注 |
| GET | `/api/locations` | 获取所有出现过的地点 |
| GET | `/api/stats` | 获取全局统计（待审核/开放/认领/关闭数量） |

### 审核接口

| 方法 | 路径 | 说明 |
|-----|------|------|
| PUT | `/api/items/<id>/audit` | 审核信息（通过或驳回） |

---

### 接口详细说明

#### 1. `GET /api/items` - 获取列表

Query 参数（全部可选）：
| 参数 | 类型 | 说明 |
|-----|------|------|
| keyword | string | 关键词搜索（标题、描述、地点） |
| type | string | `lost` 失物 / `found` 招领 |
| location | string | 精确地点匹配 |
| status | string | `open` / `claimed` / `closed` |
| audit_status | string | `pending` / `approved` / `rejected` |
| contact | string | 按发布者联系方式精确匹配（"我的发布"用） |
| date_from | string | 起始日期，格式 `YYYY-MM-DD` |
| date_to | string | 截止日期，格式 `YYYY-MM-DD` |
| include_pending | bool | 是否包含未审核信息（我的发布/审核中心需传 `1`） |

响应：
```json
{
  "items": [
    {
      "id": 1,
      "title": "黑色皮质钱包",
      "description": "...",
      "item_type": "lost",
      "location": "图书馆三楼",
      "event_time": "2026-06-19 15:30",
      "contact": "13800138000",
      "image_url": "",
      "status": "open",
      "claimer_name": null,
      "claimer_contact": null,
      "audit_status": "approved",
      "audit_remark": null,
      "audited_at": "2026-06-20 10:00:00",
      "audited_by": "admin",
      "claimed_at": null,
      "closed_at": null,
      "created_at": "2026-06-20 09:00:00",
      "updated_at": "2026-06-20 10:00:00"
    }
  ],
  "locations": ["图书馆三楼", "一食堂二楼"],
  "audit_statuses": ["pending", "approved"]
}
```

#### 2. `POST /api/items` - 发布信息

请求体：
```json
{
  "title": "黑色皮质钱包",
  "description": "内含身份证、银行卡",
  "item_type": "lost",
  "location": "图书馆三楼自习区",
  "event_time": "2026-06-19 15:30",
  "contact": "13800138000",
  "image_url": ""
}
```

响应（201 Created）：返回完整 item 对象，`audit_status` 为 `pending`。

#### 3. `PUT /api/items/<id>/status` - 更新业务状态

请求体：
```json
{
  "status": "claimed",
  "claimer_name": "王同学",
  "claimer_contact": "15800158000",
  "operator": "王同学",
  "remark": "已联系发布者"
}
```

状态转移规则：
- `open` → `claimed`：需提供 claimer_name 和 claimer_contact
- `open`/`claimed` → `closed`：任意时刻可关闭
- `closed`：不可再更新
- `claimed` → `open`：可重新开放（清空认领信息）

自动记录时间：`claimed_at`、`closed_at`，并写入 audit_logs。

#### 4. `PUT /api/items/<id>/audit` - 审核

请求体：
```json
{
  "action": "approve",
  "operator": "admin",
  "remark": ""
}
```
- `action`: `approve` 通过 / `reject` 驳回
- `remark`: 驳回时**必填**
- 只有 `audit_status = pending` 的信息可审核

#### 5. `GET /api/items/<id>/logs` - 获取操作日志

响应：
```json
{
  "logs": [
    {
      "id": 1,
      "item_id": 1,
      "action": "create",
      "operator": "user",
      "remark": "发布失物信息",
      "created_at": "2026-06-20 09:00:00"
    }
  ]
}
```

action 类型：`create`、`audit_approve`、`audit_reject`、`claim`、`close`、`reopen`、`remark`

#### 6. `POST /api/items/<id>/remark` - 添加备注

请求体：
```json
{
  "remark": "已电话沟通，明日在食堂交接",
  "operator": "张同学"
}
```

---

## 🗃️ 数据迁移说明

### 数据库文件
SQLite 数据库文件：`lost_found.db`（项目根目录）

### 迁移内容
应用启动时 `migrate_db()` 自动执行以下操作（幂等，可重复运行）：

1. **列扩展**：`items` 表新增 6 列
   - `audit_status` 审核状态（默认 `approved`）
   - `audit_remark` 审核备注
   - `audited_at` 审核时间
   - `audited_by` 审核操作人
   - `claimed_at` 认领时间
   - `closed_at` 关闭时间

2. **旧数据兼容**：
   - 所有已有数据的 `audit_status` 设为 `approved`
   - `audited_at` 取 `created_at` 值

3. **新建 audit_logs 表**：操作日志表

4. **日志补录**：为每条旧数据补录 `create` 日志，已认领/关闭的再补对应日志

5. **数据安全**：不删除任何旧数据，只做增量变更

---

## ✅ 验证步骤

共提供 **6 组**可运行的验证：

### 前置条件
1. 启动服务：`python app.py`（确保 5000 端口可用）
2. 打开新终端执行验证脚本

---

### 验证 1~3：三条主链路（原链路，保留）
**命令**：
```bash
python verify.py --suite main
```

涵盖场景：
- **发布链路**：发布失物 / 招领信息、校验必填项、校验类型、列表可见、关键词搜索、地点筛选、类型筛选
- **认领链路**：认领（含认领人信息）、认领信息校验、拒绝重复认领、状态筛选
- **关闭链路**：关闭已认领、直接关闭开放信息、禁止重复操作、404 校验

---

### 验证 4：审核流验证
**命令**：
```bash
python verify.py --suite audit
```

涵盖场景：
1. 发布信息 → 校验 audit_status = `pending`
2. 公开看板（`include_pending=false`） → 不可见
3. 审核中心（`include_pending=true`） → 可见
4. 审核驳回（无备注应被拒绝）
5. 审核驳回（有备注）→ audit_status = `rejected`
6. 重复审核应被拒绝
7. 重新发布新信息
8. 审核通过 → audit_status = `approved`
9. 公开看板可见
10. `/api/stats` 数量核对

---

### 验证 5：消息追踪验证
**命令**：
```bash
python verify.py --suite tracking
```

涵盖场景：
1. 发布信息 → 生成 `create` 日志
2. 审核通过 → 生成 `audit_approve` 日志
3. 添加处理备注 → 生成 `remark` 日志
4. 认领 → 生成 `claim` 日志，校验 claimed_at 已记录
5. 添加备注（认领后）→ 生成 remark 日志
6. 关闭 → 生成 `close` 日志，校验 closed_at 已记录
7. 验证时间线包含全部 6 条操作日志，顺序正确
8. 校验操作人、备注内容均正确存储

---

### 验证 6：筛选与我的发布验证
**命令**：
```bash
python verify.py --suite filter
```

涵盖场景：
1. 生成 4 条测试数据（不同类型、地点、时间、联系方式）
2. 审核 3 条通过、1 条驳回
3. **类型筛选**（type=lost） → 仅返回失物
4. **关键词筛选**（keyword=食堂） → 模糊匹配
5. **日期范围筛选**（date_from / date_to） → 正确限制范围
6. **组合筛选**（type + status） → 交集正确
7. **我的发布查询**（contact 匹配） → 对应联系方式的所有状态（包括 pending/rejected）
8. **URL query 保留**：构造的 query 参数全部被后端正确解析
9. **不存在的联系方式** → 返回空列表

---

### 全量验证（一次运行所有用例）
```bash
python verify.py
```

---

## 🎨 UI 改进要点

### 视觉统一
- 使用 CSS 变量体系：`--color-primary`、`--radius-*`、`--spacing-*`、`--shadow-*`
- 干净的蓝白灰主色调（#2563eb 品牌蓝）
- 告别杂乱渐变，使用纯色 + 轻阴影

### 信息架构
- **首页卡片**：三列式公告看板布局（图片条 + 内容区 + 操作区）
- **左色条**：一眼区分失物（红）/ 招领（绿）
- **分区详情**：图片 → 标题 → 描述 → 基本信息 → 认领信息 → 审核状态 → 时间线

### 状态与反馈
- 加载中：Spinner 动效
- 空状态：图标 + 视图对应的文字说明
- 错误：统一 Error Card
- 操作反馈：顶部 Toast（success / warning / error 三种样式）
- 按钮：禁用态、悬停态、active 态

### 移动端适配
- 断点：`960px / 768px / 480px` 三档
- 卡片：960px 以下自适应堆叠
- 表单：768px 以下单列排列
- 按钮：移动端自动铺满宽度

---

## 📁 项目结构

```
├── app.py              # Flask 后端（含数据库迁移）
├── requirements.txt    # 依赖
├── verify.py           # 验证脚本（6 组用例）
├── lost_found.db       # SQLite 数据库（自动生成）
├── README.md           # 本文档
└── static/
    ├── index.html      # 首页（公开看板/我的发布/审核中心 三视图）
    ├── detail.html     # 详情页
    ├── style.css       # 全局样式 + 变量体系
    ├── detail.css      # 详情页专属样式
    ├── app.js          # 首页逻辑
    └── detail.js       # 详情页逻辑
```
