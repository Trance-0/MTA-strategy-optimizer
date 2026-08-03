---
title: AMC MTA 模拟数据
lang: zh-CN
---

# AMC MTA 模拟数据

本目录的动态指标统一来自一份仅供本地演示的用户事件主表：

```text
synthetic_user_events_sample.csv
├── amc_touchpoint_events_sample.csv
│   └── amc_mta_path_report_raw_sample.csv
├── amazon_ads_report_sample.csv
└── amc_touchpoint_entity_aggregate_sample.csv
```

| 文件 | 用途 |
| --- | --- |
| `synthetic_user_events_sample.csv` | 唯一模拟事实源；一行一个合成用户的触点或结果事件 |
| `amc_touchpoint_events_sample.csv` | 按相同路径模板聚合后的匿名概念事件，供本地路径构建 |
| `amc_mta_path_report_raw_sample.csv` | 从匿名概念事件生成的五段聚合路径，供归因读取 |
| `amazon_ads_report_sample.csv` | 从主表逐日聚合的五段表现、平台末次点击结果和成本 |
| `amc_touchpoint_entity_aggregate_sample.csv` | 触点与历史 Campaign/Ad Group/Keyword/SKU 的隐私安全聚合关联 |

样例窗口为 `2026-01-01` 至 `2026-03-31`，共90天。主表包含11,147条事件、
2,400个合成用户和3,547个journey；派生645条匿名概念事件、153条唯一路径、
1,530条Ads日数据和34条实体聚合。用户可拥有多个journey；未转化journey也保留，
用于形成Null路径。实体聚合要求至少5个合成用户，但这只是本地模拟门槛，不代表
Amazon的实际隐私阈值。

`synthetic_user_id`只能存在于主表，不得进入任何聚合或归因产物。真实应用不应取得
或导出这类用户级CSV，而应在AMC clean room内完成事件处理，只接收满足平台隐私
要求的聚合结果。

五类数据统一使用 `AD_PRODUCT:FORMAT:PLACEMENT:CREATIVE:INTERACTION_TYPE`
五段触点。CPC成本只归CLICK，CPM成本只归IMPRESSION；非计费互动成本为0，平台
购买和销售由每个journey最后一个符合条件的CLICK派生。历史Keyword/SKU是观察事实，
不等同于策略模块冻结的未来候选池。

对账按指标语义执行：曝光、点击和成本在主表与Ads聚合间精确守恒；Ads购买和销售
只等于14天窗口内存在有效末次点击的结果子集，不等于主表全部转化；实体表的
`assisted_*`表示某实体参与过的journey，同一结果可以支持多个实体，因此不能跨实体
相加。实体表的`reported_*`仍遵循末次点击规则；本样例没有因隐私门槛隐藏实体组，
所以实体表曝光、点击和成本也与主表精确对齐。

重新生成并校验：

```bash
python3 -B modules/amc_mta/scripts/regenerate_simulated_dataset.py
python3 -B modules/amc_mta/scripts/validate_data_alignment.py
```

完整再生成会原子发布十项产物；任一步失败都回滚，固定输入可字节级复现。
