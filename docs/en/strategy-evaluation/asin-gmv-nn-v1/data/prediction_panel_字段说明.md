# prediction_panel.csv 字段说明（SK-II · Extended 27）

| 项 | 内容 |
|----|------|
| 版本 | v1.5 |
| 文件 | `prediction_panel.csv` |
| 粒度 | marketplace × date |
| 行数 | 424 |
| 模型输入维 | **27** |

## 键与切分

`date`, `country`, `product`(=SK-II), `split`, `is_synthetic`

## 预算 / 流量 / 标签

`budget_*`, `share_*`, `cost`, `impressions_*`, `clicks`, `revenue`/`gmv_ad`, `sales_ad`，及对应 `log1p_*`

## P0 结构列（进模型）

| 列 | 含义 |
|----|------|
| `share_cost_top_of_search` … `share_cost_dsp_unspecified_creative` | 花费结构占比 |
| `n_placement_types` | placement 种类数 |

## 进模型

输入：`log1p_budget_*` + `share_*` + `has_ad` + `is_weekend` + `dow` + `country` + **P0 结构 8 列**  
主标签：`log1p_revenue`  
辅助：`log1p_impressions_*`, `log1p_sales_ad`
