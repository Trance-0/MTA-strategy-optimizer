---
title: '统一 Campaign Group 顶层业务层级与模拟数据'
type: 'refactor'
created: '2026-07-28'
status: 'done'
baseline_commit: '4dfeb0400f6ce6d025643eb806771d454e962ff1'
context:
  - '{project-root}/modules/mta_strategy_recommender/docs/model-plan.md'
  - '{project-root}/docs/research/campaign-data-hierarchy.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** 当前工作区仍混用以 Ad Product、Campaign 或 ROI 优化为中心的旧话术，现有模拟数据也没有展示新策略模块的业务层级和候选池。

**Approach:** 将现行业务口径统一为 `Campaign Group → Campaign → Ad Group → Keyword/SKU`；`ad_product` 仅作为 Campaign 的单值固有字段。保留 AMC MTA 五段触点契约，在新策略模块新增独立层级模拟数据和校验。

## Boundaries & Constraints

**Always:** Campaign Group 是推荐顶层；样例为 1 个 Group、4 个 Campaign；每个 Campaign 恰有一个 `ad_product`；模型输出 Ad Group 数量、Keyword/SKU 分配和 `INITIAL_SEED`；Keyword/SKU 并列；物理 Group–Campaign N:N 关系不变。

**Ask First:** 若必须改变 AMC MTA 正式 CSV schema、五段触点键、17 触点集合或既有归因输出，暂停并征得批准。

**Never:** 不实现优化器、最高 ROI、因果模型或自动投放；不改变五段键；不重写外部研究或冻结规格；不触碰 `log.md`、`modules/amc_mta.zip`、`docs/系统架构图-07.drawio`。

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|---|---|---|---|
| 标准样例 | 1 Group、4 Campaign、候选池 | Campaign 保存 `ad_product`；输出 Ad Group→Keyword/SKU 与种子 | N/A |
| 层级错误 | Campaign 不是 4 个，或 `ad_product` 缺失/多值 | 不生成推荐 | 返回 Campaign 与字段错误 |
| 候选非法 | 池外对象、`BLOCKED` pair 或笛卡尔积 | 拒绝分配 | 返回非法引用 |
| 无预算基线 | 仅有 MTA 与候选池 | 只输出相对份额 | 输出 warning |

</frozen-after-approval>

## Code Map

- `modules/mta_strategy_recommender/` -- 更新计划，新增层级样例、校验与测试。
- `docs/research/campaign-data-hierarchy.md` -- 重写 Group 顶层关系。
- `README.md`、`modules/README.md`、`docs/*.md`、`docs/research/README.md` -- 更新当前入口、模块状态和目录话术。
- `modules/amc_mta/data/simulated/README.md`、`modules/amc_mta/docs/amazon-ads-report-sample.md` -- 说明两类样例边界。
- `_bmad-output/brainstorming/brainstorming-session-2026-07-28-154111.md`、`docs/workspace-file-inventory.json` -- 标记旧探索并同步清单。

## Tasks & Acceptance

**Execution:**
- [x] 统一现行文档和图示为 Group→Campaign→Ad Group→Keyword/SKU，`ad_product` 仅内嵌在 Campaign。
- [x] 新增一个 Group、四个 Campaign、候选 Keyword/SKU/pair、历史预算与初始推荐的模拟数据。
- [x] 新增校验器和测试，覆盖层级、候选引用、pair、预算守恒与无基线。
- [x] 补充 AMC MTA 样例边界说明，保持其 CSV、代码、五段键和输出不变。
- [x] 更新索引与机器清单并扫描旧话术。

**Acceptance Criteria:**
- Given 任一现行入口，when 阅读业务层级，then Campaign Group 为顶层且 Ad Product 不作为独立层级。
- Given 新样例，when 运行校验，then 4 Campaign、单值 `ad_product`、Ad Group 归属和合法候选全部通过。
- Given 无预算基线，when 检查输出，then 只有相对份额并标记非最优初始点。
- Given AMC MTA，when 运行完整回归，then 五段键、17 触点和正式输出契约不变且测试通过。

## Spec Change Log

## Design Notes

MTA 五段键是归因观察维度，不是业务实体树。新层级样例独立存放；`ad_product` 只在 Campaign 记录中保存，Ad Group 通过 `campaign_id` 继承，避免冲突。

## Verification

**Commands:**
- `python3 modules/mta_strategy_recommender/scripts/validate_simulated_hierarchy.py`
- `python3 -m unittest discover -s modules/mta_strategy_recommender/tests -p 'test_*.py'`
- `python3 -m unittest discover -s modules/amc_mta/tests -p 'test_*.py'`
- 概念残留扫描与 `git diff --check`

## Suggested Review Order

**业务契约与边界**

- 先看模型职责、初始条件、触点证据和预算种子的完整设计。
  [`model-plan.md:3`](../../docs/zh/strategy/model-plan.md#L3)

- 确认 Group 顶层、Campaign 单值属性和物理 N:N 关系。
  [`campaign-data-hierarchy.md:1`](../../docs/research/campaign-data-hierarchy.md#L1)

**数据契约与样例**

- 查看四个 Campaign 的固有 `ad_product` 定义。
  [`campaigns.csv:1`](../../modules/mta_strategy_recommender/data/simulated/campaigns.csv#L1)

- 查看 Group–Campaign 管理范围如何独立表达 N:N 关系。
  [`campaign_group_relationships.csv:1`](../../modules/mta_strategy_recommender/data/simulated/campaign_group_relationships.csv#L1)

- 查看触点证据、候选分配、原因码和预算种子如何落到 Ad Group。
  [`initial_recommendation.json:1`](../../modules/mta_strategy_recommender/data/simulated/initial_recommendation.json#L1)

**校验边界**

- 校验 Group、四个 Campaign、关系表与单值 `ad_product`。
  [`hierarchy_validator.py:97`](../../modules/mta_strategy_recommender/src/hierarchy_validator.py#L97)

- 校验候选池版本、可执行 SKU、pair 和历史预算归属。
  [`hierarchy_validator.py:151`](../../modules/mta_strategy_recommender/src/hierarchy_validator.py#L151)

- 校验 MTA 五段证据、原因码、置信度和非优化状态。
  [`hierarchy_validator.py:204`](../../modules/mta_strategy_recommender/src/hierarchy_validator.py#L204)

- 校验 Keyword/SKU/match pairing 与三级预算守恒。
  [`hierarchy_validator.py:304`](../../modules/mta_strategy_recommender/src/hierarchy_validator.py#L304)

**回归与反例**

- 标准样例、四 Campaign、候选池和无基线行为。
  [`test_hierarchy_validator.py:49`](../../modules/mta_strategy_recommender/tests/test_hierarchy_validator.py#L49)

- 布尔预算、停用 Campaign、不可执行 SKU 和重复分配反例。
  [`test_hierarchy_validator.py:134`](../../modules/mta_strategy_recommender/tests/test_hierarchy_validator.py#L134)

- N:N 关系、触点兼容性和 Match Type 配对反例。
  [`test_hierarchy_validator.py:185`](../../modules/mta_strategy_recommender/tests/test_hierarchy_validator.py#L185)
