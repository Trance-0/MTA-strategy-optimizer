# AMC MTA 提交入口

基于 Amazon Marketing Cloud（AMC）匿名聚合路径的归因流程。默认示例从本地概念事件生成区分曝光与点击的聚合路径，再运行 Markov、Shapley，并按五段互动键关联 Amazon Ads 指标与成本，计算 ROI、ROAS 和 CPA。

> `amc_touchpoint_events_sample.csv` 只用于演示路径构建；真实 AMC 应在 clean room 内处理事件，只导出满足隐私门槛的聚合结果。

本模块只用于归因分析，不承担预算分配、投放优化或自动执行。

## 从这里开始

- [完整使用说明](docs/amc-mta-complete-guide.md)：范围、输入、路径、模型、指标、可靠性、运行、排错与 Demo。
- [数据流流程图](docs/assets/amc-mta-data-flow.png)：独立 PNG 图像；可编辑源文件为 [SVG](docs/assets/amc-mta-data-flow.svg)。
- [正式输出索引](docs/output-reference.md)：五份 CSV 的阅读顺序、粒度、字段与解释边界。
- [提交清单](SUBMISSION_MANIFEST.md)：必交、选交、不提交内容和验收状态。
- [当前文档索引](docs/README.md)：模块事实源与专题说明。

## 快速运行

在项目根目录执行：

```bash
python3 -B modules/amc_mta/run_pipeline.py
python3 modules/amc_mta/scripts/validate_data_alignment.py
```

更新 events 与 Amazon Ads 输入文件后直接运行即可。正式流程以 Ads 中最早至最晚
`reportDate` 自动确定窗口，支持任意长度、跨年和闰日，不需要修改配置日期。
聚合路径与五份模型结果全部验证成功后才统一发布；失败时保留上一批六份派生产物，
且不会覆盖原始输入。自定义文件位置和完整校验规则见[运行方式](docs/usage.md)。

默认正式输出：

```text
modules/amc_mta/outputs/attribution/amc_markov_attribution_results.csv
modules/amc_mta/outputs/attribution/amc_shapley_attribution_results.csv
modules/amc_mta/outputs/attribution/amc_mta_model_comparison_touchpoints.csv
modules/amc_mta/outputs/attribution/amc_mta_model_comparison_summary.csv
modules/amc_mta/outputs/attribution/amc_mta_recommended_attribution.csv
```

前两份是两个模型各自的五字段主结果；后三份分别提供“触点数 × 3 个 outcome”的
诊断、三个 outcome 的整体摘要，以及同样“触点数 × 3”的归因推荐记录。当前全年
样例为 17 个触点，所以诊断和推荐各 51 行。三份双模型产物
均直接给出“计算有效、数据支撑充分、模型一致”三个布尔值及二元可靠性结果；
三项全真才是 `RELIABLE`。摘要分别 AND 聚合同一 outcome 全部触点的三个布尔
值；整体比较状态和其他差异指标只作诊断。当前样例为
`51 RELIABLE / 0 UNRELIABLE`。

推荐表新增 `recommended_value`：非零 outcome 的可靠记录直接使用 Markov
`official_share`，不可靠记录使用 Markov 与 Shapley share 的升序闭区间
`[low,high]`；零 outcome 保持为空。推荐表因此为 15 列，其他输出 schema 不变。

当前没有滚动窗口稳定性证据，因此现有结果仍只能解释为当前窗口的探索性归因，
不能表述为长期稳定贡献或因果增量。稳定性和自动决策约束不参与可靠性计算，也
不会因 `RELIABLE` 自动开放预算执行。

首次审阅建议按“本页 → [完整使用说明](docs/amc-mta-complete-guide.md) →
[正式输出索引](docs/output-reference.md) → [提交清单](SUBMISSION_MANIFEST.md)”阅读。

## 文档

- [数据契约](docs/amc-data-requirements.md)：字段、14 天路径规则、AMC/Ads 五段键、计费归属和模型语义的唯一完整说明。
- [运行方式](docs/usage.md)：命令、参数和输出。
- [单触点归因可靠性判断](docs/touchpoint-reliability-guide.md)：按计算有效、数据支撑充分、模型一致三个标准判断归因结果。
- [Amazon Ads 样例](docs/amazon-ads-report-sample.md)：成本表及关联键。
- [模拟数据](data/simulated/README.md)：三个样例文件的角色。
- [AMC 背景与数据流](../../docs/research/amazon/amc/README.md)：平台边界与整体链路。
- [项目介绍](../../docs/product/amc-mta/project-introduction.md)：项目目标与边界。

AMC 路径、Amazon Ads 输入和归因输出统一使用 `AD_PRODUCT:FORMAT:PLACEMENT:CREATIVE:INTERACTION_TYPE`，其中 `INTERACTION_TYPE` 只能是 `IMPRESSION` 或 `CLICK`。CPC 成本只归属 CLICK，CPM 成本只归属 IMPRESSION，非计费互动成本为 0。AMC 输入明确区分 `converted_users`（去重购买用户）和 `purchase_count`（订单次数）；完整约束以[数据契约](docs/amc-data-requirements.md)为准。
