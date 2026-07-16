# MTA 数据需求说明

本文档说明 Markov Chain Attribution 和 Shapley Value Attribution 分别需要什么数据。因为后续还要计算 ROI / ROAS，所以渠道花费数据也直接写进两个模型的数据需求中。

## 1. Markov Chain Attribution 需要的数据

Markov 需要用户级、有时间顺序的路径数据。

### 1.1 用户触点数据

核心字段：

| 字段 | 作用 |
| --- | --- |
| `user_id` | 区分不同用户 |
| `timestamp` | 给用户触点排序 |
| `channel` | 用户接触的渠道 |
| `event_type` | 事件类型，例如 impression、click、purchase、no_conversion |
| `conversion` | 用户最后是否转化 |
| `revenue` | 用户转化带来的收入 |

原始数据示例：

```csv
user_id,timestamp,channel,event_type,conversion,revenue
u001,2026-06-01 10:00:00,TikTok,impression,0,0
u001,2026-06-02 14:20:00,Meta,click,0,0
u001,2026-06-03 09:30:00,Conversion,purchase,1,120
u002,2026-06-01 11:00:00,Meta,impression,0,0
u002,2026-06-05 18:00:00,Null,no_conversion,0,0
```

整理后的 Markov 输入表：

```csv
user_id,path,conversion,revenue
u001,"Start > TikTok > Meta > Conversion",1,120
u002,"Start > Meta > Null",0,0
u003,"Start > TikTok > Google Search > Conversion",1,80
u004,"Start > Google Search > Meta > Null",0,0
```

### 1.2 ROI / ROAS 需要补充的花费数据

Markov 算出每个渠道分到多少收入贡献后，要结合渠道花费计算 ROI / ROAS。

核心字段：

| 字段 | 作用 |
| --- | --- |
| `date` | 花费日期 |
| `channel` | 渠道名称 |
| `spend` | 渠道花费 |

花费数据示例：

```csv
date,channel,spend
2026-06-01,TikTok,500
2026-06-01,Meta,450
2026-06-01,Google Search,600
```

## 2. Shapley Value Attribution 需要的数据

Shapley 需要用户级渠道集合数据。

### 2.1 用户渠道集合数据

核心字段：

| 字段 | 作用 |
| --- | --- |
| `user_id` | 区分不同用户 |
| `channels` | 用户接触过的渠道集合 |
| `conversion` | 用户最后是否转化 |
| `revenue` | 用户转化带来的收入 |

整理后的 Shapley 输入表：

```csv
user_id,channels,conversion,revenue
u001,"TikTok,Meta",1,120
u002,"Meta",0,0
u003,"TikTok,Google Search",1,80
u004,"Google Search,Meta",0,0
u005,"TikTok,Meta,Google Search",1,200
```

如果已经有 Markov 的 `path`，可以直接整理出 Shapley 的 `channels`：

```text
Start > TikTok > Meta > Conversion
        ↓
TikTok, Meta
```

### 2.2 ROI / ROAS 需要补充的花费数据

Shapley 算出每个渠道分到多少收入贡献后，也要结合渠道花费计算 ROI / ROAS。

核心字段：

| 字段 | 作用 |
| --- | --- |
| `date` | 花费日期 |
| `channel` | 渠道名称 |
| `spend` | 渠道花费 |

花费数据示例：

```csv
date,channel,spend
2026-06-01,TikTok,500
2026-06-01,Meta,450
2026-06-01,Google Search,600
```

## 3. Summary：两个模型需要的数据并集

如果同时做 Markov、Shapley，并且后续要计算 ROI / ROAS，最终需要准备的数据并集是：

| 数据 | 用途 |
| --- | --- |
| `user_id` | 区分不同用户 |
| `timestamp` | 生成 Markov 路径 |
| `channel` | 识别触点渠道，也用于匹配花费 |
| `event_type` | 区分 impression、click、purchase、no_conversion |
| `conversion` | 判断用户是否转化 |
| `revenue` | 计算归因收入 |
| `path` | Markov 输入，可由用户触点数据整理得到 |
| `channels` | Shapley 输入，可由 `path` 整理得到 |
| `date` | 匹配渠道花费日期 |
| `spend` | 计算 ROI / ROAS |

最推荐的原始数据形式是两张表：

```text
user_touchpoint_events.csv
channel_spend.csv
```

其中：

| 表 | 需要包含 |
| --- | --- |
| `user_touchpoint_events.csv` | `user_id`, `timestamp`, `channel`, `event_type`, `conversion`, `revenue` |
| `channel_spend.csv` | `date`, `channel`, `spend` |