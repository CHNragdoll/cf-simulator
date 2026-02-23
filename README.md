# 穿越火线抽奖模拟器（本地版）超详细 README

这是一套**纯本地运行**的抽奖活动模拟器。你可以把它当成一个“可改概率、可改奖池、可看统计、可做成本模拟”的活动沙盘。

如果你完全不懂代码，按本文的“第 1 步、第 2 步”做，也能跑起来并正常操作。

---

## 0. 这个项目能做什么（先看结论）

它支持：

- 买钥匙（`10元1抽`、`100元11抽`）
- 单抽 / 十连
- 道具进暂存箱或直发仓库
- 暂存箱道具可“发送仓库”或“分解换积分/钥匙”
- 积分兑换（保底兑换）
- 概率公布弹窗
- 抽奖历史 / 兑换历史
- 数据分析（分布、理论值偏差、置信区间、Z 值、卡方、趋势拟合）
- Monte Carlo 模拟（不同策略下达成目标道具的成本分布）

---

## 1. 项目目录（你要认识的文件）

项目根目录：`/Users/apple/Documents/PyCharm/穿越火线模拟器_副本6`

关键目录和文件：

- `/Users/apple/Documents/PyCharm/穿越火线模拟器_副本6/lottery_simulator/server.py`
  - 后端主程序（HTTP 服务 + 抽奖逻辑 + 统计 + 模拟）
- `/Users/apple/Documents/PyCharm/穿越火线模拟器_副本6/lottery_simulator/static/index.html`
  - 前端页面结构
- `/Users/apple/Documents/PyCharm/穿越火线模拟器_副本6/lottery_simulator/static/app.js`
  - 前端交互逻辑（按钮事件、图表渲染、调用 API）
- `/Users/apple/Documents/PyCharm/穿越火线模拟器_副本6/lottery_simulator/static/style.css`
  - 前端样式
- `/Users/apple/Documents/PyCharm/穿越火线模拟器_副本6/lottery_simulator/data/lottery.db`
  - 奖池配置数据库（SQLite）
- `/Users/apple/Documents/PyCharm/穿越火线模拟器_副本6/lottery_simulator/data/state.json`
  - 你的模拟过程状态（消费、钥匙、抽奖历史等）
- `/Users/apple/Documents/PyCharm/穿越火线模拟器_副本6/cf_images/`
  - 活动图片资源（本地图片）
- `/Users/apple/Documents/PyCharm/穿越火线模拟器_副本6/main.py`
  - 批量下载图片脚本（需要 `requests`）

---

## 2. 小白启动教程（一步一步照抄）

### 第 1 步：确认你有 Python 3

在终端执行：

```bash
python3 --version
```

看到 `Python 3.x.x` 就行。

### 第 2 步：进入后端目录

```bash
cd "/Users/apple/Documents/PyCharm/穿越火线模拟器_副本6/lottery_simulator"
```

### 第 3 步：启动服务

```bash
python3 server.py
```

启动成功会看到类似：

```text
Simulator running: http://127.0.0.1:8000
DB path: .../lottery_simulator/data/lottery.db
```

### 第 4 步：打开网页

浏览器访问：

```text
http://127.0.0.1:8000
```

到这里就已经可以玩完整流程了。

---

## 3. 页面操作教学（真的按按钮就行）

### 3.1 购买钥匙

- 点击 `10元1抽`：消费 10 元，+1 钥匙
- 点击 `100元11抽`：消费 100 元，+11 钥匙

顶部会更新：

- 累计消费
- 剩余钥匙
- 总积分
- 总抽数

### 3.2 抽奖

- `抽一次`：消耗 1 把钥匙
- `抽十次`：消耗 10 把钥匙

结果逻辑：

- 抽中积分子项：直接加积分
- 抽中道具且 `direct_to_warehouse=1`：直接进仓库
- 抽中道具且 `direct_to_warehouse=0`：进暂存箱，等待你后续“发送”或“分解”

### 3.3 暂存箱

“暂存道具表”里每条记录可做两件事（一次性）：

- `发送仓库`
- `分解`

分解收益来自该道具配置：

- `decompose_points`
- `decompose_keys`

### 3.4 仓库直发

展示所有“已进仓库”的道具数量（包括抽中直发 + 兑换发放 + 暂存发送）。

### 3.5 积分兑换（保底）

点击兑换卡片按钮（例如 `1888积分兑换`）：

- 扣除对应积分
- 道具发往仓库
- 记录到兑换日志

如果该道具设置了限兑，会校验：

- `redeem_limit_enabled=1`
- `redeem_limit_count` 上限

### 3.6 概率公布

点击 `概率公布` 可看所有奖项当前概率（积分组会展开成具体积分项）。

### 3.7 礼包记录

有两个 tab：

- 抽奖奖池记录（含“欧皇时刻”查看）
- 积分兑换记录

### 3.8 数据分析区

可查看：

- 命中分布
- 理论值 vs 实际值偏差
- 95% 置信区间 + Z 值
- 最近 50 抽 vs 全局
- 日趋势
- 卡方统计量
- 累计积分线性拟合（含公式和 R²）

### 3.9 模拟模块（成本模拟）

你可以输入“模拟次数”，并选策略：

- `最低单钥匙成本`
- `优先10元1抽`
- `优先100元11抽`

系统会异步跑任务并显示进度条，最后给出：

- 全分解均价 / P50 / P90 / 95% 区间
- 纯保底均价
- CDF 曲线
- 置信区间图
- 命中方式占比（抽中/兑换）
- 成本回归模型与训练/测试误差

---

## 4. 数据存储说明（非常重要）

### 4.1 配置数据库（`lottery.db`）

路径：

- `/Users/apple/Documents/PyCharm/穿越火线模拟器_副本6/lottery_simulator/data/lottery.db`

主要表：

- `purchase_options`：买钥匙方案
- `points_groups`：积分组（例如“积分”）
- `prize_items`：道具 + 积分子项 + 兑换项
- `pool_layout_settings`：奖池布局参数
- `pool_palette_priority`：稀有度（颜色）优先级
- `popup_highlight_rules`：哪些颜色触发“稀有弹窗”

### 4.2 用户状态（`state.json`）

路径：

- `/Users/apple/Documents/PyCharm/穿越火线模拟器_副本6/lottery_simulator/data/state.json`

常见字段：

- `money_spent`：累计消费
- `keys`：当前钥匙
- `points`：当前积分
- `total_draws`：总抽数
- `draw_counts`：每个奖项命中次数
- `stash`：暂存箱聚合数量
- `stash_records`：暂存箱逐条记录（有 pending/sent/decomposed 状态）
- `warehouse`：仓库总量
- `warehouse_draw`：由抽奖直接进仓库的量
- `redeem_logs`：兑换日志
- `history`：抽奖历史（最多保留最近 300 条）

---

## 5. 抽奖算法（核心逻辑）

### 5.1 权重归一化

设奖池元素权重为 `w_i`，总权重：

`W = Σ w_i`

每个元素命中概率：

`p_i = w_i / W`

### 5.2 二级奖池（积分组）

积分组本身是一个顶层元素，权重等于其子项权重和：

`w_group = Σ w_child`

积分子项全局概率：

`p_child_global = w_child / W`

积分子项组内条件概率：

`p_child_in_group = w_child / w_group`

### 5.3 加权随机抽样（轮盘法）

后端使用“累计权重区间命中”方式：

1. 计算总权重 `total`
2. 取随机数 `r ~ U(0, total)`
3. 按顺序累加权重 `cur += w_i`
4. 第一项满足 `r <= cur` 即命中

这就是 `weighted_pick` 的逻辑。

### 5.4 单抽状态转移

抽到积分：

- `points += 子项积分值`
- `draw_counts[积分名称] += 1`

抽到道具：

- 若 `direct_to_warehouse=1`：进入仓库
- 否则进入暂存箱，并写入 `stash_records`

同时：

- `total_draws += 1`
- 抽奖结果写入 `history`（最多保留 300 条）

---

## 6. 数学分析模型（页面里看到的那些指标怎么来的）

### 6.1 理论命中数与偏差

若总抽数为 `n`，某奖项理论概率为 `p`：

- 理论命中数：`E = n * p`
- 实际命中数：`O`
- 偏差：`Δ = O - E`

### 6.2 Wilson 95% 置信区间

对观测命中率 `p̂ = O / n`，后端用 Wilson 区间（`z=1.96`）：

中心：

`center = (p̂ + z²/(2n)) / (1 + z²/n)`

半径：

`half = z * sqrt( p̂(1-p̂)/n + z²/(4n²) ) / (1 + z²/n)`

区间：

`[max(0, center-half), min(1, center+half)]`

### 6.3 Z 分数（显著性偏离）

`Z = (O - n*p) / sqrt(n*p*(1-p))`

绝对值越大，说明与理论概率偏离越明显。

### 6.4 卡方拟合统计量

对全部奖项：

`χ² = Σ (O-E)² / E`

自由度近似：`dof = 奖项数 - 1`

### 6.5 最近窗口 vs 全局

后端默认窗口最近 50 抽：

- 全局率：`O_global / n_global`
- 最近率：`O_recent / n_recent`
- 差异：`|recent_rate - global_rate|`

### 6.6 累计积分线性回归

拟合：

`y = a*x + b`

- `x`：抽奖序号
- `y`：累计积分

并计算 `R²`：

`R² = 1 - SS_res / SS_tot`

---

## 7. 模拟模块（Monte Carlo）详解

### 7.1 目标

对每个可兑换道具，重复模拟 `runs` 次，估计“达成该道具”的成本分布。

### 7.2 策略 A：全分解

规则：

- 抽到目标道具 -> 立即达成（抽中路径）
- 如果积分达到兑换门槛 -> 达成（兑换路径）
- 抽到非目标且可进暂存箱道具 -> 立即按配置分解，返还积分和钥匙

输出：

- 平均成本
- P50、P90
- 95% 经验分位区间（2.5% ~ 97.5%）
- 均值置信区间（`mean ± 1.96 * SE`）
- 抽中达成率、兑换达成率
- CDF 经验曲线点

### 7.3 策略 B：纯保底

规则：

- 忽略道具直中收益与道具分解收益
- 只靠抽到积分子项累计到兑换阈值

输出：

- 平均成本
- P50、P90

### 7.4 购钥匙策略

买钥匙选项有单价：

`unit = price / keys_count`

策略选择：

- `min_unit`：选 unit 最小方案
- `single_first`：优先 10 元 1 抽
- `bundle_first`：优先 100 元 11 抽

### 7.5 模型拟合（成本 vs 稀有度）

后端会做一个经验模型：

`avg_cost ≈ a*(1/p) + b`

其中 `p` 是目标道具抽中概率，`avg_cost` 来自策略 A 的样本均值。

并给出：

- 相关系数
- 全样本 `R²`
- 训练/测试切分（70/30）下 MAE、RMSE、R²

---

## 8. 后端 API 一览（便于二开）

### GET

- `/api/config`
  - 获取购买选项、奖池、兑换区、布局参数等
- `/api/state`
  - 获取当前状态（含暂存明细、仓库明细）
- `/api/analysis`
  - 获取统计分析结果
- `/api/simulate`
  - 同步模拟（默认 500 次）
- `/api/simulate/status?job_id=...`
  - 查询异步模拟任务状态
- `/api/db/items`
  - 直接查看 `prize_items` 全量行

### POST

- `/api/buy`
  - 入参：`{"option":"single"}` 或 `{"option":"bundle"}`
- `/api/draw`
  - 入参：`{"count":1}` 或 `{"count":10}`
- `/api/stash/decompose`
  - 入参：`{"item_id":"xxx","qty":1}`
- `/api/stash/send`
  - 入参：`{"item_id":"xxx","qty":1}`
- `/api/stash/record-action`
  - 入参：`{"record_id":123,"action":"send|decompose"}`
- `/api/redeem`
  - 入参：`{"item_id":"xxx","qty":1}`
- `/api/state/reset`
  - 重置用户状态
- `/api/simulate`
  - 同步跑模拟，入参：`{"runs":500,"strategy":"min_unit"}`
- `/api/simulate/start`
  - 异步模拟，返回 `job_id`
- `/api/config/reload`
  - 前端“重载配置”触发（返回 ok；配置本身每次读取都来自 DB）

---

## 9. 数据库字段说明（重点）

表：`prize_items`

- `item_id`：唯一 ID（英文，建议稳定）
- `name`：显示名称
- `item_type`：`item` 或 `points_child`
- `in_pool`：是否参加抽奖（1/0）
- `pool_weight`：权重（越大越容易中）
- `group_key`：积分子项所属分组（仅 `points_child` 用）
- `points_value`：积分子项积分值
- `exchange_points`：兑换所需积分（>0 则进入兑换区）
- `decompose_points`：分解返还积分
- `decompose_keys`：分解返还钥匙
- `direct_to_warehouse`：是否直发仓库（1 直发，0 暂存）
- `image_url`：卡面图片
- `popup_image_url`：弹窗图
- `card_bg_color`：卡片背景
- `palette_key`：稀有色（`orange/purple/blue/gray`）
- `redeem_limit_enabled`：是否限兑
- `redeem_limit_count`：限兑数量
- `redeem_tag_left`、`redeem_tag_right`：兑换卡片角标
- `sort_order`：排序

---

## 10. 常用 SQL 操作（直接可用）

建议先备份：

```bash
cp "/Users/apple/Documents/PyCharm/穿越火线模拟器_副本6/lottery_simulator/data/lottery.db" "/Users/apple/Documents/PyCharm/穿越火线模拟器_副本6/lottery_simulator/data/lottery.db.bak"
```

### 10.1 查看当前奖池

```sql
SELECT item_id,name,item_type,in_pool,pool_weight,group_key,points_value,exchange_points,decompose_points,decompose_keys,direct_to_warehouse
FROM prize_items
ORDER BY sort_order,item_id;
```

### 10.2 调整某道具概率（权重）

```sql
UPDATE prize_items
SET pool_weight = 0.35
WHERE item_id = 'knife_champion';
```

### 10.3 设置“抽中即进仓库”

```sql
UPDATE prize_items
SET direct_to_warehouse = 1
WHERE item_id = 'king_stone';
```

### 10.4 新增一个积分子项

```sql
INSERT INTO prize_items(
  item_id,name,item_type,in_pool,pool_weight,group_key,points_value,
  exchange_points,decompose_points,decompose_keys,direct_to_warehouse,
  image_url,popup_image_url,card_bg_color,palette_key,sort_order
) VALUES(
  'points_30','30积分','points_child',1,3.0,'points_pool',30,
  0,0,0,0,'','','','gray',207
);
```

### 10.5 新增奖池外兑换道具

```sql
INSERT INTO prize_items(
  item_id,name,item_type,in_pool,pool_weight,group_key,points_value,
  exchange_points,decompose_points,decompose_keys,direct_to_warehouse,
  image_url,popup_image_url,card_bg_color,palette_key,
  redeem_limit_enabled,redeem_limit_count,redeem_tag_left,redeem_tag_right,sort_order
) VALUES(
  'redeem_only_ak','AK47-兑换专属','item',0,0,NULL,0,
  1688,0,0,1,'','','','gray',
  1,1,'单大区限兑1','不可交易',400
);
```

### 10.6 调整兑换限兑

```sql
UPDATE prize_items
SET redeem_limit_enabled=1, redeem_limit_count=2
WHERE item_id='redeem_honor_soul';
```

### 10.7 配置稀有弹窗颜色

```sql
UPDATE popup_highlight_rules SET enabled=1 WHERE palette_key IN ('orange','purple','blue');
UPDATE popup_highlight_rules SET enabled=0 WHERE palette_key='gray';
```

---

## 11. 图片资源与路径规则

后端支持两种静态图路径：

- `/cf_images/...` -> 读取项目根目录 `/cf_images/`
- `/cfimages/...` -> 读取 `/lottery_simulator/cfimages/`

本项目现有素材主要在：

- `/Users/apple/Documents/PyCharm/穿越火线模拟器_副本6/cf_images/`

### 下载素材脚本

需要第三方库：

```bash
python3 -m pip install requests
```

下载主图（在项目根目录执行）：

```bash
cd "/Users/apple/Documents/PyCharm/穿越火线模拟器_副本6"
python3 main.py
```

下载 `lotb` 组图（建议在 `cf_images` 目录执行）：

```bash
cd "/Users/apple/Documents/PyCharm/穿越火线模拟器_副本6/cf_images"
python3 炫耀图片下载.py
```

---

## 12. 重置、备份、恢复

### 12.1 只重置“玩家进度”

网页里点 `重置模拟数据`，或调用 `/api/state/reset`。

只影响 `state.json`，不会改奖池配置。

### 12.2 重置“奖池配置”

删除数据库文件后重启服务，后端会按内置默认值重建：

- `/Users/apple/Documents/PyCharm/穿越火线模拟器_副本6/lottery_simulator/data/lottery.db`

### 12.3 最稳妥的备份策略

每次改 SQL 前备份两个文件：

- `lottery.db`
- `state.json`

---

## 13. 常见问题（排错）

### Q1：端口 8000 被占用，启动失败

改 `server.py` 里的 `PORT = 8000` 为别的端口（例如 `8010`），重启后访问新端口。

### Q2：抽奖提示“钥匙不足”

先点击购买按钮补钥匙，再抽。

### Q3：我改了数据库但页面没变化

先点页面上的 `重载后端配置`，不行就刷新浏览器。仍不行时重启 `server.py`。

### Q4：模拟很慢

- 降低 `模拟次数`
- 避免把某些目标设置得过于极端（很高兑换门槛 + 很低概率）
- 每个目标最多 100000 步保护，不会无限循环

### Q5：为什么统计波动这么大

样本量小的时候，偏差、Z 值、趋势都容易抖动。多抽几百次后再观察更稳定。

---

## 14. 给开发者的二次开发提示

- 后端无第三方框架，基于 `http.server`，结构简单，适合快速改逻辑。
- 前端是原生 JS + SVG 绘图，无构建工具。
- 异步模拟任务在内存里管理（`SIM_JOBS`），服务重启后任务会丢失，这是预期行为。
- 线程安全依赖全局 `LOCK` + `SIM_JOBS_LOCK`，改并发逻辑时注意锁粒度。

---

## 15. 免责声明（和页面保持一致）

- 本项目是本地概率模拟工具，不代表官方活动真实结果。
- 统计结论受样本量、配置和模型假设影响，不构成收益承诺。
- 所有道具发放均为本地数据演示，不接入真实账号资产系统。

