---
title: Shapley 路径归因
description: AggregatedShapleyAttribution 的算法、公式和代码映射
lang: zh-CN
---

# Shapley 路径归因

## 模型直觉 <span class="status-label status-verified" aria-label="Verified"></span>

Shapley Value 源自合作博弈论，用所有可能加入顺序中的平均边际贡献分配团队收益。本项目实现的是一个更具体的 **Path-level Unanimity Game**：一条聚合路径的 Outcome 只有在该路径全部唯一触点都存在时才可获得。

如需了解 Shapley Value 在广告归因中的应用，可阅读 [Shapley Value Methods for Attribution Modeling in Online Advertising](/research/mta/Shapley%20Value%20Methods%20for%20Attribution%20Modeling%20in%20Online%20Advertising.pdf)。

在这种价值函数下，精确 Shapley Value 有闭式解：一条路径的 Outcome 在该路径的唯一触点之间等分。

## 当前实现 <span class="status-label status-verified" aria-label="Verified"></span>

实现位置：`modules/amc_mta/src/amc_mta_attribution.py` 中的 `AggregatedShapleyAttribution` 类。下面直接重现相关代码块，并逐行拆解。

代码分为四步：把有序路径适配为联盟、定义联盟价值、应用精确闭式解，以及把得分转换为份额和归因总量。

### 1. 将一条路径转换为一个联盟

`amc_rows_to_shapley_rows()` 适配每条已校验的 AMC 聚合：

```python
for idx, row in enumerate(amc_rows, start=1):                         # 1
    touchpoints = unique_touchpoints(                                 # 2
        validate_amc_aggregated_row(row, idx)                         # 3
    )
    rows.append({                                                     # 4
        "channels": ",".join(touchpoints),                            # 5
        "converted_users": safe_int(row.get("converted_users")),      # 6
        "purchase_count": safe_int(row.get("purchase_count")),        # 7
        "revenue": safe_float(row.get("revenue")),                    # 8
    })
```

| 行 | 详细步骤 | 算法映射 | 这样实现的原因 |
| --- | --- | --- | --- |
| 1 | 遍历聚合时保留稳定行标识 | 使校验错误可以追溯到输入行 | 适配器必须在错误联盟进入模型前失败 |
| 2 | 每个触点只保留首次出现 | 将有序路径转为类似集合的联盟 | 在一致同意博弈中，成员身份才重要；重复曝光不是第二个参与者 |
| 3 | 执行路径、终止状态、键和 Outcome 不变量 | 建立有效的博弈记录 | 模型不能给无效状态或保留状态分配价值 |
| 4-5 | 将唯一成员序列化为 `channels` | 提供该类的联盟输入 | 这个名称把无序成员关系与有序 AMC `path` 区分开 |
| 6-8 | 独立携带每个 Outcome | 在同一批联盟上创建三个博弈 | 人、购买和金额分别分配，永远不会相加 |

`unique_touchpoints()` 保留首次出现顺序，使序列化具有确定性；但评分算法把结果视为联盟。因此路径顺序和曝光次数不会影响一行的分配。

### 2. 定义联盟价值

实现保留 `coalition_value()`，用它明确界定博弈：

```python
members = set(coalition)                                             # 1
return sum(                                                          # 2
    safe_float(row.get(outcome_field))                               # 3
    for row in self.rows                                             # 4
    if set(parse_channels(str(row["channels"]))).issubset(members)   # 5
)
```

| 行 | 详细步骤 | 对 Shapley 博弈的映射 | 原因 |
| --- | --- | --- | --- |
| 1 | 把待评估联盟转成成员集合 | 移除无关顺序 | 合作博弈中的联盟是参与者集合 |
| 2-4 | 对合格路径博弈的选定 Outcome 求和 | 定义价值 `v(S)` | 每条聚合贡献自己的收益质量 |
| 5 | 只有当路径全部唯一触点都存在时才纳入 | 实现一致同意博弈 | 路径收益不能被其成员的部分子集取得 |

用符号表示，实现的价值函数为：

$$
v(S) = \sum_p \text{path outcome}(p)\,
\mathbf{1}\!\left[U_p \subseteq S\right]
$$

其中 $U_p$ 是路径 $p$ 的唯一触点集合。

### 3. 应用精确闭式解

因为总博弈是一组一致同意博弈之和，`_scores()` 不需要枚举所有子集或排列：

```python
scores = {touchpoint: 0.0 for touchpoint in self.touchpoints}        # 1
for row in self.rows:                                               # 2
    touchpoints = tuple(dict.fromkeys(                              # 3
        parse_channels(str(row["channels"]))
    ))
    if not touchpoints:                                             # 4
        continue
    outcome = safe_float(row.get(outcome_field))                    # 5
    per_touchpoint_credit = outcome / len(touchpoints)              # 6
    for touchpoint in touchpoints:                                  # 7
        scores[touchpoint] += per_touchpoint_credit                  # 8
return scores                                                       # 9
```

| 行 | 详细步骤 | 算法映射 | 这样实现的原因 |
| --- | --- | --- | --- |
| 1 | 将每个已观测参与者初始化为零 | 创建完整且确定性的结果域 | 即使某个 Outcome 总量为零，触点仍保留在结果中 |
| 2 | 将每条聚合视为一个加权的一致同意子博弈 | 使用 Shapley 可加性 | 博弈之和的 Shapley Value 等于各博弈 Shapley Value 之和 |
| 3 | 防御性去重，同时保留首次出现 | 定义该行的唯一成员 | 即使绕过适配器，也能保护等分逻辑 |
| 4 | 跳过空联盟 | 避免除以零 | 有效 AMC 路径通常不会触发此分支，但该类独立使用时仍安全 |
| 5 | 只读取调用者指定的 Outcome | 让同一机制运行三个不同度量 | Outcome 类型保持分离 |
| 6 | 在全部联盟成员间等分该行收益 | 应用一致同意博弈的精确 Shapley Value | 每个成员在该子博弈中都是必要且对称的 |
| 7-8 | 累加成员在全部路径博弈中的信用 | 使用 Shapley 可加性 | 触点最终得分包含它出现过的每条路径 |
| 9 | 返回未规范化的归因质量 | 在计算 share 前保持 Outcome 总量 | 调用者可同时暴露金额和份额 |

因此，如果路径 $p$ 的唯一触点集合为 $U_p$，Outcome 为 $y_p$，触点 $t$ 的得分为：

$$
\text{Shapley score}(t)
= \sum_{p: t \in U_p}
\frac{\text{path outcome}(p)}{|U_p|}
$$

### 4. 生成份额和归因总量

`attribute()` 运行三次 `_scores()`，然后为每个触点构建一条结果：

```python
converted_user_scores = self._scores("converted_users")             # 1
purchase_count_scores = self._scores("purchase_count")              # 2
revenue_scores = self._scores("revenue")                             # 3
total_revenue_score = sum(revenue_scores.values())                   # 4
revenue_share = (                                                    # 5
    revenue_scores[touchpoint] / total_revenue_score                 # 6
    if total_revenue_score > 0 else 0.0                              # 7
)
AttributionResult(                                                   # 8
    revenue_share=revenue_share,                                    # 9
    attributed_revenue=revenue_scores[touchpoint],                  # 10
    ...
)
```

| 行 | 详细步骤 | 算法映射与原因 |
| --- | --- | --- |
| 1-3 | 为三个 Outcome 计算独立的得分向量 | 不使用任何 Outcome 代理另一个 Outcome，也不把它们相加 |
| 4 | 汇总一个得分向量 | Shapley 效率性使它等于输入 Outcome 总量，仅受浮点运算影响 |
| 5-7 | Outcome 总量为正时规范化，否则返回零 | 避免未定义的除法，并正确表示零 Outcome 数据集 |
| 8-10 | 同时输出规范化 share 与原始分配质量 | 使用者可使用比例，审计者可对照源总量验证守恒 |

转化用户与购买量分支使用相同的代码行和保护条件。输出舍入之后由共享的最大余数序列化器处理，因此行格式不会改变模型内部得分。

份额为：

$$
\text{Shapley share}(t)
= \frac{\text{Shapley score}(t)}
{\sum_j \text{Shapley score}(j)}
$$

## 与通用 Shapley 实现的差异 <span class="status-label status-verified" aria-label="Verified"></span>

当前代码没有训练一个预测模型后再枚举所有特征子集，也没有使用 SHAP 软件包。它对明确定义的路径一致性价值函数计算精确闭式解，因此确定性强、总量守恒且容易复算，但同一路径内的触点不会因为位置或时间不同而获得不同信用。

## 如何解释 <span class="status-label status-inference" aria-label="Inference"></span>

Shapley 结果提供一种对路径共同出现关系对称的敏感性参照。它不能自动识别因果顺序、预算饱和或触点间真实协同效应。

正式输出为 `amc_shapley_attribution_results.csv`，并与 Markov 结果一起进入模型比较。

## 参考资料

- [Shapley Value Methods for Attribution Modeling in Online Advertising（PDF）](/research/mta/Shapley%20Value%20Methods%20for%20Attribution%20Modeling%20in%20Online%20Advertising.pdf)
