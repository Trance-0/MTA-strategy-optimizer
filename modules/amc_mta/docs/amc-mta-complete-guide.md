# AMC MTA 完整使用说明

本文是 AMC MTA 提交审阅和本地演示的一站式入口。模块只做当前报告窗口内的
探索性多触点归因，不做因果增量测量、预算分配、投放优化或自动执行。

## 1. 能力范围

流程接收 AMC 匿名聚合路径和 Amazon Ads 五段表现/成本，分别计算 Markov 与
Path-level Shapley 的购买用户、订单次数和收入归因，再生成触点比较、outcome
摘要和管理层推荐。Markov 是 `official` 正式展示口径；Shapley 是模型敏感性参照，
两者不平均，也不能互相替代。

真实 AMC 应在 clean room 内完成事件排序、路径构建和隐私聚合，只导出满足隐私
门槛的聚合路径。本地概念事件仅用于演示，不能当作真实 AMC 用户级导出格式。

## 2. 输入与数据位置

默认演示输入位于 [`../data/simulated/`](../data/simulated/README.md)：

- 概念事件：只用于本地构建聚合路径；
- AMC 聚合路径：归因算法的直接输入；
- Amazon Ads 报告：提供逐日五段表现和成本。

一次运行只接受一个 marketplace、广告账户和币种。Ads 日期必须连续、每天的
五段触点集合一致，且日期与触点组合唯一。流程从 Ads 最早和最晚 `reportDate`
自动识别窗口，所以换入新数据后无需修改日期配置。

完整字段、数值关系和对齐条件以[数据契约](amc-data-requirements.md)为准。

## 3. 五段触点与路径规则

统一关联键为：

```text
AD_PRODUCT:FORMAT:PLACEMENT:CREATIVE:INTERACTION_TYPE
```

`INTERACTION_TYPE` 只能是 `IMPRESSION` 或 `CLICK`。两者是独立触点；CPC 成本只
归属点击，CPM 成本只归属曝光，非计费互动成本为 0。

路径从购买前最后触点向前回溯，相邻触点以及最后触点到购买的间隔均不得超过
14 天；正好 14 天有效。首次遇到更长间隔时截断更早触点。回溯后的最早触点必须
严格晚于窗口起点，购买不得晚于窗口终点。同一旅程多次购买时，后一次购买只使用
前一次购买之后的新触点。

## 4. 模型与守恒

Markov 使用路径顺序和转移依赖；Path-level Shapley 对每条路径的唯一触点集合
计算参与贡献，同一路径内重复触点只计一次。两个模型均分别计算：

- `converted_users`：去重购买用户；
- `purchase_count`：订单次数；
- `revenue`：收入。

三套 attributed value 必须分别与 AMC 总量守恒，非零 outcome 的 share 必须为
1。输出还关联 Amazon Ads 表现、成本与效率指标：

```text
ROAS = attributed_revenue / cost
ROI  = (attributed_revenue - cost) / cost
CPA  = cost / attributed_purchase_count
cost_per_converted_user = cost / attributed_converted_users
```

成本为 0 时，ROAS 和 ROI 为空；对应归因订单数或归因购买用户为 0 时，CPA 或
`cost_per_converted_user` 为空，不输出无穷值。

## 5. 可靠性与推荐值

每个 `touchpoint + outcome` 只有在以下三项全部为真时才是 `RELIABLE`：

1. `calculation_valid`：严格 schema、集合、数值和守恒校验通过；
2. `data_support_sufficient`：购买次数至少 30、购买用户至少 20、唯一路径至少 5；
3. `models_consistent`：`gap_pp <= 1.0` 且 `relative_gap <= 0.20`。

`RELIABLE` 只表示当前窗口满足这三项证据标准，不代表因果有效、长期稳定，也不
授权自动预算操作。推荐表中，非零 outcome 的可靠记录使用 Markov
`official_share` 单点；不可靠记录使用两模型 share 的升序闭区间。该区间不是统计
置信区间。零 outcome 的推荐值为空。

详细规则见[可靠性判断](touchpoint-reliability-guide.md)和
[双模型治理规范](model-comparison-governance.md)。

## 6. 运行与整组发布

解压后进入 `amc_mta/` 目录执行：

```bash
cd amc_mta
python3 -B run_pipeline.py
python3 -B scripts/validate_data_alignment.py
```

完整流程先在临时位置生成并校验一份聚合路径和五份正式输出，只有整组六份派生
产物全部成功才发布。输入错误、空路径、校验失败或发布失败时，原始输入不被覆盖，
上一批派生产物保持不变。自定义路径和分步命令见[运行方式](usage.md)。

独立验证模块测试时，不运行流水线，在 `amc_mta/` 目录执行：

```bash
python3 -B -m unittest discover -s tests -p 'test_*.py'
```

预期结果为 106 项测试通过；该命令不会发布或覆盖正式 CSV。

## 7. 输出阅读顺序

建议依次阅读：

1. Markov 主结果，确认正式展示口径；
2. Shapley 主结果，观察模型敏感性；
3. 触点比较，定位差距和支持不足；
4. outcome 摘要，查看整体差异诊断；
5. 推荐表，取得管理展示值或模型范围。

逐文件主键、字段和限制见[正式输出索引](output-reference.md)。

## 8. 常见错误

| 现象 | 常见原因 | 处理 |
| --- | --- | --- |
| 输入立即失败 | 清理后的空/重名表头、缺列、多列、非法数值或旧字段 | 首尾空白可直接容错；其他问题按数据契约修正上游导出 |
| 对齐失败 | 窗口、账户、币种、日期或触点集合不一致 | 先运行对齐校验，确保 Ads 每日完整覆盖 |
| 路径为空 | 没有有效转化、触点间隔超限或窗口起点不合法 | 检查事件类型、时间戳和 14 天规则 |
| 效率指标为空 | 成本为 0，或 CPA 类指标的归因分母为 0 | 保留为空，不复制成本或输出无穷值 |
| 结果不可靠 | 支持量不足或两模型差距超限 | 使用推荐范围并明确当前证据不足 |

任何失败都应修正输入后整组重跑，不手工拼接新旧批次。

## 9. 五分钟 Demo

1. 从模块 [README](../README.md) 说明范围和自动窗口。
2. 展示[数据契约](amc-data-requirements.md)中的五段键和 14 天规则。
3. 运行完整流程与对齐校验。
4. 按[输出索引](output-reference.md)顺序查看五份结果。
5. 用推荐表解释 `official`、`RELIABLE` 和不可靠区间的边界。
6. 用[提交清单](../SUBMISSION_MANIFEST.md)确认核心包与辅助材料边界。

## 10. 限制与后续验证

- 当前没有滚动窗口、重采样或 3/7/14 天敏感性证据；
- 结果不是实验增量、反事实因果或长期稳定贡献；
- 并发发布与强一致读取仍需独立设计；
- 如要用于预算审批或自动化，必须另建治理产物和人工审批机制；
- 新数据上线前应重新完成输入对齐、整组发布、测试和结果解释审阅。
