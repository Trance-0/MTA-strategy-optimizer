---
title: MTA 驱动的 Ad Group 预算初始化器
lang: zh-CN
---

# MTA 驱动的 Ad Group 预算初始化器

本模块只生成新 Ad Group 的**数量与初始预算**，不生成 Keyword/SKU 分配、Targeting、动作或
策略角色，也不做优化、因果增量判断或自动投放。

```text
候选数量 + 产品容量 → 每个 Campaign 的新 Ad Group 数量
MTA outcome + AMC 实体桥接 → Campaign 预算份额
Campaign 份额 ÷ 匿名新组数量 → 每个 Ad Group 初始预算
```

当前 Campaign Group 固定包含四个 Campaign，每个分别使用 SP、SB、SD、DSP。v4 样例的
真实容量计算结果为 `1/1/1/1`，不是为了保留旧结果而写死。

## 当前实现 <span class="status-label status-verified" aria-label="Verified"></span>

该实现是确定性初始化器，不是学习型优化器。其主函数 `modules/mta_strategy_recommender/src/budget_recommender.py` 中的 `generate_budget_recommendation()` 按以下顺序执行：

| 阶段 | 代码 | 算法职责 | 独立设置的原因 |
| --- | --- | --- | --- |
| 1. 加载对齐证据 | `load_aligned_strategy_inputs()` | 读取请求、候选计数、MTA 推荐和实体 bridge；校验文件、哈希、行数和范围 | 有效分配必须能从所引用的准确 AMC 证据复现 |
| 2. 校验策略契约 | `_campaign_inputs()` | 强制精确 schema、四个已启用产品 Campaign、规范化 Outcome 权重和容量规则 | 意外字段或缺失产品不能静默改变分配全集 |
| 3. 将经治理的 MTA 值转为点值 | `_recommended_point()` | 直接使用可靠点值，或取不可靠区间中点 | 初始化器需要标量，同时明确警告区间已被折叠 |
| 4. 将触点 bridge 到 Campaign | `_bridge_campaign_scores()` | 把五段触点中的广告产品映射到其 Campaign，并验证支撑它的历史实体 | MTA 是触点粒度，但预算决策从 Campaign 粒度开始 |
| 5. 合并 Outcome | `_bridge_campaign_scores()` | 将转化用户、购买量和收入贡献加权为 Campaign MTA 分数 | 三个业务 Outcome 在显式加权前保持分离 |
| 6. 计算组数 | `recommend_ad_group_count()` | 将合格候选计数和产品容量转为最少可行新组数 | 数量是执行容量计算，不是效果预测 |
| 7. 分配初始值 | `generate_budget_recommendation()` | 规范化 Campaign 分数，并在各 Campaign 的匿名新组间等分 | 没有证据可区分同一 Campaign 内未来组的相对表现 |
| 8. 重新生成并校验 | `validate_simulated_hierarchy()` | 拒绝禁止字段，与新生成的确定性结果比较，并检验守恒 | 被检查文件必须完全可复现，且仅含预算内容 |

### 1. 计算前验证证据血缘

命令行生成器首先调用 `src/hierarchy_validator.py` 中的 `load_aligned_strategy_inputs()`。关键证据代码块为：

```python
attribution = _resolve_evidence_path(                               # 1
    attribution_path, source["attribution_file"], "AMC attribution file")
entity = _resolve_evidence_path(                                    # 2
    entity_path, source["entity_file"], "AMC entity file")
if _sha256(attribution) != source["attribution_sha256"]:            # 3
    raise HierarchyValidationError(...)                             # 4
if _sha256(entity) != source["entity_sha256"]:                      # 5
    raise HierarchyValidationError(...)                             # 6
attribution_rows = _read_csv(attribution)                           # 7
entity_rows = _read_csv(entity)                                     # 8
```

| 行 | 详细步骤 | 对算法的映射 | 这样实现的原因 |
| --- | --- | --- | --- |
| 1-2 | 如果显式提供证据路径就解析它，否则使用请求声明的路径 | 选择输入分数的 MTA 与 bridge 快照 | 数据可以位于模块外部，而不依赖仓库相对导入 |
| 3-6 | 将每个文件的 256 位安全散列算法（Secure Hash Algorithm 256-bit，SHA-256）摘要与请求比较 | 将计算锁定到准确的证据字节 | 同名但行内容已改变的文件不能沿用旧血缘标识复现 |
| 7-8 | 完整性通过后才解析证据 | 建立纯推荐器所使用的内存行 | 不从未验证证据计算任何分数 |

加载器随后验证声明的触点与实体行数、报告窗口、marketplace、advertiser、Campaign Group，以及每条实体记录的 Campaign/广告产品关系。`_campaign_inputs()` 进一步执行精确键校验，要求每个受支持产品恰好有一个已启用 Campaign，要求 Outcome 权重总和为一，并要求候选池使用相同血缘和 `USE_ALL_ELIGIBLE` 策略。

### 2. 将经治理的 MTA 推荐转换为一个标量

归因交接包含可靠点值或不可靠区间。`_recommended_point()` 明确处理两种表示：

```python
status = _required_text(row.get("reliability_status"), ...)          # 1
value = row.get("recommended_value")                                 # 2
if status == "RELIABLE":                                            # 3
    point = _number(value, ...)                                      # 4
    if point > 1.0:                                                  # 5
        raise BudgetRecommendationError(...)
    return point, status                                             # 6
if status != "UNRELIABLE":                                          # 7
    raise BudgetRecommendationError(...)
parts = value[1:-1].split(",")                                      # 8
if len(parts) != 2:                                                 # 9
    raise BudgetRecommendationError(...)
low = _number(parts[0], ...)                                        # 10
high = _number(parts[1], ...)                                       # 11
if low > high or high > 1.0:                                       # 12
    raise BudgetRecommendationError(...)
return (low + high) / 2.0, status                                  # 13
```

| 行 | 详细步骤 | 算法映射与原因 |
| --- | --- | --- |
| 1-2 | 将可靠性和推荐值作为耦合契约读取 | 不知道它是点还是区间，就不能解释数字字符串 |
| 3-6 | 将可靠推荐校验为不超过一的非负 share，再原样使用 | 可靠 AMC 行指定 Markov 为正式点估计 |
| 7 | 拒绝任何未知治理状态 | 初始化器不为未定义状态虚构行为 |
| 8-9 | 拆分方括号内容并要求恰好两个字段 | 保持 AMC MTA 输出的精确双端点区间形状 |
| 10-12 | 解析非负数字端点，要求升序，并限制高端点不超过一 | 保证区间是有效归因 share 范围 |
| 13 | 使用算术中点作为已披露的代表点 | 初始值需要确定性标量；结果记录 `UNRELIABLE_MTA_RANGE_MIDPOINT_USED` |

中点只是当前实现政策，并不证明中心比端点更可能。未来优化器可以传播不确定性，但这不属于本初始化器。

### 3. 将触点 bridge 到历史实体和 Campaign

每条 MTA 行使用 `AD_PRODUCT:FORMAT:PLACEMENT:CREATIVE:INTERACTION_TYPE` 键。`_touchpoint_product()` 校验全部五段，并读取第一段，为该广告产品寻找唯一 Campaign。随后 `_bridge_campaign_scores()` 查找同时匹配触点和 Campaign 的历史实体行。

对每个触点和 Outcome，bridge 使用 `_entity_weight_method()` 选择实体加权字段：

```python
assisted_metric = ASSISTED_METRIC_BY_OUTCOME[outcome]                # 1
for metric in (assisted_metric, *BRIDGE_FALLBACK_METRICS):          # 2
    values = [_number(row.get(metric), ...) for row in rows]        # 3
    if sum(values) > 0:                                             # 4
        return metric.upper(), values                               # 5
return "EQUAL", [1.0] * len(rows)                                  # 6
```

| 行 | 详细步骤 | 映射与原因 |
| --- | --- | --- |
| 1 | 选择与 Outcome 匹配的 assisted 指标 | 转化用户、购买和收入应优先使用各自对应的实体证据 |
| 2 | 依次尝试该指标、点击、曝光和唯一用户 | 定义确定性的证据质量回退顺序 |
| 3-4 | 校验非负值并要求总质量为正 | 总量为零的指标无法定义比例 |
| 5 | 返回第一个可用方法和权重 | 记录所选方法以供审计 |
| 6 | 只有所有证据字段质量都不为正时才等权 | 所有匹配历史实体仍可表示，且不会除以零 |

分配代码块是：

```python
denominator = sum(entity_weights)                                   # 1
for entity, value in zip(matching_entities, entity_weights):        # 2
    historical_allocations[entity["ad_group_id"]] += (              # 3
        recommended_value * value / denominator                     # 4
    )
allocated = sum(historical_allocations.values())                    # 5
if not math.isclose(allocated, recommended_value, abs_tol=1e-12):   # 6
    raise BudgetRecommendationError(...)                            # 7
outcome_contributions[campaign_id][outcome] += allocated            # 8
```

| 行 | 详细步骤 | 算法映射 | 这样实现的原因 |
| --- | --- | --- | --- |
| 1 | 汇总所选 bridge 权重 | 建立触点内规范化分母 | 触点 MTA 值必须守恒 |
| 2-4 | 按所选指标比例把推荐值分配到匹配历史 Ad Group | 验证具体的触点到实体 bridge | 历史实体证据建立 Campaign 归属，但不会直接成为未来组的分数 |
| 5-7 | 重新汇总，并以 `1e-12` 容差与原推荐值比较 | 检验局部守恒 | 缺失或重复的 bridge 分配必须终止运行 |
| 8 | 将守恒的触点值汇总到其 Campaign 和 Outcome | 生成 Campaign 评分所需粒度 | 历史拆分可审计，但当前输出创建匿名新组，不复用历史组 ID |

全部行处理完后，函数还要求每个触点包含全部三个 Outcome、每个实体触点都存在于归因中，并要求每个 Outcome 的 `recommended_value` 总量为一。这些检查保证 Campaign 贡献形成完整分配全集。

### 4. 将三个 Outcome 合并为 Campaign 分数

对 Campaign $c$，代码计算：

$$
\text{Campaign MTA score}(c)
= \sum_{o \in \{\text{converted users},\text{purchase count},\text{revenue}\}}
\text{Outcome weight}(o)\times\text{Campaign contribution}(c,o)
$$

对应代码有意保持简短：

```python
contributions = outcome_contributions[campaign_id]                  # 1
score = sum(                                                        # 2
    weights[outcome] * contributions[outcome]                       # 3
    for outcome in OUTCOMES                                         # 4
)
```

| 行 | 详细步骤 | 原因 |
| --- | --- | --- |
| 1 | 取得 Campaign 三个分别守恒的贡献 share | 保持源 Outcome 在输出中可检查 |
| 2-4 | 每个 share 乘以请求中的显式权重，再将乘积相加 | 这是异构业务 Outcome 唯一合并之处；权重使该选择可见且可复现 |

推荐器拒绝非正的 Campaign 总分，因为这种分数无法规范化为预算 share 分布。

### 5. 推导最少可行新 Ad Group 数量

`recommend_ad_group_count()` 使用向上取整除法：

```python
def _ceil_ratio(count, capacity):                                   # 1
    return 0 if count == 0 else (count + capacity - 1) // capacity  # 2
```

第 1 行定义一种候选类型需要多少容器。第 2 行在没有候选时返回零，否则执行整数向上取整；即使最后一个组未填满，也需要完整组槽位。

对 SP 和 SB，关键容量代码块为：

```python
capacity_counts = {                                                 # 1
    "keyword_capacity_count": _ceil_ratio(                          # 2
        counts["eligible_keyword_unit_count"], keyword_capacity
    ),
    "sku_capacity_count": _ceil_ratio(                              # 3
        counts["eligible_sku_count"], sku_capacity
    ),
    "legal_pair_capacity_count": _ceil_ratio(                       # 4
        counts["eligible_legal_pair_count"], pair_capacity
    ),
    "target_capacity_count": 0,                                    # 5
    "audience_capacity_count": 0,                                  # 6
}
capacity_required = max(min_groups, *capacity_counts.values())      # 7
```

对 SD 和 DSP，第 2、4 行换成 target 和 audience 的向上取整比率，同时 keyword 和 legal-pair 计数必须为零。第 7 行取最大值，是因为全部容量约束必须同时满足：最紧的维度决定组数，并受 `min_ad_groups` 下限约束。如果结果超过 `max_ad_groups`，则不可行并抛出错误，而不是静默截断。

Campaign 最低可执行预算随后为：

$$
\text{Minimum required daily budget}(c)
= \text{Recommended group count}(c)
\times \text{Minimum daily budget per group}(c)
$$

该最低值只用于可行性检查，不改变基于分数的初始分配。

### 6. 规范化 Campaign 分数并在 Campaign 内拆分

`generate_budget_recommendation()` 的主分配代码块为：

```python
score_total = sum(                                                   # 1
    bridge[campaign["campaign_id"]]["campaign_mta_score"]
    for campaign in campaigns
)
campaign_score = bridge[campaign_id]["campaign_mta_score"]          # 2
campaign_share = campaign_score / score_total                       # 3
campaign_budget = campaign_share * (total_budget or 0.0)            # 4
group_share = campaign_share / count                                # 5
for position in range(1, count + 1):                                # 6
    slot_id = f"{campaign_id}_NEW_AG_{position:02d}"                 # 7
    ad_group = {"budget_seed_share": group_share}                   # 8
    ad_group["initial_daily_budget"] = (                            # 9
        group_share * (total_budget or 0.0)
    )
```

| 行 | 详细步骤 | 算法映射 | 这样实现的原因 |
| --- | --- | --- | --- |
| 1 | 汇总四个 Campaign MTA 分数 | 定义 Campaign 规范化全集 | 当前 Campaign Group 是完整预算全集 |
| 2-3 | 读取一个 Campaign 分数并除以总分 | 将异构加权分数转换为总和为一的 share | 分配只依赖相对分数 |
| 4 | 应用可选的 Group 日预算 | 将 share 转为货币 | 未提供总预算时，模块只返回相对 share |
| 5 | 将 Campaign share 除以容量推导的组数 | 在 Campaign 内实现等分 | 当前数据没有匿名未来组相对表现的证据 |
| 6-7 | 创建确定性的新槽位标识，并拒绝与历史 ID 冲突 | 表示拟议组，而不假装它们已经存在 | 历史 bridge 实体与新执行槽位必须保持分离 |
| 8-9 | 同时保存比例初始值，以及可计算时的货币初始值 | 支持有无预算基准的下游使用 | 两种单位都暴露同一守恒关系 |

如果 Campaign 基于分数的预算低于计算出的最低值，代码保留该初始值，但标记 `INSUFFICIENT_BUDGET_FOR_MINIMUMS`；不会从其他 Campaign 抢预算，也不会声称方案可执行。未提供 Group 预算时，输出 `BUDGET_BASELINE_NOT_PROVIDED` 并省略货币字段。

### 7. 重新生成结果并验证守恒

`validate_simulated_hierarchy()` 不只校验 JSON 形状。它从已验证输入重新生成预期结果，递归查找第一个类型、字段、长度或值差异，并拒绝任何不能完全确定性复现的输出。它还递归拒绝禁止的策略字段，因此 budget-only 结果不能混入 targeting 或 activation 内容。

最终不变量代码块验证：

```text
sum(group_shares) == campaign_share                                 # 1
sum(group_budgets) == campaign_budget                              # 2
sum(campaign_shares) == 1.0                                        # 3
sum(campaign_budgets) == budget_seed_total                          # 4
```

第 1、2 行保证每个 Campaign 分配在其新组间守恒；第 3、4 行保证完整 Campaign Group 在比例和货币单位上守恒。实现使用 `math.fsum()` 和显式绝对容差，以容纳浮点表示，同时拒绝实质漂移。

### 当前交付

- `strategy_request.json`：Group 范围、四个 Campaign、AMC 血缘、outcome 权重、容量和最低预算；
- `candidate_pool.json`：每个 Campaign 的合格候选计数，不保存具体候选 ID；
- `budget_recommender.py`：数量、AMC bridge、Campaign 分数和匿名组等分的单一纯函数；
- `outputs/initial_budget_recommendation.json`：确定性生成的正式预算结果，也是测试唯一基准；
- budget-only 确定性校验器；
- AMC 文件只读，`assisted_*` 只在触点内部作为分摊权重。

可靠 MTA 行使用推荐单点；不可靠 `[low,high]` 行只取中点作为可披露的初始预算代表值。

## 运行

```bash
python3 -B modules/mta_strategy_recommender/scripts/generate_initial_budget.py --check-output
python3 -B modules/mta_strategy_recommender/scripts/validate_simulated_hierarchy.py
python3 -B -m unittest discover -s modules/mta_strategy_recommender/tests -p 'test_*.py'
```

不带 `--check-output` 时，生成器把结果写到标准输出，方便下游另行保存。旧
`--check-fixture` 参数仍是兼容别名；当前文档和新调用统一使用 `--check-output`。

## 文档

- [整体模型计划](model-plan.md)
- [当前 Ad Group 初始预算计算详解](current-budget-calculation.md)
- [MTA 到 Ad Group 预算问题定义与研究计划](optimization-plan.md)
- [输出数据契约](output-data-contract.md)
- [预算策略输出契约](strategy-output-contract.md)
- [模拟输入说明](../datasets/strategy-simulated-data.md)
- 正式初始预算结果：`modules/mta_strategy_recommender/outputs/initial_budget_recommendation.json`
