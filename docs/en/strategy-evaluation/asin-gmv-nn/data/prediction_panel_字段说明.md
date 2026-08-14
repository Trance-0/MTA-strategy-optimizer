# prediction_panel.csv 字段说明（SK-II 单品）

| 项 | 内容 |
|----|------|
| 版本 | v1.3 |
| 文件 | `prediction_panel.csv` |
| 产品 | SK-II（无 ASIN 列） |
| 粒度 | **marketplace × date** |
| 行数 | 62 |

`log1p(x) = ln(1+x)`。

---

## 键与切分

| 变量 | 含义 |
|------|------|
| `date` | 报告日 |
| `country` | 市场 `US` / `CA` |
| `product` | 固定 `SK-II`（元数据） |
| `split` | `train` / `val` / `test`（按日切） |

**本版没有 `asin`。**

---

## 预算输入

| 变量 | 含义 |
|------|------|
| `cost` | 四类花费之和 |
| `budget_sp/sb/sd/dsp` | 当日该市场 SP/SB/SD/DSP **真实花费**（来自 `adProduct`） |
| `share_*` | 各类型占 `cost` 的比例，加总=1 |
| `has_ad` | 是否有花费 |

---

## 流量 / 转化 / 标签

| 变量 | 含义 |
|------|------|
| `impressions` / `impressions_*` | 总曝光 / 分类型曝光 |
| `clicks` | 总点击 |
| `gmv_ad` / `revenue` | **主标签**：归因销售额合计 |
| `sales_ad` | 归因件数合计（效率头） |

---

## 时间与 log 列

| 变量 | 含义 |
|------|------|
| `dow` | 星期 0–6 |
| `is_weekend` | 是否周末 |
| `log1p_budget_*` | 模型主输入 |
| `log1p_impressions_*` | 流量头标签 |
| `log1p_revenue` | 交易额头标签 |
| `log1p_sales_ad` | 效率头标签 |
| `log1p_impressions` / `log1p_clicks` | 对照用 |

---

## 进模型 vs 不进

| 角色 | 列 |
|------|-----|
| 输入 | `log1p_budget_*`、`share_*`、`has_ad`、`is_weekend`、`dow`、`country` |
| 主标签 | `log1p_revenue` |
| 辅助标签 | `log1p_impressions_*`、`log1p_sales_ad` |
| 不含 | **asin**、惯性、岭回归特征 |

## v1.4 扩样说明

| 字段 | 含义 |
|------|------|
| `is_synthetic` | 0=真实 July；1=按 `generator_params.json` 模拟的 Jan–Jun |

面板约 424 行；切分见 `dataset_stats.json` / `01-数据集分析.md`。

