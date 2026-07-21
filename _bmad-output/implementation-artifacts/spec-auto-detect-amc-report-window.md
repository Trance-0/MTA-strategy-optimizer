---
title: 'AMC MTA 根据新增数据自动识别窗口并输出'
type: 'feature'
created: '2026-07-21'
status: 'done'
baseline_commit: '5c677248b76e4ab11f04f9703c6001f0620a581a'
context:
  - '{project-root}/modules/amc_mta/docs/amc-data-requirements.md'
  - '{project-root}/modules/amc_mta/docs/usage.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** 正式流水线仍读取固定日期；新增 AMC 事件和 Ads 数据后需要改配置。

**Approach:** 以 Ads 最早至最晚 `reportDate` 为权威窗口。程序自动校验、构建路径并输出，用户只需更新输入文件后运行一个命令。

## Boundaries & Constraints

**Always:** 默认读取现有 events/Ads CSV，也允许 CLI 指定文件。窗口首尾包含并支持任意长度、跨年和闰日；Ads 日期必须连续，每日触点及账户/市场/币种一致。路径与五份模型结果全部成功后统一发布，失败保留旧结果。正式流程不依赖固定日期且不覆盖原始输入。

**Ask First:** 改用事件日期或输入交集推断；允许日期缺口、多账户或窗口外转化；自动监听、增量合并或改变输出 schema。

**Never:** 不静默裁剪或补零，不发布空路径/部分结果，不改变归因、可靠性或 14 天规则；不读取、哈希、移动或修改 `log.md`。

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|---|---|---|---|
| 正常新增 | Ads 连续、事件有效 | 自动采用 Ads 首尾日期并输出六份派生产物 | N/A |
| 任意窗口 | 单日、跨年或闰日 | 输出窗口匹配输入，无需改配置 | N/A |
| Ads 无效 | 空、坏日期、缺日、重复键日期或多范围 | 不生成 | `ValueError`，旧输出不变 |
| 事件无效 | 空、无转化、越界转化或零有效路径 | 不裁剪、不发布 | `ValueError`，旧输出不变 |

</frozen-after-approval>

## Code Map

- `modules/amc_mta/run_pipeline.py` -- 正式入口、自动窗口和原子发布。
- `modules/amc_mta/scripts/build_amc_path_report.py` -- 使用推断窗口构建路径。
- `modules/amc_mta/scripts/validate_data_alignment.py` -- Ads 窗口与覆盖预检。
- `modules/amc_mta/src/amc_path_builder.py` -- 转化窗口边界。
- `modules/amc_mta/tests/` -- 数据驱动与失败保护测试。

## Tasks & Acceptance

**Execution:**
- [x] `validate_data_alignment.py` -- 增加窗口推断，验证日期连续、键日期唯一和单一范围。
- [x] `build_amc_path_report.py` -- 正式流程取消固定窗口；CLI 默认从 Ads 推断；零路径不覆盖旧文件。
- [x] `run_pipeline.py` -- 增加可复用运行函数和 CLI 文件参数；临时区验证后发布。
- [x] `amc_path_builder.py` -- 窗口外 conversion 明确失败，保留 14 天和不复用规则。
- [x] `tests/` -- 覆盖任意窗口、坏/缺日期、空数据、越界转化、零路径、配置解耦和原子保护。
- [x] `README.md`、模块文档 -- 记录更新输入后的一键运行方式。

**Acceptance Criteria:**
- Given 有效的新输入，when 运行 `python3 -B modules/amc_mta/run_pipeline.py`，then 无需改代码或配置即可输出匹配窗口的路径和五份结果。
- Given 固定样例日期与输入不同，when 运行正式流程，then 结果只采用输入窗口。
- Given 输入校验失败，when 流程退出，then 已发布六份派生产物逐字节不变。

## Spec Change Log

## Design Notes

Ads 提供每日成本网格，是窗口权威；事件可能合法包含窗口前触点，不能用事件最早日期或输入交集推断。

## Verification

实际结果：99/99 测试通过；默认输入自动识别 `2026-01-01` 至 `2026-12-31`；
六份派生产物连续两次 SHA-256 一致；17/17 触点、365 天和单一范围对齐通过。

**Commands:**
- `python3 -B -m unittest discover -s modules/amc_mta/tests -p 'test*.py'` -- expected: 全部通过。
- `python3 -B modules/amc_mta/run_pipeline.py` 连跑两次 -- expected: 自动显示窗口且六文件哈希稳定。
- `python3 -B modules/amc_mta/scripts/validate_data_alignment.py` -- expected: 窗口、范围、触点和每日覆盖一致。
- `git diff --check` -- expected: 无格式错误，`log.md` 未进入变更。

## Suggested Review Order

**正式入口与发布**

- 数据驱动入口串联自动窗口、临时构建和六文件统一发布。
  [`run_pipeline.py:151`](../../modules/amc_mta/run_pipeline.py#L151)

- 目标旁暂存支持跨文件系统，并在发布失败时恢复旧结果。
  [`run_pipeline.py:32`](../../modules/amc_mta/run_pipeline.py#L32)

**输入契约**

- Ads 日期网格决定窗口，并严格校验连续性和每日触点集合。
  [`validate_data_alignment.py:86`](../../modules/amc_mta/scripts/validate_data_alignment.py#L86)

- 独立路径入口在写入前完成窗口推断和完整数据对齐。
  [`build_amc_path_report.py:28`](../../modules/amc_mta/scripts/build_amc_path_report.py#L28)

- 窗口外转化明确失败，避免新增数据被静默裁剪。
  [`amc_path_builder.py:189`](../../modules/amc_mta/src/amc_path_builder.py#L189)

**失败保护测试**

- 空数据、越界转化和零路径均保持六份旧产物不变。
  [`test_auto_report_window.py:179`](../../modules/amc_mta/tests/test_auto_report_window.py#L179)

- 输入别名与嵌套输出路径在执行前被拒绝。
  [`test_auto_report_window.py:309`](../../modules/amc_mta/tests/test_auto_report_window.py#L309)
