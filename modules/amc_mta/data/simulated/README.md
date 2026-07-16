# AMC MTA 模拟数据

此目录包含三个可复现样例：

| 文件 | 用途 |
| --- | --- |
| `amc_touchpoint_events_sample.csv` | 本地路径算法概念输入，覆盖曝光、点击、曝光后点击、乱序、14 天边界、起点拒绝、多购买和 creative 对照 |
| `amc_mta_path_report_raw_sample.csv` | 从事件生成的匿名聚合五段路径，供归因读取 |
| `amazon_ads_report_sample.csv` | 同期 Amazon Ads 风格触点表现和成本；不包含未参与计算的 campaign/ad group 管理字段 |

事件样例不是 AMC 可直接导出的用户级数据。真实 AMC 应在 clean room 内执行路径处理并只导出匿名聚合结果。

AMC 事件、路径和 Amazon Ads 报告统一使用 `AD_PRODUCT:FORMAT:PLACEMENT:CREATIVE:INTERACTION_TYPE` 五段粒度，`INTERACTION_TYPE` 为 `IMPRESSION` 或 `CLICK`。Ads 每个基础广告每日有两个互动行：CPC 成本只归 CLICK，CPM 成本只归 IMPRESSION，非计费行成本为 0，平台转化指标只归 CLICK。报告窗口为 `2026-05-01` 至 `2026-06-30`。完整字段、14 天规则和购买语义见[数据契约](../../docs/amc-data-requirements.md)。

重新生成并校验：

```bash
python3 modules/amc_mta/scripts/generate_simulated_amazon_ads_report.py
python3 modules/amc_mta/run_pipeline.py
python3 modules/amc_mta/scripts/validate_data_alignment.py
```

Ads 生成器按日期和五段触点确定性地产生 61 天数据，不复用月度模板；同一输入每次生成结果一致。
