---
title: '统一用户事件驱动的 AMC MTA 模拟数据链路'
type: 'refactor'
created: '2026-07-29'
status: 'done'
baseline_commit: '80389bf2832032dadd2b8fa24044441cf014967c'
context:
  - '{project-root}/modules/amc_mta/data/simulated/README.md'
  - '{project-root}/modules/mta_strategy_recommender/docs/model-plan.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** AMC 概念事件与 Amazon Ads 日报目前独立模拟，Keyword、SKU、Campaign、Ad Group 也没有共同底层来源，无法证明策略证据和 MTA 路径来自同一批行为。

**Approach:** 新增仅供本地模拟的用户事件主表；AMC 概念事件、路径、Ads 日报、触点实体聚合和五份归因结果全部由它确定性生成。样例约90天、主表不超过20,000行，同时保留17个五段式触点和现有MTA算法契约。

## Boundaries & Constraints

**Always:** 主表一行一个合成用户事件，包含用户、journey、时间、事件类型、五段触点、历史 Campaign/Ad Group、适用的 Keyword/Match Type/Target/SKU/ASIN、成本和结果；用户可有多个事件和journey。用户ID不得进入下游产物，不适用的产品实体字段允许为空，所有动态指标必须可回溯和对账。

**Ask First:** 若必须改变17触点、五段键、正式路径schema、五份归因输出schema或Markov/Shapley逻辑，暂停并征得批准。

**Never:** 不实现策略或预算推荐；不声称真实AMC可导出用户级明细；不推断未观察候选效果；不把Campaign Group预算、候选资格、容量或平台政策混入行为主表；不覆盖既有无关变更。

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|---|---|---|---|
| 完整再生成 | 固定种子和报告窗口 | 原子发布主表、三类聚合、路径及五份MTA输出；重复运行字节一致 | 任一步失败全部回滚 |
| 未转化journey | 有触点、结果未转化 | 保留Null路径和实体观察，购买与收入为0 | 不得丢弃用户 |
| 产品字段不适用 | SD/DSP无Keyword，SP/SB有Keyword/Match Type | 空字段合法且聚合键稳定 | 非法组合拒绝生成 |
| 隐私或对账失败 | 用户ID泄露或上下游不守恒 | 不发布任何新产物 | 返回明确校验错误 |

</frozen-after-approval>

## Code Map

- `modules/amc_mta/config.py` -- 新文件路径和统一窗口。
- `modules/amc_mta/src/synthetic_event_pipeline.py` -- 生成、校验主表并派生AMC事件、Ads和实体聚合。
- `modules/amc_mta/src/simulated_touchpoints.py` -- 保留17触点并补充历史实体映射。
- `modules/amc_mta/scripts/regenerate_simulated_dataset.py` -- 十项产物的归因、对账和原子发布。
- `modules/amc_mta/tests/test_amc_mta_end_to_end.py` -- 跨层守恒、隐私、确定性和回滚测试。
- `modules/amc_mta/data/simulated/`、`modules/amc_mta/docs/` -- 重建样例并更新边界说明。

## Tasks & Acceptance

**Execution:**
- [x] `config.py`、`simulated_touchpoints.py` -- 固定文件契约、范围、实体映射和生成约束。
- [x] `synthetic_event_pipeline.py`、旧生成脚本 -- 实现唯一主表和三类派生器，兼容现有脚本入口。
- [x] `regenerate_simulated_dataset.py` -- 原子生成十项产物，发布前执行隐私和守恒校验。
- [x] `tests/` -- 替换旧精确规模断言，覆盖多事件用户、未转化、产品空值、17触点、字节复现及十文件回滚。
- [x] 模拟CSV、归因输出、文档和工作区清单 -- 再生成并同步说明。

**Acceptance Criteria:**
- Given 任一下游动态指标，when 追溯来源，then 可通过确定性聚合回到主表且总量守恒。
- Given 完整再生成两次，when 比较十项产物，then 字节一致且主表不超过20,000行。
- Given 聚合与归因产物，when 扫描内容，then 不含用户ID，17触点及现有输出schema不变。
- Given 完整回归，when 运行AMC MTA与策略层测试，then 路径、归因、治理和层级校验全部通过。

## Spec Change Log

## Design Notes

主表是模拟历史事实，不是生产输入。未来候选池、总预算、四个Campaign和容量规则仍由策略模块提供。AMC概念事件按相同路径模板聚合多个用户journey，所以其中的`journey_id`表示匿名群组，不是用户ID。

“总量守恒”按字段的业务口径解释：曝光、点击和成本在主表与Ads之间精确守恒；
Ads购买与销售只对14天内存在有效末次点击的结果子集守恒；实体表的`assisted_*`
是可重叠的参与量，不能跨实体求和，而`reported_*`遵循同一末次点击口径。路径与
归因输出则分别对`converted_users`、`purchase_count`和`revenue`的AMC路径总量守恒。

## Verification

**Commands:**
- `python3 -B modules/amc_mta/scripts/regenerate_simulated_dataset.py`
- `python3 -B modules/amc_mta/scripts/validate_data_alignment.py`
- `python3 -m unittest discover -s modules/amc_mta/tests -p 'test_*.py'`
- `python3 -m unittest discover -s modules/mta_strategy_recommender/tests -p 'test_*.py'`
- `git diff --check`

## Suggested Review Order

**统一事实源**

- 从一个确定性用户事件表驱动全部动态指标。
  [`synthetic_event_pipeline.py:285`](../../modules/amc_mta/src/synthetic_event_pipeline.py#L285)

- 在发布前统一校验来源、派生、隐私和守恒。
  [`synthetic_event_pipeline.py:975`](../../modules/amc_mta/src/synthetic_event_pipeline.py#L975)

**派生语义**

- 将用户journey聚合成不含用户ID的AMC概念事件。
  [`synthetic_event_pipeline.py:623`](../../modules/amc_mta/src/synthetic_event_pipeline.py#L623)

- Ads日报使用14天内最后有效点击承接结果。
  [`synthetic_event_pipeline.py:738`](../../modules/amc_mta/src/synthetic_event_pipeline.py#L738)

- 实体表连接触点与历史Keyword、SKU及广告层级。
  [`synthetic_event_pipeline.py:827`](../../modules/amc_mta/src/synthetic_event_pipeline.py#L827)

**发布边界**

- 十项产物在全部校验成功后一次性原子发布。
  [`regenerate_simulated_dataset.py:57`](../../modules/amc_mta/scripts/regenerate_simulated_dataset.py#L57)

- 独立白名单锁定获批的17个五段触点。
  [`simulated_touchpoints.py:102`](../../modules/amc_mta/src/simulated_touchpoints.py#L102)

**验证与说明**

- 端到端测试独立重算成本、末次点击和隐私边界。
  [`test_amc_mta_end_to_end.py:114`](../../modules/amc_mta/tests/test_amc_mta_end_to_end.py#L114)

- 数据说明明确各指标的可加性与对账口径。
  [`README.md:1`](../../docs/zh/datasets/amc-simulated-data.md#L1)

- 配置固定来源路径、90天窗口和模拟隐私门槛。
  [`config.py:9`](../../modules/amc_mta/config.py#L9)
