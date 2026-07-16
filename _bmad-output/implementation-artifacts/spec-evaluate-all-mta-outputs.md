---
title: '全量评估 AMC MTA 双模型输出'
type: 'feature'
created: '2026-07-15'
status: 'done'
baseline_commit: 'NO_VCS'
context:
  - 'modules/amc_mta/docs/model-comparison-governance.md'
  - 'modules/amc_mta/docs/amc-data-requirements.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** 当前只有 Markov 和 Shapley 两份模型结果，尚未将全部触点、三个 outcome、四段父级、成本与效率字段逐项套用治理规则，用户无法获得完整、可审计的差异分类和输出动作。

**Approach:** 新增独立比较模块，将每个五段触点的购买用户、购买次数和收入全部转换为长表评估记录，同时生成整体/父级摘要和管理层推荐文件；把三份新产物接入现有归因流程与原子发布机制。

## Boundaries & Constraints

**Always:** 保留 Markov 为 intended official model、Shapley 为 benchmark；逐触点逐 outcome 计算模型 share、归因值、绝对/相对差距、方向、模型区间、差距等级、父级等级、支持度和效率指标；原始模型输出保持独立；所有 CSV 使用严格无空白表头；当前没有滚动窗口证据时必须标记 `UNVERIFIED/EVIDENCE_UNVERIFIED` 且 `decision_value` 为空；父级支持度从 AMC 路径重新计算，不能对子触点支持度求和。

**Ask First:** 修改已批准的差距阈值、支持度阈值、Markov/Shapley 主从关系、自动预算规则，或新增模型融合逻辑。

**Never:** 默认平均两个模型；将模型区间描述成置信区间；在输入校验、支持度或稳定性未通过时输出自动决策值；静默接受重复触点、集合错位、非有限值、负值或不守恒结果。

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| 完整样例 | 17个匹配触点、3个outcome及AMC路径 | 51行触点评估、五段及四段摘要、51行推荐记录 | N/A |
| 输入错位 | 模型触点集合不同、重复行或模型名错误 | 不发布任何新旧混合产物 | 抛出明确 `ValueError` |
| 非法数值 | share为负数、NaN/Inf或不守恒 | 停止比较 | 指出模型、outcome和违规类型 |
| 零outcome | 两模型同一outcome总量均为0 | 标记 `NO_OUTCOME`，跳过TVD/排名 | 仅一侧为0时校验失败 |
| 零成本 | 触点成本为0 | 保留归因评估，效率指标为空 | 不使用空效率指标判断差距 |
| 稳定性缺失 | 无滚动窗口或重采样证据 | 完整输出差异预判，所有决策值为空 | `decision_status=EVIDENCE_UNVERIFIED` |

</frozen-after-approval>

## Code Map

- `modules/amc_mta/src/model_comparison.py` -- 纯函数校验、支持度、触点/父级指标、排名与状态计算。
- `modules/amc_mta/scripts/compare_attribution_models.py` -- 对已有 Markov/Shapley CSV 执行严格比较的命令行入口。
- `modules/amc_mta/scripts/run_amc_attribution.py` -- 在生成两模型行后生成三份全量评估产物。
- `modules/amc_mta/config.py` -- 三份比较产物文件名常量。
- `modules/amc_mta/run_pipeline.py` -- 将原子发布集合从两份扩展为五份归因产物。
- `modules/amc_mta/tests/test_model_comparison.py` -- 阈值、边界、父级、支持度、排名和错误输入测试。
- `modules/amc_mta/tests/test_amc_mta_end_to_end.py` -- 当前样例精确指标、行数、表头及五文件返回测试。
- `modules/amc_mta/README.md`、`modules/amc_mta/docs/usage.md`、`modules/amc_mta/docs/amc-data-requirements.md` -- 记录命令、文件和字段语义。

## Tasks & Acceptance

**Execution:**
- [x] `modules/amc_mta/src/model_comparison.py` -- 实现无第三方依赖的全量比较与CSV行生成，确保规则单一来源且可单测。
- [x] `modules/amc_mta/scripts/compare_attribution_models.py` -- 实现严格物理表头校验和独立重跑入口。
- [x] `modules/amc_mta/config.py`、`modules/amc_mta/scripts/run_amc_attribution.py`、`modules/amc_mta/run_pipeline.py` -- 生成并原子发布五份产物。
- [x] `modules/amc_mta/tests/test_model_comparison.py`、`modules/amc_mta/tests/test_amc_mta_end_to_end.py` -- 覆盖规则边界和当前样例回归。
- [x] AMC MTA 文档 -- 更新默认输出、状态限制及运行方式。

**Acceptance Criteria:**
- Given 当前17个五段触点，when 运行归因比较，then 每个触点的3个outcome均有且仅有一条评估记录，共51行，推荐文件同样保留51行。
- Given 当前样例，when 生成摘要，then 购买用户/购买次数/收入TVD分别为约9.160%/9.228%/9.821%，排名相关性和Top K与已核对结果一致。
- Given任意触点，when 查看评估行，then 两模型所有share、归因值、成本/表现、对应效率、父级诊断和输出状态均可追溯。
- Given稳定性证据缺失，when 生成推荐文件，then 所有 `decision_value` 为空且禁止自动化。
- Given任一比较或写盘失败，when 运行完整管线，then 已发布产物集合保持原状，不出现部分更新。
- Given重新生成的五份CSV，when读取物理表头，then 字段无首尾空白且结果可确定性复现。

## Design Notes

三份产物分别承担不同职责：`amc_mta_model_comparison_touchpoints.csv` 保存51条完整诊断；`amc_mta_model_comparison_summary.csv` 保存三个outcome在五段和四段粒度的整体指标；`amc_mta_recommended_attribution.csv` 保留全部51条记录并明确是否可决策。当前证据条件下，前两份提供完整分析，第三份只展示 intended Markov 与 benchmark Shapley，不开放决策值。

## Verification

**Commands:**
- `python3 -m unittest discover -s modules/amc_mta/tests -p 'test_*.py'` -- 比较单测和现有回归通过；缺失概念事件样例导致的既有完整路径测试需单独记录。
- `python3 modules/amc_mta/scripts/run_amc_attribution.py` -- 基于现有聚合路径生成两份模型结果和三份评估结果。
- `python3 modules/amc_mta/scripts/compare_attribution_models.py` -- 对已生成模型CSV严格复算并得到同样结果。

**Implementation result (2026-07-15):**
- 42 项比较、归因、键与当前样例定向测试通过；全量 discovery 共执行 75 项，只有 3 个既有错误，均由缺少 `data/simulated/amc_touchpoint_events_sample.csv` 引起。
- 聚合路径归因命令和严格比较命令均成功；五份输出已确定性生成，比较/推荐各 51 行，摘要 6 行。
- 完整 `run_pipeline.py` 在构建路径前因同一概念事件样例缺失而失败；失败发生在临时工作区写入前，未发布部分产物。
- 三层审查发现的集合对齐、逐行守恒、效率公式、零 outcome、父级支持度、严格 CSV 和整组发布问题均已修复并加入回归测试。

## Suggested Review Order

**流程入口与产物生成**

- 从一次归因运行生成两模型和三份治理产物。
  [`run_amc_attribution.py:74`](../../modules/amc_mta/scripts/run_amc_attribution.py#L74)

- 独立严格比较已有模型文件并复现相同结果。
  [`compare_attribution_models.py:77`](../../modules/amc_mta/scripts/compare_attribution_models.py#L77)

**比较、校验与状态治理**

- 集中生成 51 行明细、6 行摘要和 51 行推荐记录。
  [`model_comparison.py:638`](../../modules/amc_mta/src/model_comparison.py#L638)

- 统一验证模型、AMC 范围、集合、守恒和效率关系。
  [`model_comparison.py:325`](../../modules/amc_mta/src/model_comparison.py#L325)

- 计算 TVD、Spearman、Top K 及整体比较状态。
  [`model_comparison.py:578`](../../modules/amc_mta/src/model_comparison.py#L578)

**安全发布**

- 整组暂存、替换和失败回滚避免部分 CSV 更新。
  [`amc_mta_attribution.py:127`](../../modules/amc_mta/src/amc_mta_attribution.py#L127)

- 完整管线将五份归因产物纳入统一发布集合。
  [`run_pipeline.py:109`](../../modules/amc_mta/run_pipeline.py#L109)

**测试与治理文档**

- 验证全部触点、outcome 和决策阻断结果。
  [`test_model_comparison.py:130`](../../modules/amc_mta/tests/test_model_comparison.py#L130)

- 覆盖错位、逐行守恒、效率和范围边界。
  [`test_model_comparison.py:181`](../../modules/amc_mta/tests/test_model_comparison.py#L181)

- 验证多文件发布失败时恢复完整旧集合。
  [`test_model_comparison.py:309`](../../modules/amc_mta/tests/test_model_comparison.py#L309)

- 记录当前正式诊断结果与不可决策原因。
  [`model-comparison-governance.md:661`](../../modules/amc_mta/docs/model-comparison-governance.md#L661)
