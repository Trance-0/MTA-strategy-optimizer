---
title: '将 MTA 策略样例与 AMC 证据逐条对齐'
type: 'refactor'
created: '2026-07-30'
status: 'done'
baseline_commit: '883f7e6'
context:
  - '{project-root}/modules/mta_strategy_recommender/docs/strategy-output-contract.md'
  - '{project-root}/modules/amc_mta/data/simulated/README.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** 当前策略样例只在 Group、Campaign 和触点名称上对齐；候选实体、SD/DSP 定向、MTA 数值和预算仍是手写或错误映射。

**Approach:** 冻结 `modules/amc_mta/`，以推荐归因和实体聚合为只读事实源，重构策略输入、预期输出和校验器，生成平台适配且可复算的六组初始策略。

## Boundaries & Constraints

**Always:** 保留一个 Group、四个 Campaign 和 `2/2/1/1` 六个 Ad Group；SP/SB 可原生使用 Keyword/Match Type/SKU，SD/DSP 只原生使用 SKU/Target/Audience；预算按三类 outcome 对六个入选触点归一化并披露 `17 → 6` 口径；历史与推荐 Ad Group ID 不要求相同。

**Ask First:** 修改 AMC、五段键/归因 schema、四个 Campaign、六组数量或预算归一化范围前暂停确认。

**Never:** 不重生成 AMC，不实现优化器/自动投放/因果模型，不伪造补充候选的历史证据，不要求输入预算等于历史花费，不碰受保护文件。

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|---|---|---|---|
| 标准对齐 | 两输入、夹具、两张 AMC 表 | 4 Campaign、6 Ad Group 和预算通过 | 返回摘要 |
| 历史候选 | `HISTORICAL` | 实体及广告产品范围在 AMC 中存在 | 否则拒绝 |
| 补充候选 | `VALIDATED`/探索 | 只作非直接证据的策略信号 | 冒充原生历史则拒绝 |
| 数据漂移 | SHA、范围、MTA 值、Target 或预算变化 | 不接受对齐声明 | 精确报错 |

</frozen-after-approval>

## Code Map

- `modules/mta_strategy_recommender/data/simulated/*.json` -- AMC 血缘、候选证据和策略约束。
- `modules/mta_strategy_recommender/tests/fixtures/expected_initial_recommendation.json` -- 六组真实证据与预算初始点。
- `modules/mta_strategy_recommender/src/hierarchy_validator.py` -- 跨模块血缘、实体、平台和预算校验。
- `modules/mta_strategy_recommender/scripts/validate_simulated_hierarchy.py` -- 连接现有 AMC 表。
- `modules/mta_strategy_recommender/tests/test_hierarchy_validator.py` -- 正反例与 AMC 不变回归。

## Tasks & Acceptance

**Execution:**
- [x] 两输入 JSON -- 增加 `mta_source`；拆分候选证据、角色和政策，补 Match Type、广告产品范围及信号规则。
- [x] 推荐夹具 -- 使用真实 AMC 数值和实体；采用 `native_targets/strategy_signals/pairings`；保存选点范围、分数和预算。
- [x] validator、CLI、tests -- 校验 SHA/范围、MTA 值、历史实体、平台字段和预算，覆盖关键篡改与无预算场景。
- [x] README、契约和派生清单 -- 同步当前 schema、边界和命令。

**Acceptance Criteria:**
- Given 当前 AMC，when 校验，then 摘要确认 17 触点、34 实体行、6 Ad Group、8 历史 Pair和预算来源。
- Given `HISTORICAL` 候选或原生定向，when 回查，then存在同 Campaign/触点且字段一致的 AMC 行。
- Given SD/DSP，when 校验，then Keyword 只作信号，SKU/Target/Audience 与 AMC 一致。
- Given权重和六个触点，when复算，then composite score、份额和金额一致并守恒。
- Given完整回归，when验收，then AMC 相对 `883f7e6` 无变化，107 项 AMC 测试和策略测试通过。

## Spec Change Log

- 2026-07-30：完成 AMC 只读对齐；审查后收紧单实体基数、候选资格和平台边界。

## Design Notes

同一触点有多条实体时，按 `assisted_revenue` 降序选择同 Campaign 未重复的可执行组合；这是确定性初始点，不是实体级 MTA 或因果贡献。预算口径固定为 `SELECTED_RECOMMENDED_TOUCHPOINTS`。

## Verification

**Commands:**
- `python3 -B modules/mta_strategy_recommender/scripts/validate_simulated_hierarchy.py`
- `python3 -B -m unittest discover -s modules/mta_strategy_recommender/tests -p 'test_*.py'`
- `python3 -B -m unittest discover -s modules/amc_mta/tests -p 'test_*.py'`
- `git diff --exit-code 883f7e6 -- modules/amc_mta`
- `git diff --check -- . ':(exclude)log.md' ':(exclude)docs/系统架构图-07.drawio'`

## Suggested Review Order

**证据对齐与选择**

- 从入口理解 AMC 血缘、候选和预算的完整校验链。
  [`hierarchy_validator.py:181`](../../modules/mta_strategy_recommender/src/hierarchy_validator.py#L181)

- 输入冻结 AMC 文件、范围及 17→6 选择口径。
  [`strategy_request.json:5`](../../modules/mta_strategy_recommender/data/simulated/strategy_request.json#L5)

- 候选池区分历史、验证、政策和平台适用性。
  [`candidate_pool.json:115`](../../modules/mta_strategy_recommender/data/simulated/candidate_pool.json#L115)

**推荐结果与契约**

- 六组夹具保存真实 MTA 数值、实体和预算份额。
  [`expected_initial_recommendation.json:8`](../../modules/mta_strategy_recommender/tests/fixtures/expected_initial_recommendation.json#L8)

- 数据契约解释平台定向和单实体样例边界。
  [`output-data-contract.md:126`](../../docs/zh/strategy/output-data-contract.md#L126)

**验证与回归**

- 标准验收确认 17、34、6 和八条历史 Pair。
  [`test_hierarchy_validator.py:67`](../../modules/mta_strategy_recommender/tests/test_hierarchy_validator.py#L67)

- 边界测试拒绝追加任何未回查的原生实体。
  [`test_hierarchy_validator.py:267`](../../modules/mta_strategy_recommender/tests/test_hierarchy_validator.py#L267)

- CLI 显式连接两张既有 AMC 事实表。
  [`validate_simulated_hierarchy.py:15`](../../modules/mta_strategy_recommender/scripts/validate_simulated_hierarchy.py#L15)
