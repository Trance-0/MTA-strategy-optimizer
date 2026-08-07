---
title: 数据集
description: MTA-SIM 契约、本项目输入和兼容性边界
lang: zh-CN
---

# 数据集

本页采用 [Trance-0/MTA-SIM-dataset 数据契约](https://github.com/Trance-0/MTA-SIM-dataset/blob/main/ZheyuanWu/docs/DATA_CONTRACT.md)和[生成流程](https://github.com/Trance-0/MTA-SIM-dataset/blob/main/ZheyuanWu/docs/dataset-creation/generation-flow.md)的文档分类方式，并说明它与本仓库当前输入的差异。

## MTA-SIM 的三张逻辑表 <span class="status-label status-external" aria-label="External"></span>

| 表 | 用途 | 训练边界 |
| --- | --- | --- |
| `amc_path_report` | 聚合、有序的客户路径和观察到的 Outcome | 主要路径归因输入 |
| `amazon_ads_daily_touchpoint_performance` | 每日触点投放、成本和平台报告结果 | 可选特征、诊断或报表输入 |
| `simulation_ground_truth` | 模拟器已知的触点移除增量和信用份额 | **仅评估，禁止作为训练特征** |

路径表的购买与 Ads 表的平台报告购买不能相加；它们是不同语义的 Outcome。

## 本仓库当前输入 <span class="status-label status-verified" aria-label="Verified"></span>

| 文件 | 粒度 | 作用 |
| --- | --- | --- |
| `amc_mta_path_report_raw_sample.csv` | 聚合路径 | Markov 与 Shapley 输入 |
| `amazon_ads_report_sample.csv` | 日期 × 触点 | 成本和诊断指标 |
| `amc_touchpoint_entity_aggregate_sample.csv` | 触点 × 投放实体 | 从触点桥接到 Campaign/历史 Ad Group |
| `amc_mta_recommended_attribution.csv` | 触点 × Outcome | 策略初始化器的归因输入 |
| `strategy_request.json` | Campaign Group 请求 | 总预算、Outcome 权重和容量规则 |
| `candidate_pool.json` | Campaign 候选计数 | 计算新 Ad Group 数量 |

## 为什么两边的模拟结果不能直接兼容 <span class="status-label status-verified" aria-label="Verified"></span>

两边的路径表列名目前一致，但触点契约不同：

| 项目 | MTA-SIM | 本仓库当前 AMC MTA |
| --- | --- | --- |
| 标准化触点 | 四段：`AD_PRODUCT:FORMAT:PLACEMENT:CREATIVE` | 五段：再加入 `INTERACTION_TYPE` |
| Ads 特有字段 | 含 `unitsSold` | 含 `interaction_type`、`cost_type`，不含 `unitsSold` |
| 曝光/点击表达 | 聚合在四段触点表现中 | 作为触点键的第五段明确区分 |
| 策略 Bridge | 不在三张核心表内 | 需要额外实体聚合表 |

因此，“来自相同源代码思想”不等于“拥有相同 Schema”。若直接把四段触点路径交给要求五段键的实现，路径与表现表的连接键会失败，也无法确定 `IMPRESSION` 或 `CLICK`。

## 推荐的适配方式 <span class="status-label status-recommendation" aria-label="Recommendation"></span>

建立显式 Dataset Adapter：

1. 校验输入版本和列顺序；
2. 由真实字段生成 `INTERACTION_TYPE`，不得默认猜测；
3. 将 `unitsSold` 保留为可选诊断字段，而不是强行映射；
4. 生成本项目需要的实体 Bridge；
5. 在完整数据包验证通过后再运行归因；
6. 把 `simulation_ground_truth` 隔离到评估流程。

这使两张生成表可以用于预测与归因验证，同时保持 Ground Truth 作为“答案表”的独立性。
