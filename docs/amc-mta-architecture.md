# AMC MTA 架构

## 架构结论

当前项目是一个单进程、标准库优先、CSV 驱动的 AMC MTA 批处理模块。其核心价值
不是搭建平台，而是把匿名聚合路径、双模型归因、Amazon Ads 成本和治理诊断做成
可复现、可校验的闭环。

```text
概念事件样例
  │  amc_path_builder
  ▼
匿名聚合五段路径 ───────────────┐
  │                              │
  ├─ Weighted Markov             │ raw support
  └─ Path-level Shapley          │
          │                      │
          ▼                      │
两份五段归因结果 ◀─ Amazon Ads 日报
          │
          ▼
五段触点比较 + 五段摘要 + 治理推荐
```

真实使用时，第一步应在 AMC clean room 内完成。项目只能接收满足隐私门槛的匿名
聚合路径；仓库中的概念事件是测试夹具，不是可导出的真实 AMC 用户明细。

## 组件职责

| 组件 | 职责 |
| --- | --- |
| `src/touchpoint_key.py` | 构造和严格校验五段键；曝光与点击保持独立 |
| `src/amc_path_builder.py` | 事件排序、14 天连续间隔、多购买切段、匿名路径聚合 |
| `src/amc_mta_attribution.py` | 输入校验、Markov、Shapley、Ads 成本聚合、效率指标和原子 CSV 写入 |
| `src/model_comparison.py` | 五段支持度、模型差距、三项可靠性、TVD、排名与治理推荐 |
| `scripts/` | 路径构建、数据生成、归因、独立比较和对齐校验入口 |
| `run_pipeline.py` | 以 Ads 首尾日期自动确定窗口，在临时目录生成完整产物，并在发布失败时恢复旧文件 |
| `tests/` | 锁定字段契约、边界、守恒、严格解析和发布回滚 |

代码目前通过 `sys.path` 注入组织模块，没有 Python package、依赖清单或安装入口。
这对本地 Demo 足够，但不适合被其他服务稳定依赖。

正式入口不使用配置中的模拟日期。用户可以替换默认 events/Ads 文件，或通过 CLI
传入自定义输入、路径报告和输出目录；程序只发布路径报告与五份模型结果，不修改
两份原始输入。Ads 必须形成连续且每日触点一致的日期网格，任何输入或模型失败都
发生在六份派生产物统一发布之前。

## 数据契约

### 五段触点

```text
AD_PRODUCT:FORMAT:PLACEMENT:CREATIVE:INTERACTION_TYPE
```

广告属性段使用大写字母、数字和下划线；缺失 placement/creative 归一为
`UNSPECIFIED`；第五段只能是 `IMPRESSION` 或 `CLICK`。完整键同时用于 AMC 路径、
Amazon Ads 行和模型输出，确保曝光、点击和成本始终独立。

### 三类输入

| 输入 | 当前样例规模 | 角色 |
| --- | ---: | --- |
| 概念事件 | 47 行 | 仅验证本地路径构建 |
| AMC 聚合路径 | 12 行 | 归因算法直接输入 |
| Amazon Ads 日报 | 6,205 行 | 17 个触点 × 365 天的表现和成本 |

一次运行只允许一个 marketplace、advertiser、currency 和报告窗口。AMC 与 Ads
必须具有完全相同的触点集合与逐日覆盖。CPC 成本只能落在 `CLICK`，CPM 成本只能
落在 `IMPRESSION`；非计费互动成本为零。

### 路径构建

- 以 UTC 排序；无时区时间当前按 UTC 解释。
- 相邻触点和最后触点到购买的间隔必须不超过 14 天，正好 14 天有效。
- 首次出现超过 14 天的间隔时截断更早触点，但路径总时长不设上限。
- 最早保留触点必须严格晚于报告起点。
- 同一 journey 多次购买时，后一次购买不复用前一次购买之前的触点。
- 当前只按 `journey_id` 分组，这是生产化前需要修复的范围隔离风险。

## 模型语义

### Markov

项目实现一阶加权 Markov removal effect：

- `converted_users` 模型同时使用 Conversion 与 Null，权重来自购买用户和未购买用户；
- `purchase_count` 与 `revenue` 模型只保留 outcome 为正的路径，并分别以订单数和收入加权；
- 移除触点时，到达该触点的转移改为 Null 并截断；
- 负 removal effect 被截为零；全部 effect 为零时退化为均分。

因此，购买用户结果最接近“转化概率 removal effect”。订单和收入结果更适合解释
为对正 outcome 路径结构的加权贡献分配，不应被表述为独立的订单/收入发生概率。
移除语义、负效应截断和均分退化仍需手算基准与方法评审。

### Path-level Shapley

当前 Shapley 是“路径 unanimity game”的精确闭式解：每条聚合路径的 outcome 在
该路径的唯一触点之间均分，再跨路径求和。重复触点在单条路径内只获得一次份额。

它保留路径参与信息，但不保留顺序和重复频次，也不是基于全部观察联盟估计边际
响应的通用 Shapley 模型。文档和输出中应始终使用 `Path-level Shapley`。

## 输出架构

| 文件 | 行数 | 作用 |
| --- | ---: | --- |
| `amc_markov_attribution_results.csv` | 17 | Markov 五段结果 |
| `amc_shapley_attribution_results.csv` | 17 | Shapley 五段结果 |
| `amc_mta_model_comparison_touchpoints.csv` | 51 | 14 列 share、gap、支持证据与可靠性 |
| `amc_mta_model_comparison_summary.csv` | 3 | 3 outcome × 五段摘要 |
| `amc_mta_recommended_attribution.csv` | 51 | 14 列 Markov 正式值、Shapley 参照值与可靠性 |

两模型分别对购买用户、购买次数和收入守恒。ROI、ROAS、CPA 与每购买用户成本使用
同一五段成本计算；零成本行的效率指标为空。推荐文件不是第三套归因模型，而是治理
视图：当前 Markov 仅作为展示口径，Shapley 作为参照；文件不提供预算决策值或
自动化许可字段。
三份双模型产物另输出计算有效、数据支撑充分、模型一致及其二元可靠性状态；当前
样例为 `51 RELIABLE / 0 UNRELIABLE`。摘要按 outcome 对三个触点级布尔值分别
做 AND；TVD、Spearman、Top-K 重合率只在 13 列摘要中展示，不参与合成。

## 可靠性与测试

当前 99 项测试覆盖：

- 五段键和 CPC/CPM 计费冲突；
- 路径排序、14 天边界、报告起点和多购买不复用；
- 非法指标关系、重复时间戳和保留状态；
- 三个 outcome 的模型守恒和舍入残差；
- 模型集合、成本、窗口、范围和严格 CSV 表头一致性；
- 五段支持度、差距阈值、TVD、Spearman 和 Top K；
- 三项可靠性阈值、固定原因顺序、长尾和零 outcome 边界；
- 多文件发布失败回滚与按文件名匹配。

测试能证明实现符合当前契约，不能独立证明模型具有因果真实性。模拟事件可精确复现
存储路径，主要属于回归夹具，而不是外部正确性证据。

## 实现追踪

| 声明 | 实现 | 主要测试 |
| --- | --- | --- |
| 五段键与 CPC/CPM 归属 | `src/touchpoint_key.py`, `aggregate_spend_by_touchpoint` | `test_touchpoint_key.py` |
| 14 天路径、起点和多购买切段 | `src/amc_path_builder.py` | `test_amc_path_builder.py` |
| Markov/Shapley 语义与守恒 | `src/amc_mta_attribution.py` | `test_amc_mta_attribution.py` |
| 差距、支持度、可靠性与治理阻断 | `src/model_comparison.py` | `test_model_comparison.py` |
| 全流程复现和发布回滚 | `run_pipeline.py`, `scripts/` | `test_amc_mta_end_to_end.py` |

本文核对基线为 `1000bcc` 加本轮可靠性实现；代码、测试、文档和五份输出已按
当前三项可靠性契约同步更新。

## 生产化边界

当前缺少：

- 可执行的 AMC 查询模板、隐私阈值和查询版本管理；
- 真实窗口历史、促销/季节切片和数据快照版本；
- 滚动窗口、3/7/14 天敏感性和合适的重采样稳定性；
- 进程锁或版本目录/manifest 的强一致发布；
- currency 进入 AMC 路径契约及金额 `Decimal` 计算；
- package、依赖锁定、CI 和生产监控；
- 因果增量实验或校准。

这些缺口不影响 Demo 的可运行性，但阻止它成为自动预算或生产归因服务。
