---
title: '将 AMC MTA 模拟数据扩展为完整一年'
type: 'feature'
created: '2026-07-21'
status: 'done'
baseline_commit: 'e820a3080eb488b87c0f93b979d0e4e8b814e920'
context:
  - '{project-root}/modules/amc_mta/docs/amc-data-requirements.md'
  - '{project-root}/modules/amc_mta/data/simulated/README.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** 当前模拟数据只覆盖 2026-05-01 至 2026-06-30；只延长 Ads 日期会留下两个月 AMC 路径，不能形成真实的一年数据支撑。

**Approach:** 将默认窗口改为完整自然年 `2026-01-01` 至 `2026-12-31`，新增确定性 AMC 事件生成器，让 12 个月都产生不同路径，并重建三份输入和五份归因产物。

## Boundaries & Constraints

**Always:** 年度数据包含 365 个日期、每天固定 17 个 Ads 五段触点；AMC 每月包含 12 类路径模板和 13 次 conversion，全年触点集合仍精确为同一 17 个键。事件、Ads、路径和输出可重复生成；14 天间隔、起点拒绝、多 conversion 不复用、单一 US/`adv_demo_001`/USD 范围保持。单模型 `18/18` 列、双模型 `14/13/14` 列及 `17/17/51/3/51` 输出行数不变。可靠性结果必须按全年证据重算，不预设沿用两月结论。

**Ask First:** 改为滚动 365 天而非 2026 自然年、增加或删除触点、改变路径规则/模型/可靠性门槛、引入随机不可复现数据、改变公开输出 schema。

**Never:** 不只扩 Ads 而保留两月 AMC；不机械复制完全相同路径字符串；不通过复制旧输出伪造年度结果；不把模拟数据描述为真实 AMC 证据；不读取、哈希、移动或修改 `log.md`。

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| 完整生成 | 2026 自然年 | 520 条事件、144 条聚合路径、6205 条 Ads 数据 | N/A |
| 单日/区间 Ads | 年内任意子区间 | 与全年文件同日期切片逐字节语义一致 | N/A |
| 边界夹具 | 1 月 1 日起点、14 天加 1 秒 | 两条 journey 均被路径构建拒绝 | 不进入正式路径 |
| 非法日期区间 | 起点晚于终点 | 不覆盖旧样例 | `ValueError` |

</frozen-after-approval>

## Code Map

- `modules/amc_mta/config.py` -- 默认年度窗口。
- `modules/amc_mta/scripts/generate_simulated_amazon_ads_report.py` -- 365 天 Ads 生成与共享触点目录。
- `modules/amc_mta/scripts/generate_simulated_amc_touchpoint_events.py` -- 新增年度事件、路径轮换和季节权重生成器。
- `modules/amc_mta/scripts/build_amc_path_report.py`, `modules/amc_mta/run_pipeline.py` -- 从年度输入确定性重建路径和五份输出。
- `modules/amc_mta/tests/` -- 年度规模、边界、复现、守恒、可靠性和回滚验证。

## Tasks & Acceptance

**Execution:**
- [x] `config.py`、两个生成器 -- 实现 2026 全年窗口、有序共享 17 触点目录和月度唯一事件；生成器均原子写入。
- [x] `data/simulated/*.csv`、`outputs/attribution/*.csv` -- 从生成器和 pipeline 全量重建八份正式 CSV，不手工改派生值。
- [x] `tests/` -- 覆盖 520 事件、146 journey、12 conversion 月份、144 唯一路径、6205 Ads、年度切片一致、边界拒绝、守恒、schema、可靠性和双跑。
- [x] 当前文档与派生状态 -- 更新全年日期、规模、结果基准、生成命令、扫描报告和工作区清单；历史完成规格不改写。

**Acceptance Criteria:**
- Given 年度生成器，when 连续运行两次，then 三份输入与五份输出逐字节一致且无部分发布。
- Given 年度事件，when 构建路径，then 12 个月均有 conversion、形成 144 条路径、覆盖精确 17 个触点且两条拒绝 journey 不出现。
- Given 年度 Ads，when 检查日期和触点，then 365 天每天恰有 17 行，任意子区间与独立生成结果一致。
- Given 完整 pipeline，when 检查结果，then模型守恒、数据对齐、精简 schema 和 17/17/51/3/51 行数保持，可靠性计数与全年重算一致。

## Spec Change Log

## Design Notes

每月使用同一 12 类业务路径结构，但按固定步长轮换有序触点目录，避免路径字符串重复；conversion 位于每月 20–24 日，触点间隔取 9/5/2 天。月度整数指标用确定性分配，收入按分处理。Ads 波动应使用自然年绝对日序，使全年切片与单独生成相同日期得到一致值。

## Verification

实际结果：520 事件、146 journey、158 conversion（144 次入模、12 次因无新增触点
不复用、2 次边界拒绝）、144 条唯一聚合路径、6205 Ads；归因总量
3316/4185/343161；51/51 触点结果与 3/3 摘要为 RELIABLE。91 项测试、
八文件双跑哈希、独立 compare、365 天对齐、schema/守恒和清单检查均通过。

**Commands:**
- `python3 -B -m unittest discover -s modules/amc_mta/tests -p 'test*.py'` -- expected: 全部通过。
- `python3 -B modules/amc_mta/scripts/regenerate_simulated_dataset.py` 连跑两次 -- expected: 八份 CSV 哈希稳定。
- `python3 modules/amc_mta/scripts/validate_data_alignment.py` -- expected: 17 个触点、365 天、单一范围一致。
- schema、行数、守恒、可靠性、清单与 `git diff --check`（排除 `log.md`）-- expected: 0 failures。

## Suggested Review Order

**全集发布边界**

- 先暂存并验证全部八份产物，再统一发布并支持整体回滚。
  [`regenerate_simulated_dataset.py:38`](../../modules/amc_mta/scripts/regenerate_simulated_dataset.py#L38)

**共享触点与年度生成**

- 单一结构化目录同时约束 AMC 事件键和 Ads 指标参数。
  [`simulated_touchpoints.py:14`](../../modules/amc_mta/src/simulated_touchpoints.py#L14)

- 精确 17 键校验阻止目录漂移被静默发布。
  [`simulated_touchpoints.py:104`](../../modules/amc_mta/src/simulated_touchpoints.py#L104)

- 固定 epoch 生成全年 Ads，保证独立子区间完全一致。
  [`generate_simulated_amazon_ads_report.py:45`](../../modules/amc_mta/scripts/generate_simulated_amazon_ads_report.py#L45)

- 月度模板轮换均衡首触点，并保留拒绝与不复用夹具。
  [`generate_simulated_amc_touchpoint_events.py:32`](../../modules/amc_mta/scripts/generate_simulated_amc_touchpoint_events.py#L32)

**验证与防回归**

- 逐 journey 验证 144 次入模、12 次不复用和两次拒绝。
  [`test_amc_mta_end_to_end.py:90`](../../modules/amc_mta/tests/test_amc_mta_end_to_end.py#L90)

- 模拟第五次发布失败，验证八个旧文件全部恢复。
  [`test_amc_mta_end_to_end.py:549`](../../modules/amc_mta/tests/test_amc_mta_end_to_end.py#L549)
