# AMC MTA

基于 Amazon Marketing Cloud（AMC）匿名聚合路径的归因流程。默认示例从本地概念事件生成区分曝光与点击的聚合路径，再运行 Markov、Shapley，并按五段互动键关联 Amazon Ads 指标与成本，计算 ROI、ROAS 和 CPA。

> `amc_touchpoint_events_sample.csv` 只用于演示路径构建；真实 AMC 应在 clean room 内处理事件，只导出满足隐私门槛的聚合结果。

## 快速运行

在项目根目录执行：

```bash
python3 modules/amc_mta/run_pipeline.py
python3 modules/amc_mta/scripts/validate_data_alignment.py
```

默认输出：

```text
modules/amc_mta/outputs/attribution/amc_markov_attribution_results.csv
modules/amc_mta/outputs/attribution/amc_shapley_attribution_results.csv
modules/amc_mta/outputs/attribution/amc_mta_model_comparison_touchpoints.csv
modules/amc_mta/outputs/attribution/amc_mta_model_comparison_summary.csv
modules/amc_mta/outputs/attribution/amc_mta_recommended_attribution.csv
```

前两份是两个模型各自的五段主结果；后三份分别提供 51 行五段触点/outcome
诊断、三个 outcome 的五段整体摘要，以及 51 行管理层推荐记录。当前没有滚动
窗口稳定性证据，因此推荐记录的 `decision_status` 为
`EVIDENCE_UNVERIFIED`、`decision_value` 为空，不可用于自动预算。

## 文档

- [数据契约](docs/amc-data-requirements.md)：字段、14 天路径规则、AMC/Ads 五段键、计费归属和模型语义的唯一完整说明。
- [运行方式](docs/usage.md)：命令、参数和输出。
- [Amazon Ads 样例](docs/amazon-ads-report-sample.md)：成本表及关联键。
- [模拟数据](data/simulated/README.md)：三个样例文件的角色。
- [AMC 背景与数据流](../../docs/research/amazon/amc/README.md)：平台边界与整体链路。
- [项目介绍](../../docs/product/amc-mta/project-introduction.md)：项目目标与边界。

AMC 路径、Amazon Ads 输入和归因输出统一使用 `AD_PRODUCT:FORMAT:PLACEMENT:CREATIVE:INTERACTION_TYPE`，其中 `INTERACTION_TYPE` 只能是 `IMPRESSION` 或 `CLICK`。CPC 成本只归属 CLICK，CPM 成本只归属 IMPRESSION，非计费互动成本为 0。AMC 输入明确区分 `converted_users`（去重购买用户）和 `purchase_count`（订单次数）；完整约束以[数据契约](docs/amc-data-requirements.md)为准。
