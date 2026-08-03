---
title: AMC MTA 模块
lang: zh-CN
---

# AMC MTA 模块

基于 Amazon Marketing Cloud（AMC）匿名聚合路径的归因流程。默认示例先从一份仅供
模拟的用户事件主表派生匿名概念事件、Amazon Ads 日报和实体聚合，再生成区分曝光与
点击的路径，运行 Markov、Shapley，并按五段互动键关联成本和效率指标。

> `synthetic_user_events_sample.csv` 和 `amc_touchpoint_events_sample.csv` 只用于演示
> 数据整合与路径构建；真实 AMC 应在 clean room 内处理事件，只导出满足隐私门槛的聚合结果。

本模块只用于归因分析，不承担预算分配、投放优化或自动执行。

## 从这里开始

- [完整使用说明](complete-guide.md)：范围、输入、路径、模型、指标、可靠性、运行、排错与 Demo。
- [数据流流程图](../../assets/amc-mta/data-flow.png)：独立 PNG 图像；可编辑源文件为 [SVG](../../assets/amc-mta/data-flow.svg)。
- [正式输出索引](output-reference.md)：五份 CSV 的阅读顺序、粒度、字段与解释边界。
- [提交清单](../reference/submission-manifest.md)：必交、选交、不提交内容和验收状态。
- [当前文档索引](reference-index.md)：模块事实源与专题说明。

## 当前实现 <span class="status-label status-verified" aria-label="Verified"></span>

当前实现是一个六阶段确定性流程。下表遵循 `modules/amc_mta/run_pipeline.py` 的实际调用顺序，而不是输出文件的展示顺序。

| 阶段 | 代码入口 | 算法职责 | 独立设置的原因 |
| --- | --- | --- | --- |
| 1. 确定报告窗口 | `infer_ads_report_window()` | 从 Amazon Ads 的 `reportDate` 推导一个首尾均包含的日期窗口 | AMC 路径、Ads 成本和模型输出必须描述同一观察期 |
| 2. 校验并规范化事件 | `_validated_events()` 与 `canonical_amc_touchpoint_key()` | 拒绝格式错误的事件，并构造五段触点键 | 单一键契约可防止归因与成本按不同粒度关联 |
| 3. 构建匿名路径 | `build_aggregated_path_rows()` | 在转化处切分旅程、执行最大间隔规则，并聚合相同路径 | 归因消费匿名聚合数据，而不是用户级事件历史 |
| 4. 运行两个归因模型 | `run_markov_attribution()` 与 `run_shapley_attribution()` | 使用两种不同路径算法分配三个 Outcome | Markov 是正式模型；路径级 Shapley 是结构独立的基准 |
| 5. 关联花费并治理推荐值 | `aggregate_spend_by_touchpoint()`、`result_rows()` 与 `compare_attribution_models()` | 添加效率指标，检验数据支撑和模型一致性，并选择点值或区间 | 归因、成本效率和可靠性是不同计算，必须保持可审计 |
| 6. 发布完整产物集 | `publish_with_rollback()` | 将六份派生产物作为一个可恢复集合整体替换 | 部分失败不能留下来自不同执行批次的路径、模型和推荐文件 |

### 1. 规范化共享触点粒度

`src/touchpoint_key.py` 的键构造代码块，是 AMC 事件、Amazon Ads 行、归因结果和策略交接共同遵守的第一项不变量：

```python
interaction = _component(interaction_type, "interaction_type")       # 1
if interaction not in INTERACTION_TYPES:                              # 2
    raise ValueError(...)                                              # 3
return ":".join((                                                      # 4
    _component(ad_product, "ad_product"),                              # 5
    _component(format_value, "format"),                                # 6
    _component(placement, "placement", allow_missing=True),            # 7
    _component(creative, "creative", allow_missing=True),              # 8
    interaction,                                                       # 9
))
```

| 行 | 详细步骤 | 对数据算法的映射 | 这样实现的原因 |
| --- | --- | --- | --- |
| 1 | 通过 `_component()` 去除首尾空白、转为大写并校验互动文本 | 在比较前规范化键的第五段 | 大小写或首尾空白不能为同一互动制造第二个身份 |
| 2 | 将该段限制为 `IMPRESSION` 或 `CLICK` | 保留后续使用的计费和路径语义 | CPC 与 CPM 的归属依赖该区别；任意值会使成本校验含糊 |
| 3 | 在错误键进入路径或输出前失败 | 在摄取时执行契约 | 静默修复会掩盖上游 schema 错误 |
| 4 | 用 `:` 连接且只连接五个组件 | 建立正式归因粒度 | 固定形状使相等性检查和关联具有确定性 |
| 5-6 | 强制要求广告产品和格式 | 标识广告产品以及库存/广告类型 | 这两个维度在模型中不允许结构性空值 |
| 7-8 | 在规范化键内把缺失 placement 或 creative 转为 `UNSPECIFIED` | 在保持原始结构空值规则独立的同时补全键 | 键不能有空段，但代码不会假装缺失的原始数据曾被观测到 |
| 9 | 追加已经校验的互动类型 | 完成区分曝光/点击的身份 | 即使前四段相同，曝光与点击节点仍然分离 |

对 Amazon Ads 行，`touchpoint_key_from_ads_row()` 还会为 `AMAZON_DSP` 选择 `inventoryType`，为 Sponsored Ads 选择 `adType`，重建预期键并与已存的 `normalizedTouchpoint` 比较。这样成本侧的键是经验证的值，而不是被盲目信任的预计算字符串。

### 2. 在构造路径前校验事件

`_validated_events()` 在聚合任何旅程之前处理每一行：

```python
for row_number, row in enumerate(event_rows, start=2):                 # 1
    missing = [field for field in REQUIRED_FIELDS if ...]              # 2
    event_type = str(row["event_type"]).strip().upper()                # 3
    if event_type == TOUCHPOINT:                                        # 4
        touchpoint = canonical_amc_touchpoint_key(...)                  # 5
    if event_type == CONVERSION:                                        # 6
        users = int(_number(row, "users", integer=True))                # 7
        converted_users = int(_number(row, "converted_users", integer=True)) # 8
        if converted_users > users:                                     # 9
            raise ValueError(...)                                       # 10
    events.append({... "event_time_parsed": _parse_datetime(...), ...}) # 11
```

| 行 | 详细步骤 | 算法映射与原因 |
| --- | --- | --- |
| 1 | 保留 CSV 行号以给出精确错误 | 校验快速失败时必须指出源记录 |
| 2 | 强制要求旅程身份、事件类型和时间戳 | 这些是分组、分支和排序所需的最少字段 |
| 3 | 只规范化一次判别值 | 后续分支比较同一种稳定表示 |
| 4-5 | 从组件列构造触点身份，并拒绝旧的自由格式键 | 路径节点只能经正式五段构造器进入 |
| 6-8 | 将转化计数和金额解析为有限非负值 | Outcome 会成为聚合权重；无效数字不能安全进入求和 |
| 9-10 | 执行 `converted_users <= users` | 一行所代表的去重转化用户不能超过其所代表的用户数 |
| 11 | 在规范化行旁保存 UTC 时间戳 | 排序和间隔计算统一使用一个时间基准，且不修改输入记录 |

同一代码块还执行 `purchase_count >= converted_users`、`new_to_brand_purchases <= purchase_count`，以及“正的购买量、收入或新客购买 Outcome 必须至少有一个转化用户”的规则。这些检查在建模前编码 Outcome 契约，而不是让模型补偿不可能的输入状态。

### 3. 为每个转化分段构造一条合格路径

`build_aggregated_path_rows()` 的核心部分把事件历史映射为路径算法：

```python
for conversion in sorted(conversions, key=lambda event: event["event_time_parsed"]): # 1
    eligible = [event for event in touchpoints                           # 2
                if (previous_conversion_time is None                     # 3
                    or event["event_time_parsed"] > previous_conversion_time)
                and event["event_time_parsed"] <= conversion["event_time_parsed"]] # 4
    previous_conversion_time = conversion["event_time_parsed"]           # 5
    path_events = _contiguous_path(eligible, max_gap)                     # 6
    if not path_events or path_events[0]["event_time_parsed"] <= start_boundary: # 7
        continue
    if conversion["event_time_parsed"] - path_events[-1]["event_time_parsed"] > max_gap: # 8
        continue
    path = " > ".join(event["touchpoint"] for event in path_events)      # 9
```

| 行 | 详细步骤 | 对路径算法的映射 | 这样实现的原因 |
| --- | --- | --- | --- |
| 1 | 按时间顺序处理同一旅程中的转化 | 定义互不重叠的转化分段 | 较早转化必须先为后续转化建立边界 |
| 2-4 | 保留前次转化之后、且不晚于当前转化的触点 | 每个触点最多归入一个转化分段 | 防止复用历史互动来支撑多次购买 |
| 5 | 将分段边界移动到当前转化 | 关闭当前分段 | 下一次循环不能回看本次购买之前的数据 |
| 6 | 排序合格触点，只保留相邻间隔均不超过配置上限的最后一个连续后缀 | 在路径内执行 14 天相邻规则 | 一处旧断点会移除不连通的前缀，但不会丢弃有效的近期后缀 |
| 7 | 拒绝空路径，以及起点等于或早于报告下界的路径 | 执行严格的路径起始窗口 | 完整可观测路径必须从分析窗口内开始 |
| 8 | 对最后触点到转化执行相同最大间隔 | 把终止边也纳入相邻规则 | 只检查触点间隔会放过已过期的最后一次互动 |
| 9 | 使用 ` > ` 序列化有序的正式节点 | 生成 AMC 路径契约 | Markov 保留顺序；Shapley 随后会显式推导唯一集合 |

随后对相同 `(marketplace, advertiser_id, path)` 记录的 `users`、`converted_users`、`purchase_count` 和 `revenue` 求和。收入只在聚合后舍入，并按分组键排序行，因此相同输入会产生相同输出顺序。

### 4. 将路径映射到两个算法

两个模型有意接收同一份已校验聚合数据的不同表示：

| 表示 | 构造方式 | 算法含义 |
| --- | --- | --- |
| 转化用户 Markov 路径 | 一条以 `converted_users` 加权、终止于 `CONVERSION` 的 `START ...` 行，加上一条以 `users - converted_users` 加权、终止于 `NULL` 的行 | 估计最终到达转化与未转化的概率 |
| 购买量和收入 Markov 路径 | 只保留 Outcome 为正的路径，以 `CONVERSION` 结尾，并按所选 Outcome 加权 | 对订单量与收入质量分别运行同一个移除效应网络 |
| Shapley 联盟行 | 将有序路径转为按首次出现顺序排列的唯一触点集合 | 定义路径级一致同意博弈的成员；位置和重复次数有意不改变分配 |

模型内部逐行说明见 [Markov 移除效应](markov.md)与 [Shapley 路径归因](shapley.md)。

### 5. 关联成本并保持输出总量

`aggregate_spend_by_touchpoint()` 重建并校验每个 Amazon Ads 键，执行 `CPC -> CLICK` 与 `CPM -> IMPRESSION`，并在同一五段粒度聚合花费。`result_rows()` 拒绝输出没有匹配花费的模型触点。

序列化前，`_rounded_with_residual()` 使用最大余数法：

1. 把每个非负原始值缩放为整数输出单位；
2. 对每个值向下取整；
3. 舍入原始总量，得到目标单位数；
4. 按小数余数从大到小分配剩余单位，并使用确定性的并列规则；
5. 除以缩放因子。

因此，即使每一行必须独立舍入，展示的 share 和 attributed amount 仍保持展示总量守恒。

### 6. 比较模型并选择交接值

对每个触点和三个 Outcome，`compare_attribution_models()` 执行以下代码级序列：

```python
gap_pp, relative_gap = _decimal_gap_metrics(markov_share, shapley_share) # 1
support = support_five[touchpoint]                                       # 2
reliability = reliability_fields(                                       # 3
    calculation_valid=True,                                             # 4
    data_support_sufficient=data_support_is_sufficient(support),         # 5
    models_consistent=models_are_consistent(gap_pp, relative_gap, ...),  # 6
)
recommended_value = _recommended_value(row, has_outcome=has_outcome)     # 7
```

| 行 | 详细步骤 | 这样实现的原因 |
| --- | --- | --- |
| 1 | 使用保留精度的十进制 share 计算绝对百分点差和基于均值的相对差 | 可靠性不能因输出列为展示而舍入发生变化 |
| 2 | 取得完整触点的原始唯一路径数、转化用户数和购买量支撑 | 支撑是源数据的证据，不是模型分配结果的证据 |
| 3-6 | 同时要求计算有效、全部支撑阈值通过，以及两个一致性阈值通过 | 契约暴露三个独立布尔条件，只有全部为真才标记 `RELIABLE` |
| 7 | 可靠时返回正式 Markov share；否则返回有序的 Markov-Shapley 区间 | 下游得到一个经治理的点值，或一个明确的敏感性范围 |

总量为零的 Outcome 保持为空，因为没有 Outcome 质量时，规范化归因推荐没有定义。

### 7. 使用回滚进行原子发布

`run_pipeline()` 在一个临时目录中构建路径报告和全部五份归因产物。随后 `publish_with_rollback()` 在目标旁暂存副本、备份现有目标，并用 `os.replace()` 逐一替换。如果任何替换失败，已替换文件按相反顺序恢复。该设计把六文件快照作为一个整体保护：校验成功时全部发布；模型、校验或 I/O 失败时，先前发布的集合保持不变。

## 快速运行

从仓库根目录执行：

```bash
python3 -B modules/amc_mta/run_pipeline.py
python3 -B modules/amc_mta/scripts/validate_data_alignment.py
```

更新 events 与 Amazon Ads 输入文件后直接运行即可。正式流程以 Ads 中最早至最晚
`reportDate` 自动确定窗口，支持任意长度、跨年和闰日，不需要修改配置日期。
聚合路径与五份模型结果全部验证成功后才统一发布；失败时保留上一批六份派生产物，
且不会覆盖原始输入。自定义文件位置和完整校验规则见[运行方式](../environment/amc-mta-usage.md)。

默认正式输出：

```text
modules/amc_mta/outputs/attribution/amc_markov_attribution_results.csv
modules/amc_mta/outputs/attribution/amc_shapley_attribution_results.csv
modules/amc_mta/outputs/attribution/amc_mta_model_comparison_touchpoints.csv
modules/amc_mta/outputs/attribution/amc_mta_model_comparison_summary.csv
modules/amc_mta/outputs/attribution/amc_mta_recommended_attribution.csv
```

前两份是两个模型各自的五段主结果；后三份分别提供“触点数 × 3 个 outcome”的
诊断、三个 outcome 的整体摘要，以及同样“触点数 × 3”的归因推荐记录。当前90天
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

首次审阅建议按“本页 → [完整使用说明](complete-guide.md) →
[正式输出索引](output-reference.md) → [提交清单](../reference/submission-manifest.md)”阅读。

## 文档

- [数据契约](../datasets/amc-data-contract.md)：字段、14 天路径规则、AMC/Ads 五段键、计费归属和模型语义的唯一完整说明。
- [运行方式](../environment/amc-mta-usage.md)：命令、参数和输出。
- [单触点归因可靠性判断](reliability.md)：按计算有效、数据支撑充分、模型一致三个标准判断归因结果。
- [Amazon Ads 样例](../datasets/amazon-ads-sample.md)：成本表及关联键。
- [模拟数据](../datasets/amc-simulated-data.md)：用户事件主表及四类派生产物的角色。
- AMC 平台背景研究与项目管理材料属于原项目外部资料，不是本独立交付包的运行依赖，
  也不随 `amc_mta/` 提交。

AMC 路径、Amazon Ads 输入和归因输出统一使用 `AD_PRODUCT:FORMAT:PLACEMENT:CREATIVE:INTERACTION_TYPE`，其中 `INTERACTION_TYPE` 只能是 `IMPRESSION` 或 `CLICK`。CPC 成本只归属 CLICK，CPM 成本只归属 IMPRESSION，非计费互动成本为 0。AMC 输入明确区分 `converted_users`（去重购买用户）和 `purchase_count`（订单次数）；完整约束以[数据契约](../datasets/amc-data-contract.md)为准。
